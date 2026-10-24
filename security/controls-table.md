# The controls table: how to write one and keep it true

This is the format of the table that lists your security controls, and the check that keeps it honest. Use it when you write
the security section of a repository (the table is the heart of it) and when you add, rename or delete a control script.

A table of controls is a set of claims: "this is checked, by this script, here." A reader plans around those claims. If a
script was renamed, deleted or never written, the claim is false and nobody notices until it matters. The fix is not
discipline, it is a script that parses the table and compares it with the tree on every change. Then the document cannot lie.

## The format

One Markdown table, under a heading that is exactly `## Controls`, with exactly these columns in this order:

| Column | What goes in it |
|---|---|
| ID | `C01`, `C02`, ... Two digits. Unique. Never reused for another control. Other documents refer to controls by this id. |
| Control | One sentence, as a rule that is either kept or broken: "Every dependency is an exact pin, or allowlisted with a reason." |
| Threat it stops | The threat ids from your threat model (`T1`, `T3`) and a few words on what goes wrong without it. |
| Enforcing script | Backticked repository paths of the scripts that enforce it. Or `none` when a tool enforces it (say which tool in Evidence). |
| Config | Backticked repository paths of the settings and data the control reads: the lockfile, `pnpm-workspace.yaml`, an allowlist, a manifest. |
| Runs in | Where it runs. `gates` means a gate in your gate list. Anything else is free text: `session start`, `install command`, `release step`, `none yet`. |
| Status | `enforced`, `manual` or `planned`. Nothing else. |
| Evidence | How you know it works: the script's `--self-test`, the tool that refuses, the command to run by hand. |

Status means:

- **enforced**: it runs as a gate on every change, or a tool enforces it on every install. A row whose `Runs in` is `gates`
  must be `enforced`.
- **manual**: the script exists and a person runs it at a defined moment (a release step, a pre-merge smoke test). The row
  says when.
- **planned**: not built. The row describes the design and names the script it will have. That script must not exist yet.
  This is how you list what you have not done without hiding it.

Below the table add one line, which the check also verifies:

```text
Counts: 10 enforced, 3 manual, 1 planned.
```

## What the check enforces

[`check-controls-table.py`](../examples/security/check-controls-table.py) parses the table and fails when:

1. an `enforced` or `manual` row names no script or config path, or names a path that does not exist (a backticked token with a
   `/` or a file extension is a path; a `*` makes it a glob);
2. a `planned` row's script exists: the control landed, so flip the row to `enforced` or `manual`;
3. a script in the declared set is named by no row, or no longer exists. The declared set is the list of scripts that count as
   controls. A new control script cannot land without a row, and a deleted script cannot stay documented;
4. a row's `Runs in` is `gates` and its gate script is not named in your gate list file, or its status is not `enforced`;
5. a status is not one of the three words, an id is repeated or malformed, a row has the wrong number of cells (a stray `|`
   inside a cell), an id like `C99` appears anywhere in the document without a row, or the Counts line disagrees with the table;
6. a required heading is missing, or the security policy (`SECURITY.md`) is missing or does not contain the path of this document.

The check ends with its own self-test. It copies your tree to a temporary directory and applies mutations one at a time:
delete an enforced script, point a row at a config file that is not there, remove the row of a declared script, create a planned
row's script, set an unknown status, rename a heading, reference an id with no row, falsify the count, repeat an id, blank the
paths of an enforced row, add a stray cell, drop a gate script from the gate list, empty `SECURITY.md`. Each mutation must turn
the check red for the intended reason, and the unmutated tree must stay green. A check that cannot fail checks nothing.

## Run it

```sh
python3 -I examples/security/check-controls-table.py \
  --root . --doc docs/supply-chain.md \
  --security SECURITY.md \
  --gate-list scripts/run-gates.sh \
  --declared scripts/supply-chain-scripts.txt \
  --heading '## Threat model' --heading '## Controls'
python3 -I examples/security/check-controls-table.py ... --self-test    # the same flags, verbose self-test
```

Flags, all paths relative to `--root`:

| Flag | Meaning |
|---|---|
| `--doc FILE` | The document with the `## Controls` table. Required. |
| `--security FILE` | The security policy. It must exist and contain `--playbook-link` (default: the path of `--doc`). |
| `--gate-list FILE` | The file that lists your gates (your `run-gates` script). Omit it and gate rows are not checked against a list. |
| `--gate-runs-in WORD` | The `Runs in` value that means a gate. Default `gates`. |
| `--gate-script-re RE` | Which table scripts are gates for a gate row. Default `scripts/check-[a-z0-9-]+\.sh`. |
| `--declared FILE` | A file with one declared control script per line (`#` comments allowed). Repeatable. |
| `--declared-glob PATTERN` | A glob of declared control scripts, for example `'scripts/check-*.sh'`. Repeatable. With a glob, every check script automatically needs a row. |
| `--heading TEXT` | A heading the document must contain. Repeatable. |

Put the check itself in your gate list, with a row in the table (it is the control that enforces C14 of the playbook). Exit
status: 0 true, 1 drift, 2 unreadable input.

## Writing good rows

- **One control, one rule.** If a row needs "and" twice, split it. Rows are the unit other documents cite.
- **Name the script, not the tool.** `scripts/check-pins.sh` is checkable. "We use dependabot" is not.
- **Name config you rely on.** If a control is a setting (`onlyBuiltDependencies: []`), the row's config cell names the file, so
  deleting the file turns the check red. Add a script that reads the setting so lowering it turns red too.
- **A tool is a script too.** When the package manager enforces it, write `none (pnpm)` in the script cell and the config file
  in the config cell. The row then still names a path that must exist.
- **Planned means designed.** Write the script path it will have, the gate it will join, and what it will read. Do not mark a
  row `planned` to avoid deciding.
- **Evidence is how you know**, not how you hope: the `--self-test`, the failing install, the exact command.
- **Never edit the Counts line by feel.** Run the check and copy the numbers it prints.

## When you add or change a control

In one commit: the script, its entry in the gate list, its row in the table, its line in the declared set, the Counts line,
and a self-test case if the script is new. When a planned control lands, flip its row and the check stops complaining that
the script exists. When you delete a script, delete its row and its declared-set line. The check tells you each missing piece.

## A complete example

Fourteen controls for a project that has a JavaScript front end, a Python tool and a Rust core, all adopted. The ids match
the controls in the [playbook](./supply-chain-playbook.md). Paths are illustrative. The runnable subset, which passes its
check, is [`sample/docs/supply-chain.md`](../examples/security/sample/docs/supply-chain.md).

### Example

| ID | Control | Threat it stops | Enforcing script | Config | Runs in | Status | Evidence |
|---|---|---|---|---|---|---|---|
| C01 | Every dependency is an exact pin, or allowlisted with a reason | T1 T8: a range takes an untested release | `scripts/check-pins.sh` | `package.json`, `requirements.txt`, `Cargo.toml`, `pins.allow` | gates | enforced | `check-pins.py --self-test` |
| C02 | Every committed lockfile resolves against its manifest offline | T1 T3: a stale lock a later build rewrites | `scripts/check-locks.sh` | `Cargo.lock`, `pnpm-lock.yaml`, `requirements.txt` | gates | enforced | the script fails a lock that would change |
| C03 | Installs read only the lock: frozen installs, `--locked`, `--require-hashes` | T3 T11: an install that rewrites the lock | `scripts/session-setup.sh` | `pnpm-lock.yaml` | session start | enforced | each package manager refuses a disagreeing lock |
| C04 | pnpm refuses versions younger than 30 days | T1: a freshly published malicious release | `scripts/check-pins.sh` | `pnpm-workspace.yaml` | gates | enforced | the script fails when `minimumReleaseAge` is lowered |
| C05 | No dependency runs an install script | T2: a malicious `postinstall` | `scripts/check-pins.sh` | `pnpm-workspace.yaml`, `.npmrc` | gates | enforced | the script fails unless `onlyBuiltDependencies` is `[]` |
| C06 | Committed generated files match their sources through a hash manifest and rebuild identically | T5: a one-sided edit of source or output | `scripts/check-artifacts.sh`, `scripts/build-artifacts.sh` | `web/dist/artifacts.manifest` | gates | enforced | `artifact-manifest.py --self-test` |
| C07 | The one module that parses untrusted text has a fixed crate set, an exact pin with features off, an allowlist of options and no raw-markup sink | T6 T4: input reaching output as markup | `scripts/check-markup-parser.sh` | `Cargo.toml`, `Cargo.lock` | gates | enforced | the script's own mutation self-test |
| C08 | The site loads no remote image, font, stylesheet or script | T9: a third party sees every visitor | `scripts/check-remote-assets.sh` | `web/index.html` | gates | enforced | `check-remote-assets.py --self-test` |
| C09 | The registry URL is one constant and every spelling equals it; one pip index | T7: an install resolving from another source | `scripts/check-registry-url.sh` | `.cargo/config.toml`, `.npmrc`, `pip.conf` | gates | enforced | the script compares every spelling |
| C10 | Dependency evaluation: a cost table with an outcome per direct dependency, counts from the tool | T2 T4: growth with no decision | `scripts/dep-report.sh` | `docs/dependency-register.md` | review of each dependency change | manual | `inventory.py` output pasted in the table |
| C11 | Release stamping: one 40-hex `rev` in every git-sourced dependency | T8: sources resolving to different commits | `scripts/release-stamp.sh` | `Cargo.toml` | release step | manual | `scripts/release-stamp.sh --check` |
| C12 | Advisory scan of every lock against a pinned snapshot, plus a networked refresh step | T1: a known vulnerability in a locked version | `scripts/check-advisories.sh`, `scripts/refresh-advisories.sh` | `advisory-db.rev` | none yet | planned | to be written: the gate reads the snapshot, the refresh advances it |
| C13 | Named owners on checks, allowlists, workflows and manifests; fork pull requests get no secrets | T10 T11: an edit that turns a check off, a privileged run of proposed code | none (repository settings) | `CODEOWNERS`, `.github/workflows/ci.yml` | repository settings | manual | branch protection requires the owner's review |
| C14 | This table is true of the tree | T12: the document drifting from the tree | `scripts/check-controls-table.sh` | `docs/supply-chain.md`, `SECURITY.md`, `scripts/supply-chain-scripts.txt` | gates | enforced | `check-controls-table.py --self-test` |

Counts: 10 enforced, 3 manual, 1 planned.

## Why the table is built this way

- **Every row names a path** so the check has something to compare. A row without a path is an opinion.
- **Planned rows are first-class** so honesty is cheaper than omission. Without them, teams leave out what they have not done.
- **The declared set** is what makes the table complete, not just correct: a script that is not named by a row cannot exist as
  a control.
- **Status flips are forced.** A planned control that lands silently turns the check red until the row is flipped, and the
  counts line moves with it, so the headline numbers in the policy are always the table's numbers.
