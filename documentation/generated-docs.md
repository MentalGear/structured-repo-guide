# Generated docs

**What this is for.** Replace a hand-kept list of checks (or commands, options, routes) with a page generated from the
code that already describes itself, plus a freshness check that fails when the page is stale. Use it when a doc lists
things that change, and the list keeps lagging behind them.

The worked case is a catalogue of check scripts. The same shape fits any list whose items already have a description
in the source.

## Contents

- [The problem](#the-problem)
- [The construction](#the-construction)
- [Script headers](#script-headers)
- [The generator](#the-generator)
- [The freshness check](#the-freshness-check)
- [Keeping the entry point and the catalogue complete](#keeping-the-entry-point-and-the-catalogue-complete)
- [Adding a new check](#adding-a-new-check)
- [Pitfalls](#pitfalls)
- [Other things to generate](#other-things-to-generate)

## The problem

A project grows checks. Each time, someone must remember to add a sentence about it to the entry file, the
contributor guide and the checks list. They do not all remember. The entry file lists twelve checks and the repository
has twenty-five. The agent that reads it trusts the list, and the other thirteen are invisible.

Hand-keeping fails because the work is a copy, and a copy has no owner.

## The construction

```
 scripts/check-*.sh      each with a header comment      <- source of truth, edited by people
        |
        v
 docs_catalogue.py --write                                 <- pure function of the headers
        |
        v
 docs/checks.md          "generated, do not edit"          <- committed
        ^
        |
 docs_catalogue.py --check  fails when the page differs    <- freshness check, runs with the other checks
```

Three properties make it work:

1. **One source.** A check is described by its own header and nowhere else.
2. **Pure generation.** The output depends only on the headers: no dates, no run counts, a stable sort order, the
   same line endings. Two runs on the same tree give the same bytes.
3. **A freshness check.** It regenerates in memory and compares. A stale page fails the run, so the author
   regenerates and commits it with the change.

The page says so at the top: "Generated from the header of each `scripts/check-*`. Do not edit it by hand."

## Script headers

A header is the comment block at the top of the file, after the shebang. The first paragraph is the catalogue entry.

```sh
#!/bin/sh
# check-no-tabs.sh -- no tab characters in source files
#
# group: Source hygiene
#
# Fails when a file under src/ contains a tab character, because tab width differs by editor and a diff then
# shows alignment that the file does not have.
#
# Usage: sh scripts/check-no-tabs.sh
```

| Line | Meaning |
|---|---|
| `check-name.sh -- title` | Optional. Names the script. Dropped from the entry. |
| `group: Title` | Optional. The heading the entry is listed under. Default `Other`. |
| First paragraph | The entry. What the check forbids, and why, in a sentence or two. |
| Later paragraphs | Detail for the script's own readers: markers, baselines, usage. Not printed in the catalogue. |

The generator reads `#` headers (sh, py, rb, pl), `//` headers (js, ts) and Python module docstrings. A table
keyed by extension (`HEADER_STYLES`) says which; add a row for another language.

Write the entry in the present tense, as a rule: "Fails when X, because Y." The "because" is what a contributor
needs when the check goes red, and what an agent needs to avoid working around it.

## The generator

[`../examples/documentation/docs_catalogue.py`](../examples/documentation/docs_catalogue.py):

```sh
python3 docs_catalogue.py --write                 # regenerate docs/checks.md
python3 docs_catalogue.py --check                 # exit 1 when stale or when a header is unusable
python3 docs_catalogue.py --scripts 'tools/lint-*' --out docs/lint.md --title Lint     # another catalogue
```

The output groups entries under their `group:` heading (headings sorted, `Other` last), sorts the entries by file
name, and links each entry to its script by a relative path, so the link checker verifies the catalogue too.

## The freshness check

The same script, `--check`, fails in these cases:

| Case | Why it fails |
|---|---|
| The page differs from the generated text | A header changed, a script was added or removed, or the page was edited by hand. |
| The page is missing | The generator was never run. |
| A script has no header description | The catalogue would have a hole. |
| A description is too thin (under 60 characters by default) | `Checks the thing.` tells nobody what is enforced. |
| A description is too long (over 700) | Detail belongs in the later paragraphs. |
| A description ends in a colon | It introduces something it does not say. |

The generator has a `--self-test` that builds a throwaway tree for each case, and requires the right exit code.
That is the proof that the freshness check goes red when it should.

Run the check with every other check, from the one entry point.

## Keeping the entry point and the catalogue complete

The catalogue lists the scripts that match its glob (`scripts/check-*`). The entry point must run the same set,
or a check exists that nobody runs. Two ways to make that true by construction:

- **Run by glob.** The entry point loops over `scripts/check-*.sh`. A new script is picked up with no edit. The sample
  entry point [`../examples/documentation/sample/scripts/run-checks.sh`](../examples/documentation/sample/scripts/run-checks.sh)
  does this.
- **Run from a list, and check the list.** Use this when order or grouping matters, or some checks are slow. The entry
  point keeps an explicit list. One more check fails when a `check-*` script is not in the list. Then a forgotten
  registration is red, not silent.

In both, the catalogue's group comes from the script header, so the list carries no prose.

## Adding a new check

1. Write `scripts/check-thing.sh`. Its header's first paragraph says what it forbids and why. Give it a `group:`.
2. If the entry point uses a list, add one line to it.
3. Run `docs_catalogue.py --write`.
4. Commit the script and the regenerated page together.

No other document is edited. The entry file does not change. If you find yourself editing a second prose file, that
file held a copy ([`principles.md`](./principles.md#2-one-home-per-rule)).

## Pitfalls

- **Non-deterministic output.** A timestamp, a "N checks" count computed at write time that differs from the check's
  count, a dict order. The freshness check then fails on a clean tree. Generate only what is derived, and sort.
- **Platform differences.** Normalise path separators to `/` and read files as UTF-8. A page generated on one machine
  must compare equal on another.
- **A header that is a license banner.** The first paragraph is then the licence. Put the licence after the header
  paragraph, or skip it with a blank `#` line, and keep the first paragraph for the description.
- **The generator becoming a template engine.** Keep it a short script. If the page needs hand-written prose, put the
  prose in a separate file and link it.
- **Editing the generated page.** The marker and the check stop this, but also say it in the entry file's rule: edit the
  header, run `--write`.

## Other things to generate

The same three parts (source, generator, freshness check) fit:

- A command reference from `tool --help`.
- A table of environment variables or config keys from the schema or the config parser.
- A route or API list from the router.
- A list of components, from each component's manifest.
- The tracker indexes, from the item files ([`tracker-as-files.md`](./tracker-as-files.md)).
- A "what cites this doc" map, from `git grep`.

Choose to generate when the source already has the sentence you would write. If you would have to write new
sentences, the source is missing them. Add them to the source, and generate from there.
