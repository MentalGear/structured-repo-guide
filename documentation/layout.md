# Layout: what goes where

**What this is for.** A target documentation tree and the rule for each directory in it. Use it when you start a
repository's docs, when you decide where a new document goes, and as the target of a cleanup
([`cleanup-playbook.md`](./cleanup-playbook.md)).

## Contents

- [The tree](#the-tree)
- [What goes where](#what-goes-where)
- [Choosing the home of a new document](#choosing-the-home-of-a-new-document)
- [Keeping cited paths and headings stable](#keeping-cited-paths-and-headings-stable)
- [Sizes](#sizes)
- [The map file](#the-map-file)

## The tree

```
AGENTS.md                  entry file: a screen of rules, pointers to the rest
README.md                  what the project is, how to build it, link to docs/
docs/
  README.md                the map: every path below, one line each
  STATUS.md                where we are right now
  decisions.md             current decisions, one line each
  backlog.md               generated index of open items
  backlog-done.md          generated index of finished items
  backlog/                 the tracker: one file per item
    NNN-slug.md
    done/NNN-slug.md
  checks.md                generated catalogue of checks
  guides/                  how-to recipes and conventions (stable)
  reference/               explanations of how and why the system is built as it is (stable)
  research/                notes that back an OPEN item, and nothing else
  issues/                  records of known defects outside our control, which code cites
    NNN-slug.md
  drafts/                  outward-facing filings that wait for the owner's go
  archive/                 finished, historical material; kept because something still cites it
    README.md              its index, under a "historical" banner
scripts/
  run-gates.sh             the one runner
  gates.list               the gates it runs, one line each, grouped
  check-*.sh               one check per file, each with a header
  baselines/               ratchet files, one per check that has debt
```

The names are suggestions. The roles are not. Keep one directory for each role and keep each role's rule.

## What goes where

| Directory | Holds | Rule |
|---|---|---|
| Entry file | Rules that apply to every change, each a line or two, each linking to its home. | Fits on one screen. Never lists checks. |
| `docs/README.md` | The map. | Every doc appears once, with what it is. Written by hand, linked by the entry file. |
| `docs/STATUS.md` | Right now: deployed, running, next, waiting. | Edited at every merge. Has a "Last updated" line. |
| `docs/decisions.md` | Current decisions, one line each. | Reversed decisions leave. Line points to the item. |
| `docs/backlog/` | The tracker, one file per item. | Ids are never renumbered or reused. See [`tracker-as-files.md`](./tracker-as-files.md). |
| `docs/guides/` | Recipes: "how to add a component", "how to run the suite". | Current steps only. A guide that is wrong is fixed in place. |
| `docs/reference/` | The reasoning behind the design: platform caveats, invariants, rationale. | Present tense. Code comments cite its headings. |
| `docs/research/` | Evidence behind an item that is still open. | Each note names the open item it backs. When the item closes, the note moves to `archive/` or is deleted. |
| `docs/issues/` | One record per known defect that we do not control and that code works around: an upstream bug, a platform quirk, a browser difference. | Present tense: the symptom, the affected versions, the link to the upstream report, and which code carries the workaround. Code cites it by id, so ids are never reused. A fixed defect is closed (the record moves to `archive/` once the workaround is gone). It is a statement about the world; work to do is an item in `backlog/`. |
| `docs/drafts/` | Text that will leave the repository once someone decides: an upstream bug report, a security disclosure, an announcement. | Nothing in it is sent without the owner's go. Each draft names who must approve and where it goes. Sent or dropped drafts are deleted (the sent text lives where it was sent). |
| `docs/archive/` | Finished plans, landing logs, closed investigations. | Read-only. Has its own index (`README.md`) with every file as a row. Every page, and the index, starts with a banner: "historical; check the date before acting on anything here". A worked example is [`../examples/documentation/sample/docs/archive/`](../examples/documentation/sample/docs/archive/README.md). |
| `docs/checks.md` | The catalogue of checks. | Generated. Do not edit. |
| `scripts/run-gates.sh`, `scripts/gates.list` | The runner and the one list of everything it runs. | Every check is a line of the list. See [`gate-runner.md`](./gate-runner.md). |
| `scripts/baselines/` | Ratchet files. | Edited only by `--update-baseline`. See [`ratchets.md`](./ratchets.md). |

Three directories need the strictest discipline:

- **`research/`** is the one that fills with finished work. Keep it honest: a note with no open item behind it is
  archived. Every note is linked from the item it backs ([`tracker-as-files.md`](./tracker-as-files.md#linking-research-to-items)).
- **`archive/`** is not a trash can and not a living doc. It exists because code or items still cite the material. If
  nothing cites it and nobody needs it, delete it. Version control keeps it.
- **`drafts/`** is the one place where text waits for a person. A draft that sits there for months is a decision nobody
  made: ask, then send it or delete it.

## Choosing the home of a new document

Ask in order. Use the first yes.

1. Is it a rule every change must follow? One line in the entry file, with its full text in `guides/` or `reference/`.
2. Is it a decision somebody made? A line in `decisions.md`, and the reasoning in the item.
3. Is it a unit of work to do? An item in `backlog/`.
4. Is it a recipe someone follows step by step? `guides/`.
5. Does it explain why the system is the way it is? `reference/`.
6. Is it evidence for an open item? `research/`, named in that item.
7. Is it a known defect that is not ours, which code works around? `issues/`.
8. Is it text that leaves the repository after somebody says go? `drafts/`.
9. Is it finished and still cited? `archive/`.
10. None of the above? Probably it does not need to exist. A commit message, an item or a code comment may be the home.

## Keeping cited paths and headings stable

Code comments, items and other docs cite documents by path and by heading. A move that breaks a citation is a
regression, so a living doc keeps its path and the headings that something cites.

- **Before you move or rename a doc**, find the citations: `git grep -n 'docs/guides/old-name'`. Cite by the path as
  written, and also by the file name alone.
- **Move with the link rewrite in the same commit.** `git mv`, then `sed` or a script over the citing files, then
  `git grep` again and confirm zero hits on the old path.
- **Rename a heading only with its citations.** The link checker verifies `#anchor` links, so a renamed heading that a
  doc links to goes red. Comments that cite a heading by name need a search: `git grep -n 'Gate procedure'`.
- **When you split a big doc, keep the old headings** in the file that stays, or leave a pointer where the heading was.
- **Prefer ids to paths in code.** A comment that cites `backlog 312` survives any reorganisation of the docs. A comment
  that cites `docs/research/old/x.md` does not.
- **Let the checks hold the line.** The link checker fails on a broken relative link or anchor. The reference check
  fails on a comment that cites a missing path. Both run before every commit.

## Sizes

Size is a smell, not a rule. These are starting points.

| File | Look at it when | Usually means |
|---|---|---|
| Entry file | Over one screen | Rules were pasted instead of linked. |
| A living doc | Over about 20 KB | Two documents, or a landing log mixed in with the rules. |
| A done item | Over about 5 KB | The narrative should be trimmed to a summary plus the landing commit. |
| `research/` | More notes than open items | Finished research has not been archived. |

A cleanup reports every file over its threshold with a proposed split, and the owner decides
([`cleanup-playbook.md`](./cleanup-playbook.md#step-2-inventory-the-docs)).

## The map file

`docs/README.md` is the one hand-written index. Write it as tables grouped by role (status and backlog, rules and
recipes, reference, research, archive), one row per document: the path, and what it is in one sentence. Every row's
path is a link, so the link checker verifies the map. A doc that is not in the map does not exist for a new reader.

The map opens with: "start with `STATUS.md`, then the rules, then pick an item from the open backlog". A worked
map is in [`../examples/documentation/sample/docs/README.md`](../examples/documentation/sample/docs/README.md). It is an
example: when you copy it, **adapt it** (one row per doc your repository really has, each row's sentence true of its file),
because a copied map describes the sample's docs, not yours.

Two checks keep the map honest. `check-doc-links.sh` fails when a row's link is dead. `check-doc-map.sh` fails when a
Markdown file under `docs/` cannot be reached from the map by following links (an index such as `backlog.md` or
`archive/README.md` that the map links is enough for the files it lists), so a new doc must land in the map in the same change.
