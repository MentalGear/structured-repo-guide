---
id: 1
title: "Describe the first piece of work"
status: open            # open | active | blocked | done | dropped (done and dropped live in done/)
area: general           # a coarse tag: render, build, docs, ...
updated: 2025-01-01     # the date of the last substantive change to this item: set it to today
---

<!--
Template, ready to run as the FIRST item: save it as docs/backlog/001-<slug>.md (the slug is a few lower-case words joined by
hyphens, such as 001-adopt-the-doc-checks.md), edit the title and the sections, run
`python3 -I scripts/backlog_index.py --write` (it writes both indexes, docs/backlog.md and docs/backlog-done.md), and commit the
three files together.
For a LATER item: the file name is NNN-slug.md where NNN is the next free id (the highest id in docs/backlog/ and
docs/backlog/done/, plus one), zero-padded to three digits; set `id` to the same number without padding, here and in the
heading. Ids are never renumbered or reused. If the id and the file name disagree the index check fails, which is why this
file says id 1: set the id first.
When the item is finished: move the file to docs/backlog/done/, set status to done (or dropped), record the landing commit in
"Status", regenerate the indexes. Keep the three section headings, in this order. Delete this comment.
-->

# Item 1: Describe the first piece of work

## Item

What is wanted, in a few sentences, written for someone who has not seen the discussion. Say the problem before the
solution. Name who asked if that matters ("owner request"), without a date: the front matter carries `updated`.

## Status

Where it stands now. One of: not started; in progress, with what is done and what is left; blocked on what and on whom.

When done: the landing commit or pull request, and a sentence on what changed. This is the place for the story that
code comments must not carry: the incident, the first wrong fix, the evidence that settled it.

## Detail

Everything else, as long as the item is open: the evidence, the options with their trade-offs, measurements, links to
research notes (files under `docs/research/`, each starting with the line `Backs: item 1`), and the plan.

Code that carries a reason for this item cites it in a comment, in the form the reference check understands:
`(backlog 1)`.
