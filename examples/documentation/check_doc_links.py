#!/usr/bin/env python3
"""check_doc_links.py -- every relative link in the Markdown files of a tree must resolve.

Usage (Python 3 standard library only):

    check_doc_links.py [--root DIR] [--no-anchors] [--skip PREFIX]... [PATH...]
    check_doc_links.py --self-test

    --root DIR      the tree to check (default: the current directory); an absolute link `/x.md` resolves from here
    --no-anchors    check only that the file exists, not that a `#heading` fragment names a heading in it
    --skip PREFIX   do not check Markdown files whose root-relative path starts with PREFIX (repeatable); use it for
                    templates, whose links are relative to the place they are copied to
    PATH...         Markdown files or directories to check (default: every *.md under --root)

Checked: inline links and images `[t](target)`, reference definitions `[id]: target`. Ignored: fenced code blocks,
inline code spans, http(s)/mailto and other scheme links, and a bare `#fragment` that points into the same file
(that one IS checked against the file's headings unless --no-anchors). Heading anchors follow the GitHub rule:
lower-case, punctuation dropped, spaces to hyphens, a repeated heading gets -1, -2.

A moved file, a renamed heading or a deleted page fails here instead of in a reader's browser.
Exit status: 0 clean, 1 a broken link, 2 bad usage.
"""
import os
import re
import subprocess
import sys
import tempfile

SKIP_DIRNAMES = {".git", "node_modules", "target", "dist", "build", "__pycache__", ".venv"}
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFDEF = re.compile(r"(?m)^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?\s*$")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"(?ms)^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$")


def strip_code(text):
    text = FENCE.sub("", text)
    return re.sub(r"`[^`\n]*`", "", text)


def slug(heading):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)  # a link in a heading keeps its text
    t = t.replace("`", "").lower()
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"\s", "-", t.strip())


def anchors_of(path, cache={}):
    if path not in cache:
        seen, out = {}, set()
        with open(path, encoding="utf-8") as fh:
            body = FENCE.sub("", fh.read())
        for ln in body.split("\n"):
            m = HEADING.match(ln)
            if m:
                s = slug(m.group(2))
                n = seen.get(s, 0)
                seen[s] = n + 1
                out.add(s if n == 0 else f"{s}-{n}")
        cache[path] = out
    return cache[path]


def md_files(root, paths):
    if paths:
        found = []
        for p in paths:
            full = p if os.path.isabs(p) else os.path.join(root, p)
            if os.path.isdir(full):
                found += md_files(full, [])
            elif os.path.isfile(full):
                found.append(full)
        return sorted(found)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRNAMES)
        out += [os.path.join(dirpath, f) for f in sorted(filenames) if f.endswith(".md")]
    return out


def check(root, paths, anchors=True, skip=()):
    bad, n = [], 0
    for f in md_files(root, paths):
        if os.path.relpath(f, root).replace(os.sep, "/").startswith(tuple(skip)):
            continue
        with open(f, encoding="utf-8") as fh:
            text = strip_code(fh.read())
        for t in LINK.findall(text) + REFDEF.findall(text):
            if re.match(r"[a-z][a-z0-9+.-]*:", t, re.I) or t.startswith("//"):
                continue
            path, _, frag = re.split(r"\?", t, maxsplit=1)[0].partition("#")
            n += 1
            dest = f if not path else (os.path.join(root, path.lstrip("/")) if path.startswith("/")
                                       else os.path.join(os.path.dirname(f), path))
            rel = os.path.relpath(f, root)
            if not os.path.exists(dest):
                bad.append(f"{rel}: broken link ({t})")
            elif frag and anchors and dest.endswith(".md") and os.path.isfile(dest) and frag.lower() not in anchors_of(dest):
                bad.append(f"{rel}: no heading for the anchor ({t})")
    return bad, n


def self_test():
    ok_tree = {"a.md": "# A\n\n## The `x` rule\n\n[b](sub/b.md) [rule](#the-x-rule) [b2](sub/b.md#second-part) "
                       "[web](https://example.com/x)\n",
               "sub/b.md": "# B\n\n## Second part\n\n[up](../a.md#a)\n"}
    cases = [
        ("good tree passes", ok_tree, 0),
        ("broken file link fails", {**ok_tree, "c.md": "[x](nope.md)\n"}, 1),
        ("broken anchor fails", {**ok_tree, "c.md": "[x](a.md#no-such-heading)\n"}, 1),
        ("broken same-file anchor fails", {**ok_tree, "c.md": "# C\n[x](#gone)\n"}, 1),
        ("broken reference definition fails", {**ok_tree, "c.md": "[x][r]\n\n[r]: missing/file.md\n"}, 1),
        ("broken image fails", {**ok_tree, "c.md": "![alt](img/none.png)\n"}, 1),
        ("link in a code fence is ignored", {**ok_tree, "c.md": "```\n[x](nope.md)\n```\n"}, 0),
        ("link in an inline code span is ignored", {**ok_tree, "c.md": "see `[x](nope.md)`\n"}, 0),
        ("repeated heading gets -1", {"a.md": "# T\n## Same\n## Same\n[x](#same-1)\n"}, 0),
        ("absolute link resolves from the root", {**ok_tree, "sub/c.md": "[x](/a.md)\n"}, 0),
    ]
    fails = 0
    for name, files, want in cases:
        with tempfile.TemporaryDirectory(prefix="doc-links-") as d:
            for p, text in files.items():
                full = os.path.join(d, p)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(text)
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--root", d], capture_output=True, text=True)
        ok = r.returncode == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (rc {r.returncode}, want {want})")
        if not ok:
            print("    " + (r.stdout + r.stderr).replace("\n", "\n    "))
    # --no-anchors lets a broken fragment through
    with tempfile.TemporaryDirectory(prefix="doc-links-") as d:
        with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as fh:
            fh.write("# A\n[x](a.md#gone)\n")
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--root", d, "--no-anchors"],
                           capture_output=True, text=True)
    ok = r.returncode == 0
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} --no-anchors ignores a fragment (rc {r.returncode}, want 0)")
    with tempfile.TemporaryDirectory(prefix="doc-links-") as d:
        os.makedirs(os.path.join(d, "templates"))
        with open(os.path.join(d, "templates", "t.md"), "w", encoding="utf-8") as fh:
            fh.write("[x](./docs/STATUS.md)\n")
        r0 = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--root", d], capture_output=True, text=True)
        r1 = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--root", d, "--skip", "templates"],
                            capture_output=True, text=True)
    ok = r0.returncode == 1 and r1.returncode == 0
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} --skip leaves out a template tree (rc {r0.returncode} then {r1.returncode}, want 1 then 0)")
    print(f"check_doc_links --self-test: {'OK' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def main(argv):
    if "--self-test" in argv[1:]:
        return self_test()
    root, anchors, paths, skip = os.getcwd(), True, [], []
    it = iter(argv[1:])
    try:
        for a in it:
            if a == "--root":
                root = next(it)
            elif a == "--no-anchors":
                anchors = False
            elif a == "--skip":
                skip.append(next(it))
            elif a.startswith("-"):
                print(f"check_doc_links: unknown option {a}", file=sys.stderr)
                return 2
            else:
                paths.append(a)
    except StopIteration:
        print("check_doc_links: an option is missing its value", file=sys.stderr)
        return 2
    root = os.path.abspath(root)
    bad, n = check(root, paths, anchors, skip)
    if bad:
        print("check_doc_links: broken relative links")
        for b in bad:
            print("  - " + b)
        return 1
    print(f"check_doc_links: OK -- {n} relative links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
