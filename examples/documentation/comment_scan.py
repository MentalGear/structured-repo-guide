#!/usr/bin/env python3
"""comment_scan.py -- two checks over the comments of a source tree, behind one comment extractor.

    history   per-file ratchet on comment lines that retell history: dates, commit hashes and the phrases
              of PHRASES below (narrated changes, replaced behaviour, incident stories)
    refs      every tracker id and every repository path that a comment cites must resolve

Usage (run from the repository root; Python 3 standard library only):

    comment_scan.py history [--root DIR] [--baseline FILE] [--skip PREFIX]... [--min-date YYYY-MM-DD]
                            [--inventory | --update-baseline [--allow-grow]] [FILE...]
    comment_scan.py refs    [--root DIR] [--baseline FILE] [--skip PREFIX]... [--tracker DIR] [--word WORD]
                            [--inventory | --update-baseline [--allow-grow]] [FILE...]
    comment_scan.py --self-test [history | refs]

    --root DIR          the tree to scan (default: the current directory)
    --baseline FILE     the ratchet file (default: history-comments.tsv or comment-refs.tsv in the baselines
                        directory under scripts/, relative to --root)
    --skip PREFIX       skip files whose root-relative path starts with PREFIX (repeatable; adds to SKIP_PREFIXES)
    --min-date DATE     history only: dates before DATE are data, not history (default: every date counts); a date
                        written as a month and year, or as dd/mm/yyyy, is placed on the last day of that month or year
    --tracker DIR       refs only: the tracker directory, one file per item, NNN-slug.md, finished ones in DIR/done/
                        (default docs/backlog)
    --word WORD         refs only: the word that introduces a cited id, as in "backlog N" (default backlog). A bare
                        "<word> N" is a citation only when it is unmistakable (see "Citations" below)
    --inventory         list every counted line (the worklist for a cleanup sweep); exit 0
    --update-baseline   rewrite the baseline from the current tree; refuses to let any count grow
                        unless --allow-grow is also given (say why in the commit message)
    FILE...             scan only these files (root-relative)

Exit status: 0 clean, 1 violation, 2 bad usage.

What is a comment is decided in ONE place, `syntax_for` and the SYNTAX table below: a file is matched by its extension,
else by its name (Makefile, Dockerfile, ...), else, for a file with no extension, by its `#!` line. Add a language by
adding a row. A comment marker inside a string literal is not a comment, and the extractor reads the literals that
matter for that: Python triple-quoted strings (only a docstring, the first statement of a module, class or function,
counts as a comment), shell heredoc bodies and multi-line quoted strings, Java, Kotlin, Swift and C# text blocks, and
JavaScript regex literals (a `/` after an operator, a bracket or a keyword such as `return`).
Known gaps, which can hide a comment (lenient) or read text as one (strict): code that lives inside a string of
another language (the comments of a Python file that a heredoc writes are not seen), the `${...}` expressions of a
JavaScript template literal, a JavaScript `/` after `)` or `}` (read as division even where it opens a regex),
nested quotes inside shell `$(...)`, and a file without a section model (a Vue or Svelte file is one stream of `<!-- -->`,
`//` and `/* */` comments, so a `//` in template text reads as a comment).
Not read at all: comments inside JavaScript, CSS, SQL or HTML that sits in a string literal, the `<script>` and `<style>`
bodies of an HTML file (only its `<!-- -->` comments are read), and names such as test titles, test function names and test
file names. Those want an extractor of their own that feeds `history_reason`, and a gate with no baseline for the names.

Citations. The tracker word is often an ordinary English word ("issue", "ticket", "item"), and "the second issue 5
times larger" is not a citation. So `<word> N` counts as one when (a) it is written `<word> #N`, or (b) the comment
block also names the tracker (the tracker directory's name, e.g. "backlog", or the word "tracker"), or (c) N has three
or more digits and is at most 25 above the highest existing id (it looks like an id) and does not read as a quantity
("<word> N of/times/per ..."). With the default word ("backlog") the word itself names the tracker, so every
`backlog N` counts. A citation that is none of these is not checked: write it `<word> #N`.

Paths. A path a comment names is checked when it starts at a top-level directory of the tree (also with a leading
`./`), when it is written `./name` for a root-level file, and when it is a bare upper-case Markdown name, which must exist
somewhere in the tree. Any other bare file name is an example, not a citation. A list of ids stops at a number that a
noun follows: the tail of "<word> N and 3 others" is a count.

What the history check knows is a list of common shapes (dates, hashes, the PHRASES below). Green means "no common
shape found", not "clean": a comment can retell history in words no pattern matches.

Deliberate exceptions carry a marker WITH a reason on the line itself:
    history-ok: <reason>     the line is history on purpose (a quoted upstream changelog, a date the code needs)
    ref-ok: <reason>         the cited id or path is missing on purpose
A marker without a reason exempts nothing.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

# --------------------------------------------------------------------------- configuration
# Comment syntax. Keys: line (markers), block ((start, end) pairs), nested (block comments nest), strings
# ((delimiter, may_span_lines): the longest delimiter first), docstrings (delimiters read as comments, only where a
# docstring can stand), hash (a line marker must follow whitespace or one of ;|&( so `$#` and `${#x}` are not
# comments), chars (C-style 'x' character literals), raw (string delimiters without backslash escapes), heredoc
# (shell here-documents: the body is text), backslash (a backslash outside a string escapes the next character),
# regex (JavaScript regex literals), attr (a `#[` is an attribute, not a comment).
C = dict(line=("//",), block=(("/*", "*/"),), strings=(('"', False),), chars=True)
TEXTBLOCK = dict(C, strings=(('"""', True), ('"', False)))
HASH = dict(line=("#",), strings=(('"', False), ("'", False)), hash=True)
SHELL = dict(line=("#",), strings=(('"', True), ("'", True)), hash=True, raw=("'",), heredoc=True, backslash=True)
PYTHON = dict(line=("#",), docstrings=('"""', "'''"),
              strings=(('"""', True), ("'''", True), ('"', False), ("'", False)))
JS = dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False, regex=True)
MAKE = dict(line=("#",), hash=True)
PHP = dict(line=("//", "#"), block=(("/*", "*/"),), strings=(('"', False), ("'", False)), attr=True)
SFC = dict(line=("//",), block=(("<!--", "-->"), ("/*", "*/")), strings=(('"', False), ("'", False)))
SYNTAX = {
    ".py": PYTHON,
    ".sh": SHELL, ".bash": SHELL, ".zsh": SHELL,
    ".rb": HASH, ".yml": HASH, ".yaml": HASH, ".toml": HASH,
    ".js": JS, ".mjs": JS, ".cjs": JS, ".jsx": JS, ".ts": JS, ".tsx": JS,
    ".rs": dict(C, nested=True, rust=True),
    ".go": dict(C, strings=(('"', False), ("`", True))),
    ".java": TEXTBLOCK, ".cs": TEXTBLOCK,
    ".kt": dict(TEXTBLOCK, nested=True), ".kts": dict(TEXTBLOCK, nested=True), ".swift": dict(TEXTBLOCK, nested=True),
    ".c": C, ".h": C, ".cpp": C, ".hpp": C,
    ".css": dict(block=(("/*", "*/"),), strings=(('"', False), ("'", False))),
    ".scss": dict(line=("//",), block=(("/*", "*/"),), strings=(('"', False), ("'", False))),
    ".sql": dict(line=("--",), block=(("/*", "*/"),), strings=(("'", True),)),
    ".lua": dict(line=("--",), block=(("--[[", "]]"),), strings=(('"', False), ("'", False))),
    ".html": dict(block=(("<!--", "-->"),)),
    ".php": PHP, ".vue": SFC, ".svelte": SFC, ".mk": MAKE,
}
# A file whose NAME decides (no extension, or one the table does not know), then a `#!` line for an extensionless file.
FILENAMES = {
    "Makefile": MAKE, "makefile": MAKE, "GNUmakefile": MAKE,
    "Dockerfile": HASH, "Containerfile": HASH,
    "Gemfile": HASH, "Rakefile": HASH, "Vagrantfile": HASH, "Justfile": HASH, "justfile": HASH,
}
FILENAME_PREFIXES = (("Dockerfile.", HASH), ("Containerfile.", HASH))
SHEBANGS = (
    (re.compile(r"^(?:sh|bash|zsh|dash|ash|ksh)$"), SHELL),
    (re.compile(r"^python[\d.]*$"), PYTHON),
    (re.compile(r"^(?:node|nodejs|deno|bun)$"), JS),
    (re.compile(r"^(?:ruby|perl)$"), HASH),
    (re.compile(r"^php[\d.]*$"), PHP),
)
# Paths (root-relative prefixes) that are never scanned: history is allowed in docs, baselines are data,
# vendored and generated trees are not ours. A directory NAME in SKIP_DIRNAMES is skipped at any depth.
SKIP_PREFIXES = ("docs/", "scripts/baselines/", "node_modules/", "vendor/", "target/", "dist/", "build/", "third_party/")
SKIP_DIRNAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "target", "dist", "build"}
SKIP_SUFFIXES = (".min.js", ".lock")
# Upstream revisions pinned on purpose are provenance, not history; list their prefixes here. The form
# `<path> @ <sha>` is always provenance.
PINNED_REVS = ()

HISTORY_BASELINE = "scripts/baselines/history-comments.tsv"
REFS_BASELINE = "scripts/baselines/comment-refs.tsv"


# --------------------------------------------------------------------------- files
def listed_paths(root):
    """Root-relative paths of every file under root, sorted. Inside a git work tree this is git's view (tracked and
    untracked files, minus what .gitignore ignores, so a virtualenv or a build tree is never scanned); anywhere else,
    or without git, it is a directory walk that skips the names in SKIP_DIRNAMES."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        r = None
    if r is not None and r.returncode == 0:
        paths = r.stdout.decode("utf-8", "surrogateescape").split("\0")
        return sorted({p for p in paths if p and os.path.isfile(os.path.join(root, p))})
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRNAMES)
        for f in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return sorted(out)


def shebang_syntax(full):
    """The syntax a `#!` line names, or None."""
    try:
        with open(full, "rb") as fh:
            first = fh.readline(200)
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    words = first[2:].decode("utf-8", "replace").split()
    if not words:
        return None
    prog = os.path.basename(words[0])
    if prog == "env":
        rest = [w for w in words[1:] if not w.startswith("-") and "=" not in w]
        prog = os.path.basename(rest[0]) if rest else ""
    return next((syn for rx, syn in SHEBANGS if rx.match(prog)), None)


def syntax_for(root, path):
    """The comment syntax of a file, or None when it is not one the table knows."""
    base = os.path.basename(path)
    ext = os.path.splitext(base)[1]
    if ext in SYNTAX:
        return SYNTAX[ext]
    if base in FILENAMES:
        return FILENAMES[base]
    for prefix, syn in FILENAME_PREFIXES:
        if base.startswith(prefix):
            return syn
    if ext == "":
        return shebang_syntax(os.path.join(root, path))
    return None


def tracked_files(root, skip):
    """Root-relative paths of every file with a known comment syntax, sorted."""
    out = []
    for p in listed_paths(root):
        if p.startswith(tuple(skip)) or p.endswith(SKIP_SUFFIXES):
            continue
        if any(part in SKIP_DIRNAMES for part in p.split("/")[:-1]):
            continue
        if syntax_for(root, p) is not None:
            out.append(p)
    return sorted(out)


# --------------------------------------------------------------------------- comment extraction
def _emit_block(out, start_line, raw, strip_star):
    for k, ln in enumerate(raw.split("\n")):
        out.append((start_line + k, re.sub(r"^\s*\*+ ?", "", ln) if strip_star else ln))


REGEX_BEFORE = set("(,=:[!&|?{};<>~^%*")
REGEX_KEYWORDS = {"return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do",
                  "instanceof", "yield", "await"}
HEREDOC = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([A-Za-z_][A-Za-z0-9_]*))")
PY_DOC_AFTER = ("", "def", "class", "async")


def _regex_end(text, i):
    """If the `/` at i opens a JavaScript regex literal, the index just past it, else 0. A regex may follow an
    operator, an opening bracket or a keyword; after an identifier, a number or a closing bracket the `/` divides."""
    k = i - 1
    while k >= 0 and text[k] in " \t\r\n":
        k -= 1
    if k >= 0:
        ch = text[k]
        if ch.isalnum() or ch in "_$":
            e = k
            while k >= 0 and (text[k].isalnum() or text[k] in "_$"):
                k -= 1
            if text[k + 1:e + 1] not in REGEX_KEYWORDS:
                return 0
        elif ch not in REGEX_BEFORE:
            return 0
    j, in_class = i + 1, False
    while j < len(text):
        ch = text[j]
        if ch == "\n":
            return 0
        if ch == "\\":
            j += 2
            continue
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif ch == "/" and not in_class:
            return j + 1
        j += 1
    return 0


def extract(text, syn):
    """[(line_number, body)] for every comment line; a block comment gives one entry per physical line."""
    out = []
    i, n, line = 0, len(text), 1
    blocks, lines_, strings = syn.get("block", ()), syn.get("line", ()), syn.get("strings", ())
    docs = syn.get("docstrings", ())
    raw_delims = syn.get("raw", ())
    pending = []  # shell here-documents opened on the current line: (delimiter, strip leading tabs)
    # Python statement state: a triple-quoted string is a docstring (a comment) only as the FIRST statement of a
    # module, class or function; anywhere else it is a string.
    depth, stmt_start, first_word, first_pos, prev_first, doc_pos_ok = 0, True, None, -1, "", False
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            if docs and depth == 0 and not text.startswith("\\", i - 2):
                if first_word is not None:
                    prev_first, first_word = first_word, None
                stmt_start = True
            while pending:
                delim, strip = pending.pop(0)
                while i < n:
                    e = text.find("\n", i)
                    e = n if e < 0 else e
                    body = text[i:e].rstrip("\r")
                    i = min(e + 1, n)
                    line += 1 if e < n else 0
                    if (body.lstrip("\t") if strip else body) == delim:
                        break
            continue
        if docs and stmt_start and first_word is None and not c.isspace() and c != "#":
            wm = re.match(r"\w+", text[i:i + 40])
            first_word, first_pos, stmt_start = (wm.group(0) if wm else c), i, False
            doc_pos_ok = prev_first in PY_DOC_AFTER
        hit = next(((s, e) for s, e in blocks if text.startswith(s, i)), None)
        if hit:
            s, e = hit
            j, depth_ = i + len(s), 1
            while j < n and depth_:
                if syn.get("nested") and text.startswith(s, j):
                    depth_ += 1
                    j += len(s)
                elif text.startswith(e, j):
                    depth_ -= 1
                    j += len(e)
                else:
                    j += 1
            end = j - len(e) if depth_ == 0 else j
            _emit_block(out, line, text[i + len(s):max(i + len(s), end)], True)
            line += text.count("\n", i, j)
            i = j
            continue
        if syn.get("backslash") and c == "\\":
            line += text.startswith("\n", i + 1)
            i += 2
            continue
        d = next((d for d in docs if text.startswith(d, i)), None)
        if d and doc_pos_ok and (first_pos == i or (text[first_pos:i].lower() in ("r", "u") and first_pos + 1 == i)):
            j = text.find(d, i + len(d))
            j = n if j < 0 else j + len(d)
            _emit_block(out, line, text[i + len(d):max(i + len(d), j - len(d))], False)
            line += text.count("\n", i, j)
            i = j
            doc_pos_ok = False
            continue
        m = next((m for m in lines_ if text.startswith(m, i)), None)
        if m and (not syn.get("hash") or i == 0 or text[i - 1] in " \t;|&(\n") \
                and not (syn.get("attr") and text.startswith("#[", i)):
            j = text.find("\n", i)
            j = n if j < 0 else j
            body = text[i + len(m):j]
            if m == "#" and i == 0 and body.startswith("!"):
                pass  # a shebang is not a comment
            else:
                out.append((line, body[1:] if m == "//" and body[:1] in ("/", "!") else body))
            i = j
            continue
        if syn.get("heredoc") and text.startswith("<<", i) and not text.startswith("<<<", i):
            hm = HEREDOC.match(text, i)
            if hm:
                delim = next(g for g in hm.groups()[1:] if g is not None)
                ls = text.rfind("\n", 0, i) + 1
                body_ok = re.search(r"(?m)^%s%s\r?$" % ("\t*" if hm.group(1) else "", re.escape(delim)), text[hm.end():])
                if "((" not in text[ls:i] and body_ok:
                    pending.append((delim, bool(hm.group(1))))
                    i = hm.end()
                    continue
        if syn.get("rust") and c in "rb" and not (i and (text[i - 1].isalnum() or text[i - 1] == "_")):
            rm = re.match(r'b?r(#*)"', text[i:i + 12])
            if rm:
                end = '"' + rm.group(1)
                j = text.find(end, i + rm.end())
                j = n if j < 0 else j + len(end)
                line += text.count("\n", i, j)
                i = j
                continue
        if syn.get("chars") and c == "'":
            if text.startswith("\\", i + 1):
                j = text.find("'", i + 3)
                i = i + 1 if j < 0 else j + 1
            elif i + 2 < n and text[i + 2] == "'":
                i += 3
            else:
                i += 1  # a lifetime or label
            continue
        if syn.get("regex") and c == "/":
            j = _regex_end(text, i)
            if j:
                i = j
                continue
        s = next(((d, multi) for d, multi in strings if text.startswith(d, i)), None)
        if s:
            d, multi = s
            raw = d in raw_delims and not (i and text[i - 1] == "$")
            j = i + len(d)
            while j < n and not text.startswith(d, j):
                if text[j] == "\n" and not multi:
                    break
                j += 1 if raw else (2 if text[j] == "\\" else 1)
            stop = j if (j >= n or text[j] == "\n") and not text.startswith(d, j) else j + len(d)
            line += text.count("\n", i, min(stop, n))
            i = stop
            continue
        if docs:
            depth = depth + 1 if c in "([{" else max(depth - 1, 0) if c in ")]}" else depth
        i += 1
    return out


def comments_of(root, path):
    with open(os.path.join(root, path), encoding="utf-8", errors="replace") as fh:
        return extract(fh.read(), syntax_for(root, path))


# --------------------------------------------------------------------------- history detection
DATE = re.compile(r"(?<![\w.-])(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?![\w-])")
HEX = re.compile(r"(?<![\w#.\-/$@])(?:[0-9a-f]{7,40})(?![\w\-/])")
PHRASES = [
    (re.compile(r"\bbefore the (?:fix|change|rewrite|refactor|migration)\b", re.I), "before the fix"),
    (re.compile(r"\bformerly\b", re.I), "formerly"),
    (re.compile(r"\bold (?:behaviou?r|implementation|approach|name)\b", re.I), "old behaviour"),
    (re.compile(r"\bwas\s+\S+(?:\s+\S+){0,2},\s*(?:and\s+)?now\b", re.I), "was X, now Y"),
    (re.compile(r"\bwe (?:now|used to|no longer|previously)\b", re.I), "we now"),
    (re.compile(r"\bnow (?:uses|reads|writes|goes|lives|comes|calls|returns|lets|owns|runs|derives)\b", re.I), "now uses"),
    (re.compile(r"\bsince (?:been )?(?:removed|replaced|renamed|dropped|fixed)\b", re.I), "was changed"),
    (re.compile(r"\b(?:after|following|since) (?:the|a|an) (?:incident|outage|regression|post-?mortem|bug report)\b",
                re.I), "incident"),
    (re.compile(r"\bwe (?:found|discovered|noticed|hit|saw)\b", re.I), "incident"),
    # Shapes that retell a fix, a removal or a rewrite. Each stays low in false positives: "was fixed" needs a
    # following word that makes it a story (a width that "is fixed at 3 columns" is not one).
    (re.compile(r"\b(?:was|were|got|has been|have been) (?:fixed|resolved|patched|addressed) (?:in|upstream|since|after|as of)\b",
                re.I), "was fixed"),
    (re.compile(r"\b(?:fixed|resolved|patched) (?:in|since|as of) (?:v|version |release )?\d+(?:\.\d+)+", re.I), "fixed in"),
    (re.compile(r"\b(?:removed|dropped|deprecated) (?:in|since|as of|from) (?:v|version |release )?\d+(?:\.\d+)+", re.I),
     "removed in"),
    (re.compile(r"\bkept for (?:the )?old\b", re.I), "kept for old"),
    (re.compile(r"\b(?:leftovers?|left over|remnants?|relics?|vestiges?) (?:from|of) (?:the |an? )?"
                r"(?:old|previous|former|earlier|original|legacy|rewrite|migration|refactor|port)\b", re.I), "leftover from"),
    (re.compile(r"\bwe (?:switched|moved|replaced|dropped|removed|rewrote|renamed|changed|migrated|ported)\b", re.I),
     "we changed"),
    (re.compile(r"\b(?:originally|initially) (?:was|were|used|written|designed|implemented|had|did)\b", re.I), "originally"),
    (re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b[^\n]*\b(?:since the|after the (?:rewrite|migration|refactor|port|outage|incident))\b",
                re.I), "narrative TODO"),
    # Who or which work stream found it. "session" and "round" alone are ordinary words of code (a user session, to
    # round a number), so only the numbered and the "earlier/previous" forms count.
    (re.compile(r"\b(?:lane|sprint|round) \d+\b", re.I), "work stream"),
    (re.compile(r"\b(?:an?|the|another) (?:earlier|previous|prior|last) (?:lane|session|round|sprint|agent)\b", re.I),
     "work stream"),
    (re.compile(r"\b(?:the|an?|another) (?:agent|lane) (?:found|noticed|reported|flagged|added|wrote|changed|hit|saw|left)\b",
                re.I), "work stream"),
    # Evidence narration: how somebody came to know, which stays true of the code for no longer than the next change.
    (re.compile(r"\b(?:confirmed|verified|reproduced|observed|measured) (?:live|in production|on a device|on hardware|"
                r"manually|by hand)\b", re.I), "evidence"),
    (re.compile(r"\bmeasured (?:before|after)\b", re.I), "evidence"),
    (re.compile(r"\bthe (?:report|review|audit|trace|profile) (?:showed|found|said|revealed|flagged)\b", re.I), "evidence"),
    # Evidence narration in the rationale prose (test headers, script headers, config sections): a trial, a run count, a
    # failure seen somewhere. A reason ("flaky under load") and a present fact ("an input of 0.07 gives hue 221") stay.
    (re.compile(r"\bthe (?:audit|sweep|benchmark|experiment|investigation|test run|run) "
                r"(?:measured|reproduced|confirmed|observed|recorded|counted)\b", re.I), "evidence"),
    (re.compile(r"\b(?:seen|observed|reproduced|hit|found) (?:under load|in (?:ci|production|the field)|on (?:ci|a device))\b",
                re.I), "evidence"),
    (re.compile(r"\breproduced the (?:identical|same|exact) (?:failure|error|crash|result)\b", re.I), "evidence"),
    (re.compile(r"\b\d+/\d+ (?:clean |green |passing |failing )?(?:runs?|passes|failures?)\b", re.I), "evidence"),
    # How a gate came to be: the adoption day is history, the rule it enforces is not.
    (re.compile(r"\b(?:when|once|at the time) (?:the|this) (?:gate|check|ratchet|rule|baseline|scanner|lint) "
                r"(?:was|were) (?:adopted|introduced|added|written|installed|enabled|turned on)\b", re.I), "adoption"),
    # A tuning trial: the value that was tried and what it gave, in the past tense.
    (re.compile(r"\b\d[\d.]* (?:gave|yielded|produced|scored|failed|clipped|overflowed)\b"), "trial"),
    # An upper-case word in a header that records an edit instead of describing the section.
    (re.compile(r"\b(?:NARROWED|WIDENED|TIGHTENED|LOOSENED|RELAXED|RAISED|LOWERED|REPLACED|DROPPED|REWRITTEN)\b"),
     "change stamp"),
    # A contrast with the state before, without the word "before".
    (re.compile(r"\b(?:as before|always was|same as (?:before|earlier)|unchanged (?:from|since|after))\b", re.I),
     "contrast"),
    (re.compile(r"\bit replaces the (?:old|previous|former|earlier)\b", re.I), "contrast"),
]
# A scratch file of whoever does the work: a temp path, a home path or a scratch directory. It is gone with the session.
SCRATCH = re.compile(r"(?:^|[\s(`'\"])(?:/tmp/|/var/tmp/|~/)\S|\bscratch(?:pad)?/\S", re.I)
# A path names a file, so the words inside it are not prose (a file name that spells a phrase holds no prose). A token counts as
# a path with two slashes or more, or with one slash and a file extension; a slash date and "and/or" stay as they are.
PATH_TOKEN = re.compile(r"(?<![\w/.-])(?:\.{1,2}/)?[A-Za-z_][\w.@-]*(?:/[\w.@-]+)+")


def _mask_paths(body):
    def hide(m):
        t = m.group(0)
        return "_path_" if t.count("/") >= 2 or re.search(r"\.\w{1,5}$", t) else t
    return PATH_TOKEN.sub(hide, body)


USED_TO = re.compile(r"(?:\b(\w+)\s+)?\bused to\b", re.I)
# "is used to X", "can be used to X": the instrument sense, not history.
PASSIVE_PREV = {"is", "are", "be", "been", "being", "was", "were", "get", "gets", "got", "it's", "also", "only",
                "then", "often", "just", "can", "could", "may", "might", "must", "should", "will", "would",
                "not", "if", "when", "and", "or", "both", "either", "so", "thus", "than"}
PREVIOUSLY = re.compile(r"\bpreviously\b(?!-)(?:\s+(\w+))?", re.I)
# The word describes a state when a determiner (or a preposition or conjunction that continues a noun phrase) stands
# before it and a participle after it (the focused element). It tells a story when it opens a clause or follows a
# pronoun or an auxiliary.
PREVIOUSLY_DET = {"the", "a", "an", "its", "their", "his", "her", "our", "your", "my", "this", "that", "these", "those",
                  "any", "each", "every", "all", "of", "to", "from", "with", "for", "by", "and", "or", "no"}
PREVIOUSLY_IRREGULAR = {"set", "read", "run", "put", "shown", "sent", "hidden", "open", "active", "visible", "built",
                        "kept", "left", "found", "held", "made", "seen", "known", "given", "taken", "done", "lost"}
# A passive change verb is history when it is about the code and runtime when a named actor (RUNTIME_ACTOR) or a data
# structure (RUNTIME_DATA) did it, as in a value changed by the caller or a field removed from the payload.
PASSIVE_CHANGE = re.compile(r"\b(?:was|were|got|has been|have been) (?:changed|renamed|rewritten|replaced|removed|dropped)\b"
                            r"(?P<rest>[^.;]*)", re.I)
RUNTIME_ACTOR = (r"caller|callee|user|server|client|browser|host|parent|child|consumer|producer|sender|receiver|peer|"
                 r"plugin|handler|service|backend|frontend|runtime|kernel|driver|library|application|app|operator|admin|"
                 r"owner|reader|writer|listener|observer|subscriber|publisher|provider|framework|engine|scheduler|"
                 r"compiler|hook|middleware|network|proxy|os")
RUNTIME_DATA = (r"payload|request|response|message|input|output|list|queue|map|set|cache|table|array|buffer|stream|"
                r"file|document|dom|tree|registry|store|database|db|collection|batch|row|record|result|results|page|"
                r"form|state|session|body|header|headers|url|path|query|object|config|configuration|environment")
RUNTIME_PASSIVE = re.compile(r"^\s+(?:\w+\s+){0,3}?(?:by (?:the|a|an|its|each|any|that|this) (?:%s)\b|"
                             r"(?:from|in|into|on) (?:the|a|an|its|each|that|this) (?:%s)\b)" % (RUNTIME_ACTOR, RUNTIME_DATA), re.I)
CONDITIONAL = re.compile(r"\b(?:when|once|if|until|unless|whenever|whether|while|as soon as)\b", re.I)
NO_LONGER = re.compile(r"\bno longer\b(?!\s+(?:than|then)\b)", re.I)
CLAUSE_BREAK = re.compile(r"[,;:.()]")
# A date that is not written ISO. Month names are matched capitalised ("May" the month, never "may" the verb).
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
MONTH_RX = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|" \
           r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
FULL_MONTH_RX = r"(?:%s)" % "|".join(MONTHS)
MONTH_YEAR = re.compile(r"\b(%s)\.?,?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?((?:19|20)\d\d)\b" % MONTH_RX)
MONTH_DAY = re.compile(r"\b%s\s+\d{1,2}(?:st|nd|rd|th)?\b(?!\s*(?:items?|times|of|%%|x\b))" % FULL_MONTH_RX)
SINCE_MONTH = re.compile(r"\b(?:since|as of|until|after|before|in|during|from)\s+(?:early |late |mid-)?%s\b" % FULL_MONTH_RX)
SLASH_DATE = re.compile(r"(?<![\w/.-])(\d{1,2})/(\d{1,2})/((?:19|20)\d\d|\d\d)(?![\w/])")
DOT_DATE = re.compile(r"(?<![\w.])(\d{1,2})\.(\d{1,2})\.((?:19|20)\d\d)(?![\w.])")
MARK_HISTORY = re.compile(r"history-ok:\s*\S")
MARK_REF = re.compile(r"ref-ok:\s*\S")


def _loose_date(body, min_date):
    """True when body has a date that is not written ISO and is not before min_date. A month and year is placed on the
    last day of that month, dd/mm/yyyy on the last day of the year, and a month name alone on no day (it always counts)."""
    for m in MONTH_YEAR.finditer(body):
        month = next(i for i, name in enumerate(MONTHS, 1) if name.startswith(m.group(1)[:3]))
        if "%s-%02d-31" % (m.group(2), month) >= min_date:
            return True
    for m in SLASH_DATE.finditer(body):
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if a <= 31 and b <= 31 and (a <= 12 or b <= 12) and ("%s-12-31" % (y if len(y) == 4 else "20" + y)) >= min_date:
            return True
    for m in DOT_DATE.finditer(body):
        if int(m.group(1)) <= 31 and int(m.group(2)) <= 31 and "%s-12-31" % m.group(3) >= min_date:
            return True
    return bool(MONTH_DAY.search(body) or SINCE_MONTH.search(body))


def _clause_before(body, pos):
    return CLAUSE_BREAK.split(body[:pos])[-1]


def history_reason(body, min_date="0000-01-01"):
    """Why a comment line retells history, or None. One reason per line is enough: the unit is the line."""
    if MARK_HISTORY.search(body):
        return None
    if SCRATCH.search(body):
        return "scratch path"
    body = _mask_paths(body)
    for m in DATE.finditer(body):
        if "-".join(m.groups()) >= min_date:
            return "date"
    if _loose_date(body, min_date):
        return "date"
    for m in HEX.finditer(body):
        tok = m.group(0)
        if re.search(r"\d", tok) and len(re.findall(r"[a-f]", tok)) >= 2 and not re.fullmatch(r"\d+e\d+", tok):
            if any(rev.startswith(tok) for rev in PINNED_REVS) or body[:m.start()].endswith("@ "):
                continue
            return "sha"
    for rx, why in PHRASES:
        if rx.search(body):
            return why
    for m in PASSIVE_CHANGE.finditer(body):
        if RUNTIME_PASSIVE.match(m.group("rest")) or CONDITIONAL.search(_clause_before(body, m.start())):
            continue
        return "was changed"
    for m in NO_LONGER.finditer(body):
        if not CONDITIONAL.search(_clause_before(body, m.start())):
            return "no longer"
    for m in USED_TO.finditer(body):
        if (m.group(1) or "").lower() not in PASSIVE_PREV:
            return "used to"
    for m in PREVIOUSLY.finditer(body):
        if re.search(r"\b(?:whatever|what|that|which)\s+(?:was|were|is)\s+$", body[:m.start()], re.I):
            continue
        nxt = (m.group(1) or "").lower()
        words = re.findall(r"[\w']+", body[:m.start()])
        prev = words[-1].lower() if words else ""
        participle = nxt.endswith(("ed", "en")) or nxt in PREVIOUSLY_IRREGULAR
        if not (nxt and participle and prev in PREVIOUSLY_DET) or re.search(r"previously,", body, re.I):
            return "previously"
    return None


def scan_history(root, files, min_date):
    """{path: [(line, reason, text)]} for every file with at least one retelling comment line."""
    result = {}
    for p in files:
        hits = [(ln, why, b.strip()) for ln, b in comments_of(root, p) if (why := history_reason(b, min_date))]
        if hits:
            result[p] = hits
    return result


# --------------------------------------------------------------------------- baselines
def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [ln for ln in fh.read().splitlines() if ln and not ln.startswith("#")]


def write_baseline(path, header, lines):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        for ln in lines:
            fh.write(ln + "\n")


def cmd_history(root, opts):
    base_path = opts["baseline"] or os.path.join(root, HISTORY_BASELINE)
    files = opts["files"] or tracked_files(root, opts["skip"])
    hits = scan_history(root, files, opts["min_date"])
    counts = {p: len(h) for p, h in hits.items()}
    if opts["inventory"]:
        for p in sorted(hits):
            for ln, why, text in hits[p]:
                print(f"{p}:{ln}\t{why}\t{text[:140]}")
        sys.stdout.flush()  # the summary is the LAST line of `2>&1`: the worklist must not trail it
        print(f"history: {sum(counts.values())} lines in {len(counts)} files", file=sys.stderr)
        return 0
    base = {k: int(v) for k, _, v in (ln.partition("\t") for ln in read_lines(base_path))}
    if opts["update"]:
        grow = {p: (base.get(p, 0), c) for p, c in counts.items() if c > base.get(p, 0)}
        if grow and os.path.exists(base_path) and not opts["allow_grow"]:
            print("history: refusing to GROW the baseline (shrink-only; rewrite the comments or add\n"
                  "`history-ok: <reason>`; --allow-grow overrides, say why in the commit):", file=sys.stderr)
            for p, (a, b) in sorted(grow.items()):
                print(f"  {p}: {a} -> {b}", file=sys.stderr)
            return 1
        write_baseline(base_path, "# history baseline: comment lines that retell history, per file (shrink-only).\n"
                       "# path<TAB>count. Regenerate with: sh scripts/check-history-comments.sh --update-baseline\n",
                       [f"{p}\t{counts[p]}" for p in sorted(counts)])
        print(f"history: baseline written ({len(counts)} files, {sum(counts.values())} lines)")
        return 0
    rc = 0
    rose = [(p, base.get(p, 0), c) for p, c in sorted(counts.items()) if c > base.get(p, 0)]
    if rose:
        rc = 1
        print("history: comment lines that retell history (dates, hashes, \"used to\", \"previously\", \"no longer\" ...)\n"
              "were ADDED. A comment says what the code is and why; history lives in the tracker item and is linked.\n"
              "Rewrite the line (archive, link, fold), or mark a deliberate one `history-ok: <reason>`.", file=sys.stderr)
        for p, was, now in rose:
            print(f"  {p}: {was} -> {now}" + ("  (not in the baseline)" if p not in base else ""), file=sys.stderr)
            for ln, why, text in hits[p][:12]:
                print(f"      {p}:{ln} [{why}] {text[:110]}", file=sys.stderr)
    stale = [(p, v, counts.get(p, 0)) for p, v in sorted(base.items()) if counts.get(p, 0) < v]
    if stale:
        rc = 1
        print("history: the count FELL (good) but the baseline still allows the old number, which would let history\n"
              "creep back in. Lock the drop in: sh scripts/check-history-comments.sh --update-baseline", file=sys.stderr)
        for p, was, now in stale:
            print(f"  {p}: baseline {was}, now {now}" + ("  (file gone or clean)" if now == 0 else ""), file=sys.stderr)
    if rc == 0:
        print(f"history: OK ({sum(counts.values())} baselined history lines in {len(counts)} files, none new); "
              "green means no common shape found, not that the comments are clean")
    return rc


# --------------------------------------------------------------------------- reference detection
PLACEHOLDER = re.compile(r"[<>{}*$|]|\.\.\.|…|\bNNN\b|\bXXX\b")


def tracker_ids(tracker):
    ids = set()
    for d in (tracker, os.path.join(tracker, "done")):
        if os.path.isdir(d):
            for f in os.listdir(d):
                m = re.match(r"(\d+)[a-z]?-.*\.md$", f)
                if m:
                    ids.add(int(m.group(1)))
    return ids


# A bare upper-case Markdown name lives at the root by convention (a README, a BACKLOG): it must exist somewhere in
# the tree. Any other bare file name is as often an example as a citation and is not checked. A name written with a
# leading `./` and no further slash is an unmistakable root-relative path and must exist at the root.
ROOT_NAMES = r"[A-Z][A-Z0-9_-]*\.md"
ROOT_DOT = r"\./[A-Za-z0-9_][A-Za-z0-9_.-]*\.[A-Za-z0-9]+"
# A number that continues an id list is not one when a noun follows it: the tail of "<word> N and 3 others" is a count.
NOT_AN_ID = r"(?!\s+(?:of|times|per|percent|others?|more|items?|rows?|cases?|places?|files?|tickets?|issues?|ids?|" \
            r"entries|lines?|sites?|callers?|users?|bytes|ms|seconds?|minutes?|hours?|days?)\b)"


def make_patterns(root, word):
    tops = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and d not in SKIP_DIRNAMES)
    path_rx = re.compile(r"(?<![\w./@~-])(?:\./)?(?:%s)/[A-Za-z0-9_.\-/\[\]*<>{}$\u2026]*" % "|".join(map(re.escape, tops))) \
        if tops else None
    name_rx = re.compile(r"(?<![\w./@~-])(?:%s|%s)(?![\w/-]|\.\w)" % (ROOT_NAMES, ROOT_DOT))
    num = r"#?(\d{1,6})(?!\d|-\d\d-)[a-z]?"
    more = num + NOT_AN_ID
    cite_rx = re.compile(r"\b%s(?:\s+(?:item|row|id))?\s+%s((?:\s*(?:,|/|&|and|-|to)\s*%s)*)" % (re.escape(word), num, more), re.I)
    return path_rx, name_rx, cite_rx


NEAR = 25  # a bare number is "id-like" when it has 3+ digits and is at most this far above the highest id
NOT_A_CITATION = re.compile(r"^\s*(?:of|times|per|percent|%|x\b)", re.I)


def blocks_of(comment_lines):
    """Group (line, body) comment lines into blocks: runs of consecutive lines."""
    spans, cur, prev = [], [], None
    for ln, body in comment_lines:
        if cur and ln != prev + 1:
            spans.append(cur)
            cur = []
        cur.append((ln, body))
        prev = ln
    if cur:
        spans.append(cur)
    return spans


def is_citation(m, ids, names_tracker):
    """Is a `<word> N` match a citation? `#N` and a block that names the tracker always; otherwise N must look like
    an id and must not read as a quantity ("issue 5 times larger")."""
    first = m.group(1)
    if re.search(r"#\d", m.group(0)) or names_tracker:
        return True
    if NOT_A_CITATION.match(m.string[m.end():m.end() + 12]):
        return False
    return len(first) >= 3 and int(first) <= max(ids, default=0) + NEAR


def refs_in(blocks, ids, path_rx, name_rx, cite_rx, tracker_rx):
    """[(line, kind, ref)] cited in a comment and not resolved by the id set (paths are checked by the caller)."""
    bad = []
    for span in blocks_of(blocks):
        names_tracker = any(tracker_rx.search(b) for _, b in span)
        for ln, body in span:
            if MARK_REF.search(body):
                continue
            for m in cite_rx.finditer(body):
                if not is_citation(m, ids, names_tracker):
                    continue
                nums = [m.group(1)] + re.findall(r"\d{1,6}", m.group(2) or "")
                for x in nums:
                    if int(x) not in ids:
                        bad.append((ln, "id", str(int(x))))
            if path_rx:
                for m in path_rx.finditer(body):
                    if m.end() >= len(body.rstrip()) and m.group(0).endswith("-"):
                        continue  # hyphen-wrapped onto the next line: the rest of the name is not on this one
                    tok = m.group(0).rstrip(".-")
                    if not PLACEHOLDER.search(tok):
                        bad.append((ln, "path", tok))
            for m in name_rx.finditer(body):
                bad.append((ln, "name", m.group(0)))
    return bad


def scan_refs(root, files, tracker, word):
    ids = tracker_ids(os.path.join(root, tracker))
    path_rx, name_rx, cite_rx = make_patterns(root, word)
    names = {os.path.basename(tracker.rstrip("/")).lower(), "tracker"}
    tracker_rx = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, sorted(names))), re.I)
    basenames = {os.path.basename(p) for p in listed_paths(root)}
    out = {}
    for p in files:
        res = []
        for ln, kind, ref in refs_in(comments_of(root, p), ids, path_rx, name_rx, cite_rx, tracker_rx):
            if kind == "path":
                target = re.sub(r":\d+(?:-\d+)?$", "", ref)
                target = target[2:] if target.startswith("./") else target
                if os.path.exists(os.path.join(root, target)) or os.path.exists(os.path.join(root, target.rstrip("/"))):
                    continue
            elif kind == "name":
                if (os.path.exists(os.path.join(root, ref[2:])) if ref.startswith("./") else ref in basenames):
                    continue
                kind = "path"
            res.append((ln, kind, ref))
        if res:
            out[p] = res
    return out


def cmd_refs(root, opts):
    base_path = opts["baseline"] or os.path.join(root, REFS_BASELINE)
    if not os.path.isdir(os.path.join(root, opts["tracker"])):
        print(f"refs: tracker directory {opts['tracker']} not found under {root} (--tracker DIR)", file=sys.stderr)
        return 2
    files = opts["files"] or tracked_files(root, opts["skip"])
    found = scan_refs(root, files, opts["tracker"], opts["word"])
    keys = sorted({f"{p}\t{kind}\t{ref}" for p, rs in found.items() for _, kind, ref in rs})
    if opts["inventory"]:
        for p in sorted(found):
            for ln, kind, ref in found[p]:
                print(f"{p}:{ln}\t{kind}\t{ref}")
        sys.stdout.flush()
        print(f"refs: {len(keys)} unresolved reference(s)", file=sys.stderr)
        return 0
    base_lines = set(read_lines(base_path))
    if opts["update"]:
        new = [k for k in keys if k not in base_lines]
        if new and os.path.exists(base_path) and not opts["allow_grow"]:
            print("refs: refusing to GROW the baseline (shrink-only; fix the citation or add\n"
                  "`ref-ok: <reason>`; --allow-grow overrides, say why in the commit):", file=sys.stderr)
            for k in new:
                print(f"  {k}", file=sys.stderr)
            return 1
        write_baseline(base_path, "# refs baseline: dead tracker-id and repository-path citations in comments (shrink-only).\n"
                       "# file<TAB>kind<TAB>ref. Fix the citation, then: sh scripts/check-comment-refs.sh --update-baseline\n", keys)
        print(f"refs: baseline written ({len(keys)} dead references)")
        return 0
    rc = 0
    new = [k for k in keys if k not in base_lines]
    if new:
        rc = 1
        print(f"refs: a comment cites a tracker id or a repository path that does not exist\n"
              f"(an id needs {opts['tracker']}/NNN-*.md or {opts['tracker']}/done/NNN-*.md; a path must exist in the tree):",
              file=sys.stderr)
        for k in new:
            p, kind, ref = k.split("\t")
            where = next(ln for ln, kd, rf in found[p] if kd == kind and rf == ref)
            print(f"  {p}:{where}: {kind} {ref}", file=sys.stderr)
        print("Fix the citation (an id never changes; a moved doc has a new path), or mark a deliberate one\n"
              "`ref-ok: <reason>`.", file=sys.stderr)
    stale = [k for k in sorted(base_lines) if k not in keys]
    if stale:
        rc = 1
        print("refs: baseline entries that now resolve (or whose comment is gone); lock it in with\n"
              "sh scripts/check-comment-refs.sh --update-baseline:", file=sys.stderr)
        for k in stale:
            print("  " + k.replace("\t", "  "), file=sys.stderr)
    if rc == 0:
        print(f"refs: OK ({len(keys)} baselined dead references, none new)")
    return rc


# --------------------------------------------------------------------------- self-test
def _fixture(kind, files, baseline=None, extra=()):
    """Write {path: text} to a temp tree (plus a baseline), run this script on it, return (rc, output)."""
    with tempfile.TemporaryDirectory(prefix="comment-scan-") as d:
        for p, text in files.items():
            full = os.path.join(d, p)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(text)
        if baseline is not None:
            default = HISTORY_BASELINE if kind == "history" else REFS_BASELINE
            write_baseline(os.path.join(d, default), "", baseline)
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), kind, "--root", d, *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


def _run_cases(label, kind, cases):
    fails = 0
    for name, files, bl, want, *extra in cases:
        rc, out = _fixture(kind, files, bl, extra[0] if extra else ())
        ok = rc == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (rc {rc}, want {want})")
        if not ok:
            print("    " + out.replace("\n", "\n    "))
    return fails


def self_test(kind=None):
    fails = 0
    if kind in (None, "history"):
        fails += self_test_history()
    if kind in (None, "refs"):
        fails += self_test_refs()
    print(f"comment_scan --self-test{' ' + kind if kind else ''}: {'OK' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def self_test_history():
    one = ["src/a.py\t1"]
    history = [
        # (name, files, baseline lines or None, expected rc)
        ("clean tree passes", {"src/a.py": "# the cache key includes the locale\nx = 1\n"}, [], 0),
        ("baselined history passes", {"src/a.py": "# used to be 3\nx = 1\n"}, one, 0),
        ("python: dated comment in a clean file", {"src/a.py": "# changed on 2025-03-02\nx = 1\n"}, [], 1),
        ("python: docstring is a comment", {"src/a.py": 'def f():\n    """Previously, this retried twice."""\n'}, [], 1),
        ("typescript: commit hash", {"src/a.ts": "// fixed in 3fa9c21b\nconst x = 1;\n"}, [], 1),
        ("rust: doc comment, no longer", {"src/a.rs": "/// no longer uses the shared timer\nfn a() {}\n"}, [], 1),
        ("rust: block comment line", {"src/a.rs": "/*\n * was 3px, now 2px\n */\nfn a() {}\n"}, [], 1),
        ("css: formerly", {"src/a.css": "/* formerly 2px */\na { top: 0 }\n"}, [], 1),
        ("shell: we now", {"src/a.sh": "# we now run this first\necho hi\n"}, [], 1),
        ("go: incident narration", {"src/a.go": "// after the incident we added a retry\nfunc a() {}\n"}, [], 1),
        ("sql: line comment", {"src/a.sql": "-- before the migration this was text\nselect 1;\n"}, [], 1),
        ("a rise in a baselined file fails", {"src/a.py": "# used to be 3\n# changed on 2025-03-02\nx = 1\n"}, one, 1),
        ("a new file with history fails", {"src/b.ts": "// previously, this was 2px\n"}, [], 1),
        ("stale baseline (count fell) fails", {"src/a.py": "x = 1\n"}, one, 1),
        ("baselined file gone fails", {"src/z.py": "x = 1\n"}, ["src/gone.py\t2"], 1),
        ("history-ok with a reason exempts", {"src/a.py": "# used to differ 2025-03-02 history-ok: quoted changelog\n"}, [], 0),
        ("history-ok without a reason does not", {"src/a.py": "# used to differ history-ok:\n"}, [], 1),
        ("date in a string is not a comment", {"src/a.rs": 'const D: &str = "2025-03-02 // not a comment";\n'}, [], 0),
        ("quote char literal does not open a string", {"src/a.rs": "fn a() { let q = '\"'; } // clean\n// used to\n"}, [], 1),
        ("colour is not a hash", {"src/a.css": "a { color: #abcdef1; }\n/* border is #abc1234 */\n"}, [], 0),
        ("`is used to` is not history", {"src/a.py": "# is used to size the panel; can be used to anchor it\n"}, [], 0),
        ("`<path> @ <sha>` is provenance", {"src/a.py": "# ported from lib/x.py @ 7e4034b2\n"}, [], 0),
        ("skipped prefix is ignored", {"docs/a.py": "# 2025-03-02 used to\n", "vendor/b.js": "// used to\n"}, [], 0),
        ("--min-date: old dates are data", {"src/a.py": "# fixture date 2019-05-05\n"}, [], 0, ["--min-date", "2024-01-01"]),
        # shapes that retell a fix, a removal or a rewrite
        ("css: a workaround that retells its fix", {"src/a.css": "/* Workaround for bug that was fixed in 1.4, kept for old browsers */\na { top: 0 }\n"}, [], 1),
        ("ts: fixed in a version", {"src/a.ts": "// fixed in 2.3.1\nconst x = 1;\n"}, [], 1),
        ("ts: removed in a version", {"src/a.ts": "// removed in v3.0 but still read for old files\n"}, [], 1),
        ("python: was fixed upstream", {"src/a.py": "# the leak was fixed upstream\n"}, [], 1),
        ("python: kept for old", {"src/a.py": "# kept for old callers\n"}, [], 1),
        ("go: narrative TODO", {"src/a.go": "// TODO: tidy this up after the rewrite\nfunc a() {}\n"}, [], 1),
        ("sh: leftover from the old parser", {"src/a.sh": "# leftover from the old parser\n"}, [], 1),
        ("rust: we switched", {"src/a.rs": "// we switched to a map because lookups were slow\nfn a() {}\n"}, [], 1),
        ("ts: originally", {"src/a.ts": "// originally written as a loop\n"}, [], 1),
        ("a present-tense reason with `kept for backward compatibility` passes", {"src/a.py": "# kept for backward compatibility with v1 callers\n"}, [], 0),
        ("a width that is fixed passes", {"src/a.css": "/* fixed at 3 columns; the width is fixed in the constructor */\na { top: 0 }\n"}, [], 0),
        ("`removed items` and a deprecation window pass", {"src/a.py": "# removed items are listed in the footer; deprecated flags warn\n"}, [], 0),
        # dates that are not ISO
        ("a month and year is a date", {"src/a.py": "# changed in March 2025\nx = 1\n"}, [], 1),
        ("a month, day and year is a date", {"src/a.ts": "// moved on Mar 3, 2025\n"}, [], 1),
        ("`since <Month>` is a date", {"src/a.py": "# the retry is off since March\n"}, [], 1),
        ("dd/mm/yyyy is a date", {"src/a.py": "# raised on 02/03/2025\n"}, [], 1),
        ("dd.mm.yyyy is a date", {"src/a.py": "# raised on 02.03.2025\n"}, [], 1),
        ("--min-date also places a month and year", {"src/a.py": "# fixture of March 2019\n"}, [], 0, ["--min-date", "2024-01-01"]),
        ("the verb `may` and a march of items are not dates", {"src/a.py": "# a caller may retry; the march of 3 items\n"}, [], 0),
        ("a path of numbers is not a date", {"src/a.py": "# see v1/2/2024x and a/10/11/2025\n"}, [], 0),
        # stories that a clause-opening or relative-pronoun form tells
        ("`Previously it returned nil` is a story", {"src/a.go": "// Previously it returned nil on timeout\n"}, [], 1),
        ("`it previously returned` is a story", {"src/a.go": "// it previously returned nil\n"}, [], 1),
        ("`which used to be a timer` is a story", {"src/a.ts": "// a frame callback, which used to be a timer\n"}, [], 1),
        ("`that used to live here` is a story", {"src/a.py": "# the value that used to live here\n"}, [], 1),
        ("`the previously returned page` is a state", {"src/a.py": "# the previously returned page stays visible\n"}, [], 0),
        ("`and previously selected rows` is a state", {"src/a.py": "# the focused and previously selected rows\n"}, [], 0),
        # a retired behaviour, and its conditional and length look-alikes
        ("`no longer used by` is history", {"src/a.rs": "// no longer used by the renderer\nfn a() {}\n"}, [], 1),
        ("`no longer retries on 429` is history", {"src/a.ts": "// no longer retries on 429\n"}, [], 1),
        ("`no longer than` is a length", {"src/a.py": "# a name no longer than 80 characters\n"}, [], 0),
        ("`once it is no longer referenced` is a condition", {"src/a.py": "# freed once it is no longer referenced\n"}, [], 0),
        # a passive verb about runtime data, not about the code
        ("a value changed by the caller is runtime", {"src/a.py": "# returns a value that was changed by the caller\n"}, [], 0),
        ("a field removed from the payload by the server is runtime", {"src/a.py": "# the field was removed from the payload by the server\n"}, [], 0),
        ("`if the item was removed` is a condition", {"src/a.py": "# if the item was removed, skip it\n"}, [], 0),
        ("`was replaced by a map` is history", {"src/a.py": "# the loop was replaced by a map\n"}, [], 1),
        # the lexer: what is a comment
        ("js: a regex literal does not open a block comment", {"src/a.js": 'const r = /\\/*$/;\nconst m = "used to retry";\n'}, [], 0),
        ("js: a regex after `return` and a division are told apart", {"src/a.js": "function f(a, b) { return /[/*]x/.test(a) || a / b / 2; }\n// used to\n"}, [], 1),
        ("python: a triple-quoted string that is not a docstring is a string", {"src/a.py": 'SQL = """\n-- used to be a view\n"""\n'}, [], 0),
        ("python: a module docstring is a comment", {"src/a.py": '"""Previously this was a script."""\nx = 1\n'}, [], 1),
        ("python: a class docstring is a comment", {"src/a.py": 'class A:\n    """Formerly a function."""\n'}, [], 1),
        ("python: a docstring after a multi-line signature is a comment", {"src/a.py": 'def f(\n    a,\n    b,\n):\n    """Formerly took one argument."""\n'}, [], 1),
        ("python: a string statement after code is a string", {"src/a.py": 'def f():\n    x = 1\n    """formerly x"""\n'}, [], 0),
        ("python: a triple-quoted default in a call is a string", {"src/a.py": 'run(\n    """\n# used to\n""",\n)\n'}, [], 0),
        ("shell: a heredoc body is text", {"src/a.sh": "cat <<EOF\n# used to be 3\nEOF\necho ok\n"}, [], 0),
        ("shell: a quoted, tab-stripped heredoc body is text", {"src/a.sh": "cat <<-'END'\n\t# used to be 3\n\tEND\n"}, [], 0),
        ("shell: a comment after a heredoc is a comment", {"src/a.sh": "cat <<EOF\nx\nEOF\n# used to be 3\n"}, [], 1),
        ("shell: `<<` in arithmetic opens no heredoc", {"src/a.sh": "x=$((1<<n))\n# used to be 3\n"}, [], 1),
        ("shell: a multi-line single-quoted string is text", {"src/a.sh": "echo 'a\n# used to be 3\nb'\n"}, [], 0),
        ("shell: a backslash-escaped quote opens no string", {"src/a.sh": "echo it\\'s fine\n# used to be 3\n"}, [], 1),
        ("java: a text block is a string", {"src/A.java": 'class A { String s = """\n  // used to\n  """; }\n'}, [], 0),
        ("kotlin: a text block is a string", {"src/a.kt": 'val s = """\n// used to\n"""\n'}, [], 0),
        # G3: the syntax is found by name and by `#!` line, and the table has more rows
        ("Dockerfile is scanned", {"Dockerfile": "FROM x\n# we now pin the digest\n"}, [], 1),
        ("Dockerfile.dev is scanned", {"Dockerfile.dev": "FROM x\n# used to be alpine\n"}, [], 1),
        ("Makefile is scanned", {"Makefile": "all:\n\t@echo hi\n# before the fix this was cc\n"}, [], 1),
        ("an extensionless sh script is scanned by its shebang", {"bin/run": "#!/bin/sh\n# used to take two arguments\n"}, [], 1),
        ("an extensionless env python script is scanned by its shebang", {"bin/tool": "#!/usr/bin/env python3\n# used to\n"}, [], 1),
        ("an extensionless file with no shebang is not scanned", {"bin/notes": "# used to\n"}, [], 0),
        ("php: `//`, `#` and block comments are comments", {"src/a.php": "<?php\n// used to\n"}, [], 1),
        ("php: `#[Attribute]` is not a comment", {"src/a.php": "<?php\n#[Route('/x')] // clean\n"}, [], 0),
        ("vue: an HTML comment is a comment", {"src/A.vue": "<template><!-- used to be a list --></template>\n"}, [], 1),
        # lessons of a large sweep: the shapes the first scanner missed, and the false positives that kept it trusted
        ("work stream: a numbered lane", {"src/a.py": "# found in lane 4\nx = 1\n"}, [], 1),
        ("work stream: an earlier session", {"src/a.py": "# an earlier session added this guard\n"}, [], 1),
        ("work stream: an agent found it", {"src/a.py": "# the agent found a race here\n"}, [], 1),
        ("a user session and rounding are not history", {"src/a.py": "# the user session expires; round the total up\n"}, [], 0),
        ("evidence: confirmed live", {"src/a.ts": "// confirmed live on the staging cluster\n"}, [], 1),
        ("evidence: measured before", {"src/a.ts": "// 40 ms, measured before the cache\n"}, [], 1),
        ("evidence: the report showed", {"src/a.ts": "// the profile showed a long task\n"}, [], 1),
        # lessons of late cold reads: rationale prose written fresh by helpers
        ("evidence: the audit measured", {"src/a.ts": "// the audit measured 40 ms per frame\n"}, [], 1),
        ("evidence: seen under load", {"src/a.ts": "// seen under load on a slow runner\n"}, [], 1),
        ("evidence: reproduced the identical failure", {"src/a.ts": "// reproduced the identical failure twice\n"}, [], 1),
        ("evidence: N/N clean runs", {"src/a.ts": "// 20/20 clean runs against 5/5 failures without it\n"}, [], 1),
        ("a reason about load is not history", {"src/a.ts": "// flaky under load, so the wait polls instead of sleeping\n"}, [], 0),
        ("a fraction that is not a run count passes", {"src/a.ts": "// shows 3/4 of the columns; runs 4 workers\n"}, [], 0),
        ("adoption: when the gate was adopted", {"src/a.sh": "# the sites known to exist when the gate was adopted\n"}, [], 1),
        ("a gate described in the present tense passes", {"src/a.sh": "# a site is listed when the gate is adopted by a project\n"}, [], 0),
        ("trial: 0.12 gave 4.48:1", {"src/a.css": "/* 0.12 gave 4.48:1, so the mix is 0.14 */\n"}, [], 1),
        ("a present fact about an input passes", {"src/a.css": "/* an input of 0.07 gives hue 221 */\n"}, [], 0),
        ("change stamp: an upper-case NARROWED", {"src/a.py": "# NARROWED: only the first match\n"}, [], 1),
        ("upper-case requirements pass", {"src/a.py": "# the caller MUST NOT retry; a NARROW range is allowed\n"}, [], 0),
        ("an id with a finding number passes", {"src/a.py": "# see row 84 finding 2\n"}, [], 0),
        ("a measurement stated as a fact is not history", {"src/a.ts": "// takes 40 ms on the reference machine\n"}, [], 0),
        ("contrast: as before", {"src/a.go": "// returns the same slice as before\nfunc a() {}\n"}, [], 1),
        ("contrast: it replaces the old", {"src/a.go": "// it replaces the old index\nfunc a() {}\n"}, [], 1),
        ("scratch path: /tmp file", {"src/a.sh": "# worklist in /tmp/sweep.txt\n"}, [], 1),
        ("scratch path: a scratch directory", {"src/a.py": "# see scratch/notes for the run\n"}, [], 1),
        ("a path is masked: no old name inside a file name", {"src/a.py": "# see docs/old-name.md and ./old-name/old-name.md\n"}, [], 0),
        ("a path is masked: no date inside a file name", {"src/a.py": "# the note is docs/archive/2025-03-02-notes.md\n"}, [], 0),
        ("a slash date is still a date", {"src/a.py": "# changed on 02/03/2025\n"}, [], 1),
        ("an absolute path in prose is still scanned for the rest of the line", {"src/a.py": "# used to write to /var/log/x.log\n"}, [], 1),
        ("svelte: a script comment is a comment", {"src/A.svelte": "<script>\n// we now fetch once\n</script>\n"}, [], 1),
    ]
    fails = _run_cases("history", "history", history)
    # the ratchet commands themselves
    rc, _ = _fixture("history", {"src/a.py": "# used to a\n# used to b\n"}, ["src/a.py\t1"], ["--update-baseline"])
    ok = rc == 1
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} --update-baseline refuses to grow (rc {rc}, want 1)")
    rc, _ = _fixture("history", {"src/a.py": "# used to a\n# used to b\n"}, ["src/a.py\t1"], ["--update-baseline", "--allow-grow"])
    ok = rc == 0
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} --update-baseline --allow-grow grows (rc {rc}, want 0)")
    rc, _ = _fixture("history", {"src/a.py": "x = 1\n"}, ["src/a.py\t1"], ["--update-baseline"])
    ok = rc == 0
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} --update-baseline locks a drop in (rc {rc}, want 0)")
    fails += _self_test_inventory_order()
    fails += _self_test_git_view()
    return fails


def _self_test_inventory_order():
    """`--inventory 2>&1 | tail -1` must print the summary: the worklist is flushed before the summary line."""
    fails = 0
    for kind, files in (("history", {"src/a.py": "# used to a\n# used to b\n"}),
                        ("refs", {"docs/backlog/001-x.md": "x", "src/a.py": "# backlog 98\n# backlog 99\n"})):
        with tempfile.TemporaryDirectory(prefix="comment-scan-") as d:
            for p, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, p)), exist_ok=True)
                with open(os.path.join(d, p), "w", encoding="utf-8") as fh:
                    fh.write(text)
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), kind, "--root", d, "--inventory"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        last = r.stdout.rstrip("\n").split("\n")[-1]
        ok = r.returncode == 0 and last.startswith(kind + ":")
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {kind} --inventory 2>&1: the last line is the summary ({last[:40]!r})")
    return fails


def _self_test_git_view():
    """Inside a git work tree the scan is git's view: an ignored tree is skipped whatever its name, an untracked file
    that is not ignored is scanned. Needs git; the case is skipped, and says so, without it."""
    if shutil.which("git") is None:
        print("  skip a git work tree is scanned as git sees it (git is not installed)")
        return 0
    fails = 0
    for name, extra, want in (("an ignored tree is skipped", {"gen/x.py": "# used to a\n"}, 0),
                              ("an untracked file that is not ignored is scanned", {"src/b.py": "# used to a\n"}, 1)):
        with tempfile.TemporaryDirectory(prefix="comment-scan-git-") as d:
            files = {".gitignore": "gen/\n", "src/a.py": "x = 1\n", **extra}
            for p, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, p)) or d, exist_ok=True)
                with open(os.path.join(d, p), "w", encoding="utf-8") as fh:
                    fh.write(text)
            if subprocess.run(["git", "init", "-q", d], capture_output=True).returncode != 0:
                print("  skip a git work tree is scanned as git sees it (git init failed)")
                return fails
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "history", "--root", d],
                               capture_output=True, text=True)
        ok = r.returncode == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} git: {name} (rc {r.returncode}, want {want})")
    return fails


def self_test_refs():
    fails = 0
    tracker = {"docs/backlog/012-cache.md": "x", "docs/backlog/done/007-old.md": "y", "scripts/real.sh": "# hi\n"}
    refs = [
        ("existing ids and path pass", {**tracker, "src/a.py": "# backlog 12 and backlog 7, 12; see scripts/real.sh:3\n"}, [], 0),
        ("dead id fails", {**tracker, "src/a.py": "# (backlog 99) explains it\n"}, [], 1),
        ("dead id in a list fails", {**tracker, "src/a.py": "# backlog 12, 98\n"}, [], 1),
        ("dead path fails", {**tracker, "src/a.py": "# see docs/research/nowhere.md for numbers\n"}, [], 1),
        ("dead path in css fails", {**tracker, "src/a.css": "/* see scripts/gone.sh */\n"}, [], 1),
        ("dead path in ts fails", {**tracker, "src/a.ts": "// see scripts/missing.spec.ts\n"}, [], 1),
        ("dead path in shell fails", {**tracker, "src/a.sh": "# see scripts/missing.sh\n"}, [], 1),
        ("ref-ok with a reason exempts", {**tracker, "src/a.py": "# see docs/old.md ref-ok: quoted from an upstream issue\n"}, [], 0),
        ("a date is not an id", {**tracker, "src/a.py": "# backlog 2026-10-05 is a date\n"}, [], 0),
        ("another word is not a citation", {**tracker, "src/a.py": "# item 99 of the list\n"}, [], 0),
        ("placeholder path is skipped", {**tracker, "src/a.py": "# docs/<name>/x.md and scripts/*.sh\n"}, [], 0),
        ("path in a string is not a comment", {**tracker, "src/a.py": "P = 'docs/gone/x.md'\n"}, [], 0),
        ("baselined dead path passes", {**tracker, "src/a.py": "# see docs/old.md\n"}, ["src/a.py\tpath\tdocs/old.md"], 0),
        ("stale baseline fails", {**tracker, "src/a.py": "# see scripts/real.sh\n"}, ["src/a.py\tpath\tdocs/old.md"], 1),
        ("--word: a project's own word, written #N", {**tracker, "src/a.py": "# ticket #99\n"}, [], 1, ["--word", "ticket"]),
        ("--word issue: prose is not a citation", {**tracker, "src/a.py": "# the second issue 5 times larger; see issue 3\n"}, [], 0, ["--word", "issue"]),
        ("--word issue: a quantity near the highest id is not a citation", {**tracker, "src/a.py": "# issue 30 of them\n"}, [], 0, ["--word", "issue"]),
        ("--word issue: #N is explicit", {**tracker, "src/a.py": "# see issue #3 for the numbers\n"}, [], 1, ["--word", "issue"]),
        ("--word issue: the block names the tracker", {**tracker, "src/a.py": "# the backlog tracks it:\n# see issue 3\n"}, [], 1, ["--word", "issue"]),
        ("--word issue: the tracker named in another block does not count", {**tracker, "src/a.py": "# the backlog\nx = 1\n# see issue 3\n"}, [], 0, ["--word", "issue"]),
        ("--word issue: a three-digit id just above the highest is checked", {**tracker, "docs/backlog/100-big.md": "z", "src/a.py": "# fixed by issue 112\n"}, [], 1, ["--word", "issue"]),
        ("--word issue: a three-digit number far above is data", {**tracker, "docs/backlog/100-big.md": "z", "src/a.py": "# a ceiling of issue 450 or so\n"}, [], 0, ["--word", "issue"]),
        ("--word issue: a real id passes", {**tracker, "src/a.py": "# issue #12 and issue #7\n"}, [], 0, ["--word", "issue"]),
        ("missing tracker directory is bad usage", {"src/a.py": "# backlog 1\n"}, [], 2),
        ("a leading ./ is checked: dead", {**tracker, "src/a.sh": "# see ./scripts/gone.sh\n"}, [], 1),
        ("a leading ./ is checked: alive", {**tracker, "src/a.sh": "# see ./scripts/real.sh\n"}, [], 0),
        ("`../x` is not a repository path", {**tracker, "src/a.sh": "# see ../scripts/gone.sh\n"}, [], 0),
        ("a dead root-level file is checked", {**tracker, "src/a.py": "# the list lives in BACKLOG.md\n"}, [], 1),
        ("a live root-level file passes", {**tracker, "README.md": "r\n", "src/a.py": "# see README.md.\n"}, [], 0),
        ("a bare upper-case name found elsewhere in the tree passes", {**tracker, "src/NOTES.md": "n\n", "src/a.py": "# see NOTES.md\n"}, [], 0),
        ("`./file` names the root: dead", {**tracker, "src/a.py": "# keep in sync with ./Cargo.toml\n"}, [], 1),
        ("`./file` names the root: alive", {**tracker, "Cargo.toml": "c\n", "src/a.py": "# keep in sync with ./Cargo.toml\n"}, [], 0),
        ("a bare lower-case name is an example, not a citation", {**tracker, "src/a.py": "# e.g. Cargo.toml or utils.py\n"}, [], 0),
        ("`backlog 12 and 3 others` is a count, not a list of ids", {**tracker, "src/a.py": "# backlog 12 and 3 others\n"}, [], 0),
        ("a list still stops at a real dead id", {**tracker, "src/a.py": "# backlog 12 and 98, 3 others\n"}, [], 1),
        ("an ignored directory's files are not scanned (name)", {**tracker, "venv/lib/x.py": "# backlog 99\n"}, [], 0),
    ]
    fails += _run_cases("refs", "refs", refs)
    return fails


# --------------------------------------------------------------------------- main
def usage(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def main(argv):
    if "--self-test" in argv[1:]:
        rest = [a for a in argv[1:] if a != "--self-test"]
        if rest not in ([], ["history"], ["refs"]):
            usage("usage: comment_scan.py --self-test [history | refs]")
        return self_test(rest[0] if rest else None)
    if len(argv) < 2 or argv[1] not in ("history", "refs"):
        usage("usage: comment_scan.py <history|refs> [--root DIR] [--baseline FILE] [--skip PREFIX] [--inventory|"
              "--update-baseline [--allow-grow]] [FILE...]   |   comment_scan.py --self-test")
    kind = argv[1]
    opts = {"inventory": False, "update": False, "allow_grow": False, "files": [], "baseline": None,
            "skip": list(SKIP_PREFIXES), "min_date": "0000-01-01", "tracker": "docs/backlog", "word": "backlog"}
    root = os.getcwd()
    it = iter(argv[2:])
    try:
        for a in it:
            if a == "--inventory":
                opts["inventory"] = True
            elif a == "--update-baseline":
                opts["update"] = True
            elif a == "--allow-grow":
                opts["allow_grow"] = True
            elif a == "--root":
                root = next(it)
            elif a == "--baseline":
                opts["baseline"] = next(it)
            elif a == "--skip":
                opts["skip"].append(next(it))
            elif a == "--min-date":
                opts["min_date"] = next(it)
            elif a == "--tracker":
                opts["tracker"] = next(it)
            elif a == "--word":
                opts["word"] = next(it)
            elif a.startswith("-"):
                usage(f"comment_scan: unknown option {a}")
            else:
                opts["files"].append(a)
    except StopIteration:
        usage("comment_scan: an option is missing its value")
    return (cmd_history if kind == "history" else cmd_refs)(os.path.abspath(root), opts)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
