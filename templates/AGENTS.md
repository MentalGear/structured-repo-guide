# Agent notes

<!--
Template. Copy to AGENTS.md (or CLAUDE.md, CONTRIBUTING.md: the name your tool reads) at the repository root, then adapt it:
fill the two <placeholders> below, and make every command and link match your repository. The check-placeholders check fails
while a placeholder or this comment is left. Keep it to one screen. Each rule is one or two lines and links to its home. A rule
that needs a paragraph gets the paragraph in docs/ and a pointer here. Never list the checks here: the generated catalogue
does. Delete this comment.
-->

Short on purpose: each rule has one home, linked here. A rule that belongs in a linked doc goes there, not here. A new
check never needs an edit to this file.

## Session start

- Read [`docs/STATUS.md`](./docs/STATUS.md) first: what is deployed, what runs, what is next, what waits for a person.
- Then [`docs/README.md`](./docs/README.md), the map of the docs.
- The backlog is one file per item under `docs/backlog/`. The indexes are generated: edit the item file, run
  `python3 -I scripts/backlog_index.py --write` (it rewrites both indexes), commit all three. Cite an item by id, as in
  "backlog 12".

## Rules for every change

- **Run every check before every commit:** `sh scripts/run-gates.sh`. Green is `ALL GREEN` with exit 0. A partial run
  (`--fast`, `--only`) is not a pass. What each check enforces is [`docs/checks.md`](./docs/checks.md), generated from the
  gate list and the script headers. A new check: write its header, add one line to `scripts/gates.list`, run
  `python3 -I scripts/docs_catalogue.py --write`; no other doc is edited.
- **Code describes only its current state.** A comment, test name or user-visible string gives a reason, in present
  tense, plus the item id. History (dates, commit hashes, "used to", incident stories, which agent or round found it)
  is written straight into the item, or the archive for a long note, and is linked, never retold in the code. Rule and examples:
  [`docs/guides/history-in-comments.md`](./docs/guides/history-in-comments.md).
- **When the same problem shows up twice, stop patching instances.** Find the root cause and fix the class by
  construction: a check that makes it unable to recur. Existing debt goes in a shrink-only baseline.
- **One home per rule.** When you are about to paste a rule into a second file, link it instead.
- **Rules and procedures live in this repository,** in this file or under `docs/`, never only in a chat, a session or a
  home directory. A rule an agent learned and wrote nowhere is lost with the session.
- **Decisions in force** are in [`docs/decisions.md`](./docs/decisions.md). Do not reopen one without the owner (the person
  who decides; on a solo project, you).

## Conventions

- Commits: <your commit convention>, with a body that says why and cites the item id.
- <One line per other rule that applies to every change, each linking to its home.>
