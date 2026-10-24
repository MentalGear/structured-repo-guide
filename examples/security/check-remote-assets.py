#!/usr/bin/env python3
"""check-remote-assets.py: fail when a page or stylesheet loads something from another host.

What it is for: an image, font, stylesheet or script fetched from a third-party host at
runtime sends every visitor's request to that party, lets that party change what your page
runs or shows, and makes the page depend on someone else being up. Bundle the file or inline
it instead. This check scans web sources for remote loads. No network, Python 3 standard library.

Flags, in .html .htm .css .svg .js .mjs .ts .tsx .jsx .vue and .svelte files under the roots
(a tag or an `image-set(...)` may span lines):
  - an `src`, `srcset` or `poster` attribute whose value is `http(s)://` or `//host`;
  - a `<link ... href=remote>` (stylesheet, preload, icon, preconnect: all contact the host);
  - an `href` or `xlink:href` on the SVG elements that load what they name (`<image>`, `<use>`,
    `<feImage>`, `<script>`), and a `<object data=remote>`;
  - a CSS `url(remote)`, an `@import` of a remote URL, and a string inside `image-set(...)`;
  - a module import of a remote URL: `import x from "https://..."`, `import "https://..."`,
    `import("https://...")`, `export ... from "https://..."`.
Not flagged: `data:` URIs, relative paths, ordinary `<a href>` links, XML namespaces.
Not checked (extend this file, or add a Content-Security-Policy and test that): a URL that a
script builds at runtime or passes to `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`,
`new Worker`, `importScripts` or `new URL`; `<meta http-equiv="refresh">`.

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
    re.compile(r"""<(?:image|use|feImage|script)\b[^>]*?\b(?:xlink:)?href\s*=\s*["']?(""" + URL + ")", re.I),
    re.compile(r"""<object\b[^>]*?\bdata\s*=\s*["']?(""" + URL + ")", re.I),
    re.compile(r"""\burl\(\s*["']?(""" + URL + ")", re.I),
    re.compile(r"""@import\s+["']?(""" + URL + ")", re.I),
    re.compile(r"""\bimport\s*\(?\s*["'](""" + URL + ")", re.I),
    re.compile(r"""\bfrom\s*["'](""" + URL + ")", re.I),
]
IMAGE_SET = re.compile(r"image-set\(([^)]*)\)", re.I)
IMAGE_SET_STRING = re.compile(r"""["'](""" + URL + ")", re.I)


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
                path = path.replace(os.sep, "/")
                seen = set()
                hits = [m for pat in PATTERNS for m in pat.finditer(text)]
                for body in IMAGE_SET.finditer(text):
                    hits += [(body, m) for m in IMAGE_SET_STRING.finditer(body.group(1))]
                for h in hits:
                    if isinstance(h, tuple):
                        body, m = h
                        at, url = body.start(1) + m.start(1), m.group(1)
                    else:
                        at, url = h.start(1), h.group(1)
                    n = text.count("\n", 0, at) + 1
                    if (n, url) not in seen:
                        seen.add((n, url))
                        found.append((path, n, url))
    return sorted(found)


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
    case("SVG <image href>", "remote load", {"web/logo.svg": '<svg><image href="https://cdn.example.com/a.png"/></svg>'})
    case("SVG <use xlink:href>", "remote load", {"web/logo.svg": '<svg><use xlink:href="https://cdn.example.com/s.svg#a"/></svg>'})
    case("an <object data>", "remote load", {"web/index.html": '<object data="https://cdn.example.com/a.pdf"></object>'})
    case("a CSS image-set string", "remote load",
         {"web/app.css": 'a { background: image-set("local.png" 1x, "https://cdn.example.com/b@2x.png" 2x); }'})
    case("a module import from a URL", "remote load", {"web/app.js": 'import confetti from "https://cdn.example.com/confetti.js";'})
    case("a bare module import of a URL", "remote load", {"web/app.js": "import 'https://cdn.example.com/side-effect.js';"})
    case("a dynamic import of a URL", "remote load", {"web/app.js": 'const m = await import("https://cdn.example.com/m.js");'})
    case("a re-export from a URL", "remote load", {"web/app.js": "export { a } from 'https://cdn.example.com/a.js';"})
    case("a <link> whose href is on the next line", "remote load",
         {"web/index.html": '<link rel="stylesheet"\n      href="https://fonts.example.com/css">'})
    case("an <a xlink:href> link and a local import are green", None,
         {"web/logo.svg": '<svg><a xlink:href="https://example.com/docs"><text>docs</text></a></svg>', "web/app.js": 'import x from "./x.js";'})
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
