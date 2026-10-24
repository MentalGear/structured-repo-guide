#!/usr/bin/env python3
"""docs_catalogue.py -- generate a catalogue page of checks from the header of each check script.

Usage (Python 3 standard library only):

    docs_catalogue.py [--root DIR] [--scripts GLOB] [--out FILE] [--title TITLE]
                      [--min-chars N] [--max-chars N] (--write | --check)
    docs_catalogue.py --self-test

    --root DIR       the repository root (default: the current directory)
    --scripts GLOB   the check scripts, relative to --root (default scripts/check-*)
    --out FILE       the generated page, relative to --root (default: checks.md in the docs directory)
    --title TITLE    the page's h1 (default Checks)
    --min-chars N    a description shorter than N is too thin (default 60)
    --max-chars N    a description longer than N is too long (default 700)
    --write          regenerate the page
    --check          write nothing; exit 1 when the committed page differs from the generated text, or when a
                     script has no usable description

The page is a pure function of the script headers: no dates, no counts that are not derived, a stable order.
So it cannot drift, and a new check needs one thing only, its own header. No prose is edited anywhere else.

What a header looks like (the comment block at the top of the file, after the shebang):

    # check-no-todo.sh -- optional title line, naming the script
    #
    # group: Source hygiene                      <- optional; the heading it is listed under (default: Other)
    #
    # The first paragraph is the catalogue entry: one or two sentences saying what the check forbids and
    # why. Blank comment line ends it. Everything after is detail for the script's own readers.

Header styles by extension (HEADER_STYLES): `#` comment lines (sh, py, rb, pl), `//` comment lines (js, ts), and
the module docstring (py, tried first). Add a row to support another language.
Exit status: 0 clean, 1 stale page or a bad description, 2 bad usage.
"""
import fnmatch
import os
import re
import subprocess
import sys
import tempfile

HEADER_STYLES = {".sh": ("hash",), ".bash": ("hash",), ".py": ("pydoc", "hash"), ".rb": ("hash",), ".pl": ("hash",),
                 ".js": ("slash",), ".mjs": ("slash",), ".ts": ("slash",)}
DEFAULT_GROUP = "Other"

INTRO = """\
Generated from the header of each `{glob}` by the catalogue generator; its `--check` fails when this page differs
from the generated text. **Do not edit it by hand.** Each script's header is the full account (escape-hatch markers,
baselines, self-tests); this page prints its first paragraph and links the script.
"""


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def header_lines(text, styles):
    """The leading comment block of a script as plain lines (marker stripped, shebang skipped)."""
    for style in styles:
        out = []
        if style == "pydoc":
            m = re.match(r'\A(?:#![^\n]*\n)?(?:\s*#[^\n]*\n)*\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', text, re.S)
            if m:
                return m.group(1).strip("\n").split("\n")
            continue
        marker = "#" if style == "hash" else "//"
        for i, line in enumerate(text.split("\n")):
            if i == 0 and line.startswith("#!"):
                continue
            if line.startswith(marker):
                out.append(re.sub("^" + re.escape(marker) + " ?", "", line))
            else:
                break
        if any(x.strip() for x in out):
            return out
    return []


def describe(lines, name):
    """(group, description) from a header: drop the title line and `group:` lines, take the first paragraph."""
    group, body = DEFAULT_GROUP, []
    for ln in lines:
        m = re.match(r"^\s*group:\s*(.+?)\s*$", ln)
        if m:
            group = m.group(1)
        else:
            body.append(ln)
    while body and not body[0].strip():
        body.pop(0)
    stem = os.path.splitext(name)[0]
    if body and re.match(r"^" + re.escape(name) + r"(?:\s|$)|^" + re.escape(stem) + r"(?:\s|$)", body[0].strip()):
        title = body.pop(0).strip()
        m = re.match(r"^\S+\s*--\s*(.+)$", title)
        if m and body and body[0].strip():
            body.insert(0, m.group(1))  # `name -- text` followed directly by more text starts the paragraph
    while body and not body[0].strip():
        body.pop(0)
    para = []
    for ln in body:
        if not ln.strip():
            break
        para.append(ln.strip())
    return group, re.sub(r"\s+", " ", " ".join(para)).strip()


def problems(name, desc, lo, hi):
    out = []
    if not desc:
        out.append(f"{name}: no header description (the comment block at the top of the file)")
        return out
    if len(desc) < lo:
        out.append(f"{name}: description too thin ({len(desc)} chars, need {lo}+): {desc!r}")
    if len(desc) > hi:
        out.append(f"{name}: description too long ({len(desc)} chars, at most {hi}); keep detail in later paragraphs")
    if desc.endswith(":"):
        out.append(f"{name}: the first paragraph ends with a colon, so it introduces something it does not say")
    return out


def generate(root, glob, out_rel, title, lo, hi):
    """(page text, [problems])."""
    scripts = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in {".git", "node_modules", "__pycache__"})
        for f in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
            if fnmatch.fnmatch(rel, glob):
                scripts.append(rel)
    probs, groups = [], {}
    out_dir = os.path.dirname(os.path.join(root, out_rel))
    for rel in sorted(scripts):
        name = os.path.basename(rel)
        styles = HEADER_STYLES.get(os.path.splitext(name)[1], ("hash",))
        group, desc = describe(header_lines(read(os.path.join(root, rel)), styles), name)
        probs += problems(name, desc, lo, hi)
        link = os.path.relpath(os.path.join(root, rel), out_dir).replace(os.sep, "/")
        groups.setdefault(group, []).append(f"**`{name}`** ([`{rel}`]({link})): {desc}")
    parts = [f"# {title}\n", INTRO.format(glob=glob)]
    for g in sorted(groups, key=lambda x: (x == DEFAULT_GROUP, x)):
        parts.append(f"## {g}\n\n" + "\n\n".join(groups[g]) + "\n")
    return "\n".join(parts), probs


def run(root, glob, out_rel, title, lo, hi, mode):
    text, probs = generate(root, glob, out_rel, title, lo, hi)
    out = os.path.join(root, out_rel)
    if mode == "write":
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        for p in probs:
            print("docs_catalogue: " + p, file=sys.stderr)
        print(f"docs_catalogue: wrote {out_rel}")
        return 1 if probs else 0
    rc = 0
    for p in probs:
        rc = 1
        print("docs_catalogue: " + p, file=sys.stderr)
    if not os.path.exists(out) or read(out) != text:
        rc = 1
        print(f"docs_catalogue: {out_rel} is stale or missing; regenerate it with --write and commit it", file=sys.stderr)
    if rc == 0:
        print(f"docs_catalogue: OK -- {out_rel} matches the headers of {glob}")
    return rc


def self_test():
    good = ("#!/bin/sh\n# check-a.sh -- no tabs\n#\n# group: Hygiene\n#\n# Fails when a tracked file contains a tab character,\n"
            "# because tab width differs by editor and the diff then lies about alignment.\n#\n# More detail for readers of the script.\nexit 0\n")
    other = ("#!/bin/sh\n#\n# Fails when a script has no final newline, because the next appended line would\n"
             "# join the last one and the diff would show a change to a line nobody touched.\nexit 0\n")
    pyscript = ('#!/usr/bin/env python3\n"""check-b.py -- every id is unique\n\nFails when two tracker files share an id, '
                'because a citation would then resolve to two different items.\n"""\n')
    base = {"scripts/check-a.sh": good, "scripts/check-c.sh": other, "scripts/check-b.py": pyscript}

    def attempt(files, mode, pre=None, extra=()):
        with tempfile.TemporaryDirectory(prefix="catalogue-") as d:
            for p, t in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, p)), exist_ok=True)
                with open(os.path.join(d, p), "w", encoding="utf-8") as fh:
                    fh.write(t)
            me = [sys.executable, "-I", os.path.abspath(__file__), "--root", d]
            if pre:
                subprocess.run(me + ["--write"], capture_output=True, check=False)
                pre(d)
            r = subprocess.run(me + [mode, *extra], capture_output=True, text=True)
            page = read(os.path.join(d, "docs/checks.md")) if os.path.exists(os.path.join(d, "docs/checks.md")) else ""
            return r.returncode, r.stdout + r.stderr, page

    def append_file(d):
        with open(os.path.join(d, "scripts/check-new.sh"), "w", encoding="utf-8") as fh:
            fh.write(good.replace("check-a", "check-new"))

    def edit_page(d):
        with open(os.path.join(d, "docs/checks.md"), "a", encoding="utf-8") as fh:
            fh.write("hand edit\n")

    def edit_header(d):
        p = os.path.join(d, "scripts/check-a.sh")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(good.replace("tab character", "tab or a carriage return"))

    thin = {**base, "scripts/check-d.sh": "#!/bin/sh\n# check-d.sh\n#\n# Checks d.\nexit 0\n"}
    colon = {**base, "scripts/check-d.sh": "#!/bin/sh\n#\n# Fails when a file is not formatted the way the formatter prints it, as follows:\n#\n# - a\nexit 0\n"}
    none = {**base, "scripts/check-d.sh": "#!/bin/sh\nexit 0\n"}
    cases = [
        ("fresh page passes --check", base, "--check", lambda d: None, 0),
        ("hand edit of the page fails", base, "--check", edit_page, 1),
        ("a new script not in the page fails", base, "--check", append_file, 1),
        ("an edited header not in the page fails", base, "--check", edit_header, 1),
        ("missing page fails", base, "--check", None, 1),
        ("thin description fails", thin, "--check", lambda d: None, 1),
        ("colon-ended description fails", colon, "--check", lambda d: None, 1),
        ("no header fails", none, "--check", lambda d: None, 1),
    ]
    fails = 0
    for name, files, mode, pre, want in cases:
        rc, out, _ = attempt(files, mode, pre)
        ok = rc == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (rc {rc}, want {want})")
        if not ok:
            print("    " + out.replace("\n", "\n    "))
    rc, _, page = attempt(base, "--write")
    shape = ("## Hygiene" in page and page.index("## Hygiene") < page.index("## Other")
             and "no tabs" not in page and "Fails when a tracked file contains a tab character" in page
             and "(../scripts/check-a.sh)" in page and "every id is unique" not in page and "Fails when two tracker files" in page)
    fails += not shape
    print(f"  {'ok  ' if shape else 'FAIL'} page shape: groups, title line dropped, docstring header read, relative links")
    print(f"docs_catalogue --self-test: {'OK' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def main(argv):
    if "--self-test" in argv[1:]:
        return self_test()
    cfg = {"root": os.getcwd(), "scripts": "scripts/check-*", "out": "docs/checks.md", "title": "Checks",
           "min": 60, "max": 700}
    mode = None
    it = iter(argv[1:])
    try:
        for a in it:
            if a in ("--write", "--check"):
                mode = a[2:]
            elif a in ("--root", "--scripts", "--out", "--title"):
                cfg[a[2:]] = next(it)
            elif a in ("--min-chars", "--max-chars"):
                cfg[a[2:5]] = int(next(it))
            else:
                print(f"docs_catalogue: unknown argument {a}", file=sys.stderr)
                return 2
    except (StopIteration, ValueError):
        print("docs_catalogue: an option is missing its (numeric) value", file=sys.stderr)
        return 2
    if mode is None:
        print("usage: docs_catalogue.py [--root DIR] [--scripts GLOB] [--out FILE] (--write | --check) | --self-test", file=sys.stderr)
        return 2
    return run(os.path.abspath(cfg["root"]), cfg["scripts"], cfg["out"], cfg["title"], cfg["min"], cfg["max"], mode)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
