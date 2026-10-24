#!/usr/bin/env python3
"""doc_hygiene.py -- three small checks over the Markdown docs of a tree.

    placeholders   a document copied from a template has no leftover `<placeholder>`, no `YYYY-MM-DD`, and no
                   template comment: the template's own instructions are deleted once it is filled in. The
                   placeholders are checked in the entry file, the status page and the decisions index; the
                   template comment (an HTML comment that opens with the word Template) in EVERY Markdown file of
                   the tree, so a guide or an item copied from a template cannot keep its instructions unseen
    map            every Markdown file under docs/ is reachable from the docs map (docs/README.md) by following
                   relative links, so a doc that is not in the map does not exist for a new reader
    dated          a ratchet on dated headings and dated lead-ins ("## Status (<a month and year>)")
                   in living docs: such a paragraph is a diary entry, and history belongs in the archive

Usage (run from the repository root; Python 3 standard library only):

    doc_hygiene.py placeholders [--root DIR] [FILE...]
    doc_hygiene.py map          [--root DIR] [--map FILE] [--docs DIR] [--skip PREFIX]...
    doc_hygiene.py dated        [--root DIR] [--baseline FILE] [--skip PREFIX]... [--inventory |
                                --update-baseline [--allow-grow]] [FILE...]
    doc_hygiene.py --self-test [placeholders | map | dated]

    --root DIR          the tree to check (default: the current directory)
    FILE...             placeholders: the documents to check fully; dated: scan only these. With none, placeholders
                        checks AGENTS.md, CLAUDE.md, docs/STATUS.md and docs/decisions.md ref-ok: names the tool looks for
                        (those that exist) fully, and every other Markdown file for the template comment only
    --map FILE          the map (default docs/README.md); --docs DIR the tree it must cover (default docs)
    --skip PREFIX       map: root-relative paths that need no link (repeatable); dated: living docs are everything
                        under docs/ and the root-level *.md except the history homes (archive/, backlog/, research/,
                        issues/ and drafts/ under docs/; --skip adds to them)
    --baseline FILE     dated: the ratchet file (default: dated-headings.tsv in the baselines directory under scripts/)
    --inventory         dated: list every dated heading or lead-in; exit 0
    --update-baseline   dated: rewrite the baseline; refuses to let a count grow unless --allow-grow is given

Markers, each with a reason on the line itself (a marker without one exempts nothing):
    placeholder-ok: <reason>   the angle brackets are the document's own text (a command's syntax)
    dated-ok: <reason>         the date is data the page needs, not a diary entry

Exit status: 0 clean, 1 a violation, 2 bad usage.
"""
import os
import re
import subprocess
import sys
import tempfile

SKIP_DIRNAMES = {".git", "node_modules", "target", "dist", "build", "__pycache__", ".venv", "venv", ".tox"}
DEFAULT_PLACEHOLDER_FILES = ("AGENTS.md", "CLAUDE.md", "docs/STATUS.md", "docs/decisions.md")
HISTORY_HOMES = ("docs/archive/", "docs/backlog/", "docs/research/", "docs/issues/", "docs/drafts/")
DATED_BASELINE = "scripts/baselines/dated-headings.tsv"

HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
TEMPLATE_COMMENT = re.compile(r"\s*(?:Template|TEMPLATE)\b")
ANGLE = re.compile(r"<([^<>\n]+)>")
HTML_TAG = re.compile(r"^/?(?:a|b|br|code|details|div|em|h[1-6]|hr|i|img|kbd|li|ol|p|pre|span|strong|sub|summary|sup|"
                      r"table|tbody|td|th|thead|tr|ul)(?:\s[^<>]*)?/?$", re.I)
AUTOLINK = re.compile(r"^(?:https?://|mailto:)\S+$", re.I)
DATE_WORD = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
HEADING_DATE = re.compile(r"^#{1,6}\s.*(?:\d{4}-\d{2}-\d{2}|\b%s\s+\d{1,2}\b|\b%s,?\s+\d{4}\b|\b20\d\d-Q[1-4]\b|\bQ[1-4]\s+20\d\d\b)"
                          % (DATE_WORD, DATE_WORD))
LEAD_DATE = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*|__)?(?:[A-Za-z]+(?: [A-Za-z]+){0,2} \()?\d{4}-\d{2}-\d{2}")
MARK_PLACEHOLDER = re.compile(r"placeholder-ok:\s*\S")
MARK_DATED = re.compile(r"dated-ok:\s*\S")
FENCE = re.compile(r"(?ms)^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$")
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFDEF = re.compile(r"(?m)^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?\s*$")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def listed_markdown(root):
    """Root-relative Markdown files: git's view (tracked and untracked, minus ignored) inside a work tree, a walk
    elsewhere; never the history homes' archive, where a template may be quoted."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "*.md"],
                           capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        r = None
    if r is not None and r.returncode == 0:
        paths = [p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0")
                 if p and os.path.isfile(os.path.join(root, p))]
    else:
        paths = markdown_files(root)
    return sorted(p for p in paths if not p.startswith("docs/archive/")
                  and not any(part in SKIP_DIRNAMES for part in p.split("/")[:-1]))


def markdown_files(root, under=""):
    out = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, under)):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRNAMES)
        for f in filenames:
            if f.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return sorted(out)


def blank_keep_lines(rx, text):
    """Replace every match of rx with spaces, keeping the newlines, so line numbers stay true."""
    return rx.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


# --------------------------------------------------------------------------- placeholders
def check_placeholders(root, files, comment_only=()):
    """Problems in `files` (placeholders and the template comment) and in `comment_only` (the template comment)."""
    probs = []
    for rel in comment_only:
        text = read(os.path.join(root, rel))
        for m in HTML_COMMENT.finditer(text):
            if TEMPLATE_COMMENT.match(m.group(1)):
                probs.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: the template's instruction comment is still "
                             "here; delete it")
    for rel in files:
        text = read(os.path.join(root, rel))
        for m in HTML_COMMENT.finditer(text):
            if TEMPLATE_COMMENT.match(m.group(1)):
                probs.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: the template's instruction comment is still "
                             "here; delete it")
        body = blank_keep_lines(HTML_COMMENT, text)
        for ln, line in enumerate(body.split("\n"), 1):
            if MARK_PLACEHOLDER.search(line):
                continue
            found = [m.group(0) for m in ANGLE.finditer(line)
                     if not (HTML_TAG.match(m.group(1)) or AUTOLINK.match(m.group(1)))]
            if "YYYY-MM-DD" in line.replace("<YYYY-MM-DD>", ""):
                found.append("YYYY-MM-DD")
            if found:
                shown = ", ".join(dict.fromkeys(found))
                probs.append(f"{rel}:{ln}: leftover placeholder {shown}")
    return probs


def cmd_placeholders(root, opts):
    files = opts["files"] or [f for f in DEFAULT_PLACEHOLDER_FILES if os.path.exists(os.path.join(root, f))]
    missing = [f for f in files if not os.path.exists(os.path.join(root, f))]
    if missing or not files:
        print("placeholders: no such file: " + ", ".join(missing or DEFAULT_PLACEHOLDER_FILES) +
              " (name the copied documents: doc_hygiene.py placeholders FILE...)", file=sys.stderr)
        return 2
    extra = [] if opts["files"] else [f for f in listed_markdown(root) if f not in files]
    probs = check_placeholders(root, files, extra)
    for p in probs:
        print("placeholders: " + p, file=sys.stderr)
    if probs:
        print("Fill in or delete every placeholder, and delete the template's own comment. Text that really is angle "
              "brackets takes `placeholder-ok: <reason>` on its line.", file=sys.stderr)
        return 1
    print(f"placeholders: OK ({len(files)} files: {', '.join(files)}; template comment also checked in "
          f"{len(extra)} other Markdown files)")
    return 0


# --------------------------------------------------------------------------- map
def links_of(root, rel):
    """Root-relative Markdown files that rel links to (code spans and fences ignored, anchors dropped)."""
    text = blank_keep_lines(FENCE, read(os.path.join(root, rel)))
    text = re.sub(r"`[^`\n]*`", "", text)
    out = set()
    for tgt in LINK.findall(text) + REFDEF.findall(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", tgt, re.I) or tgt.startswith("#"):
            continue
        path = tgt.split("#", 1)[0].split("?", 1)[0]
        if not path:
            continue
        full = os.path.normpath(os.path.join(os.path.dirname(os.path.join(root, rel)), path))
        if os.path.isdir(full):
            full = os.path.join(full, "README.md")
        if full.endswith(".md") and os.path.isfile(full):
            out.add(os.path.relpath(full, root).replace(os.sep, "/"))
    return out


def cmd_map(root, opts):
    map_rel, docs = opts["map"], opts["docs"].rstrip("/")
    if not os.path.exists(os.path.join(root, map_rel)):
        print(f"map: the docs map {map_rel} does not exist (--map FILE)", file=sys.stderr)
        return 1
    seen, todo = {map_rel}, [map_rel]
    while todo:
        for nxt in links_of(root, todo.pop()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    skip = tuple(opts["skip"])
    orphans = [f for f in markdown_files(root, docs) if f not in seen and not f.startswith(skip)]
    for f in orphans:
        print(f"map: {f} is not reachable from {map_rel}", file=sys.stderr)
    if orphans:
        print(f"Add a row for it to {map_rel} (or to the index it belongs to, which the map links), or delete it.",
              file=sys.stderr)
        return 1
    print(f"map: OK (every Markdown file under {docs}/ is reachable from {map_rel}; {len(seen)} files linked)")
    return 0


# --------------------------------------------------------------------------- dated headings
def dated_hits(root, rel):
    """[(line, text)] of dated headings and dated lead-ins in a living doc."""
    text = blank_keep_lines(HTML_COMMENT, blank_keep_lines(FENCE, read(os.path.join(root, rel))))
    out = []
    for ln, line in enumerate(text.split("\n"), 1):
        if MARK_DATED.search(line):
            continue
        if HEADING_DATE.match(line) or LEAD_DATE.match(line):
            out.append((ln, line.strip()))
    return out


def living_docs(root, skip):
    docs = [f for f in markdown_files(root) if f.startswith("docs/") or "/" not in f]
    return [f for f in docs if not f.startswith(tuple(HISTORY_HOMES) + tuple(skip))]


def read_baseline(path):
    if not os.path.exists(path):
        return {}
    out = {}
    for ln in read(path).splitlines():
        if ln and not ln.startswith("#"):
            k, _, v = ln.partition("\t")
            out[k] = int(v)
    return out


def cmd_dated(root, opts):
    base_path = opts["baseline"] or os.path.join(root, DATED_BASELINE)
    files = opts["files"] or living_docs(root, opts["skip"])
    hits = {f: h for f in files if (h := dated_hits(root, f))}
    counts = {f: len(h) for f, h in hits.items()}
    if opts["inventory"]:
        for f in sorted(hits):
            for ln, text in hits[f]:
                print(f"{f}:{ln}\t{text[:120]}")
        print(f"dated: {sum(counts.values())} dated headings or lead-ins in {len(counts)} files", file=sys.stderr)
        return 0
    base = read_baseline(base_path)
    if opts["update"]:
        grow = {f: (base.get(f, 0), c) for f, c in counts.items() if c > base.get(f, 0)}
        if grow and os.path.exists(base_path) and not opts["allow_grow"]:
            print("dated: refusing to GROW the baseline (shrink-only; move the paragraph to the archive or add "
                  "`dated-ok: <reason>`; --allow-grow overrides, say why in the commit):", file=sys.stderr)
            for f, (a, b) in sorted(grow.items()):
                print(f"  {f}: {a} -> {b}", file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(base_path)), exist_ok=True)
        with open(base_path, "w", encoding="utf-8") as fh:
            fh.write("# dated-headings baseline: dated headings and lead-ins in living docs, per file (shrink-only).\n"
                     "# path<TAB>count. Regenerate with: sh scripts/check-dated-headings.sh --update-baseline\n")
            for f in sorted(counts):
                fh.write(f"{f}\t{counts[f]}\n")
        print(f"dated: baseline written ({len(counts)} files, {sum(counts.values())} lines)")
        return 0
    rc = 0
    rose = [(f, base.get(f, 0), c) for f, c in sorted(counts.items()) if c > base.get(f, 0)]
    if rose:
        rc = 1
        print("dated: a living doc gained a dated heading or lead-in (\"Status (2025-03-02)\"). A living doc states the\n"
              "current state; the dated story goes to the archive or the tracker item and is linked.", file=sys.stderr)
        for f, was, now in rose:
            print(f"  {f}: {was} -> {now}" + ("  (not in the baseline)" if f not in base else ""), file=sys.stderr)
            for ln, text in hits[f][:8]:
                print(f"      {f}:{ln} {text[:100]}", file=sys.stderr)
    stale = [(f, v, counts.get(f, 0)) for f, v in sorted(base.items()) if counts.get(f, 0) < v]
    if stale:
        rc = 1
        print("dated: the count FELL (good) but the baseline still allows the old number. Lock the drop in:\n"
              "sh scripts/check-dated-headings.sh --update-baseline", file=sys.stderr)
        for f, was, now in stale:
            print(f"  {f}: baseline {was}, now {now}", file=sys.stderr)
    if rc == 0:
        print(f"dated: OK ({sum(counts.values())} baselined dated headings in {len(counts)} files, none new)")
    return rc


# --------------------------------------------------------------------------- self-test
def _tree(d, files):
    for p, text in files.items():
        full = os.path.join(d, p)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)


def _run(kind, files, extra=(), baseline=None):
    with tempfile.TemporaryDirectory(prefix="doc-hygiene-") as d:
        _tree(d, files)
        if baseline is not None:
            _tree(d, {DATED_BASELINE: baseline})
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), kind, "--root", d, *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


def _cases(label, kind, cases):
    fails = 0
    for name, files, want, *rest in cases:
        extra = rest[0] if rest else ()
        baseline = rest[1] if len(rest) > 1 else None
        rc, out = _run(kind, files, extra, baseline)
        ok = rc == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: {name} (rc {rc}, want {want})")
        if not ok:
            print("    " + out.replace("\n", "\n    "))
    return fails


def self_test(kind=None):
    fails = 0
    if kind in (None, "placeholders"):
        filled = "# Agent notes\n\nRun `sh scripts/run-gates.sh` before every commit. Read [status](docs/STATUS.md).\n"
        fails += _cases("placeholders", "placeholders", [
            ("a filled document passes", {"AGENTS.md": filled}, 0),
            ("a leftover <placeholder> in a code span fails", {"AGENTS.md": "Run `<the runner>`.\n"}, 1),
            ("a leftover <placeholder> in prose fails", {"AGENTS.md": "Commits: <your convention>.\n"}, 1),
            ("a leftover <id> in a link fails", {"AGENTS.md": filled, "docs/STATUS.md": "[x](./backlog/<NNN>-<slug>.md)\n"}, 1),
            ("YYYY-MM-DD fails", {"AGENTS.md": filled, "docs/STATUS.md": "Last updated: YYYY-MM-DD.\n"}, 1),
            ("a real date passes", {"AGENTS.md": filled, "docs/STATUS.md": "Last updated: 2025-03-02.\n"}, 0),
            ("the template's own comment fails", {"AGENTS.md": "<!--\nTemplate. Keep it to one screen. Delete this comment.\n-->\n" + filled}, 1),
            ("another HTML comment passes", {"AGENTS.md": "<!-- a note for editors <not a placeholder> -->\n" + filled}, 0),
            ("html tags and autolinks pass", {"AGENTS.md": "<kbd>Ctrl</kbd> <br> <https://example.com/x> <details><summary>s</summary></details>\n"}, 0),
            ("placeholder-ok with a reason exempts", {"AGENTS.md": "Run `tool <file>` placeholder-ok: the command's own syntax\n"}, 0),
            ("placeholder-ok without a reason does not", {"AGENTS.md": "Run `tool <file>` placeholder-ok:\n"}, 1),
            ("a code fence is scanned too", {"AGENTS.md": "```sh\nrun <entry point>\n```\n"}, 1),
            ("a copied guide that keeps the template comment fails (any Markdown file)",
             {"AGENTS.md": filled, "docs/guides/history-in-comments.md": "# Rule\n\n<!--\nTemplate. Copy to docs/guides/. Delete this comment.\n-->\n"}, 1),
            ("an upper-case TEMPLATE comment fails too", {"AGENTS.md": filled, "SECURITY.md": "<!-- TEMPLATE: copy this file. -->\n"}, 1),
            ("an item copied from a template keeps its comment: fails", {"AGENTS.md": filled, "docs/backlog/001-x.md": "---\nid: 1\n---\n\n<!--\nTemplate, ready to run as the FIRST item.\n-->\n"}, 1),
            ("a quoted template in the archive is history, not a leftover", {"AGENTS.md": filled, "docs/archive/old.md": "<!-- Template. x -->\n"}, 0),
            ("another comment, and a <placeholder>, in an other Markdown file pass", {"AGENTS.md": filled, "docs/guides/g.md": "<!-- a note -->\nRun `tool <file>`.\n"}, 0),
            ("a named file limits the check to it", {"AGENTS.md": filled, "docs/guides/g.md": "<!-- Template. x -->\n"}, 0, ["AGENTS.md"]),
            ("an unnamed run with no default file is bad usage", {"README.md": "x\n"}, 2),
            ("a named file that is missing is bad usage", {"AGENTS.md": filled}, 2, ["nope.md"]),
        ])
    if kind in (None, "map"):
        mp = "# Docs map\n\n[status](STATUS.md) [guides](guides/README.md) [backlog](backlog.md)\n"
        base = {"docs/README.md": mp, "docs/STATUS.md": "# s\n", "docs/guides/README.md": "# g\n\n[a](a.md)\n",
                "docs/guides/a.md": "# a\n", "docs/backlog.md": "# b\n\n[1](backlog/001-x.md)\n", "docs/backlog/001-x.md": "# x\n"}
        fails += _cases("map", "map", [
            ("every doc reachable passes (transitively, through an index)", base, 0),
            ("a doc nobody links fails", {**base, "docs/orphan.md": "# o\n"}, 1),
            ("a doc only an orphan links fails", {**base, "docs/orphan.md": "[b](b2.md)\n", "docs/b2.md": "# b\n"}, 1),
            ("a link inside a code span does not count", {**base, "docs/orphan.md": "# o\n", "docs/STATUS.md": "see `[o](orphan.md)`\n"}, 1),
            ("a link inside a fence does not count", {**base, "docs/orphan.md": "# o\n", "docs/STATUS.md": "```\n[o](orphan.md)\n```\n"}, 1),
            ("a directory link reaches its README.md", {**base, "docs/README.md": mp + "[more](more/)\n", "docs/more/README.md": "# m\n"}, 0),
            ("an anchor link reaches the file", {**base, "docs/README.md": mp + "[o](orphan.md#top)\n", "docs/orphan.md": "# o\n"}, 0),
            ("--skip exempts a prefix", {**base, "docs/gen/x.md": "# x\n"}, 0, ["--skip", "docs/gen/"]),
            ("a missing map fails", {"docs/a.md": "# a\n"}, 1),
        ])
    if kind in (None, "dated"):
        fails += _cases("dated", "dated", [
            ("a clean living doc passes", {"docs/guide.md": "# Guide\n\nSteps.\n"}, 0, (), ""),
            ("a dated heading fails", {"docs/guide.md": "# Guide\n\n## Status (2025-03-02)\n\ntext\n"}, 1, (), ""),
            ("a month-year heading fails", {"docs/guide.md": "## Update, March 2025\n"}, 1, (), ""),
            ("a quarter heading fails", {"docs/guide.md": "## 2025-Q1 plan\n"}, 1, (), ""),
            ("a dated lead-in fails", {"docs/guide.md": "Update (2025-03-02): we moved it.\n"}, 1, (), ""),
            ("a diary bullet fails", {"docs/guide.md": "- **2025-03-02**: landed the cache\n"}, 1, (), ""),
            ("`Last updated: <date>` is not a diary entry", {"docs/STATUS.md": "Last updated: 2025-03-02.\n"}, 0, (), ""),
            ("a date mid-sentence is data", {"docs/decisions.md": "- Build output is never committed. 2025-01-10 (item 1).\n"}, 0, (), ""),
            ("a dated heading in a fence is an example", {"docs/guide.md": "```\n## Status (2025-03-02)\n```\n"}, 0, (), ""),
            ("the archive may be dated", {"docs/archive/old.md": "## Status (2025-03-02)\n"}, 0, (), ""),
            ("an item may be dated", {"docs/backlog/001-x.md": "## Status (2025-03-02)\n"}, 0, (), ""),
            ("dated-ok with a reason exempts", {"docs/guide.md": "## Release 2025-03-02 dated-ok: the release's own name\n"}, 0, (), ""),
            ("dated-ok without a reason does not", {"docs/guide.md": "## Release 2025-03-02 dated-ok:\n"}, 1, (), ""),
            ("a baselined hit passes", {"docs/guide.md": "## Status (2025-03-02)\n"}, 0, (), "docs/guide.md\t1\n"),
            ("a rise above the baseline fails", {"docs/guide.md": "## A (2025-03-02)\n## B (2025-03-03)\n"}, 1, (), "docs/guide.md\t1\n"),
            ("a stale baseline (count fell) fails", {"docs/guide.md": "# Guide\n"}, 1, (), "docs/guide.md\t1\n"),
            ("--update-baseline refuses to grow", {"docs/guide.md": "## A (2025-03-02)\n## B (2025-03-03)\n"}, 1, ["--update-baseline"], "docs/guide.md\t1\n"),
            ("--update-baseline --allow-grow grows", {"docs/guide.md": "## A (2025-03-02)\n## B (2025-03-03)\n"}, 0, ["--update-baseline", "--allow-grow"], "docs/guide.md\t1\n"),
            ("--update-baseline locks a drop in", {"docs/guide.md": "# Guide\n"}, 0, ["--update-baseline"], "docs/guide.md\t1\n"),
        ])
    print(f"doc_hygiene --self-test{' ' + kind if kind else ''}: {'OK' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


# --------------------------------------------------------------------------- main
def usage(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def main(argv):
    if "--self-test" in argv[1:]:
        rest = [a for a in argv[1:] if a != "--self-test"]
        if rest not in ([], ["placeholders"], ["map"], ["dated"]):
            usage("usage: doc_hygiene.py --self-test [placeholders | map | dated]")
        return self_test(rest[0] if rest else None)
    if len(argv) < 2 or argv[1] not in ("placeholders", "map", "dated"):
        usage("usage: doc_hygiene.py <placeholders|map|dated> [--root DIR] ...   |   doc_hygiene.py --self-test")
    kind = argv[1]
    opts = {"files": [], "map": "docs/README.md", "docs": "docs", "skip": [], "baseline": None,
            "inventory": False, "update": False, "allow_grow": False}
    root = os.getcwd()
    it = iter(argv[2:])
    try:
        for a in it:
            if a == "--root":
                root = next(it)
            elif a == "--map":
                opts["map"] = next(it)
            elif a == "--docs":
                opts["docs"] = next(it)
            elif a == "--skip":
                opts["skip"].append(next(it))
            elif a == "--baseline":
                opts["baseline"] = next(it)
            elif a == "--inventory":
                opts["inventory"] = True
            elif a == "--update-baseline":
                opts["update"] = True
            elif a == "--allow-grow":
                opts["allow_grow"] = True
            elif a.startswith("-"):
                usage(f"doc_hygiene: unknown option {a}")
            else:
                opts["files"].append(a)
    except StopIteration:
        usage("doc_hygiene: an option is missing its value")
    cmd = {"placeholders": cmd_placeholders, "map": cmd_map, "dated": cmd_dated}[kind]
    return cmd(os.path.abspath(root), opts)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
