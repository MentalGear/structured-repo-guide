#!/usr/bin/env python3
"""check-controls-table.py: prove that a security controls table is true of the tree.

What it is for: a security document that lists controls is only worth reading while it is
true. This check parses the document's controls table and fails when the table and the
repository disagree, so the document cannot lie. No network, Python 3 standard library only.

The table sits under a `## Controls` heading, one row per control, exactly these columns:

    | ID | Control | Threat it stops | Enforcing script | Config | Runs in | Status | Evidence |

It fails on:
  1. an `enforced` or `manual` row that names no path, or names a script or config path
     (a backticked token with a `/` or a file extension; `*` is a glob) that does not exist;
  2. a `planned` row whose script already exists (the control landed, flip the row);
  3. a script in the declared set (`--declared FILE`, `--declared-glob PATTERN`) that no row
     names, or that no longer exists: a new control script cannot land without a row;
  4. a row whose `Runs in` is `gates` (`--gate-runs-in`) but whose gate script is not named in
     the gate list file (`--gate-list`), or whose status is not `enforced`;
  5. a status other than enforced / manual / planned, a repeated or malformed id (C01..), a row
     with the wrong number of cells, an id used anywhere in the document without a row, and a
     `Counts ...: N enforced, N manual, N planned` line that disagrees with the table;
  6. a missing required heading (`--heading`, repeatable), or a security policy file
     (`--security`) that is missing, does not contain the playbook path (`--playbook-link`), or
     still holds an unreplaced `<...>` placeholder or the template's `<!-- TEMPLATE` comment
     (code spans, code fences, autolinks such as `<https://...>` and a few HTML tags are
     skipped): the template's own placeholder line contains the playbook path, so the path
     test alone passes on an unedited template.

`--self-test` copies the tree to a temporary directory, applies a list of mutations one at a
time, and requires every mutation to turn the check red for the intended reason and the
unmutated tree to stay green. A plain run also runs the self-test quietly, so the check
itself cannot rot.

Usage:
  check-controls-table.py --root DIR --doc docs/supply-chain.md [--security SECURITY.md]
      [--playbook-link PATH] [--gate-list FILE] [--declared FILE]... [--declared-glob PAT]...
      [--heading '## Threat model']... [--self-test]

Exit status: 0 when true, 1 on drift, 2 when an input is unreadable or usage is wrong.
"""

import argparse
import glob
import os
import re
import shutil
import sys
import tempfile

STATUSES = ("enforced", "manual", "planned")
COLUMNS = ["id", "control", "threat it stops", "enforcing script", "config", "runs in", "status", "evidence"]
ID_RE = re.compile(r"C\d\d")
PLACEHOLDER_RE = re.compile(r"<(?=[^\s<>!/])[^<>]{0,400}?(?<=\S)>")
OK_ANGLE_RE = re.compile(
    r"<(?:https?://|mailto:)[^\s<>]+>"                      # autolink
    r"|<[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}>"                 # e-mail autolink
    r"|<(?:br|hr|details|summary|kbd|sub|sup|img|strong|em)\b[^<>]*>")  # a few HTML tags


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as err:
        print(f"check-controls-table: cannot read {path}: {err}", file=sys.stderr)
        sys.exit(2)


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def path_tokens(cell):
    """Backticked repository paths in a table cell: a `/` or a file extension, no spaces."""
    out = []
    for tok in re.findall(r"`([^`]+)`", cell):
        if " " in tok:
            continue
        if "/" in tok or re.search(r"\.[A-Za-z0-9]+$", tok):
            out.append(tok)
    return out


def exists(root, path):
    full = os.path.join(root, path)
    return bool(glob.glob(full)) if "*" in path else os.path.exists(full)


def placeholder_problems(text):
    """Unreplaced template placeholders in a policy file, as problem strings."""
    text = re.sub(r"```.*?```|~~~.*?~~~", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    out = []
    if re.search(r"<!--\s*TEMPLATE", text):
        out.append("still holds the template's `<!-- TEMPLATE ... -->` comment; delete it")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    left = [m.group(0) for m in PLACEHOLDER_RE.finditer(text) if not OK_ANGLE_RE.fullmatch(m.group(0))]
    if left:
        shown = ", ".join(repr(t if len(t) <= 40 else t[:37] + "...") for t in left[:3])
        out.append(f"has {len(left)} unreplaced `<...>` placeholder(s), for example {shown}; replace each (an HTML tag goes in a code span)")
    return out


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def join_row(cells):
    return "| " + " | ".join(cells) + " |"


def parse_table(doc, problems):
    lines = doc.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == "## Controls"), None)
    if start is None:
        problems.append("no `## Controls` heading")
        return []
    rows, header = [], None
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        if not l.startswith("|"):
            continue
        cells = split_row(l)
        if header is None:
            header = [c.lower() for c in cells]
            if header != COLUMNS:
                problems.append(f"controls table header is {header}, want {COLUMNS}")
                return []
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) != len(COLUMNS):
            problems.append(f"table row has {len(cells)} cells, want {len(COLUMNS)} (a `|` inside a cell?): {l[:70]}")
            continue
        rows.append(dict(zip(COLUMNS, cells)))
    if header is None:
        problems.append("`## Controls` has no table")
    return rows


def declared_set(root, cfg, extra=()):
    out = []
    for f in cfg.declared:
        for line in read(os.path.join(root, f)).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    for pat in cfg.declared_glob:
        out.extend(sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, pat))))
    out.extend(extra)
    return sorted(set(out))


def check(root, cfg, extra_declared=()):
    problems = []
    doc = read(os.path.join(root, cfg.doc))
    doc_lines = [l.strip() for l in doc.splitlines()]
    for h in cfg.heading:
        if h not in doc_lines:
            problems.append(f"missing heading `{h}`")
    rows = parse_table(doc, problems)
    gates = ""
    if cfg.gate_list:
        gl = os.path.join(root, cfg.gate_list)
        if os.path.exists(gl):
            gates = read(gl)
        else:
            problems.append(f"gate list {cfg.gate_list} does not exist")
    ids, named_scripts, counts = set(), set(), {s: 0 for s in STATUSES}
    for r in rows:
        rid = r["id"]
        if not ID_RE.fullmatch(rid):
            problems.append(f"{rid!r}: id must look like C01")
        if rid in ids:
            problems.append(f"{rid}: id repeated")
        ids.add(rid)
        status = r["status"]
        if status not in STATUSES:
            problems.append(f"{rid}: status {status!r} is not one of {STATUSES}")
            continue
        counts[status] += 1
        scripts, configs = path_tokens(r["enforcing script"]), path_tokens(r["config"])
        named_scripts.update(scripts)
        if status == "planned":
            for s in scripts:
                if exists(root, s):
                    problems.append(f"{rid}: planned, but `{s}` exists now; flip the row to enforced or manual")
            continue
        if not scripts and not configs:
            problems.append(f"{rid}: {status} row names no script or config path")
        for p in scripts + configs:
            if not exists(root, p):
                problems.append(f"{rid}: {status} row names `{p}`, which does not exist")
        if r["runs in"] == cfg.gate_runs_in:
            if status != "enforced":
                problems.append(f"{rid}: runs in {cfg.gate_runs_in} but status is {status}")
            for s in scripts:
                if cfg.gate_list and re.fullmatch(cfg.gate_script_re, s):
                    if not re.search(r"(?<![\w/.-])" + re.escape(s) + r"(?![\w/.-])", gates):
                        problems.append(f"{rid}: `{s}` is not in the gate list {cfg.gate_list}")
    for s in declared_set(root, cfg, extra_declared):
        if not exists(root, s):
            problems.append(f"declared script `{s}` does not exist (remove it from the declared set and the table)")
        if s not in named_scripts:
            problems.append(f"declared script `{s}` is in no controls-table row")
    for u in sorted(set(re.findall(r"\bC\d\d\b", doc)) - ids):
        problems.append(f"{u} is used in the document but has no controls-table row")
    m = re.search(r"Counts[^:\n]*: (\d+) enforced, (\d+) manual, (\d+) planned", doc)
    if not m:
        problems.append("no `Counts ...: N enforced, N manual, N planned` line")
    elif tuple(int(x) for x in m.groups()) != tuple(counts[s] for s in STATUSES):
        problems.append(f"Counts line says {m.groups()} but the table has {tuple(counts[s] for s in STATUSES)}")
    if cfg.security:
        sec = os.path.join(root, cfg.security)
        if not os.path.exists(sec):
            problems.append(f"{cfg.security} does not exist")
        else:
            policy = read(sec)
            if cfg.playbook_link not in policy:
                problems.append(f"{cfg.security} does not link {cfg.playbook_link}")
            problems += [f"{cfg.security} {p}" for p in placeholder_problems(policy)]
    return problems, counts, rows


def rewrite_row(doc, row_id, fn):
    """Apply fn(cells) to the cells of the row whose id is row_id; return the new document."""
    out = []
    for l in doc.splitlines():
        if l.startswith("|") and split_row(l)[0] == row_id:
            cells = split_row(l)
            fn(cells)
            l = join_row(cells)
        out.append(l)
    return "\n".join(out) + "\n"


def self_test(root, cfg, quiet=False):
    problems, _, rows = check(root, cfg)
    if problems:
        print("check-controls-table: self-test needs a green tree first:", *problems, sep="\n  - ", file=sys.stderr)
        return 1
    ix = {c: i for i, c in enumerate(COLUMNS)}
    enforced_script = next(r for r in rows if r["status"] == "enforced" and path_tokens(r["enforcing script"]))
    script_path = path_tokens(enforced_script["enforcing script"])[0]
    cfg_row = next(r for r in rows if r["status"] == "enforced" and path_tokens(r["config"]))
    planned = next((r for r in rows if r["status"] == "planned" and path_tokens(r["enforcing script"])), None)
    gate_row = None
    if cfg.gate_list:
        gate_row = next((r for r in rows if r["runs in"] == cfg.gate_runs_in and
                         any(re.fullmatch(cfg.gate_script_re, s) for s in path_tokens(r["enforcing script"]))), None)
    first_heading = cfg.heading[0] if cfg.heading else "## Controls"

    def edit_doc(tmp, fn):
        p = os.path.join(tmp, cfg.doc)
        write(p, fn(read(p)))

    def delete_script(tmp):
        os.remove(os.path.join(tmp, script_path))

    def bad_config(tmp):
        edit_doc(tmp, lambda d: rewrite_row(d, cfg_row["id"], lambda c: c.__setitem__(ix["config"], "`no/such/config.toml`")))

    named = {s for r in rows for s in path_tokens(r["enforcing script"])}
    victim = next((s for s in declared_set(root, cfg) if s in named), None)

    def drop_declared_row(tmp):
        edit_doc(tmp, lambda d: "\n".join(l for l in d.splitlines() if f"`{victim}`" not in l) + "\n")

    def planned_lands(tmp):
        write(os.path.join(tmp, path_tokens(planned["enforcing script"])[0]), "#!/bin/sh\n")

    def unknown_status(tmp):
        edit_doc(tmp, lambda d: d.replace("| enforced |", "| done |", 1))

    def drop_heading(tmp):
        edit_doc(tmp, lambda d: d.replace(first_heading, first_heading + " renamed", 1))

    def dangling_id(tmp):
        edit_doc(tmp, lambda d: d + "\nSee C99.\n")

    def wrong_counts(tmp):
        edit_doc(tmp, lambda d: re.sub(r"(Counts[^:\n]*: )\d+", r"\g<1>99", d, count=1))

    def not_in_gates(tmp):
        s = next(s for s in path_tokens(gate_row["enforcing script"]) if re.fullmatch(cfg.gate_script_re, s))
        p = os.path.join(tmp, cfg.gate_list)
        write(p, read(p).replace(s, "scripts/other-script"))

    def security_unlinked(tmp):
        write(os.path.join(tmp, cfg.security), "# Security\n")

    def policy_placeholder(tmp):
        p = os.path.join(tmp, cfg.security)
        write(p, read(p) + "\nReport privately to <SECURITY CONTACT>.\n")

    def policy_template_comment(tmp):
        p = os.path.join(tmp, cfg.security)
        write(p, "<!-- TEMPLATE: delete this comment -->\n" + read(p))

    def duplicate_id(tmp):
        rid, other = rows[0]["id"], rows[1]["id"]
        edit_doc(tmp, lambda d: rewrite_row(d, other, lambda c: c.__setitem__(0, rid)))

    def no_paths(tmp):
        def blank(c):
            c[ix["enforcing script"]] = "none"
            c[ix["config"]] = "none"
        edit_doc(tmp, lambda d: rewrite_row(d, enforced_script["id"], blank))

    def extra_cell(tmp):
        edit_doc(tmp, lambda d: rewrite_row(d, enforced_script["id"], lambda c: c.__setitem__(ix["control"], c[ix["control"]] + " | extra")))

    cases = [
        ("an enforced row's script is deleted", "which does not exist", delete_script, ()),
        ("an enforced row names a config path that does not exist", "which does not exist", bad_config, ()),
        ("a declared script does not exist", "declared script `scripts/check-no-such-thing.sh` does not exist", lambda t: None,
         ("scripts/check-no-such-thing.sh",)),
        ("an unknown status", "is not one of", unknown_status, ()),
        ("a required heading is renamed", "heading", drop_heading, ()),
        ("a control id with no row is referenced", "has no controls-table row", dangling_id, ()),
        ("the Counts line is wrong", "Counts line says", wrong_counts, ()),
        ("a repeated id", "id repeated", duplicate_id, ()),
        ("an enforced row names no path", "names no script or config path", no_paths, ()),
        ("a row with an extra cell", "cells, want", extra_cell, ()),
    ]
    if victim:
        cases.append(("a declared script has no row", "is in no controls-table row", drop_declared_row, ()))
    if planned:
        cases.append(("a planned row's script now exists", "planned, but", planned_lands, ()))
    if gate_row:
        cases.append(("a gate row's script is not in the gate list", "is not in the gate list", not_in_gates, ()))
    if cfg.security:
        cases.append(("the security policy does not link the playbook", "does not link", security_unlinked, ()))
        cases.append(("the security policy keeps a `<...>` placeholder", "unreplaced", policy_placeholder, ()))
        cases.append(("the security policy keeps the template comment", "TEMPLATE", policy_template_comment, ()))

    bad = 0
    for name, want, mutate, extra in cases:
        tmp = tempfile.mkdtemp(prefix="controls-selftest-")
        try:
            shutil.copytree(root, tmp, dirs_exist_ok=True, symlinks=True)
            mutate(tmp)
            got, _, _ = check(tmp, cfg, extra)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = any(want in g for g in got)
        if not quiet or not ok:
            detail = "" if ok else f" -- wanted a problem containing {want!r}, got {got[:2]}"
            print(f"  self-test {'ok  ' if ok else 'FAIL'} {name}{detail}")
        bad += 0 if ok else 1
    if bad:
        print(f"check-controls-table: self-test FAIL ({bad} of {len(cases)} mutations were not caught)", file=sys.stderr)
        return 1
    if not quiet:
        print(f"check-controls-table: self-test OK ({len(cases)} mutations red, the unmutated tree green)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Check that a controls table is true of the tree.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--doc", required=True, help="the document holding the `## Controls` table, relative to --root")
    ap.add_argument("--security", default="", help="the security policy file, relative to --root")
    ap.add_argument("--playbook-link", default="", help="text the security policy must contain (default: --doc)")
    ap.add_argument("--gate-list", default="", help="file listing the gates, relative to --root")
    ap.add_argument("--gate-runs-in", default="gates", help="the `Runs in` value that means a gate")
    ap.add_argument("--gate-script-re", default=r"scripts/check-[a-z0-9-]+\.sh", help="which table scripts count as gates")
    ap.add_argument("--declared", action="append", default=[], help="file with one declared control script per line")
    ap.add_argument("--declared-glob", action="append", default=[], help="glob (relative to --root) of declared scripts")
    ap.add_argument("--heading", action="append", default=[], help="a heading the document must contain")
    ap.add_argument("--self-test", action="store_true")
    cfg = ap.parse_args()
    cfg.playbook_link = cfg.playbook_link or cfg.doc
    root = os.path.abspath(cfg.root)
    if cfg.self_test:
        return self_test(root, cfg)
    problems, counts, _ = check(root, cfg)
    if problems:
        print("check-controls-table: FAIL -- the document and the tree disagree:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    n_declared = len(declared_set(root, cfg))
    print(f"check-controls-table: OK -- {counts['enforced']} enforced, {counts['manual']} manual, "
          f"{counts['planned']} planned controls; {n_declared} declared scripts all documented")
    return self_test(root, cfg, quiet=True)


if __name__ == "__main__":
    sys.exit(main())
