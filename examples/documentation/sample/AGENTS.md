# Agent notes

Short on purpose: each rule has one home, linked here. A rule that belongs in a linked doc goes there, not here.

## Session start

- Read [`docs/STATUS.md`](./docs/STATUS.md) first: what is deployed, what runs, what is next.
- Then [`docs/README.md`](./docs/README.md), the map of the docs.

## Rules for every change

- Run every check before every commit: `sh scripts/run-gates.sh`. Green is `ALL GREEN` and exit 0.
- What each check enforces is [`docs/checks.md`](./docs/checks.md), generated from the gate list and the script
  headers. A new check is its own header plus one line in `scripts/gates.list`, and nothing else.
- Comments describe the current state. History goes to the tracker item and is linked by id, as in "backlog 3".
- Open and closed work is in [`docs/backlog.md`](./docs/backlog.md) and [`docs/backlog-done.md`](./docs/backlog-done.md);
  the owner's standing decisions are in [`docs/decisions.md`](./docs/decisions.md).
