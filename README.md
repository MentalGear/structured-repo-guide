# structured-repo-guide

A language-agnostic guide to keeping a repository structured, in two halves:

- **[Documentation](./documentation/README.md):** the docs and comments state the current state only. Every rule has
  one home, generated pages are checked for freshness, history lives in version control and the tracker and is linked
  by id, and comments that narrate history are archived, linked or folded away.
- **[Security](./security/README.md):** a supply-chain playbook for Cargo, npm/pnpm and pip side by side, a threat
  model, a controls table that a script keeps true, vulnerability reporting, and rules for automated agents.

Both halves follow one principle: when a problem shows up twice it is a class, so fix it with a check that makes the
class unable to recur, and put the existing debt in a baseline that can only shrink.

## Start here

| You want to | Go to |
|---|---|
| Clean up a repository full of stale docs and history comments | [`documentation/cleanup-playbook.md`](./documentation/cleanup-playbook.md) |
| Learn the comment rule (archive / link / fold) | [`documentation/history-in-comments.md`](./documentation/history-in-comments.md) |
| Set up docs for a new repository | [`documentation/README.md`](./documentation/README.md), "Adopt it in five minutes" |
| Lock down dependencies and builds | [`security/README.md`](./security/README.md), "Adopt it in five minutes" |
| Copy a file | [`templates/`](./templates/) |

## Run the examples

Everything runnable needs only `sh` and Python 3 (3.11 or newer for the security pin checker, which reads TOML):

```sh
sh examples/documentation/run-all.sh   # ends with ALL GREEN
sh examples/security/run-examples.sh   # ends with examples/security: ALL OK
```

Each script has a `--self-test` that plants violations in a throwaway tree and proves the check goes red on them.

## Layout

```text
documentation/   the clean-documentation method
security/        the supply-chain and reporting method
examples/        runnable checks and a sample tree for each half
templates/       AGENTS.md, STATUS.md, SECURITY.md, a backlog item, a decisions index
```
