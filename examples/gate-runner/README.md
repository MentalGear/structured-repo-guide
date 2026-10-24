# Example: the gate runner

**What this is for.** The one command that runs every check of a repository, shared by both halves of this guide. Copy
`run-gates.sh` and `gates.list` into your repository's `scripts/` and edit the list. The runner needs only POSIX `sh` and
`awk` (`git` is optional). The contract and the reasoning are in
[`../../documentation/gate-runner.md`](../../documentation/gate-runner.md).

| File | What it is |
|---|---|
| [`run-gates.sh`](./run-gates.sh) | The runner. Reads `gates.list` beside it, runs every gate, exits 0 only for a full green run (`ALL GREEN`), 1 for a red gate, 2 for bad usage or a `scripts/check-*.sh` missing from the list, 3 for a green but partial run. Has `--only`, `--skip`, `--fast`, `--stop-on-fail`, `--no-reuse`, `--list` and `--self-test`. |
| [`gates.list`](./gates.list) | A starting list: the documentation half's eight checks. Yours also holds the security half's checks, your own, and plain commands. |

```sh
sh examples/gate-runner/run-gates.sh --self-test      # builds throwaway trees and proves every promise; ends with OK
sh scripts/run-gates.sh --help                        # in your repository, after the copy
```

The runner is path-relative: its tree is the parent of its own directory, so a copy at `scripts/run-gates.sh` runs the gates
of the repository that holds it. `examples/documentation/sample/scripts/run-gates.sh` is such a copy, and
`examples/documentation/run-all.sh` fails if it drifts from this file.
