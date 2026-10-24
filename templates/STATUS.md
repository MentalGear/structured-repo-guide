# Status: where we are

<!--
Template. One page, edited at every merge or round change by whoever merges. It says what is deployed, what runs, what is next
and what waits for a person. It does not say what each batch contained (the log and the tracker do), and it holds no item-level
state (the item does). Keep it under one screen. Copy it to docs/STATUS.md, fill every <placeholder> with what is true today
(from version control and the running system, not from an old status paragraph) and delete sections that do not apply. The
check-placeholders check fails while a placeholder or this comment is left. Delete this comment.
-->

**Living page. Update it with the change that makes it true. If "Last updated" is old, treat the page as stale and check
the version control log.**

Last updated: <YYYY-MM-DD>. Deployed from `<branch>` at `<commit>`: <link to the deployed site or release>.

## Deployed

<What is live, in a sentence. The commit or release it was built from.>

## Running

- Item [<id>](./backlog/<NNN>-<slug>.md): <what is in flight, one line>.

## In the queue

- <Work that is ready and waiting to merge, one line each, with the item id.>

## Next

- Item [<id>](./backlog/<NNN>-<slug>.md): <what comes next, in order, and why this order.>

## Waiting for a person

- <A decision, an approval, a test on a device, a credential. Who, and what unblocks it.>

## Decisions and rules in force

[`decisions.md`](./decisions.md) lists the current decisions. The rules for every change are in the entry file at the
repository root.

## Keeping this page current

Edit the section that changed, bump "Last updated", commit with the change that made it true.
