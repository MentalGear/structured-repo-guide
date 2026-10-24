# The gate runner: one command, one list

**What this is for.** One command that runs every check of the repository and answers one question: is this exact tree
green? Use it when you adopt the first check, when a second half of this guide (or any second set of checks) arrives, and
when the full run has become too slow to run before every commit.

The words *check*, *gate*, *runner* and *gate list* are defined once, in
[Words used in this guide](./README.md#words-used-in-this-guide). The runner is
[`../examples/gate-runner/run-gates.sh`](../examples/gate-runner/run-gates.sh).

## Contents

- [The problem](#the-problem)
- [The contract](#the-contract)
- [The gate list](#the-gate-list)
- [Adding a gate](#adding-a-gate)
- [One runner for both halves](#one-runner-for-both-halves)
- [Making the full run affordable](#making-the-full-run-affordable)
- [A tool that reports problems and exits 0](#a-tool-that-reports-problems-and-exits-0)
- [What the runner does not do](#what-the-runner-does-not-do)
- [Proving the runner](#proving-the-runner)

## The problem

Without one runner, three things go wrong, and each of them has happened:

- **A check exists that nobody runs.** A script is added and its author runs it by hand. A year later it has been red for
  months.
- **Two lists.** Each set of checks brings its own list, and a repository that adopts both has two commands. A contributor
  runs one of them. Worse, each list refuses to run because the other half's checks are not in it.
- **A green with no address.** "The checks pass" is true of some tree. Quoted in a review, it is read as true of the one
  under review.

All three have one cause: the answer to "what is the gate" is spread over people's habits. The construction below puts it in
one list, one command and one summary line that says what tree it is about.

## The contract

`sh scripts/run-gates.sh` reads `scripts/gates.list`, runs every gate in order, keeps going after a red one so a single run
shows every red gate, and prints a summary.

| Exit | Meaning |
|---|---|
| `0` | Every listed gate ran and passed. The last line is `ALL GREEN: ...`. The only exit that is a pass. |
| `1` | At least one gate is red. The summary names it, and the tail of its log is printed. |
| `2` | Bad usage: an unknown option, a bad or empty list, a duplicate name, or a `scripts/check-*.sh` that is not in the list. Nothing was run. |
| `3` | Every gate that ran passed, but some were hidden by `--only`, `--skip` or `--fast`. The last line says `PARTIAL`. Never a pass. |

`--stop-on-fail` stops at the first red gate and so exits `1`; when no gate is red it has hidden nothing, and the run is a full
one (`0`, `ALL GREEN`). Only the three hiding options can produce exit `3`. A signal (hangup, interrupt, terminate) ends the run
with `129`, `130` or `143`: the cleanup runs, nothing is summarised as green, and the run is never a pass.

Six guarantees, each tested by the runner's own `--self-test`:

1. **No check is left out.** A `scripts/check-*.sh` that no gate names fails the run with exit 2. A forgotten registration is red,
   not silent, which is why the list can be trusted as the single source.
2. **A partial run cannot pass.** `--only`, `--skip` and `--fast` turn a green into exit 3 and the word `PARTIAL`. `ALL GREEN` is printed
   only by a full run.
3. **The summary names the tree.** It prints the git `HEAD` and a hash of every uncommitted change (the diff plus the
   untracked files), or says `not a git repo`. A green quoted for a commit that has since moved can be told apart.
4. **A red gate is shown, not summarised.** The log tail of every red gate is printed at once. Logs of a green run are
   removed; with `--log-dir DIR` they are kept.
5. **Reuse is conservative** (below): only a PASS is stored, only for byte-identical inputs, and never for a tree that
   changed while the gate ran.
6. **An exit status can be wrong, and a signal is not a pass.** A gate tagged `fail-on:REGEX` is red when its output matches,
   whatever its exit status says (below), and a killed runner exits non-zero without printing `ALL GREEN`.

The rule for people and agents is one sentence, and it belongs in the entry file: run the runner before every commit; green is
`ALL GREEN` with exit 0, and a partial run is not a pass.

## The gate list

`scripts/gates.list` is a plain text file, one gate per line:

```text
# group: Source hygiene
check-no-tabs|sh scripts/check-no-tabs.sh
# group: Build
# Runs every unit test of the project. It takes minutes, so contributors skip it while editing and the full run keeps it.
test slow reuse:src,Cargo.toml|cargo test
```

| Line | Meaning |
|---|---|
| `# group: Title` | A heading. Every gate needs one above it. The catalogue prints the gates under it, in the list's order. |
| `# any other comment` | Directly above a **command** gate: its description. The catalogue prints it. |
| `name\|command` | The gate. The name is letters, digits, `.`, `_`, `-`. The command runs with `sh -c` from the root of the tree. |
| `name tag tag\|command` | Tags after the name, separated by spaces: `slow` (left out by `--fast`), `reuse`, `path-only:GLOB,GLOB`, `reuse:PATH,PATH` (all three below) and `fail-on:REGEX` (below). An unknown tag is bad usage. |

A check script is described by the first paragraph of its own header, so a comment above its line is an error: there would be
two descriptions, and one of them would drift. A command has no header, so its description is the comment above it, and a command
gate without one fails the catalogue's freshness check. The catalogue page is generated from this list and the script
headers ([`generated-docs.md`](./generated-docs.md#list-driven-catalogue)). The list therefore carries the order, the groups
and the tags, and nothing else carries prose.

Never cut the list to make a run faster. Cut the *run* (`--fast`, `--only`, reuse), not the list: a gate that is not in the list
is a check nobody runs.

## Adding a gate

1. Write `scripts/check-thing.sh`. Its header's first paragraph says what it forbids and why.
2. Add one line to `scripts/gates.list` under its group.
3. Run the catalogue generator (`python3 -I scripts/docs_catalogue.py --write`) and commit all three together.

Nothing else names the gate: not the entry file, not a contributor guide. A second file that mentions the new check is a copy
([`principles.md`](./principles.md#2-one-home-per-rule)).

## One runner for both halves

A repository that adopts the documentation half and the security half has one runner and one list. Both halves ship
`scripts/check-*.sh` wrappers, and the runner's first guarantee covers both: a check of either half that is not listed fails the
run. So adoption is additive:

```text
# group: Documentation
check-history-comments|sh scripts/check-history-comments.sh
check-comment-refs|sh scripts/check-comment-refs.sh
check-doc-links|sh scripts/check-doc-links.sh
check-docs-catalogue|sh scripts/check-docs-catalogue.sh
check-backlog-index|sh scripts/check-backlog-index.sh
check-placeholders|sh scripts/check-placeholders.sh
check-doc-map|sh scripts/check-doc-map.sh
check-dated-headings|sh scripts/check-dated-headings.sh
# group: Security
check-pins|sh scripts/check-pins.sh
check-artifacts|sh scripts/check-artifacts.sh
check-remote-assets|sh scripts/check-remote-assets.sh
check-controls-table|sh scripts/check-controls-table.sh
check-workflow-permissions|sh scripts/check-workflow-permissions.sh
```

The security half's checks are wired in the same way, as lines under their own group. The generated catalogue shows both
groups, in that order, on one page ([`generated-docs.md`](./generated-docs.md#two-halves-one-catalogue)). Two rules keep it
working: there is exactly one `run-gates.sh` and one `gates.list` per repository, and a check is added by a line in the
list, never by a second runner.

## Making the full run affordable

A runner that takes twenty minutes is run once a day, and then the checks guard nothing. Make the full run cheap in three
layers, and keep each one honest.

1. **Reuse a stored PASS for identical inputs.** Tag a slow gate `reuse`. After a real PASS the runner stores it under a key
   made of the gate's name, its command line, its tags, `$GATE_REUSE_SALT` and the bytes of **every file of the tree** (the
   tracked and the untracked-but-not-ignored files of a git repository, else every file; never `.git`, the store or the log
   directory). A later run with the same key prints `reused` and does not run the gate. The store is inside `.git` (or
   `.gate-reuse` outside a repository).
   - **The whole tree is the default, so no input can be forgotten.** The cost is that a change anywhere runs the gate again.
     Cut the cost by naming classes of files whose *content* the gate never reads: `path-only:GLOB,GLOB` counts a matching
     file by its path (so adding, removing or renaming one still changes the key) and ignores its bytes.
     `test slow reuse path-only:*.md,*.png|cargo test` is reused after a documentation or image edit and run after any
     other. Name a class only when you know the gate does not read the contents of those files.
   - **A declared list is narrower and is a claim.** `reuse:PATH,PATH` keys on just those paths plus every file the command
     names (a file or a whole directory). That is the right tool when the gate really reads little and the whole-tree key
     would rerun it constantly, and the wrong one when nobody has checked what it reads: a path left out is a stale PASS
     reused. `sh scripts/run-gates.sh --check-reuse` tests each declaration by running its gate in a copy of the tree that
     holds only the declared files; a gate that fails there reads something undeclared, and the run exits 1. The check finds
     incomplete declarations; it cannot certify one (a gate that tolerates a missing file passes), so prefer the whole-tree
     tag whenever the cost allows. `reuse` and `reuse:PATHS` on one gate is bad usage, and so is `path-only` without `reuse`.
   - Only a PASS is stored. A FAIL deletes the stored PASS, so a flaky gate is never trusted.
   - Any changed byte in any input is a different key. A tree that changed while the gate ran stores nothing.
   - `--no-reuse` (or `GATE_REUSE=0`) trusts no stored result.
   - Put the toolchain version in `GATE_REUSE_SALT` (`GATE_REUSE_SALT="$(cargo --version)"`): it is not a file of the tree.
     A gate that reads something outside the tree (the network, the clock, an installed tool's state) gets no `reuse` tag.
   - Hashing every file costs one hash per file, twice per gate (before and after). On a very large tree, `path-only`
     classes are also the way to keep that short.
2. **Give contributors `--fast`.** Tag the gates that take minutes `slow`. `sh scripts/run-gates.sh --fast` runs everything
   else, in seconds, and exits 3: the contributor sees the cheap checks go red while editing, and the run is plainly not the
   gate. A helper that edits comments or docs runs `--fast` and nothing more.
3. **Run the full runner once, before merge.** The full run, with reuse, on the tree that is about to land, and the push happens
   only on `ALL GREEN` with exit 0. With several contributors or agents working at once, the person who merges runs it per
   batch of changes, not per change: it names the tree it ran on, so it vouches for exactly the batch.

While fixing one red gate, `--only '^check-doc-links$'` runs it alone (exit 3, by design). Run the full runner again before the
commit.

Measure before you tag. A first run with timings (every gate prints its seconds) shows which gates are the slow ones;
usually two or three account for nearly all of it.

## A tool that reports problems and exits 0

The runner trusts an exit status, and some tools report problems on the output while exiting 0: a linter run without its
"warnings are errors" flag, a compiler asked for warnings, a formatter in "report" mode. A gate that wraps one is green while
it complains. Where the tool has a flag that turns the findings into an exit status, use it. Where it has none, tag the gate:

```text
# group: Source hygiene
# Reports every warning but exits 0, so a warning on the output is a failure.
lint fail-on:^warning fail-on:[[:space:]]warn\[|sh scripts/run-lint.sh
```

After the command exits 0, the runner searches its combined output (stdout and stderr) for each `fail-on:` pattern (`grep -E`);
a match makes the gate red, prints the first matching line, and stores no PASS. A non-zero exit is red as before. A tag
holds one pattern with no space and no `|` (the list line is split on both): write a space as `[[:space:]]` and an
alternative as a second `fail-on:` tag. An invalid pattern is bad usage. The tags are part of the reuse key.

## What the runner does not do

- It does not run gates in parallel. A project that needs that runs the runner in several shards with `--only`, and one final
  full run (with reuse) proves the whole.
- It does not replace the remote pipeline. It is the same list, run before the push, so the pipeline and the contributor run
  the same thing.
- It does not trace what a gate reads. The bare `reuse` tag needs no knowledge (the whole tree is the input), a `path-only:`
  class is the author's claim that the contents are not read, and a `reuse:PATHS` list is a claim that `--check-reuse`
  can refute but not prove.

## Proving the runner

```sh
sh examples/gate-runner/run-gates.sh --self-test
```

builds throwaway trees (a copy of the runner beside a list and a few scripts) and requires each promise above to hold: exit codes
0 to 3, the unlisted-check guard (a script counts only when the command runs it), each hiding option, `--stop-on-fail` in a red
and in a green run, bad lists and bad tags, signals (the run ends non-zero, never `ALL GREEN`, and leaves no temporary
directory), `fail-on:` (a match is red under exit 0, a second tag is an alternative), reuse (a PASS reused, a changed input
or salt runs again, a FAIL never stored and deleting a stored PASS, a non-PASS entry never reused, a tree changing under a
running gate storing nothing), the whole-tree key (stable, changed by an edit to any file or a new file, unchanged by an
ignored file, the store or the bytes of a `path-only` class) and `--check-reuse` (a complete declaration holds, one that
omits a file the gate reads is found), and the tree label in and outside a git repository. The runner needs only POSIX `sh` and `awk`; `git` is optional.
