#!/usr/bin/env python3
"""backlog_index.py -- a tracker kept as one file per item, with generated open and done indexes.

Usage (Python 3 standard library only):

    backlog_index.py [--root DIR] [--dir TRACKER_DIR] (--write | --check)
    backlog_index.py --self-test

    --root DIR   the repository root (default: the current directory)
    --dir DIR    the tracker directory, relative to --root (default docs/backlog)
    --write      rebuild the two index files from the item files
    --check      write nothing; exit 1 listing every problem

Layout:
    docs/backlog/NNN-slug.md        an open item   -> listed in docs/backlog.md
    docs/backlog/done/NNN-slug.md   a closed item  -> listed in docs/backlog-done.md
An item's id is its number, never renumbered and never reused; code and docs cite it ("backlog N").

An item file starts with front matter and has three sections, in this order:

    ---
    id: 12
    title: "Cache the render key"
    status: open            # open | active | blocked | done | dropped
    area: render
    updated: YYYY-MM-DD
    ---
    ## Item        what is wanted, in a few sentences
    ## Status      where it stands; the landing commit or pull request once done
    ## Detail      everything else: evidence, options, links

--check fails on: a missing front matter field or section, a section out of order, an unknown status, an id that
differs from the file name's number, a duplicate id, a status that disagrees with the folder (done and dropped live
in done/, the rest do not), a file name that is not NNN-slug.md, and an index that differs from the generated one.
The text above the BEGIN marker of an index file is yours; the generated table sits between BEGIN and END.
Exit status: 0 clean, 1 a problem, 2 bad usage.
"""
import os
import re
import subprocess
import sys
import tempfile

REQUIRED = ["id", "title", "status", "area", "updated"]
SECTIONS = ["Item", "Status", "Detail"]
OPEN_STATUSES = ("open", "active", "blocked")
CLOSED_STATUSES = ("done", "dropped")
BEGIN = "<!-- BEGIN GENERATED: rebuilt by the index generator; edit the item files, not this block -->"
END = "<!-- END GENERATED -->"
NAME = re.compile(r"^(\d{3,})-[a-z0-9][a-z0-9-]*\.md$")


def parse(path):
    """(front matter dict, [section titles], error or None)."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if not m:
        return {}, [], "no front matter (a block between two --- lines at the top)"
    fm = {}
    for ln in m.group(1).split("\n"):
        k, sep, v = ln.partition(":")
        if sep and k.strip():
            v = re.sub(r"\s+#\s.*$", "", v.strip())  # a trailing `# note`
            fm[k.strip()] = v.strip().strip("\"'")
    body = re.sub(r"(?ms)^```.*?^```", "", m.group(2))
    return fm, re.findall(r"(?m)^## (.+?)\s*$", body), None


def load(root, tracker):
    """([item dicts], [problems])."""
    items, probs = [], []
    base = os.path.join(root, tracker)
    for sub, closed_dir in (("", False), ("done", True)):
        d = os.path.join(base, sub) if sub else base
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            full = os.path.join(d, f)
            if not f.endswith(".md") or not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            nm = NAME.match(f)
            if not nm:
                probs.append(f"{rel}: the file name must be NNN-slug.md (digits, a hyphen, lower-case words)")
                continue
            fm, sections, err = parse(full)
            if err:
                probs.append(f"{rel}: {err}")
                continue
            for k in REQUIRED:
                if not fm.get(k):
                    probs.append(f"{rel}: front matter field `{k}` is missing or empty")
            if fm.get("id", "").isdigit() and int(fm["id"]) != int(nm.group(1)):
                probs.append(f"{rel}: id {fm['id']} differs from the file name's number {int(nm.group(1))}")
            st = fm.get("status", "")
            if st and st not in OPEN_STATUSES + CLOSED_STATUSES:
                probs.append(f"{rel}: unknown status `{st}` (one of {', '.join(OPEN_STATUSES + CLOSED_STATUSES)})")
            elif st and (st in CLOSED_STATUSES) != closed_dir:
                probs.append(f"{rel}: status `{st}` disagrees with the folder "
                             f"({'done/ holds only done and dropped items' if closed_dir else 'done and dropped items move to done/'})")
            if [s for s in sections if s in SECTIONS] != SECTIONS:
                probs.append(f"{rel}: needs the sections {' / '.join('## ' + s for s in SECTIONS)}, in that order")
            items.append({**fm, "n": int(nm.group(1)), "rel": rel, "closed": closed_dir})
    seen = {}
    for it in items:
        if it["n"] in seen:
            probs.append(f"{it['rel']}: id {it['n']} is also used by {seen[it['n']]}")
        seen[it["n"]] = it["rel"]
    return items, probs


def table(items, index_rel):
    cell = lambda s: s.replace("|", "\\|")
    rows = ["| id | title | status | area | updated |", "|---|---|---|---|---|"]
    for it in sorted(items, key=lambda i: i["n"]):
        link = os.path.relpath(it["rel"], os.path.dirname(index_rel)).replace(os.sep, "/")
        rows.append(f"| [{it['n']}]({link}) | {cell(it.get('title', ''))} | {it.get('status', '')} | "
                    f"{cell(it.get('area', ''))} | {it.get('updated', '')} |")
    return "\n".join(rows)


def index_files(tracker):
    return (tracker + ".md", tracker + "-done.md")


HEADERS = {
    0: "# Backlog: open items\n\nOne file per item in [`{dir}/`](./{dir}/). This page is generated; edit an item file, "
       "run the index generator, commit both. Cite an item by id, as in \"backlog 12\".\n",
    1: "# Backlog: done items\n\nFinished items (done or dropped), one file each in [`{dir}/done/`](./{dir}/done/). "
       "This page is generated.\n",
}


def build_index(existing, header, tbl):
    core = f"{BEGIN}\n\n{tbl}\n\n{END}"
    if BEGIN in existing and END in existing:
        return existing.split(BEGIN)[0] + core + existing.split(END, 1)[1]
    return header + "\n" + core + "\n"


def run(root, tracker, mode):
    items, probs = load(root, tracker)
    wrote = []
    for k, rel in enumerate(index_files(tracker)):
        path = os.path.join(root, rel)
        sel = [i for i in items if i["closed"] == bool(k)]
        existing = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        header = HEADERS[k].format(dir=os.path.basename(tracker))
        want = build_index(existing, header, table(sel, rel))
        if mode == "write":
            if want != existing:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(want)
                wrote.append(rel)
        elif want != existing:
            probs.append(f"{rel}: stale or missing; run the generator with --write and commit it")
    for p in probs:
        print("backlog_index: " + p, file=sys.stderr)
    if mode == "write":
        print(f"backlog_index: {len(items)} items; wrote {', '.join(wrote) if wrote else 'nothing (already current)'}")
        return 1 if probs else 0
    if not probs:
        print(f"backlog_index: OK -- {len(items)} items, both indexes current")
    return 1 if probs else 0


def item(i, status="open", title="A thing", extra=""):
    return (f"---\nid: {i}\ntitle: \"{title}\"\nstatus: {status}  # note\narea: core\nupdated: 2025-03-02\n{extra}---\n"
            "## Item\n\nx\n\n## Status\n\ny\n\n## Detail\n\nz\n")


def self_test():
    d1 = "docs/backlog/001-first.md"
    d2 = "docs/backlog/done/002-second.md"
    base = {d1: item(1), d2: item(2, "done")}

    def regen(d):
        subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--root", d, "--write"], capture_output=True)

    def edit(rel, fn):
        def go(d):
            p = os.path.join(d, rel)
            with open(p, encoding="utf-8") as fh:
                t = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(fn(t))
        return go

    def add(rel, text):
        def go(d):
            os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
            with open(os.path.join(d, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
        return go

    cases = [
        # (name, files, mutation applied after the first --write, expected rc of --check)
        ("fresh indexes pass", base, None, 0),
        ("hand edit of an index fails", base, edit("docs/backlog.md", lambda t: t.replace("A thing", "Edited by hand")), 1),
        ("a new item without regenerating fails", base, add("docs/backlog/003-third.md", item(3)), 1),
        ("missing front matter field fails", base, edit(d1, lambda t: t.replace("area: core\n", "")), 1),
        ("id differs from the file name fails", base, edit(d1, lambda t: t.replace("id: 1\n", "id: 9\n")), 1),
        ("duplicate id fails", base, add("docs/backlog/done/001-other.md", item(1, "done")), 1),
        ("done item in the open folder fails", base, edit(d1, lambda t: t.replace("status: open", "status: done")), 1),
        ("open item in done/ fails", base, edit(d2, lambda t: t.replace("status: done", "status: active")), 1),
        ("unknown status fails", base, edit(d1, lambda t: t.replace("status: open", "status: wip")), 1),
        ("bad file name fails", base, add("docs/backlog/Third Item.md", item(3)), 1),
        ("sections out of order fail", base, edit(d1, lambda t: t.replace("## Item", "## Detail2").replace("## Detail\n", "## Item\n")), 1),
        ("no front matter fails", base, add("docs/backlog/004-bare.md", "# just text\n"), 1),
        ("regenerated after an edit passes", base, lambda d: (edit(d1, lambda t: t.replace("A thing", "Renamed"))(d), regen(d)), 0),
        ("text above the BEGIN marker is kept", base,
         lambda d: (edit("docs/backlog.md", lambda t: "# My own heading\n\n" + t.split("\n", 1)[1])(d), regen(d)), 0),
    ]
    fails = 0
    for name, files, mutate, want in cases:
        with tempfile.TemporaryDirectory(prefix="backlog-") as d:
            for p, t in files.items():
                add(p, t)(d)
            regen(d)
            if mutate:
                mutate(d)
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--root", d, "--check"],
                               capture_output=True, text=True)
            kept = "My own heading" in open(os.path.join(d, "docs/backlog.md"), encoding="utf-8").read() \
                if name.startswith("text above") else True
        ok = r.returncode == want and kept
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (rc {r.returncode}, want {want})")
        if not ok:
            print("    " + (r.stdout + r.stderr).replace("\n", "\n    "))
    print(f"backlog_index --self-test: {'OK' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def main(argv):
    if "--self-test" in argv[1:]:
        return self_test()
    root, tracker, mode = os.getcwd(), "docs/backlog", None
    it = iter(argv[1:])
    try:
        for a in it:
            if a in ("--write", "--check"):
                mode = a[2:]
            elif a == "--root":
                root = next(it)
            elif a == "--dir":
                tracker = next(it).rstrip("/")
            else:
                print(f"backlog_index: unknown argument {a}", file=sys.stderr)
                return 2
    except StopIteration:
        print("backlog_index: an option is missing its value", file=sys.stderr)
        return 2
    if mode is None:
        print("usage: backlog_index.py [--root DIR] [--dir TRACKER_DIR] (--write | --check) | --self-test", file=sys.stderr)
        return 2
    return run(os.path.abspath(root), tracker, mode)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
