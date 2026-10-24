# structured-repo-guide

A language-agnostic guide to keeping a repository structured, in two halves:

- **[Documentation](./documentation/README.md):** the docs and comments state the current state only. Every rule has
  one home, generated pages are checked for freshness, history lives in version control and the tracker and is linked
  by id, and comments that narrate history are archived, linked or folded away.
- **[Security](./security/README.md):** a supply-chain playbook for Cargo, npm/pnpm and pip side by side, a threat
  model, a controls table that a script keeps true, vulnerability reporting, and rules for automated agents.

Both halves follow one principle: when a problem shows up twice it is a class, so fix it with a check that makes the
class unable to recur, and put the existing debt in a baseline that can only shrink (a ratchet). Every check runs from
one runner, the single command to run before a commit. The words **check**, **gate**, **runner**, **baseline** and
**ratchet** are defined once, in [Words used in this guide](./documentation/README.md#words-used-in-this-guide).

## Start here

| You want to | Go to |
|---|---|
| Clean up a repository full of stale docs and history comments | [`documentation/cleanup-playbook.md`](./documentation/cleanup-playbook.md) |
| Learn the comment rule (archive / link / fold) | [`documentation/history-in-comments.md`](./documentation/history-in-comments.md) |
| Set up docs for a new repository | [`documentation/README.md`](./documentation/README.md), "Adopt it in five minutes" |
| Lock down dependencies and builds | [`security/README.md`](./security/README.md), "Adopt it in five minutes" |
| Run every check from one command | [`documentation/gate-runner.md`](./documentation/gate-runner.md) |
| Copy a file | [`templates/`](./templates/) |

## Prerequisites

- `sh` (POSIX) and `awk`.
- Python 3.8 or newer for the documentation half, standard library only; the scripts are tested on 3.8 to 3.13. The
  security half's pin checker reads TOML and needs Python 3.11 or newer.
- `git` for the adoption paths and the cleanup playbook (they use `git ls-files`, `git grep` and `git mv`); the scripts
  run without it, and use it when present so that `.gitignore` decides what they scan.
- No network, no package install.

## Adopt both halves

Adopting the documentation half and the security half in one repository takes **one runner and one gate list**, not two:

```sh
GUIDE=/path/to/structured-repo-guide        # the same variable in both halves' commands
cp $GUIDE/examples/gate-runner/run-gates.sh $GUIDE/examples/gate-runner/gates.list scripts/
```

1. **One runner.** `scripts/run-gates.sh` runs everything. A second runner, or a second list, means a check that somebody
   forgets to run. Green is `ALL GREEN` with exit 0; a run with any gate hidden (`--fast`, `--only`) exits 3 and is not green.
2. **Every check goes in `scripts/gates.list`.** Both halves ship `scripts/check-*.sh` wrappers; each is one line in the list
   under its own `# group:` heading. The runner refuses to run (exit 2) when a `scripts/check-*.sh` is missing from the list,
   so adopting the second half is additive and a forgotten registration is red.
3. **Never cut the list to make a run faster.** Tag a slow gate `slow` and give contributors `--fast`, store a PASS for gates
   whose inputs did not change (`reuse:`), and run the full runner once before merging
   ([making the full run affordable](./documentation/gate-runner.md#making-the-full-run-affordable)).
4. **One catalogue.** `docs/checks.md` is generated from the list and the script headers, so both halves' checks appear on one
   page under their own headings ([how](./documentation/generated-docs.md#two-halves-one-catalogue)).

Step by step: documentation's [five minutes](./documentation/README.md#adopt-it-in-five-minutes), then the security half's
(`security/README.md`), each adding its lines to the same list. The runner's self-test is
`sh examples/gate-runner/run-gates.sh --self-test`.

## Run the examples

Everything runnable needs only `sh`, `awk` and Python 3 (3.8 to 3.13; 3.11 or newer for the security pin checker, which
reads TOML):

```sh
sh examples/documentation/run-all.sh        # ends with ALL GREEN (includes the runner's self-test)
sh examples/gate-runner/run-gates.sh --self-test
sh examples/security/run-examples.sh        # ends with examples/security: ALL OK
```

Each script has a `--self-test` that plants violations in a throwaway tree and proves the check goes red on them.

## Layout

```text
documentation/   the clean-documentation method, and the runner's contract (gate-runner.md)
security/        the supply-chain and reporting method
examples/        runnable checks and a sample tree for each half, and the one gate runner they share
templates/       AGENTS.md, STATUS.md, SECURITY.md, a backlog item, a decisions index, a history-in-comments page
```
