# Ratchets: shrink-only baselines

**What this is for.** A way to introduce a strict check into a codebase that already violates it. The check is strict
for everything new and patient with what exists, and the allowed debt can only go down. Use it for any check where a
sweep would be too big to do in one change.

## Contents

- [The pattern](#the-pattern)
- [The four rules](#the-four-rules)
- [Three kinds of baseline](#three-kinds-of-baseline)
- [Markers with reasons](#markers-with-reasons)
- [A minimal ratchet in shell](#a-minimal-ratchet-in-shell)
- [Working with baselines](#working-with-baselines)
- [When not to use a ratchet](#when-not-to-use-a-ratchet)
- [Pitfalls](#pitfalls)

## The pattern

A ratchet turns a wish ("no history in comments") into a check that holds, without a flag-day cleanup.

1. Count today's violations. Write them to a **baseline file**, committed with the check.
2. The check compares the tree with the baseline.
3. A **new** violation fails. A file that was clean may not become dirty. A dirty file may not get dirtier.
4. A **fixed** violation also fails, until the baseline is lowered. This is the part that makes it a ratchet: without
   it, the room you cleared would let the same amount of debt creep back in.
5. The baseline grows only with an explicit flag and a reason in the commit.

The debt is visible (it is a file in the repository), measurable (it is a number that goes down), and one-way.

## The four rules

| Rule | What the check does | Why |
|---|---|---|
| **New fails** | Fails on a violation the baseline does not allow. | Stops new debt on the day the check lands. |
| **Stale fails** | Fails when a baselined violation is gone and the baseline still lists it. | Locks every fix in. No headroom. |
| **Growth needs a flag** | `--update-baseline` refuses to raise a count. `--allow-grow` overrides. | Growth is a decision, named in a commit. |
| **A marker needs a reason** | `history-ok: <reason>` exempts one line. No reason, no exemption. | A reviewer can judge the exception. |

All four are tested by the check's `--self-test`: it builds a tree for each rule and requires the right result.

## Three kinds of baseline

| Kind | Entry | Example | Fails when |
|---|---|---|---|
| **Count per file** | `path<TAB>count` | History lines per source file | A count rises, a new file has any, or a count fell. |
| **Set of entries** | `file<TAB>kind<TAB>ref` | Dead citations in comments | An entry appears that is not in the set, or an entry in the set no longer occurs. |
| **A budget number** | `total` | Total test seconds, total KB of docs | The measured total exceeds the budget. Raising it is a one-number diff that states why. |

Choose the kind by what a fix looks like:

- If one violation can be fixed alone, use a **set**. It is exact.
- If violations are interchangeable and only how many matters, use a **count per file**. It conflicts less in review,
  because unrelated edits do not change it.
- If the thing is a quantity, not a list, use a **budget**.

Never store line numbers. They shift on every edit, so the baseline would go red on unrelated changes.

## Markers with reasons

A baseline is for debt nobody has had time to pay. A **marker** is for a line that is not debt: it is right as
written, and the pattern cannot know.

```python
# Upstream's wording, kept verbatim. history-ok: quoted from the library's changelog
```

- The marker names its check (`history-ok:`, `ref-ok:`) and carries a reason.
- Review sees the marker in the diff. A weak reason is a review comment.
- A check can also have a **reasoned allowlist** in its own file: a table of `entry: reason`. The check fails on a stale
  entry, so the list shrinks when the thing it excuses goes away.
- A pattern that fires on innocent text is a bug in the check. Fix the pattern, add the sentence to the self-test. A
  marker is for text that is exempt, not for text the check misreads.

## A minimal ratchet in shell

A count-per-file ratchet for any pattern, in POSIX shell and `awk`. The full version, with a comment extractor and the
other two baseline kinds, is [`../examples/documentation/comment_scan.py`](../examples/documentation/comment_scan.py).

```sh
#!/bin/sh
# check-no-fixme.sh -- the number of FIXME lines per file may only go down
#
# Usage: sh check-no-fixme.sh [--update-baseline]      (from the repository root)
set -eu
baseline=scripts/baselines/fixme.tsv
tab=$(printf '\t')
current=$(mktemp)
trap 'rm -f "$current"' EXIT
grep -rc 'FIXME' src | grep -v ':0$' | sed "s/:\([0-9]*\)\$/$tab\1/" | sort > "$current"   # path<TAB>count

if [ "${1:-}" = "--update-baseline" ]; then
  { echo "# path<TAB>count of FIXME lines; shrink-only"; cat "$current"; } > "$baseline"
  exit 0
fi

# first file: the baseline (its comment line keeps it non-empty); second file: the tree now
awk -F'\t' '
  NR == FNR { if ($0 !~ /^#/) base[$1] = $2; next }
            { now[$1] = $2 }
  END {
    for (p in now) {
      old = (p in base) ? base[p] : 0
      if (now[p] > old) { print p ": " old " -> " now[p] " (new FIXME)"; bad = 1 }
    }
    for (p in base) {
      cur = (p in now) ? now[p] : 0
      if (cur < base[p]) { print p ": baseline " base[p] ", now " cur " (run --update-baseline)"; bad = 1 }
    }
    exit bad
  }' "$baseline" "$current"
```

The first loop is the "new fails" rule, the second is the "stale fails" rule. Growth needs no flag here, because
`--update-baseline` is the only writer and a reviewer sees the diff. The Python version adds the refusal to grow.

## Working with baselines

- **Create** the baseline when the check lands: `--update-baseline` on the current tree. Commit it with the check.
- **Shrink** it as you clean: after a sweep, run `--update-baseline` and commit the lower numbers with the sweep.
- **Grow** it only with `--allow-grow`, and say why in the commit message. Prefer fixing the line or marking it with a
  reason.
- **Sort and one entry per line.** Merges then conflict rarely, and a conflict is easy to resolve: take the lower
  count, then run the check.
- **Review the baseline diff.** A diff that raises a number is a decision. A diff that deletes lines is progress.
- **Aim at empty.** When a baseline is empty, delete the file and make the check absolute. The ratchet has finished its
  job.

## When not to use a ratchet

- **The tree has no violations.** Use a plain check. A baseline would be an empty file that invites debt.
- **The violation is dangerous**, such as a leaked credential. Fix it now. Do not baseline it.
- **You cannot say what a fix looks like.** A ratchet needs a violation that can go away. If the rule is a matter of
  taste, write it down in a guide and leave it to review.

## Pitfalls

- **A baseline that never shrinks.** If the stale rule is off, fixed violations do not lower it, and debt returns
  silently. Keep the stale rule on.
- **A baseline file that is itself scanned.** Exclude it, or the numbers in it trip the pattern.
- **A check that only runs in some jobs.** A ratchet that is skipped on a branch can be outrun on that branch.
  Run it in the one entry point that everyone and every agent runs.
- **Updating the baseline to make the check green.** Shrinking is the only update that needs no explanation. A review
  rule: a baseline change goes with a code change that explains it.
- **No self-test.** The check may be broken in a way that makes it pass. A planted violation proves it can fail.
