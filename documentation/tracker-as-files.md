# The tracker as files

**What this is for.** Keep the backlog as one Markdown file per item, with a generated index. Use it when a
single backlog file has become too big to edit without conflicts, when code needs a stable id to cite, or when you
want the tracker to live in the repository where agents and checks can read it.

The tracker can also be an issue tracker. The method below applies if you keep an id for each item and cite it from
code. Files add three things an issue tracker lacks: the history of an item is in the same commit as the code that
closed it, checks can read it offline, and an agent can edit it with the same tools it edits code.

## Contents

- [The shape](#the-shape)
- [Front matter](#front-matter)
- [Sections](#sections)
- [Ids](#ids)
- [Open and done](#open-and-done)
- [The generated index](#the-generated-index)
- [Merging the index in parallel work](#merging-the-index-in-parallel-work)
- [Citing an item from code](#citing-an-item-from-code)
- [Linking research to items](#linking-research-to-items)
- [Creating the first item](#creating-the-first-item)
- [Adding, changing and closing an item](#adding-changing-and-closing-an-item)
- [Trimming done items](#trimming-done-items)
- [What the checks enforce](#what-the-checks-enforce)
- [Migrating a single backlog file](#migrating-a-single-backlog-file)

## The shape

```
docs/backlog.md                       generated: the OPEN items
docs/backlog-done.md                  generated: the DONE items
docs/backlog/001-first-thing.md       an open item
docs/backlog/002-second-thing.md
docs/backlog/done/003-third-thing.md  a closed item
```

The files are the source of truth. The two index files are only tables over them.

A template is in [`../templates/backlog-item.md`](../templates/backlog-item.md). The script is
[`../examples/documentation/backlog_index.py`](../examples/documentation/backlog_index.py). `backlog_index.py --write`
writes **both** index files (`docs/backlog.md` and `docs/backlog-done.md`) in one run, so there is never a reason to
write one of them by hand.

## Front matter

Every item starts with a block between two `---` lines. Five fields:

```
---
id: 12
title: "Cache the render key"
status: open            # open | active | blocked | done | dropped
area: render
updated: 2025-03-02
---
```

| Field | Rule |
|---|---|
| `id` | The number in the file name, without padding. Never changes. |
| `title` | One line, what the item is about. The index shows it. |
| `status` | One of `open`, `active`, `blocked`, `done`, `dropped`. Agrees with the folder. |
| `area` | A coarse tag (`render`, `build`, `docs`). Lets a reader filter the index. |
| `updated` | The date of the last substantive change to the item. |

Add fields if your project needs them (`size`, `owner`). Add them to the script's `REQUIRED` list so the check enforces
them. Do not add a field nobody reads.

## Sections

Three sections, in this order:

| Section | Holds |
|---|---|
| `## Item` | What is wanted, in a few sentences. Written for someone who has not seen the discussion. |
| `## Status` | Where it stands now. When done: the landing commit or pull request. This is where an incident story lives. |
| `## Detail` | Everything else: evidence, options, measurements, links. May be long while the item is open. |

A fixed order lets an agent or a script find the part it needs. It also keeps a reader from hunting.

## Ids

- The id is a number, assigned once. The file name is `NNN-slug.md` with the number zero-padded to three digits at
  least, so a directory listing sorts in order.
- Ids are never renumbered and never reused. A dropped item keeps its id. This is what makes an old citation safe.
- The next free id is the highest id in either folder plus one:

  ```sh
  ls docs/backlog docs/backlog/done | sed -n 's/^\([0-9][0-9]*\)-.*/\1/p' | sort -n | tail -1
  ```

- Sub-ids (item 12 has parts "12a" and "12b") live inside item 12's file. They are not files.
- The slug is for humans. The slug may change (rename the file, keep the number). The number may not.

## Open and done

Folder and status agree, by construction:

| Status | Folder | Index |
|---|---|---|
| `open`, `active`, `blocked` | `docs/backlog/` | `docs/backlog.md` |
| `done`, `dropped` | `docs/backlog/done/` | `docs/backlog-done.md` |

Closing an item is a move plus a status edit: `git mv docs/backlog/012-x.md docs/backlog/done/012-x.md`, set
`status: done`, add the landing commit to `## Status`, regenerate the index. The check fails if you do one without the
other.

An item that is partly done stays open. Close it when no open remainder is left, or split the remainder into a new item.

## The generated index

Each index file has a hand-written header, then a block between two markers, which the generator rewrites:

```
<!-- BEGIN GENERATED: ... -->

| id | title | status | area | updated |
|---|---|---|---|---|
| [2](backlog/002-evict-cache-by-size.md) | Evict the fragment cache by size | open | cache | 2025-01-15 |

<!-- END GENERATED -->
```

- Edit the header freely. Never edit the block.
- Regenerate after every item edit: `backlog_index.py --write`. Commit the item and the index together.
- The check regenerates in memory and fails if the committed index differs. That is what stops a hand edit or a forgotten
  regeneration.
- A reader who knows an id and not the file name looks in the index. A script can glob `docs/backlog/*NNN-*` and
  `docs/backlog/done/*NNN-*`.

## Merging the index in parallel work

Work streams that each add or change an item all rewrite the same generated rows and the same counts, so the index conflicts on
every merge into the integration branch, though no stream edited it by hand. Declare a git merge driver for the index, as
[`generated-docs.md`](./generated-docs.md#generated-files-and-parallel-merges) sets out (committed `.gitattributes`, committed
driver, registration in the session-setup hook, a fallback to `git merge-file`, a gate with a scratch merge). The index driver
has these parts:

- **Input: the three versions of the index** (base, ours, theirs). It runs before the other side's item files exist in the
  working tree and there is no `MERGE_HEAD`, so it cannot regenerate from the items.
- **Rows merge by id.** A row only one side changed takes that side. A row both sides changed to the same text takes it. A row
  both sides changed differently is a conflict, and the driver exits non-zero. A row added on either side stays, and a row
  removed on one side and unchanged on the other is removed.
- **Counts are recomputed** from the merged rows (the open count, the done count), never merged as numbers, because two sides that
  each added one item hold the same count.
- **Text outside the generated block merges with `git merge-file`.** The hand-written header is an ordinary text merge, so a real
  conflict in the header stays a conflict.
- **Rows sort by code point,** so the output is the bytes the generator writes on any machine.

The freshness check ([`backlog_index.py --check`](#what-the-checks-enforce)) stays the judge: it compares the merged index with the
item files, so a driver that merges to the wrong table goes red there, and the fix is to run `--write`. The guide describes this
driver and has no sample of it.

## Citing an item from code

Cite by one agreed word and the id: `backlog 312`, or in a list `backlog 312, 313`. Put it in the comment that
carries the current reason:

```python
# Two retries: a third doubles the load on a struggling backend (backlog 312).
```

The reference check resolves every such citation to a file in the tracker, so a deleted or mistyped id goes red. Pick
the word once. A project that uses "issue" or "ticket" passes it to the check with `--word`, and writes `issue #12` in
comments, because a bare `issue 12` is also ordinary English and is checked only when it is unmistakable
([`history-in-comments.md`](./history-in-comments.md#citing-an-item-what-counts-as-a-citation)).

The citation form is part of the contract. Use it in docs, commit messages and comments alike, so a search for
`backlog 312` finds every place the item touches.

## Linking research to items

Research notes under `docs/research/` back an open item. By construction:

- The item's `## Detail` links the note.
- The note's first line names the item: `Backs: item 312`.
- When the item closes, the note is archived or deleted in the same commit.

A quick audit lists notes that no open item links. Those are the archive candidates:

```sh
for f in docs/research/*.md; do
  b=$(basename "$f")
  grep -rqs "$b" docs/backlog --include='*.md' --exclude-dir=done || echo "unbacked: $f"
done
```

## Creating the first item

The template is ready to run as item 1, so the first item needs no edit before it works. From the root of the repository:

```sh
mkdir -p docs/backlog/done
cp /path/to/structured-repo-guide/templates/backlog-item.md docs/backlog/001-adopt-the-doc-checks.md
# edit the title and the three sections, set `updated` to today, delete the template comment
python3 -I scripts/backlog_index.py --write       # writes docs/backlog.md and docs/backlog-done.md
python3 -I scripts/backlog_index.py --check       # exit 0
```

- **The name is `NNN-slug.md`:** the number zero-padded to three digits, a hyphen, a few lower-case words joined by hyphens.
  The `id:` in the front matter is the same number without padding. The template says `id: 1`, so it passes as `001-...`;
  saved under any other number it fails the index check until `id` is set to match.
- **The first item is a good place for the work in hand:** the cleanup ([`cleanup-playbook.md`](./cleanup-playbook.md)) or
  "adopt the doc checks". Its `## Status` carries the before-and-after numbers.
- **A later item** uses the next free id (the command under [Ids](#ids)), and the same steps.

## Adding, changing and closing an item

1. **Add.** Copy the template, name it with the next id, set `id` to match, fill the front matter and the three sections,
   run `backlog_index.py --write`, commit the item and both indexes.
2. **Change.** Edit the file, bump `updated`, regenerate, commit both.
3. **Close.** Move to `done/`, set `status`, record the landing commit in `## Status`, regenerate, commit both. The code
   change that closes it carries a comment citing the id, if the comment needs a reason.
4. **Drop.** Same as close with `status: dropped` and a line in `## Status` saying why. A dropped item is still an item
   somebody may search for.

## Trimming done items

A done item keeps its front matter, its three section headings and a short summary with the landing commit. The long
narrative can go: version control has the discussion, and the id stays so citations still resolve. A done item over a
few KB is a candidate to trim. Keep the section headings, because the check requires them.

## What the checks enforce

`backlog_index.py --check` (wrapper: `check-backlog-index.sh`) fails on:

- a missing front matter field, a missing section, or sections out of order;
- an unknown `status`;
- an `id` that differs from the file name's number, or a duplicate id;
- a status that disagrees with the folder;
- a file name that is not `NNN-slug.md`;
- an index that differs from the generated one.

`check_doc_links.py` fails on any broken relative link between docs. `comment_scan.py refs` fails on a comment that cites
a missing id. All three have self-tests. See [`generated-docs.md`](./generated-docs.md) and
[`ratchets.md`](./ratchets.md).

## Migrating a single backlog file

For a repository that has one long `BACKLOG.md`:

1. Give every entry an id. Keep any numbering that comments already cite.
2. Write a throwaway script that splits the file into `NNN-slug.md` files, each with front matter and the three
   sections. Run it once. Archive the script with the history. It does not need to live on.
3. Put finished entries in `done/`.
4. Run `backlog_index.py --write` and replace the old file with the generated index, so old links to it still land on a
   table that lists every id.
5. Turn on the check, then the reference check, so a citation of a missing id goes red.
