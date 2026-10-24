# Cleanup playbook

**What this is for.** A step-by-step method for a one-time cleanup of a repository whose docs and comments are full of
history: landing logs, dated status paragraphs, incident stories, finished research, comments that say "used to".
Use it once, then let the checks keep the repository clean. Every step ends with a verification, because a cleanup
that cannot be verified is a rewrite.

## Contents

- [Ground rules](#ground-rules)
- [Step 0: measure](#step-0-measure)
- [Step 1: install the guards first](#step-1-install-the-guards-first)
- [Step 2: inventory the docs](#step-2-inventory-the-docs)
- [Step 3: choose the target layout](#step-3-choose-the-target-layout)
- [Step 4: move and archive](#step-4-move-and-archive)
- [Step 5: trim the living docs](#step-5-trim-the-living-docs)
- [Step 6: shrink the entry file and generate the catalogue](#step-6-shrink-the-entry-file-and-generate-the-catalogue)
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
- **The owner decides what is deleted.** Report the large files with a proposed plan. Do not guess.
- **Nobody deletes remote branches or published artifacts as part of a docs cleanup.** That needs its own approval.

## Step 0: measure

Record a baseline before any change. It is what the cleanup is judged against, and it cannot be recovered later.

```sh
git ls-files '*.md' | xargs wc -c | sort -n | tail -30                  # the biggest docs
git ls-files '*.md' | wc -l                                              # how many docs
git ls-files '*.md' | xargs cat | wc -c                                  # total bytes of docs
sh scripts/check-history-comments.sh --inventory 2>&1 | tail -1          # history lines in code (after step 1)
sh scripts/check-comment-refs.sh --inventory 2>&1 | tail -1              # dead citations in code (after step 1)
```

Write the numbers into the tracker item that owns the cleanup. The same commands run at the end show the change.

**Verify:** the numbers are in the item.

## Step 1: install the guards first

Install the checks before moving anything. They freeze the debt, so it cannot grow while the cleanup runs, and they catch
every citation the moves break.

1. Add the scripts from [`../examples/documentation/`](../examples/documentation/README.md): the link checker, the
   history check, the reference check. Wire them into the one entry point that runs the checks.
2. Create the baselines: `check-history-comments.sh --update-baseline`, `check-comment-refs.sh --update-baseline`.
   The first run on a large tree prints hundreds of lines. That is the debt, and now it is counted.
3. Run `check_doc_links.py`. Fix or baseline broken links. (A link checker has no baseline in the examples. Fix them;
   broken links are cheap to fix.)
4. Commit: "chore: add the history, reference and link checks with baselines".

**Verify:** the entry point is green. Plant a violation (`# used to be 3` in a source file) and see it go red. Remove it.
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
what each directory holds, so later lanes do not reopen it.

**Verify:** the item contains the target tree and the per-directory rule.

## Step 4: move and archive

One commit per group of related moves (carousel research, finished rounds, one-off scripts).

For each group:

1. `git mv` the files to `docs/archive/<group>/`. A move keeps `git log --follow` working.
2. Rewrite every citation of the old paths in the same commit:

   ```sh
   git grep -l 'docs/research/old-name' | xargs sed -i 's#docs/research/old-name#docs/archive/research/old-name#g'
   ```

3. Prove no stale citation is left: `git grep -n 'docs/research/old-name'` prints nothing.
4. Add the archive banner to each moved file: "Historical. Check the date before acting on anything here."
5. Add the group to the archive's index.
6. Run the checks.

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

**Verify:** the doc's size dropped to the target. Every cited heading still exists (`git grep` for each heading name that
a comment cites). The link checker is green. Skim the result as a new reader: nothing should require knowing the past.

## Step 6: shrink the entry file and generate the catalogue

The entry file is usually where the most history and the most copies sit.

1. Move every rule to its home ([`principles.md`](./principles.md#2-one-home-per-rule)): build rules to the contributor
   guide, tool traps to the guide for that tool, process rules to the process doc.
2. Leave in the entry file: the session-start pointer, the rules that apply to every change in a line or two each, the
   commit convention, and pointers.
3. Replace the list of checks with the generated catalogue ([`generated-docs.md`](./generated-docs.md)). Add the header
   description to each check script, then run the generator.
4. Add the freshness check to the entry point.

**Verify:** the entry file fits on one screen or close. Every removed rule appears in exactly one other place (`git grep`
a distinctive phrase). The catalogue lists every check script (`ls scripts/check-* | wc -l` matches the entry count).
The freshness check is green, and goes red if you edit a script header without regenerating.

## Step 7: sweep the comments

Do this last among the large steps, because the moves above fix many dead citations for free.

1. Get the worklist: `check-history-comments.sh --inventory > sweep.txt`. Each line is `file:line  reason  text`.
2. Work file by file, or hand a closed list of files to each helper. For each line apply
   [archive, link, fold](./history-in-comments.md#the-three-moves):
   - the story goes to the item (create it if needed),
   - the comment cites the item by id,
   - the lasting reason stays, in present tense,
   - a comment with nothing to fold is deleted.
3. After each batch: `check-history-comments.sh --update-baseline`. Commit the lower numbers with the batch.
4. Fix dead citations as you meet them: `check-comment-refs.sh --inventory` lists them. The old path becomes the new path,
   or the id of the item that now holds the story.
5. Mark the lines that are right as written (`history-ok: <reason>`), and nothing else.

**Verify, every batch:**

- The behaviour of the code is unchanged. The sweep touches comments only. Run the build and tests. For a stronger check,
  compare the code with comments stripped, before and after, and require equality
  (for a language with a formatter, format first).
- The history check shows the lower count, and nothing rose.
- A sample of 10 changed comments, read as a stranger: does each state a reason or nothing?

Delegating this step is safe. The edits are mechanical, the file lists are closed and the checks verify the result.

## Step 8: split the tracker

If the tracker is one big file, do [`tracker-as-files.md`](./tracker-as-files.md#migrating-a-single-backlog-file) now.
Trim the done items to a summary plus the landing commit. Keep the section headings, which the check requires.

**Verify:** every id that a comment cites resolves (the reference check). The index check is green. The old backlog
file is replaced by the generated index and every old link lands on it.

## Step 9: final verification and review

1. Run the full entry point. Require green on the whole tree, not only the fast checks.
2. Re-run the Step 0 commands. Put before and after in the cleanup item: docs count, total bytes, biggest file, history
   lines, dead citations.
3. Read the docs map as a new contributor. Open each row. Does every row's one-line description match the file?
4. Plant a violation of each check and see it go red: a dated comment, a dead citation, a broken link, a stale generated
   page, an index edit by hand.
5. Have somebody who did not do the cleanup review it. The question: what in here would I have to ask someone about?
6. Update the status page. Close the cleanup item with the landing commit.

## Staying clean

The cleanup is one-time. The checks make it permanent, by construction:

| What would regress | What stops it |
|---|---|
| A comment retells history | History check (ratchet). New lines fail. |
| A comment cites a missing item or path | Reference check. |
| A doc link breaks after a move | Link checker. |
| The checks list goes stale | Generated catalogue plus freshness check. |
| The backlog index lies | Index freshness check. |
| Debt creeps back after a sweep | The stale rule: a count that fell must be locked in. |
| Finished research piles up | Review rule: notes without an open item are archived; see [`layout.md`](./layout.md). |
| The entry file grows | One screen is the limit. A rule in a second place is a copy. |

As counts reach zero, delete the baseline and make the check absolute.

## Ground rules for delegating

A cleanup splits well. Split it into lanes with disjoint file sets, and say which files each lane owns and may not touch.

- **Read-only inventories and audits** (Step 0, Step 2 draft): fit a small, fast model.
- **Mechanical edits with a closed file list and a verifying check** (Step 4 moves, Step 7 sweeps): fit a small model
  too. The check is the reviewer.
- **Design and judgment** (Step 3 layout, Step 5 trims of big docs, new checks): keep with a stronger model or a person.
- **Serialize only for a reason you can name:** two lanes edit the same file, or one needs the other's output. Run the
  checks once at the end of a batch, not in every lane.
- **Capture the baseline before dispatching.** It cannot be recovered afterwards.
