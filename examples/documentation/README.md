# Example scripts for the documentation half

**What this is for.** Small, runnable scripts that enforce the rules in [`../../documentation/`](../../documentation/README.md),
and a sample tree to run them against. Copy the scripts into your repository's `scripts/` directory, or read them as
the reference implementation and port the idea. They need only `sh`, `awk` and Python 3.8 or newer (standard library). No
network, no install. `git` is optional: inside a git work tree the comment scans take the file list from git (so an ignored
virtualenv or build tree is never read), and elsewhere they walk the tree. The runner they plug into is in [`../gate-runner/`](../gate-runner/README.md).

## What is here

| File | What it does | Guide |
|---|---|---|
| `comment_scan.py` | One comment extractor behind two checks: `history` (a per-file ratchet on comment lines that retell history) and `refs` (every cited tracker id and repository path resolves). The comment syntax is found by file extension, then by file name (`Makefile`, `Dockerfile`), then by the `#!` line of an extensionless script; add a row to its `SYNTAX`, `FILENAMES` or `SHEBANGS` table for another language. It reads comments only: not the comments inside string literals or the `<script>`/`<style>` bodies of HTML, and not names (test titles, test function and file names), which want their own zero-tolerance gate ([text that is not a comment](../../documentation/history-in-comments.md#text-that-is-not-a-comment)). | [history in comments](../../documentation/history-in-comments.md), [ratchets](../../documentation/ratchets.md) |
| `check-history-comments.sh` | Wrapper: `comment_scan.py history`. | |
| `check-comment-refs.sh` | Wrapper: `comment_scan.py refs`. | |
| `check_doc_links.py`, `check-doc-links.sh` | Every relative Markdown link, and every `#anchor`, resolves. | [layout](../../documentation/layout.md#keeping-cited-paths-and-headings-stable) |
| `docs_catalogue.py`, `check-docs-catalogue.sh` | Generates a catalogue page from the runner's gate list and the header of each check script (or from a glob of scripts); `--check` is the freshness check. | [generated docs](../../documentation/generated-docs.md) |
| `backlog_index.py`, `check-backlog-index.sh` | A tracker of one file per item with generated open and done indexes; `--check` enforces front matter, ids, folders and freshness. | [tracker as files](../../documentation/tracker-as-files.md) |
| `doc_hygiene.py`, `check-placeholders.sh`, `check-doc-map.sh`, `check-dated-headings.sh` | Three small checks over the Markdown docs: no placeholder or template comment left in a copied template (the template comment is looked for in every Markdown file, so a copied guide or item cannot keep its instructions unseen); every doc under `docs/` reachable from the map; a ratchet on dated headings and dated lead-ins in living docs. | [layout](../../documentation/layout.md#the-map-file), [cleanup playbook](../../documentation/cleanup-playbook.md) |
| `run-all.sh` | Runs every self-test, then every check on the sample, then the sample's own runner. Prints `ALL GREEN` and exits 0 when all hold. | |
| `sample/` | A tiny repository: source in five languages, a tracker, a status page, a generated catalogue, an archive, baselines, and a copy of the gate runner with its list. | |

Every Python script has the same interface: a usage header (read it with `head -40 <script>`), `--root DIR` (default: the
current directory), exit 0 clean, 1 violation, 2 bad usage, and `--self-test`. Every `check-*.sh` wrapper runs its tool's
`--self-test` quietly after a normal check, so a check that can no longer go red turns the runner red
([`ratchets.md`](../../documentation/ratchets.md#the-check-proves-it-can-fail)); `--inventory` and `--update-baseline` skip it.

## Run them

From the root of this guide repository:

```sh
sh examples/documentation/run-all.sh                       # everything: self-tests, then the sample
python3 -I examples/documentation/comment_scan.py --self-test
python3 -I examples/documentation/check_doc_links.py --self-test
python3 -I examples/documentation/docs_catalogue.py --self-test
python3 -I examples/documentation/backlog_index.py --self-test
python3 -I examples/documentation/doc_hygiene.py --self-test
sh examples/gate-runner/run-gates.sh --self-test
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
sh examples/documentation/check-placeholders.sh     --root $S
sh examples/documentation/check-doc-map.sh          --root $S
sh examples/documentation/check-dated-headings.sh   --root $S
```

## See a check go red

Copy the sample so the committed one stays clean, then plant a violation in the copy:

```sh
GUIDE=/path/to/structured-repo-guide
E=$GUIDE/examples/documentation
cp -R $E/sample /tmp/sample && cd /tmp/sample

echo "# used to be 3px, changed on 2025-03-02" >> src/cache.py
sh $E/check-history-comments.sh           # red: a history line was added to a file the baseline allows none in

echo "# see docs/nowhere.md and backlog 77" >> src/cache.py
sh $E/check-comment-refs.sh               # red: a dead path and a dead id

echo "see [x](missing.md)" >> docs/README.md
sh $E/check-doc-links.sh                  # red: a broken link

echo stray >> docs/checks.md
sh $E/check-docs-catalogue.sh             # red: the generated page differs from its sources

echo "Next: <fill in>" >> docs/STATUS.md
sh $E/check-placeholders.sh               # red: a placeholder left in a status page

echo "# Orphan" > docs/orphan.md
sh $E/check-doc-map.sh                    # red: a doc that no map row reaches

printf '\n## Round 4 (2025-03-02)\n' >> docs/STATUS.md
sh $E/check-dated-headings.sh             # red: a dated heading in a living doc

printf 'a\tb\n' > src/tabbed.txt
sh scripts/run-gates.sh                   # exit 1; RED names the gate (check-no-tabs); the runner is the one command
```

Then fix and lock in:

```sh
python3 -I $E/docs_catalogue.py --write                       # regenerate the catalogue (from scripts/gates.list)
python3 -I $E/backlog_index.py --write                        # regenerate the tracker indexes
sh $E/check-history-comments.sh --inventory                   # list every history line (the sweep worklist)
sh $E/check-history-comments.sh --update-baseline             # lock in a drop; refuses to grow
```

## What the sample shows

- `sample/src/` has a comment in Python, TypeScript, Rust, shell and CSS. All state a reason and cite an item by id
  (`backlog 3`), except `legacy.py`, which holds old debt. `cache.py` carries one `history-ok:` marker with its reason.
- `sample/scripts/baselines/` holds the two baselines for that debt: two history lines and two dead references, all in
  `legacy.py`. They can only shrink. (The dated-headings baseline does not exist: the sample has none, so the check is absolute.)
- `sample/docs/backlog/` is the tracker: two open items, one done. `docs/backlog.md` and `docs/backlog-done.md` are
  generated from them.
- `sample/scripts/run-gates.sh` and `gates.list` are the runner and its list: three check scripts and one plain command, in
  groups. `docs/checks.md` is generated from the list and the script headers.
- `sample/docs/archive/` is an archive: an index (`README.md`) with one row per file and a "Historical" banner, and one
  archived page with the same banner. The map links the index, which is enough for the doc-map check.
- `sample/AGENTS.md` is the entry file: it only points. `docs/README.md` is the map, `docs/STATUS.md` the status page,
  `docs/decisions.md` the decisions index. They are examples: copy and adapt, do not keep their words.

## Adopt the scripts

The five-minute path is in [`../../documentation/README.md`](../../documentation/README.md#adopt-it-in-five-minutes). In short,
from your repository, with `GUIDE` set to the path of this guide:

```sh
cp $GUIDE/examples/documentation/*.py $GUIDE/examples/documentation/check-*.sh scripts/
cp $GUIDE/examples/gate-runner/run-gates.sh $GUIDE/examples/gate-runner/gates.list scripts/
sh scripts/check-history-comments.sh --update-baseline     # freeze the debt: writes scripts/baselines/history-comments.tsv
sh scripts/check-comment-refs.sh --update-baseline         # needs docs/backlog/ (see --tracker, --word)
python3 -I scripts/backlog_index.py --write
python3 -I scripts/docs_catalogue.py --write
sh scripts/check-doc-links.sh
sh scripts/run-gates.sh
```

The eight `check-*.sh` wrappers are listed in `gates.list`; keep them there. Their defaults assume: tracker in
`docs/backlog/`, indexes `docs/backlog.md` and `docs/backlog-done.md`, catalogue `docs/checks.md` from `scripts/gates.list`
(or from `scripts/check-*.sh` when you keep no list), baselines in `scripts/baselines/`. Every default is a flag.

## Configure

| To change | Edit |
|---|---|
| The languages whose comments are scanned, and their comment syntax | the `SYNTAX` table in `comment_scan.py` (one row per extension) |
| Paths that are never scanned | `SKIP_PREFIXES`, `SKIP_DIRNAMES`, `SKIP_SUFFIXES` in `comment_scan.py`, or `--skip PREFIX` |
| The phrases that count as history | `PHRASES` in `comment_scan.py` (work-stream words, evidence narration, contrasts without "before"; scratch paths are `SCRATCH`, and paths are masked by `PATH_TOKEN`); add the sentence that motivated it to `self_test_history()` ([teaching the scanner](../../documentation/history-in-comments.md#teaching-the-scanner-a-new-shape)) |
| Pinned upstream revisions that are provenance, not history | `PINNED_REVS` in `comment_scan.py` |
| Dates that are test data, not history | `--min-date YYYY-MM-DD` |
| The word that introduces a cited id (`backlog`, `issue`, `ticket`); a bare `issue 12` counts only when unmistakable, so write `issue #12` | `--word WORD` ([citations](../../documentation/history-in-comments.md#citing-an-item-what-counts-as-a-citation)) |
| A second tracker (defect records) | a second run: `comment_scan.py refs --tracker docs/issues --word issue --baseline scripts/baselines/issue-refs.tsv` |
| The documents the placeholder check reads | `DEFAULT_PLACEHOLDER_FILES` in `doc_hygiene.py`, or name them: `check-placeholders.sh CONTRIBUTING.md docs/STATUS.md` |
| The history homes the dated-heading check skips | `HISTORY_HOMES` in `doc_hygiene.py`, or `--skip PREFIX` |
| Which languages' script headers are read for the catalogue | `HEADER_STYLES` in `docs_catalogue.py` |
| Required item fields, sections and statuses | `REQUIRED`, `SECTIONS`, `OPEN_STATUSES`, `CLOSED_STATUSES` in `backlog_index.py` |

## Known limits

- The comment extractor is a small scanner, not a parser. It knows strings, line and block comments, nested block
  comments (Rust), Rust raw strings and character literals. It does not know shell heredocs or multi-line shell strings,
  or code that lives inside a string of another language. These gaps only make the check more lenient.
- The history check reads lines. It flags phrases and dates, and cannot judge whether a present-tense reason is true.
  **Green means "no common shape found", not "clean"**: a comment can retell history in words no pattern matches.
- The path check recognises a path by its first segment: a top-level directory of the repository. A citation of a path
  under any other prefix is not checked.
- Markdown is not scanned for history. Prose docs are kept current by the rules in
  [`principles.md`](../../documentation/principles.md).
