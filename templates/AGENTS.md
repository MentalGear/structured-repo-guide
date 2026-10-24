# Agent notes

<!--
Template. Copy to AGENTS.md (or CLAUDE.md, CONTRIBUTING.md: the name your tool reads) at the repository root.
Keep it to one screen. Each rule is one or two lines and links to its home. A rule that needs a paragraph gets the
paragraph in docs/ and a pointer here. Never list the checks here: the generated catalogue does. Delete this comment.
-->

Short on purpose: each rule has one home, linked here. A rule that belongs in a linked doc goes there, not here. A new
check never needs an edit to this file.

## Session start

- Read [`docs/STATUS.md`](./docs/STATUS.md) first: what is deployed, what runs, what is next, what waits for a person.
- Then [`docs/README.md`](./docs/README.md), the map of the docs.
- The backlog is one file per item under `docs/backlog/`. The indexes are generated: edit the item file, run
  `<index generator> --write`, commit both. Cite an item by id, as in "backlog 12".

## Rules for every change

- **Run every check before every commit:** `<the one entry point>`. Green is `ALL GREEN` with exit 0. A partial run is not
  a pass. What each check enforces is [`docs/checks.md`](./docs/checks.md), generated from the script headers.
  A new check: write its header, run `<catalogue generator> --write`; no other doc is edited.
- **Comments describe the current state.** A reason, in present tense, plus the item id. History (dates, commit hashes,
  "used to", incident stories) goes to the item and is linked, not retold. Rule and examples:
  `docs/guides/history-in-comments.md` (write the page from the guide, then link it here).
- **When the same problem shows up twice, stop patching instances.** Find the root cause and fix the class by
  construction: a check that makes it unable to recur. Existing debt goes in a shrink-only baseline.
- **One home per rule.** When you are about to paste a rule into a second file, link it instead.
- **Decisions in force** are in [`docs/decisions.md`](./docs/decisions.md). Do not reopen one without the owner.

## Conventions

- Commits: `<your convention>`, with a body that says why and cites the item id.
- <One line per other rule that applies to every change, each linking to its home.>
