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
    --min-date DATE     history only: ISO dates before DATE are data, not history (default: every date counts)
    --tracker DIR       refs only: the tracker directory, one file per item, NNN-slug.md, finished ones in DIR/done/
                        (default docs/backlog)
    --word WORD         refs only: the word that introduces a cited id, as in "backlog N" (default backlog). A bare
                        "<word> N" is a citation only when it is unmistakable (see "Citations" below)
    --inventory         list every counted line (the worklist for a cleanup sweep); exit 0
    --update-baseline   rewrite the baseline from the current tree; refuses to let any count grow
                        unless --allow-grow is also given (say why in the commit message)
    FILE...             scan only these files (root-relative)

Exit status: 0 clean, 1 violation, 2 bad usage.

What is a comment is decided in ONE place, the SYNTAX table below, keyed by file extension. Add a language by
adding a row. A comment marker inside a string literal is not a comment. Python docstrings count as comments.
Known gaps (they only make the check more lenient): code that lives inside a string of another language, and
multi-line quoted strings in shell.

Citations. The tracker word is often an ordinary English word ("issue", "ticket", "item"), and "the second issue 5
times larger" is not a citation. So `<word> N` counts as one when (a) it is written `<word> #N`, or (b) the comment
block also names the tracker (the tracker directory's name, e.g. "backlog", or the word "tracker"), or (c) N has three
or more digits and is at most 25 above the highest existing id (it looks like an id) and does not read as a quantity
("<word> N of/times/per ..."). With the default word ("backlog") the word itself names the tracker, so every
`backlog N` counts. A citation that is none of these is not checked: write it `<word> #N`.

What the history check knows is a list of common shapes (dates, hashes, the PHRASES below). Green means "no common
shape found", not "clean": a comment can retell history in words no pattern matches.

Deliberate exceptions carry a marker WITH a reason on the line itself:
    history-ok: <reason>     the line is history on purpose (a quoted upstream changelog, a date the code needs)
    ref-ok: <reason>         the cited id or path is missing on purpose
A marker without a reason exempts nothing.
"""
import os
import re
import subprocess
import sys
import tempfile

# --------------------------------------------------------------------------- configuration
# Comment syntax by extension. Keys: line (markers), block ((start, end) pairs), nested (block comments nest),
# strings ((delimiter, may_span_lines)), docstrings (delimiters read as comments), hash (a line marker must follow
# whitespace or one of ;|&( so `$#` and `${#x}` are not comments), chars (C-style 'x' character literals).
C = dict(line=("//",), block=(("/*", "*/"),), strings=(('"', False),), chars=True)
HASH = dict(line=("#",), strings=(('"', False), ("'", False)), hash=True)
SYNTAX = {
    ".py": dict(line=("#",), docstrings=('"""', "'''"), strings=(('"', False), ("'", False))),
    ".sh": HASH, ".bash": HASH, ".zsh": HASH,
    ".rb": HASH, ".yml": HASH, ".yaml": HASH, ".toml": HASH,
    ".js": dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False),
    ".mjs": dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False),
    ".cjs": dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False),
    ".jsx": dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False),
    ".ts": dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False),
    ".tsx": dict(C, strings=(('"', False), ("'", False), ("`", True)), chars=False),
    ".rs": dict(C, nested=True, rust=True),
    ".go": dict(C, strings=(('"', False), ("`", True))),
    ".java": C, ".kt": C, ".swift": C, ".cs": C,
    ".c": C, ".h": C, ".cpp": C, ".hpp": C,
    ".css": dict(block=(("/*", "*/"),), strings=(('"', False), ("'", False))),
    ".scss": dict(line=("//",), block=(("/*", "*/"),), strings=(('"', False), ("'", False))),
    ".sql": dict(line=("--",), block=(("/*", "*/"),), strings=(("'", True),)),
    ".lua": dict(line=("--",), block=(("--[[", "]]"),), strings=(('"', False), ("'", False))),
    ".html": dict(block=(("<!--", "-->"),)),
}
# Paths (root-relative prefixes) that are never scanned: history is allowed in docs, baselines are data,
# vendored and generated trees are not ours.
SKIP_PREFIXES = ("docs/", "scripts/baselines/", "node_modules/", "vendor/", "target/", "dist/", "build/", "third_party/")
SKIP_DIRNAMES = {".git", "node_modules", "__pycache__", ".venv", "target", "dist", "build"}
SKIP_SUFFIXES = (".min.js", ".lock")
# Upstream revisions pinned on purpose are provenance, not history; list their prefixes here. The form
# `<path> @ <sha>` is always provenance.
PINNED_REVS = ()

HISTORY_BASELINE = "scripts/baselines/history-comments.tsv"
REFS_BASELINE = "scripts/baselines/comment-refs.tsv"


# --------------------------------------------------------------------------- files
def tracked_files(root, skip):
    """Root-relative paths of every file with a known comment syntax, sorted."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRNAMES)
        for f in filenames:
            p = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
            if p.startswith(tuple(skip)) or p.endswith(SKIP_SUFFIXES):
                continue
            if os.path.splitext(p)[1] in SYNTAX:
                out.append(p)
    return sorted(out)


# --------------------------------------------------------------------------- comment extraction
def _emit_block(out, start_line, raw, strip_star):
    for k, ln in enumerate(raw.split("\n")):
        out.append((start_line + k, re.sub(r"^\s*\*+ ?", "", ln) if strip_star else ln))


def extract(text, syn):
    """[(line_number, body)] for every comment line; a block comment gives one entry per physical line."""
    out = []
    i, n, line = 0, len(text), 1
    blocks, lines_, strings = syn.get("block", ()), syn.get("line", ()), syn.get("strings", ())
    docs = syn.get("docstrings", ())
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        hit = next(((s, e) for s, e in blocks if text.startswith(s, i)), None)
        if hit:
            s, e = hit
            j, depth = i + len(s), 1
            while j < n and depth:
                if syn.get("nested") and text.startswith(s, j):
                    depth += 1
                    j += len(s)
                elif text.startswith(e, j):
                    depth -= 1
                    j += len(e)
                else:
                    j += 1
            end = j - len(e) if depth == 0 else j
            _emit_block(out, line, text[i + len(s):max(i + len(s), end)], True)
            line += text.count("\n", i, j)
            i = j
            continue
        d = next((d for d in docs if text.startswith(d, i)), None)
        if d:
            j = text.find(d, i + len(d))
            j = n if j < 0 else j + len(d)
            _emit_block(out, line, text[i + len(d):max(i + len(d), j - len(d))], False)
            line += text.count("\n", i, j)
            i = j
            continue
        m = next((m for m in lines_ if text.startswith(m, i)), None)
        if m and (not syn.get("hash") or i == 0 or text[i - 1] in " \t;|&(\n"):
            j = text.find("\n", i)
            j = n if j < 0 else j
            body = text[i + len(m):j]
            if m == "#" and i == 0 and body.startswith("!"):
                pass  # a shebang is not a comment
            else:
                out.append((line, body[1:] if m == "//" and body[:1] in ("/", "!") else body))
            i = j
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
        s = next(((d, multi) for d, multi in strings if text.startswith(d, i)), None)
        if s:
            d, multi = s
            j = i + len(d)
            while j < n and not text.startswith(d, j):
                if text[j] == "\n" and not multi:
                    break
                j += 2 if text[j] == "\\" else 1
            stop = j if (j >= n or text[j] == "\n") and not text.startswith(d, j) else j + len(d)
            line += text.count("\n", i, min(stop, n))
            i = stop
            continue
        i += 1
    return out


def comments_of(root, path):
    with open(os.path.join(root, path), encoding="utf-8", errors="replace") as fh:
        return extract(fh.read(), SYNTAX[os.path.splitext(path)[1]])


# --------------------------------------------------------------------------- history detection
DATE = re.compile(r"(?<![\w.-])(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?![\w-])")
HEX = re.compile(r"(?<![\w#.\-/$@])(?:[0-9a-f]{7,40})(?![\w\-/])")
PHRASES = [
    (re.compile(r"\bbefore the (?:fix|change|rewrite|refactor|migration)\b", re.I), "before the fix"),
    (re.compile(r"\bformerly\b", re.I), "formerly"),
    (re.compile(r"\bold (?:behaviou?r|implementation|approach|name)\b", re.I), "old behaviour"),
    (re.compile(r"\b(?:was|were|got|has been|have been) (?:changed|renamed|rewritten|replaced|removed|dropped)\b", re.I),
     "was changed"),
    (re.compile(r"\bwas\s+\S+(?:\s+\S+){0,2},\s*(?:and\s+)?now\b", re.I), "was X, now Y"),
    (re.compile(r"\bwe (?:now|used to|no longer|previously)\b", re.I), "we now"),
    (re.compile(r"\bnow (?:uses|reads|writes|goes|lives|comes|calls|returns|lets|owns|runs|derives)\b", re.I), "now uses"),
    (re.compile(r"\bno longer (?:uses|reads|writes|carries|ships|sets|renders|needs|does|do|owns|"
                r"holds|lives|calls|emits|paints|draws|returns|takes)", re.I), "no longer"),
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
]
USED_TO = re.compile(r"(?:\b(\w+)\s+)?\bused to\b", re.I)
# "is used to X", "can be used to X": the instrument sense, not history.
PASSIVE_PREV = {"is", "are", "be", "been", "being", "was", "were", "get", "gets", "got", "it's", "also", "only",
                "then", "often", "just", "can", "could", "may", "might", "must", "should", "will", "would",
                "not", "if", "when", "that", "which", "and", "or", "both", "either", "so", "thus", "than"}
PREVIOUSLY = re.compile(r"\bpreviously\b(?!-)(?:\s+(\w+))?", re.I)
# A participle after the word describes a state of the element, not a story; a comma after the word, or a
# preceding auxiliary verb, makes it a story.
PREVIOUSLY_STATE_OK = re.compile(r"(?:ed|en|n|t|d)$|^(?:set|read|run|put|shown|sent|hidden|open|active|visible)$")
MARK_HISTORY = re.compile(r"history-ok:\s*\S")
MARK_REF = re.compile(r"ref-ok:\s*\S")


def history_reason(body, min_date="0000-01-01"):
    """Why a comment line retells history, or None. One reason per line is enough: the unit is the line."""
    if MARK_HISTORY.search(body):
        return None
    for m in DATE.finditer(body):
        if "-".join(m.groups()) >= min_date:
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
    for m in USED_TO.finditer(body):
        if (m.group(1) or "").lower() not in PASSIVE_PREV:
            return "used to"
    for m in PREVIOUSLY.finditer(body):
        if re.search(r"\b(?:whatever|what|that|which)\s+(?:was|were|is)\s+$", body[:m.start()], re.I):
            continue
        nxt = (m.group(1) or "").lower()
        if not nxt or not PREVIOUSLY_STATE_OK.search(nxt):
            return "previously"
        if re.search(r"\b(?:was|were|had|did) previously\b|previously,", body, re.I):
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


def make_patterns(root, word):
    tops = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and d not in SKIP_DIRNAMES)
    path_rx = re.compile(r"(?<![\w./@~-])(?:%s)/[A-Za-z0-9_.\-/\[\]*<>{}$…]*" % "|".join(map(re.escape, tops))) \
        if tops else None
    num = r"#?(\d{1,6})(?!\d|-\d\d-)[a-z]?"
    cite_rx = re.compile(r"\b%s(?:\s+(?:item|row|id))?\s+%s((?:\s*(?:,|/|&|and|-|to)\s*%s)*)" % (re.escape(word), num, num), re.I)
    return path_rx, cite_rx


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


def refs_in(blocks, ids, path_rx, cite_rx, tracker_rx):
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
    return bad


def scan_refs(root, files, tracker, word):
    ids = tracker_ids(os.path.join(root, tracker))
    path_rx, cite_rx = make_patterns(root, word)
    names = {os.path.basename(tracker.rstrip("/")).lower(), "tracker"}
    tracker_rx = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, sorted(names))), re.I)
    out = {}
    for p in files:
        res = []
        for ln, kind, ref in refs_in(comments_of(root, p), ids, path_rx, cite_rx, tracker_rx):
            if kind == "path":
                ref = re.sub(r":\d+(?:-\d+)?$", "", ref)
                if os.path.exists(os.path.join(root, ref)) or os.path.exists(os.path.join(root, ref.rstrip("/"))):
                    continue
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
        ("typescript: commit hash", {"src/a.ts": "// fixed in 98e7ca1b\nconst x = 1;\n"}, [], 1),
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
