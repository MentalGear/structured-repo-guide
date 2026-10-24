#!/usr/bin/env python3
"""check-remote-assets.py: fail when a page or stylesheet loads something from another host.

What it is for: an image, font, stylesheet or script fetched from a third-party host at
runtime sends every visitor's request to that party, lets that party change what your page
runs or shows, and makes the page depend on someone else being up. Bundle the file or inline
it instead. This check scans web sources for remote loads. No network, Python 3 standard library.

Flags, in .html .htm .css .svg .js .mjs .ts .tsx .jsx .vue and .svelte files under the roots:
  - an `src`, `srcset` or `poster` attribute whose value is `http(s)://` or `//host`;
  - a `<link ... href=remote>` (stylesheet, preload, icon, preconnect: all contact the host);
  - a CSS `url(remote)` or `@import` of a remote URL.
Not flagged: `data:` URIs, relative paths, ordinary `<a href>` links, XML namespaces.

Allowlist (`--allow FILE`), one entry per line, `#` starts a comment line:
      file-path-suffix|exact-url|reason
  The reason is required and an entry matching no violation is stale and fails the run.

Usage: check-remote-assets.py [--allow FILE] ROOT...      check-remote-assets.py --self-test
Exit status: 0 clean, 1 violations, 2 usage.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile

EXTS = (".html", ".htm", ".css", ".svg", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte")
URL = r"(?:https?:)?//[^\s\"')>]+"
PATTERNS = [
    re.compile(r"""\b(?:src|srcset|poster)\s*=\s*["']?(""" + URL + ")", re.I),
    re.compile(r"""<link\b[^>]*?\bhref\s*=\s*["']?(""" + URL + ")", re.I),
    re.compile(r"""\burl\(\s*["']?(""" + URL + ")", re.I),
    re.compile(r"""@import\s+["']?(""" + URL + ")", re.I),
]


def scan(roots):
    found = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in (".git", "node_modules", "target"))
            for f in sorted(filenames):
                if not f.endswith(EXTS):
                    continue
                path = os.path.join(dirpath, f)
                try:
                    text = open(path, encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                for n, line in enumerate(text.splitlines(), 1):
                    for pat in PATTERNS:
                        for m in pat.finditer(line):
                            found.append((path.replace(os.sep, "/"), n, m.group(1)))
    return found


def run(roots, allow_path):
    entries, problems = [], []
    if allow_path and os.path.exists(allow_path):
        for n, line in enumerate(open(allow_path, encoding="utf-8").read().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|", 2)]
            if len(parts) != 3 or not all(parts):
                problems.append(f"{allow_path}:{n}: want `file-suffix|url|reason`, with a reason")
            else:
                entries.append(parts)
    used = set()
    found = scan(roots)
    for path, n, url in found:
        hit = next((i for i, (suf, u, _) in enumerate(entries) if path.endswith(suf) and u == url), None)
        if hit is None:
            problems.append(f"{path}:{n}: remote load of {url}; bundle it or inline it")
        else:
            used.add(hit)
    for i, (suf, u, _) in enumerate(entries):
        if i not in used:
            problems.append(f"{allow_path}: stale entry `{suf}|{u}`: it matches nothing, delete it")
    return problems, len(found)


def self_test():
    bad, total = 0, 0

    def case(name, want, files, allow=None):
        nonlocal bad, total
        total += 1
        tmp = tempfile.mkdtemp(prefix="remote-selftest-")
        try:
            for k, v in files.items():
                p = os.path.join(tmp, k)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "w").write(v)
            ap = None
            if allow is not None:
                ap = os.path.join(tmp, "allow.txt")
                open(ap, "w").write(allow)
            problems, _ = run([os.path.join(tmp, "web")], ap)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = (not problems) if want is None else any(want in p for p in problems)
        print(f"  self-test {'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f" -- got {problems[:2]}"))
        bad += 0 if ok else 1

    clean = '<img src="logo.svg"><a href="https://example.com/docs">docs</a><svg xmlns="http://www.w3.org/2000/svg"></svg>' \
            '<img src="data:image/png;base64,AAAA">'
    case("bundled, data: and ordinary links are green", None, {"web/index.html": clean})
    case("remote image", "remote load", {"web/index.html": '<img src="https://cdn.example.com/a.png">'})
    case("protocol-relative script", "remote load", {"web/index.html": '<script src="//cdn.example.com/x.js"></script>'})
    case("remote stylesheet link", "remote load", {"web/index.html": '<link rel="stylesheet" href="https://fonts.example.com/css">'})
    case("remote font in CSS", "remote load", {"web/app.css": "@font-face { src: url('https://fonts.example.com/f.woff2'); }"})
    case("remote @import", "remote load", {"web/app.css": '@import "https://x.example.com/a.css";'})
    case("an allowlisted load is green", None, {"web/index.html": '<img src="https://slow.example.com/a.png">'},
         allow="index.html|https://slow.example.com/a.png|the demo shows a slow-loading image on purpose\n")
    case("an allowlist entry that matches nothing is stale", "stale entry", {"web/index.html": clean},
         allow="index.html|https://gone.example.com/a.png|was needed once\n")
    if bad:
        print(f"check-remote-assets: self-test FAIL ({bad} of {total} cases wrong)", file=sys.stderr)
        return 1
    print(f"check-remote-assets: self-test OK ({total} cases)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Fail on remote asset loads.")
    ap.add_argument("roots", nargs="*")
    ap.add_argument("--allow", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.roots:
        ap.print_usage(sys.stderr)
        return 2
    problems, n = run(a.roots, a.allow)
    if problems:
        print("check-remote-assets: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"check-remote-assets: OK -- {n} remote load(s), all allowlisted with a reason" if n else
          "check-remote-assets: OK -- no remote loads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
