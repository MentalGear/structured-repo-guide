#!/usr/bin/env python3
"""docs_catalogue.py -- generate a catalogue page of checks from the header of each check script.

Usage (Python 3 standard library only):

    docs_catalogue.py [--root DIR] [--gates FILE | --scripts GLOB] [--out FILE] [--title TITLE]
                      [--min-chars N] [--max-chars N] (--write | --check)
    docs_catalogue.py --self-test

    --root DIR       the repository root (default: the current directory)
    --gates FILE     LIST-DRIVEN: the runner's gate list (scripts/gates.list, read by run-gates.sh) is the source
                     of truth. Groups come from its `# group:` lines, the order is the list's, a check script is
                     described by its own header, a plain command (`cargo test`) by the comment lines directly
                     above its entry, and a gate with no description fails. A scripts/check-*.sh that the list
                     does not name fails too. This is the default when scripts/gates.list exists under --root.
    --scripts GLOB   GLOB-DRIVEN: the check scripts to describe, relative to --root (default scripts/check-*.sh;
                     a hyphenated .py helper next to the wrappers is not a check). Groups come from each header's
                     `group:` line, entries are sorted by file name. Forces this mode.
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
    # group: Source hygiene                      <- glob mode only; the heading it is listed under (default: Other)
    #
    # The first paragraph is the catalogue entry: one or two sentences saying what the check forbids and
    # why. Blank comment line ends it. Everything after is detail for the script's own readers.

In list mode the list's `# group:` line decides the group and a `group:` line in a header is ignored.

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
DEFAULT_GLOB = "scripts/check-*.sh"
DEFAULT_GATES = "scripts/gates.list"

INTRO = """\
Generated from the header of each `{glob}` by the catalogue generator; its `--check` fails when this page differs
from the generated text. **Do not edit it by hand.** Each script's header is the full account (escape-hatch markers,
baselines, self-tests); this page prints its first paragraph and links the script.
"""


INTRO_LIST = """\
Generated from the gate list `{list}` and the headers of the check scripts it names, by the catalogue generator; its
`--check` fails when this page differs from the generated text. **Do not edit it by hand.** A check script is described
by the first paragraph of its own header (the header is the full account: markers, baselines, self-tests) and linked;
a gate that is a plain command is described by the comment lines above its entry in the list. Groups and order are the
list's, and the same run that prints `ALL GREEN` runs every gate below.
"""

CHECK_SCRIPT = re.compile(r"scripts/check-[A-Za-z0-9_.-]+\.sh")
ENTRY = re.compile(r"^([A-Za-z0-9_.-]+)((?:[ \t]+\S+)*)[ \t]*\|(.*)$")


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


def parse_gate_list(text):
    """([(group, name, tags, command, [comment lines above])], [problems]) from the text of a gate list."""
    gates, probs, group, pending = [], [], None, []
    for no, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            body = re.sub(r"^#\s?", "", line)
            m = re.match(r"^group:\s*(.+)$", body)
            if m:
                group, pending = m.group(1).strip(), []
            else:
                pending.append(body.strip())
            continue
        m = ENTRY.match(line)
        if not m:
            probs.append(f"gate list line {no}: needs the form `name [tags]|command`: {line}")
            continue
        if group is None:
            probs.append(f"gate list line {no}: gate {m.group(1)} has no `# group:` line above it")
            continue
        tags = m.group(2).split()
        gates.append((group, m.group(1), tags, m.group(3).strip(), pending))
        pending = []
    return gates, probs


def generate_list(root, list_rel, out_rel, title, lo, hi):
    """(page text, [problems]) for the list-driven catalogue."""
    path = os.path.join(root, list_rel)
    if not os.path.exists(path):
        return "", [f"{list_rel}: the gate list does not exist"]
    gates, probs = parse_gate_list(read(path))
    out_dir = os.path.dirname(os.path.join(root, out_rel))
    named, order, groups = set(), [], {}
    for group, name, tags, cmd, above in gates:
        m = next((CHECK_SCRIPT.fullmatch(w) for w in cmd.split() if CHECK_SCRIPT.fullmatch(w)), None)
        link = ""
        if m:
            rel = m.group(0)
            named.add(rel)
            if above:
                probs.append(f"{name}: comment lines above a check script's entry are ignored; its header is the description")
            if not os.path.exists(os.path.join(root, rel)):
                probs.append(f"{name}: {rel} does not exist")
                continue
            base = os.path.basename(rel)
            _, desc = describe(header_lines(read(os.path.join(root, rel)), HEADER_STYLES.get(os.path.splitext(base)[1], ("hash",))), base)
            href = os.path.relpath(os.path.join(root, rel), out_dir).replace(os.sep, "/")
            link = f" ([`{rel}`]({href}))"
        else:
            desc = re.sub(r"\s+", " ", " ".join(above)).strip()
            if not desc:
                probs.append(f"{name}: a gate that is not a check script needs comment lines directly above its entry in {list_rel}")
                continue
        probs += problems(name, desc, lo, hi)
        mark = " *(slow)*" if "slow" in tags else ""
        if group not in groups:
            order.append(group)
        groups.setdefault(group, []).append(f"**`{name}`**{mark}{link}: {desc}")
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "scripts")):
        dirnames[:] = []
        for f in sorted(filenames):
            rel = "scripts/" + f
            if CHECK_SCRIPT.fullmatch(rel) and rel not in named:
                probs.append(f"{rel}: a check script that is not in {list_rel} (add a line to the list)")
    parts = [f"# {title}\n", INTRO_LIST.format(list=list_rel)]
    for g in order:
        parts.append(f"## {g}\n\n" + "\n\n".join(groups[g]) + "\n")
    return "\n".join(parts), probs


def run(root, glob, out_rel, title, lo, hi, mode, gates=None):
    if gates:
        text, probs = generate_list(root, gates, out_rel, title, lo, hi)
    else:
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
        print(f"docs_catalogue: OK -- {out_rel} matches " + (f"the gate list {gates}" if gates else f"the headers of {glob}"))
    return rc


def self_test():
    good = ("#!/bin/sh\n# check-a.sh -- no tabs\n#\n# group: Hygiene\n#\n# Fails when a tracked file contains a tab character,\n"
            "# because tab width differs by editor and the diff then lies about alignment.\n#\n# More detail for readers of the script.\nexit 0\n")
    other = ("#!/bin/sh\n#\n# Fails when a script has no final newline, because the next appended line would\n"
             "# join the last one and the diff would show a change to a line nobody touched.\nexit 0\n")
    pyscript = ('#!/usr/bin/env python3\n"""check-b.py -- every id is unique\n\nFails when two tracker files share an id, '
                'because a citation would then resolve to two different items.\n"""\n')
    base = {"scripts/check-a.sh": good, "scripts/check-c.sh": other, "scripts/check-b.py": pyscript}

    def attempt(files, mode, pre=None, extra=(), common=("--scripts", "scripts/check-*")):
        with tempfile.TemporaryDirectory(prefix="catalogue-") as d:
            for p, t in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, p)), exist_ok=True)
                with open(os.path.join(d, p), "w", encoding="utf-8") as fh:
                    fh.write(t)
            me = [sys.executable, "-I", os.path.abspath(__file__), "--root", d, *common]
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
    helper = {**base, "scripts/check-helper.py": "#!/usr/bin/env python3\n\"\"\"The helper behind a wrapper, not a check.\"\"\"\n"}
    fails = 0
    rc, out, _ = attempt(helper, "--check", lambda d: None, (), common=())
    ok = rc == 0
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} the default glob is scripts/check-*.sh: a hyphenated .py helper is not a check (rc {rc}, want 0)")
    if not ok:
        print("    " + out.replace("\n", "\n    "))
    for name, files, mode, pre, want in cases:
        rc, out, _ = attempt(files, mode, pre)
        ok = rc == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (rc {rc}, want {want})")
        if not ok:
            print("    " + out.replace("\n", "\n    "))

    # list-driven: the gate list is the source of truth
    lgood = ("#!/bin/sh\n# check-a.sh -- no tabs\n#\n# group: Wrong, ignored in list mode\n#\n# Fails when a tracked file contains a tab character,\n"
             "# because tab width differs by editor and the diff then lies about alignment.\nexit 0\n")
    lpins = ("#!/bin/sh\n#\n# Fails when a dependency is declared with a version range instead of an exact pin, because a range\n"
             "# lets the next install resolve to code nobody reviewed.\nexit 0\n")
    glist = ("# group: Hygiene\ncheck-a|sh scripts/check-a.sh\n# group: Security\ncheck-pins|sh scripts/check-pins.sh --strict\n"
             "# group: Build\n# Formats every source file with the project formatter and fails on any difference, because\n"
             "# unformatted code makes every diff noisy.\nfmt|cargo fmt --check\n# Runs the whole test suite, which takes minutes.\n"
             "# It is the slow gate.\ntest slow|cargo test\n")
    lbase = {"scripts/gates.list": glist, "scripts/check-a.sh": lgood, "scripts/check-pins.sh": lpins}

    def with_list(extra_list=None, **files):
        out = {**lbase, **files}
        if extra_list is not None:
            out["scripts/gates.list"] = extra_list
        return out

    def lattempt(files, mode, pre=None):
        return attempt(files, mode, pre, (), common=())

    lcases = [
        ("list: a fresh page passes --check", lbase, "--check", lambda d: None, 0),
        ("list: a hand edit of the page fails", lbase, "--check", edit_page, 1),
        ("list: a gate that is a command and has no comment fails",
         with_list(lbase["scripts/gates.list"] + "lint|make lint\n"), "--check", lambda d: None, 1),
        ("list: a check script missing from the list fails", with_list(**{"scripts/check-z.sh": lgood.replace("check-a", "check-z")}),
         "--check", lambda d: None, 1),
        ("list: a listed script that does not exist fails",
         with_list(lbase["scripts/gates.list"] + "# group: More\ncheck-gone|sh scripts/check-gone.sh\n"), "--check", lambda d: None, 1),
        ("list: a comment above a check script's gate fails",
         with_list("# group: One\n# a second description\ncheck-a|sh scripts/check-a.sh\ncheck-pins|sh scripts/check-pins.sh\n"),
         "--check", lambda d: None, 1),
        ("list: a gate with no group above it fails", with_list("check-a|sh scripts/check-a.sh\ncheck-pins|sh scripts/check-pins.sh\n"),
         "--check", lambda d: None, 1),
        ("list: a thin comment fails",
         with_list("# group: One\ncheck-a|sh scripts/check-a.sh\ncheck-pins|sh scripts/check-pins.sh\n# Formats.\nfmt|cargo fmt\n"),
         "--check", lambda d: None, 1),
        ("list: a hyphenated .py helper is not an unlisted check", with_list(**{"scripts/check-helper.py": "#!/usr/bin/env python3\n"}),
         "--check", lambda d: None, 0),
        ("list: an edited list line makes the page stale", lbase, "--check",
         lambda d: open(os.path.join(d, "scripts/gates.list"), "a", encoding="utf-8").write("# group: Tail\n# Prints a banner for people reading the logs of a run.\nbanner|echo hi\n"), 1),
    ]
    for name, files, mode, pre, want in lcases:
        rc, out, _ = lattempt(files, mode, pre)
        ok = rc == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (rc {rc}, want {want})")
        if not ok:
            print("    " + out.replace("\n", "\n    "))
    rc, _, page = lattempt(lbase, "--write")
    order = [page.find(h) for h in ("## Hygiene", "## Security", "## Build")]
    shape = (all(i >= 0 for i in order) and order == sorted(order) and "Wrong" not in page and "*(slow)*" in page
             and "(../scripts/check-pins.sh)" in page and "Formats every source file" in page
             and "**`fmt`**: Formats" in page and "**`test`** *(slow)*: Runs the whole test suite" in page)
    fails += not shape
    print(f"  {'ok  ' if shape else 'FAIL'} list page shape: groups in list order from both halves, tags, comment-described commands, header group ignored")
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
    cfg = {"root": os.getcwd(), "scripts": None, "gates": None, "out": "docs/checks.md", "title": "Checks",
           "min": 60, "max": 700}
    mode = None
    it = iter(argv[1:])
    try:
        for a in it:
            if a in ("--write", "--check"):
                mode = a[2:]
            elif a in ("--root", "--scripts", "--gates", "--out", "--title"):
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
        print("usage: docs_catalogue.py [--root DIR] [--gates FILE | --scripts GLOB] [--out FILE] (--write | --check) | --self-test",
              file=sys.stderr)
        return 2
    if cfg["gates"] and cfg["scripts"]:
        print("docs_catalogue: --gates and --scripts are two sources of truth; give one", file=sys.stderr)
        return 2
    root = os.path.abspath(cfg["root"])
    gates = cfg["gates"]
    if not gates and not cfg["scripts"] and os.path.exists(os.path.join(root, DEFAULT_GATES)):
        gates = DEFAULT_GATES
    return run(root, cfg["scripts"] or DEFAULT_GLOB, cfg["out"], cfg["title"], cfg["min"], cfg["max"], mode, gates)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
