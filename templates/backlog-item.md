---
id: 0
title: "One line: what this item is about"
status: open            # open | active | blocked | done | dropped (done and dropped live in done/)
area: general           # a coarse tag: render, build, docs, ...
updated: YYYY-MM-DD     # the date of the last substantive change to this item
---

<!--
Template. Save as docs/backlog/NNN-slug.md, where NNN is the next free id, zero-padded (the highest id in docs/backlog/
and docs/backlog/done/, plus one). Set `id` to the same number without padding. Ids are never renumbered or reused.
Then run the index generator with --write and commit the item and the indexes together.
When the item is finished: move the file to docs/backlog/done/, set status to done (or dropped), record the landing
commit in "Status", regenerate the indexes. Keep the three section headings, in this order. Delete this comment.
-->

# Item <id>: <title>

## Item

What is wanted, in a few sentences, written for someone who has not seen the discussion. Say the problem before the
solution. Name who asked if that matters ("owner request"), without a date: the front matter carries `updated`.

## Status

Where it stands now. One of: not started; in progress, with what is done and what is left; blocked on what and on whom.

When done: the landing commit or pull request, and a sentence on what changed. This is the place for the story that
code comments must not carry: the incident, the first wrong fix, the evidence that settled it.

## Detail

Everything else, as long as the item is open: the evidence, the options with their trade-offs, measurements, links to
research notes (`docs/research/<note>.md`, whose first line says `Backs: item <id>`), and the plan.

Code that carries a reason for this item cites it in a comment, in the form the reference check understands:
`(backlog <id>)`.
