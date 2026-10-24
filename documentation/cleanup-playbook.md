# Cleanup playbook

**What this is for.** A step-by-step method for a one-time cleanup of a repository whose docs and comments are full of
history: landing logs, dated status paragraphs, incident stories, finished research, comments that say "used to".
Use it once, then let the checks keep the repository clean. Every step ends with a verification, because a cleanup
that cannot be verified is a rewrite.

**Before you start.** You need `git` (the playbook uses `git ls-files`, `git grep` and `git mv`), `sh`, `awk` and Python 3.8
or newer (standard library only; the tested versions are in [the prerequisites](./README.md#prerequisites)). The words
**owner**, **helper** (a person or an agent who does one piece of the cleanup, which is split into **work streams**: pieces
with disjoint sets of files, each handed to one helper), **check**, **gate**, **runner**, **baseline**, **ratchet** and
**entry file** are defined once, in [the guide's word list](./README.md#words-used-in-this-guide).

## Contents

- [Ground rules](#ground-rules)
- [Step 0: measure](#step-0-measure)
- [Step 1: install the guards first](#step-1-install-the-guards-first)
- [Step 2: inventory the docs](#step-2-inventory-the-docs)
- [Step 3: choose the target layout](#step-3-choose-the-target-layout)
- [Step 4: move and archive](#step-4-move-and-archive)
- [Step 5: trim the living docs](#step-5-trim-the-living-docs)
- [Step 6: the entry file, decisions, status and catalogue](#step-6-the-entry-file-decisions-status-and-catalogue)
- [Step 7: sweep the comments](#step-7-sweep-the-comments)
- [Step 8: split the tracker](#step-8-split-the-tracker)
- [Step 9: final verification and review](#step-9-final-verification-and-review)
- [Staying clean](#staying-clean)
- [Ground rules for delegating](#ground-rules-for-delegating)

## Ground rules

- **History is not deleted. It is moved and linked.** Version control keeps every deleted line. The archive keeps what
  code still cites.
- **Archive what anything still cites.** Delete only pure duplicates and notes that a later note fully supersedes.
- **A living doc keeps its path and the headings that something cites.** A cleanup that breaks citations has made the
  repository worse.
- **One step per commit.** A step is reviewable and revertible. The commit message names the step and the evidence.
- **Verify after every step.** The verification is in the step. A step is not done until it passes.
- **The owner decides what is deleted.** Report the large files with a proposed plan. Do not guess. (On a solo project the
  owner is you: write the plan down anyway, because the plan is what the verification checks.)
- **Nobody deletes remote branches or published artifacts as part of a docs cleanup.** That needs its own approval.

## Step 0: measure

Record a baseline before any change. It is what the cleanup is judged against, and it cannot be recovered later.

```sh
git ls-files '*.md' | xargs wc -c | sort -n | tail -30                  # the biggest docs
git ls-files '*.md' | wc -l                                              # how many docs
git ls-files '*.md' | xargs cat | wc -c                                  # total bytes of docs
sh scripts/check-history-comments.sh --inventory 2>&1 >/dev/null | tail -1  # history lines in code (after step 1)
sh scripts/check-comment-refs.sh --inventory 2>&1 >/dev/null | tail -1      # dead citations in code (after step 1)
```

Write the numbers into the tracker item that owns the cleanup. The same commands run at the end show the change.

If there is no tracker yet, this item is the first one. Create it as a file: copy
[`../templates/backlog-item.md`](../templates/backlog-item.md) to `docs/backlog/001-docs-cleanup.md` (`NNN-slug.md`: the
number zero-padded to three digits, a few lower-case words), title it, set `updated`, and paste the numbers into its
`## Status`. The template is ready to run as item 1. The indexes come in Step 1, when the generator is installed
(`python3 -I scripts/backlog_index.py --write`, which writes both `docs/backlog.md` and `docs/backlog-done.md`); see
[`tracker-as-files.md`](./tracker-as-files.md#creating-the-first-item).

**Verify:** the numbers are in the item.

## Step 1: install the guards first

Install the checks before moving anything. They freeze the debt, so it cannot grow while the cleanup runs, and they catch
every citation the moves break.

1. Add the scripts from [`../examples/documentation/`](../examples/documentation/README.md): the link checker, the
   history check, the reference check, and the runner with its gate list
   ([`gate-runner.md`](./gate-runner.md)). List every check in `scripts/gates.list`, so the runner is the one command that
   runs them. Without a runner there is no "run every check", and the rest of the playbook has nothing to verify with.
2. Create the baselines: `sh scripts/check-history-comments.sh --update-baseline`,
   `sh scripts/check-comment-refs.sh --update-baseline` and `sh scripts/check-dated-headings.sh --update-baseline` (the dated
   headings of the living docs, which Step 5 trims). The first run on a large tree prints hundreds of lines. That is the
   debt, and now it is counted.
3. Run `sh scripts/check-doc-links.sh`. The link checker has no baseline, so there is nothing to freeze: **fix the broken links.**
   They are cheap to fix. If the tree has hundreds because nobody ever checked, fix them by directory in the order of Step 4
   and, until a directory is done, pass it as `--skip docs/that-directory/` in the gate list line; each skip is deleted when its
   directory is fixed, and the line ends with no skip at all.
4. Commit: "chore: add the history, reference and link checks with baselines".

**Verify:** the runner is green (`sh scripts/run-gates.sh`, exit 0, `ALL GREEN`). Plant a violation (`# used to be 3` in a source file) and see it go red. Remove it.
See [`ratchets.md`](./ratchets.md).

## Step 2: inventory the docs

Make a table: one row per document. Then give each row a verdict.

| Path | KB | Cited by | Verdict | Target |
|---|---|---|---|---|
| `docs/plan.md` | 41 | 3 docs, 12 comments | trim | `docs/plan.md` (dated paragraphs to archive) |
| `docs/notes-2025-q1.md` | 18 | 0 | archive | `docs/archive/notes-q1.md` |
| `docs/old-faq.md` | 4 | 0 | delete | (duplicate of `docs/faq.md`) |

How to fill it:

- **Cited by:** `git grep -c '<file name>'` over the whole tree. A doc cited from code cannot be deleted, only archived.
- **Verdict**, one of:

  | Verdict | Meaning |
  |---|---|
  | **keep** | Current rules or recipes. No change, or a link fix. |
  | **trim** | Has a current core wrapped in history (dated status paragraphs, diaries). Keep the core, archive the rest. |
  | **archive** | Finished and still cited. Move whole. |
  | **delete** | A pure duplicate, or superseded by a note that says everything it said. |

- **Big files get a plan.** Anything over the threshold in [`layout.md`](./layout.md#sizes) is reported to the owner with
  a proposed split and the headings that must stay.
- **Research notes** keep only if an open item backs them. Everything else is archive or delete.
- **Check the claim before you mark "delete".** Run the diff for duplicates (`cmp`), `git grep` for readers (is this
  file's only reader the thing next to it?).

**Verify:** every doc has a verdict and a target. The owner has seen the delete list and the over-threshold list.

## Step 3: choose the target layout

Use the tree in [`layout.md`](./layout.md). Write it down in the cleanup item before you move anything, with the
decision for each directory: which directories exist, which are new, which are removed. Include the rule for
what each directory holds, so later helpers do not reopen it.

**Verify:** the item contains the target tree and the per-directory rule.

## Step 4: move and archive

One commit per group of related moves (a series of research notes, finished rounds, one-off scripts).

For each group:

1. `git mv` the files to `docs/archive/<group>/`. A move keeps `git log --follow` working.
2. Rewrite every citation of the old paths in the same commit:

   ```sh
   git grep -l 'docs/research/old-name' | xargs sed -i 's#docs/research/old-name#docs/archive/research/old-name#g'
   ```

3. Prove no stale citation is left: `git grep -n 'docs/research/old-name'` prints nothing.
4. Add the archive banner to each moved file: "Historical. Check the date before acting on anything here."
5. Add the group to the archive's index.
6. Run the runner (`sh scripts/run-gates.sh`).

**Verify, every commit:** `git grep` on each old path is empty; the link checker is green; the reference check is green
or only shows baselined entries; the dead-reference baseline shrank where the moves fixed citations
(`--update-baseline`, commit the lower numbers).

## Step 5: trim the living docs

For each "trim" row:

1. Copy the dated, historical parts into an archive file named for what they are (`archive/rounds/plan-landing-log.md`).
2. Cut them from the living doc. Keep the current rules, recipes and the headings that are cited.
3. Replace "finished phase" paragraphs with one line and a link to the pull request or the item.
4. Replace measurement stories with the current number, and link the evidence.
5. Under a cited heading whose story moved, leave a pointer: "Moved to `archive/...`".
6. Lock the drop in: `sh scripts/check-dated-headings.sh --update-baseline`, committed with the trim.

**Verify:** the doc's size dropped to the target. Every cited heading still exists (`git grep` for each heading name that
a comment cites). The link checker is green. Skim the result as a new reader: nothing should require knowing the past.

## Step 6: the entry file, decisions, status and catalogue

The entry file is usually where the most history and the most copies sit, and it is also where the decisions in force and the
current state are hidden. This step pulls those three things apart, each to its home.

1. **Harvest the decisions.** Read the entry file and the old docs for sentences that are standing decisions: "we do not ship an
   editor", "deploys are manual until the owner says otherwise", "never delete a branch without asking". Write each as one line of
   `docs/decisions.md` ([`../templates/decisions.md`](../templates/decisions.md)): the decision in present tense, its date if
   known, and a link to the item or doc that carries the reasoning (create the item if there is none). A decision that was
   reversed does not go in; it stays in its item. Then delete the sentence from where you found it, or replace it with
   "see `docs/decisions.md`". Ask the owner about every line you are unsure of.
2. **Move every rule to its home** ([`principles.md`](./principles.md#2-one-home-per-rule)): build rules to the contributor guide,
   tool traps to the guide for that tool, process rules to the process doc.
3. **Rewrite the status page.** Do not edit the old one into shape; write a new `docs/STATUS.md` from
   [`../templates/STATUS.md`](../templates/STATUS.md). Fill it from facts you can check now (what is deployed: ask the deployment;
   what runs and what is next: the tracker; what waits: the owner), and archive the old status text whole (the moves of [Step 4](#step-4-move-and-archive) apply).
   The old one is mostly landing logs, and a landing log is history.
4. **Leave in the entry file:** the session-start pointer, the rules that apply to every change in a line or two each, the commit
   convention, and pointers. Copy [`../templates/AGENTS.md`](../templates/AGENTS.md) for the shape and adapt it.
5. **Replace the list of checks** with the generated catalogue ([`generated-docs.md`](./generated-docs.md)). Add the header
   description to each check script, the comment above each command gate in `scripts/gates.list`, then run the generator.
6. Add the freshness check and the placeholder check to `scripts/gates.list` (the runner runs them like any other).

**Verify:** the entry file fits on one screen or close. Every removed rule appears in exactly one other place (`git grep`
a distinctive phrase). Every decision in `decisions.md` links to something that exists, and the entry file holds none that it does
not list. `docs/STATUS.md` has a "Last updated" line and no placeholders (`sh scripts/check-placeholders.sh`). The catalogue
lists every check script (`ls scripts/check-*.sh | wc -l` matches the entry count). The freshness check is green, and goes red if
you edit a script header without regenerating.

## Step 7: sweep the comments

Do this last among the large steps, because the moves above fix many dead citations for free.

0. **Stop the inflow first.** Put the standing order in the entry file and in the brief of every helper of this step (and of
   every later one): "Code describes only its current state. The story goes straight into the tracker item's status or
   detail, or the archive, linked by id." A sweep without it races the writers it is cleaning up after
   ([prevention](./history-in-comments.md#prevention-say-the-order-where-the-writer-reads-it)).
1. Get the worklist: `sh scripts/check-history-comments.sh --inventory > sweep.txt`. Each line is `file:line  reason  text`.
2. Work file by file, or hand a closed list of files to each helper (one work stream per set of directories, see
   [delegating](#ground-rules-for-delegating)). For each line apply
   [archive, link, fold](./history-in-comments.md#the-three-moves):
   - the story goes to the item (create it if needed),
   - the comment cites the item by id,
   - the lasting reason stays, in present tense,
   - a comment with nothing to fold is deleted.
3. After each batch: `sh scripts/check-history-comments.sh --update-baseline`. Commit the lower numbers with the batch.
4. Fix dead citations as you meet them: `sh scripts/check-comment-refs.sh --inventory` lists them. The old path becomes the new path,
   or the id of the item that now holds the story.
5. Mark the lines that are right as written (`history-ok: <reason>`), and nothing else.
6. **Route stale facts, do not fix them silently.** A sweep reads every comment and finds claims that are wrong now: a count
   that no longer matches, a reference to a file that is gone, a setting that was retired. The sweep owns comments, not
   those facts. Add a reference check (`check-comment-refs.sh` covers paths and ids) or a tracker item for each, and keep
   the rewritten comment true by pointing at the item.
7. **When the scanner learns a form, grow the baseline once on purpose** (`--update-baseline --allow-grow`, the reason in
   the commit), then shrink it again with the sweep ([teaching the scanner](./history-in-comments.md#teaching-the-scanner-a-new-shape)).
8. **After the scanner reads zero, schedule cold reads.** A scanner cannot certify zero: a reviewer reads every comment of a
   sample by meaning ([cold reads](./history-in-comments.md#cold-reads-a-scanner-cannot-certify-zero)). Each finding that fits
   a pattern becomes a scanner rule with a self-test case, a sentence to flag and a close one not to flag. Draw each sample with
   a new seed, and also read every comment line the latest batch added: late history sits in rationale prose that helpers wrote
   fresh. Stop when a fresh-seed sample finds about none and the lines of the latest batch hold none (the rate fell from about 21
   to 3 to 2.2 per 1,000 comment lines over three reads in the worked example).
9. **Cover the text that is not a comment:** comments in embedded strings and HTML, and names (test titles, test function
   names, test file names), the last under a zero-tolerance gate with no baseline
   ([text that is not a comment](./history-in-comments.md#text-that-is-not-a-comment)).

**Verify, every batch:**

- The behaviour of the code is unchanged. The sweep touches comments only. Run the build and tests. For a stronger check,
  compare the code with comments stripped, before and after, and require equality
  (for a language with a formatter, format first).
- **The tree still parses.** A comment edit can break the build without touching code: a stray `*/` left a test file
  unparseable, and the test runner silently loaded zero files and reported green. Every comment-only batch runs a parse
  check before it hands back: compile, lint, or the test runner's list mode with an expected file count.
- The history check shows the lower count, and nothing rose.
- A sample of 10 changed comments, read as a stranger: does each state a reason or nothing?

Delegating this step is safe. The edits are mechanical, the file lists are closed and the checks verify the result. The
cold reads (item 8) are the exception: they are judgment, and they go to a reader who did not rewrite that sample.

## Step 8: split the tracker

If the tracker is one big file, do [`tracker-as-files.md`](./tracker-as-files.md#migrating-a-single-backlog-file) now.
Trim the done items to a summary plus the landing commit. Keep the section headings, which the check requires.

**Verify:** every id that a comment cites resolves (the reference check). The index check is green. The old backlog
file is replaced by the generated index and every old link lands on it.

## Step 9: final verification and review

1. Run the full runner, `sh scripts/run-gates.sh`, with no hiding option. Require `ALL GREEN` and exit 0 on the whole tree, not
   only the fast checks.
2. Re-run the Step 0 commands. Put before and after in the cleanup item: docs count, total bytes, biggest file, history
   lines, dead citations.
3. Read the docs map as a new contributor. Open each row. Does every row's one-line description match the file?
4. Plant a violation of each check and see it go red: a dated comment, a dead citation, a broken link, a stale generated
   page, an index edit by hand.
5. Have somebody who did not do the cleanup review it. The question: what in here would I have to ask someone about?
6. Check `docs/STATUS.md` against the repository as it now is (it was rewritten in Step 6; the moves since may have changed
   what is true). Close the cleanup item with the landing commit.

## Staying clean

The cleanup is one-time. The checks make it permanent, by construction:

| What would regress | What stops it |
|---|---|
| A comment retells history | History check (ratchet). New lines fail. |
| A comment cites a missing item or path | Reference check. |
| A doc link breaks after a move | Link checker. |
| The checks list goes stale | Generated catalogue plus freshness check. |
| A check exists that nobody runs | The runner fails when a `scripts/check-*.sh` is not in its list. |
| A doc is added and not found by anyone | Doc-map check: every doc under `docs/` is reachable from the map. |
| A status paragraph grows a date | Dated-heading ratchet. |
| The backlog index lies | Index freshness check. |
| Debt creeps back after a sweep | The stale rule: a count that fell must be locked in. |
| Finished research piles up | Review rule: notes without an open item are archived; see [`layout.md`](./layout.md). |
| The entry file grows | One screen is the limit. A rule in a second place is a copy. |

As counts reach zero, delete the baseline and make the check absolute.

## Ground rules for delegating

A cleanup splits well. Split it into work streams with disjoint file sets, hand each to one helper, and say which files each
stream owns and may not touch.

- **Read-only inventories and audits** (Step 0, Step 2 draft): fit a small, fast model.
- **Mechanical edits with a closed file list and a verifying check** (Step 4 moves, Step 7 sweeps): fit a small model
  too. The check is the reviewer.
- **Design and judgment** (Step 3 layout, Step 5 trims of big docs, new checks): keep with a stronger model or a person.
- **Serialize only for a reason you can name:** two streams edit the same file, or one needs the other's output. Run the full
  runner once at the end of a batch, not in every stream (a helper runs `--fast`; see
  [`gate-runner.md`](./gate-runner.md#making-the-full-run-affordable)).
- **Capture the baseline before dispatching.** It cannot be recovered afterwards.
- **Delegate a comment sweep by disjoint comment trees:** one stream per set of directories, so no two edit the same file.
- **Keep exactly one owner for the scanner and its baseline.** Streams read the inventory and fix lines. Only the owner changes
  a pattern or runs `--update-baseline`, once per batch on the merged tree, so streams never fight over the baseline file.
- **Generated files need a merge driver before the first parallel batch.** When several streams each add a tracker item or a
  measured entry, the generated index and the generated table conflict on every merge. Declare a git merge driver for each in a
  committed `.gitattributes` and register it from the session-setup hook, so no stream or merge owner resolves them by hand
  ([`generated-docs.md`](./generated-docs.md#generated-files-and-parallel-merges)).
- **Every brief carries the standing order** about history, verbatim, and every comment-only stream ends with a parse check
  ([Step 7](#step-7-sweep-the-comments)). A brief that omits either gets a stream that adds the debt it is asked to remove.
