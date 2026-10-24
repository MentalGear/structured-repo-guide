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
- [List-driven catalogue](#list-driven-catalogue)
- [Two halves, one catalogue](#two-halves-one-catalogue)
- [The freshness check](#the-freshness-check)
- [Keeping the runner and the catalogue complete](#keeping-the-runner-and-the-catalogue-complete)
- [Adding a new check](#adding-a-new-check)
- [Pitfalls](#pitfalls)
- [Other things to generate](#other-things-to-generate)

## The problem

A project grows checks. Each time, someone must remember to add a sentence about it to the entry file, the
contributor guide and the checks list. They do not all remember. The entry file lists twelve checks and the repository
has twenty-five. The agent that reads it trusts the list, and the other thirteen are invisible.

Hand-keeping fails because the work is a copy, and a copy has no owner. It also fails in a second, noisier way: a check list
kept in the entry file is edited by every change that adds a check, so two such changes in flight conflict on the same lines,
and the merge is resolved by whoever is in a hurry. Generate the list and the file that people used to edit stops being a
place where changes collide: each change adds its own script and its own one line to the gate list, in different places.

## The construction

```
 scripts/check-*.sh      each with a header comment      <- source of truth, edited by people
 scripts/gates.list      the runner's list (optional)    <- groups, order, and the text of command gates
        |
        v
 docs_catalogue.py --write                                 <- pure function of the two
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

The page says so at the top: "Generated from ... Do not edit it by hand."

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
| `group: Title` | Optional, and read only by the glob-driven catalogue. The heading the entry is listed under. Default `Other`. With a gate list the list's `# group:` lines decide and this line is ignored. |
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
python3 docs_catalogue.py --scripts 'tools/lint-*.sh' --out docs/lint.md --title Lint   # another catalogue, by glob
```

It has two modes, and exactly one is in force:

- **List-driven** when `scripts/gates.list` exists (or `--gates FILE` names one). The runner's list is the source of truth.
  This is the default for a repository that has a runner ([`gate-runner.md`](./gate-runner.md)).
- **Glob-driven** otherwise, or with `--scripts GLOB`. The default glob is `scripts/check-*.sh`: the `.sh`, so a hyphenated `.py`
  helper that sits next to a wrapper (`check-pins.py` behind `check-pins.sh`) is not mistaken for a check. Write
  `--scripts 'scripts/check-*'` when a Python script is a check in its own right. Entries are grouped under the header's
  `group:` heading (headings sorted, `Other` last) and sorted by file name.

In both modes each entry is linked to its script by a relative path, so the link checker verifies the catalogue too.

## List-driven catalogue

The runner's gate list already says what runs, in what order and under which heading. The catalogue then adds the one thing the list
does not carry: what each gate enforces.

- A **check script** gate is described by the first paragraph of the script's header, as above.
- A **command** gate (`cargo test`, `make lint`) has no header, so it is described by the comment lines directly above its entry
  in the list. A gate that is neither a check script nor has such a comment fails the freshness check: "a listed gate with
  no description fails".
- A comment above a check script's entry fails too. A script has one description, in its header.
- The groups are the list's `# group:` lines, in the list's order, and the entries keep the list's order (order can matter:
  cheap checks first). A `slow` tag is shown on the entry.
- A `scripts/check-*.sh` that the list does not name fails the catalogue as well as the runner.

```text
## Build

**`fmt`**: Formats every source file with the project formatter and fails on any difference, because ...

**`test`** *(slow)*: Runs every unit test of the project. ...
```

The list-driven catalogue is the variant to prefer: there is one list, and what the runner runs and what the page documents
cannot disagree.

## Two halves, one catalogue

A repository that adopts both halves of this guide has one gate list and therefore one catalogue. The documentation half's
wrappers are `check-history-comments.sh`, `check-comment-refs.sh`, `check-doc-links.sh`, `check-docs-catalogue.sh`,
`check-backlog-index.sh`, `check-placeholders.sh`, `check-doc-map.sh` and `check-dated-headings.sh`; the security half's wrappers
are `check-*.sh` as well. They sit in the same `scripts/`, are listed in the same `gates.list` under their own `# group:`
headings (`Documentation`, `Supply chain`), and appear on `docs/checks.md` under those headings in the list's order.

The glob never picks up the other half wrongly because the glob is `scripts/check-*.sh`: Python tools, whichever half they
belong to, are not catalogued unless a gate names them, and a wrapper's header (not its Python tool's docstring) is what the page
prints. A new check of either half is one header and one line in the list.

## The freshness check

The same script, `--check`, fails in these cases:

| Case | Why it fails |
|---|---|
| The page differs from the generated text | A header changed, a script was added or removed, or the page was edited by hand. |
| The page is missing | The generator was never run. |
| A script has no header description, or a listed command gate has no comment | The catalogue would have a hole. |
| A `scripts/check-*.sh` is not in the gate list (list mode) | A check that nobody runs is also a check nobody reads about. |
| A description is too thin (under 60 characters by default) | `Checks the thing.` tells nobody what is enforced. |
| A description is too long (over 700) | Detail belongs in the later paragraphs. |
| A description ends in a colon | It introduces something it does not say. |

The generator has a `--self-test` that builds a throwaway tree for each case, in both modes, and requires the right exit
code. That is the proof that the freshness check goes red when it should. The wrapper `check-docs-catalogue.sh` runs it quietly
after every check, so a self-test that rots turns the runner red ([`ratchets.md`](./ratchets.md#the-check-proves-it-can-fail)).

Run the check with every other check, from the runner.

## Keeping the runner and the catalogue complete

The catalogue lists what it is told to list. The runner must run the same set, or a check exists that nobody runs. Two ways to make
that true by construction:

- **Run from a list, and check the list** (the default). The runner reads `scripts/gates.list`, and fails the run when a
  `scripts/check-*.sh` is not in it ([`gate-runner.md`](./gate-runner.md)). The catalogue reads the same list. A forgotten
  registration is red, not silent.
- **Run by glob.** A runner that loops over `scripts/check-*.sh` picks up a new script with no edit, at the cost of order, groups,
  tags and command gates. Use it for a tiny repository, with the glob-driven catalogue.

In both, the catalogue's text comes from the script header, so no prose is kept anywhere else.

## Adding a new check

1. Write `scripts/check-thing.sh`. Its header's first paragraph says what it forbids and why. (Glob mode: give it a `group:` line.)
2. Add one line to `scripts/gates.list` under its group.
3. Run `docs_catalogue.py --write`.
4. Commit the script, the list line and the regenerated page together.

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
