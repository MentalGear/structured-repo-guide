# Example scripts for the documentation half

**What this is for.** Small, runnable scripts that enforce the rules in [`../../documentation/`](../../documentation/README.md),
and a sample tree to run them against. Copy the scripts into your repository's `scripts/` directory, or read them as
the reference implementation and port the idea. They need only `sh` and Python 3 (standard library). No network, no
install, no git.

## What is here

| File | What it does | Guide |
|---|---|---|
| `comment_scan.py` | One comment extractor behind two checks: `history` (a per-file ratchet on comment lines that retell history) and `refs` (every cited tracker id and repository path resolves). | [history in comments](../../documentation/history-in-comments.md), [ratchets](../../documentation/ratchets.md) |
| `check-history-comments.sh` | Wrapper: `comment_scan.py history`. | |
| `check-comment-refs.sh` | Wrapper: `comment_scan.py refs`. | |
| `check_doc_links.py`, `check-doc-links.sh` | Every relative Markdown link, and every `#anchor`, resolves. | [layout](../../documentation/layout.md#keeping-cited-paths-and-headings-stable) |
| `docs_catalogue.py`, `check-docs-catalogue.sh` | Generates a catalogue page from the header of each check script; `--check` is the freshness check. | [generated docs](../../documentation/generated-docs.md) |
| `backlog_index.py`, `check-backlog-index.sh` | A tracker of one file per item with generated open and done indexes; `--check` enforces front matter, ids, folders and freshness. | [tracker as files](../../documentation/tracker-as-files.md) |
| `run-all.sh` | Runs every self-test, then every check on the sample. Prints `ALL GREEN` and exits 0 when all hold. | |
| `sample/` | A tiny repository: source in five languages, a tracker, a status page, a generated catalogue, baselines. | |

Every Python script has the same interface: a usage header (read it with `head -40 <script>`), `--root DIR` (default: the
current directory), exit 0 clean, 1 violation, 2 bad usage, and `--self-test`.

## Run them

From the root of this guide repository:

```sh
sh examples/documentation/run-all.sh                       # everything: self-tests, then the sample
python3 -I examples/documentation/comment_scan.py --self-test
python3 -I examples/documentation/check_doc_links.py --self-test
python3 -I examples/documentation/docs_catalogue.py --self-test
python3 -I examples/documentation/backlog_index.py --self-test
```

Each self-test builds throwaway trees in a temporary directory, plants a violation per case, and requires the check to
go red (and a clean tree to stay green). A check that has never been seen to fail proves nothing.

Against the sample, one check at a time:

```sh
S=examples/documentation/sample
sh examples/documentation/check-history-comments.sh --root $S
sh examples/documentation/check-comment-refs.sh     --root $S
sh examples/documentation/check-doc-links.sh        --root $S
sh examples/documentation/check-docs-catalogue.sh   --root $S
sh examples/documentation/check-backlog-index.sh    --root $S
```

## See a check go red

Copy the sample so the committed one stays clean, then plant a violation in the copy:

```sh
cp -R examples/documentation/sample /tmp/sample && cd /tmp/sample
E=/path/to/structured-repo-guide/examples/documentation

echo "# used to be 3px, changed on 2025-03-02" >> src/cache.py
sh $E/check-history-comments.sh           # red: a history line was added to a file the baseline allows none in

echo "# see docs/nowhere.md and backlog 77" >> src/cache.py
sh $E/check-comment-refs.sh               # red: a dead path and a dead id

echo "see [x](missing.md)" >> docs/README.md
sh $E/check-doc-links.sh                  # red: a broken link

echo stray >> docs/checks.md
sh $E/check-docs-catalogue.sh             # red: the generated page differs from its sources
```

Then fix and lock in:

```sh
python3 -I $E/docs_catalogue.py --write                       # regenerate the catalogue
python3 -I $E/backlog_index.py --write                        # regenerate the tracker indexes
sh $E/check-history-comments.sh --inventory                   # list every history line (the sweep worklist)
sh $E/check-history-comments.sh --update-baseline             # lock in a drop; refuses to grow
```

## What the sample shows

- `sample/src/` has a comment in Python, TypeScript, Rust, shell and CSS. All state a reason and cite an item by id
  (`backlog 3`), except `legacy.py`, which holds old debt. `cache.py` carries one `history-ok:` marker with its reason.
- `sample/scripts/baselines/` holds the two baselines for that debt: two history lines and two dead references, all in
  `legacy.py`. They can only shrink.
- `sample/docs/backlog/` is the tracker: two open items, one done. `docs/backlog.md` and `docs/backlog-done.md` are
  generated from them.
- `sample/scripts/check-*.sh` are three small checks with headers. `docs/checks.md` is generated from those headers.
- `sample/AGENTS.md` is the entry file: it only points. `docs/README.md` is the map, `docs/STATUS.md` the status page,
  `docs/decisions.md` the decisions index.

## Adopt the scripts

```sh
cp examples/documentation/*.py examples/documentation/check-*.sh /path/to/your/repo/scripts/
cd /path/to/your/repo
sh scripts/check-history-comments.sh --update-baseline     # freeze the debt: writes scripts/baselines/history-comments.tsv
sh scripts/check-comment-refs.sh --update-baseline         # needs docs/backlog/ (see --tracker, --word)
python3 -I scripts/backlog_index.py --write
python3 -I scripts/docs_catalogue.py --write
sh scripts/check-doc-links.sh --skip templates
```

Add the five `check-*.sh` wrappers to your one entry point. Their defaults assume: tracker in `docs/backlog/`, indexes
`docs/backlog.md` and `docs/backlog-done.md`, catalogue `docs/checks.md` from `scripts/check-*`, baselines in
`scripts/baselines/`. Every default is a flag.

## Configure

| To change | Edit |
|---|---|
| The languages whose comments are scanned, and their comment syntax | the `SYNTAX` table in `comment_scan.py` (one row per extension) |
| Paths that are never scanned | `SKIP_PREFIXES`, `SKIP_DIRNAMES`, `SKIP_SUFFIXES` in `comment_scan.py`, or `--skip PREFIX` |
| The phrases that count as history | `PHRASES` in `comment_scan.py`; add the sentence that motivated it to `self_test()` |
| Pinned upstream revisions that are provenance, not history | `PINNED_REVS` in `comment_scan.py` |
| Dates that are test data, not history | `--min-date YYYY-MM-DD` |
| The word that introduces a cited id (`backlog`, `issue`, `ticket`) | `--word WORD` |
| Which languages' script headers are read for the catalogue | `HEADER_STYLES` in `docs_catalogue.py` |
| Required item fields, sections and statuses | `REQUIRED`, `SECTIONS`, `OPEN_STATUSES`, `CLOSED_STATUSES` in `backlog_index.py` |

## Known limits

- The comment extractor is a small scanner, not a parser. It knows strings, line and block comments, nested block
  comments (Rust), Rust raw strings and character literals. It does not know shell heredocs or multi-line shell strings,
  or code that lives inside a string of another language. These gaps only make the check more lenient.
- The history check reads lines. It flags phrases and dates, and cannot judge whether a present-tense reason is true.
- The path check recognises a path by its first segment: a top-level directory of the repository. A citation of a path
  under any other prefix is not checked.
- Markdown is not scanned for history. Prose docs are kept current by the rules in
  [`principles.md`](../../documentation/principles.md).
