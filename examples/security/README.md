# Security examples: runnable checks

These are small, self-contained scripts that make the security controls in [`../../security/`](../../security/README.md) true by
construction. Use them as they are, or copy one into your repository's `scripts/` and change its flags. Each one needs
only POSIX `sh` and Python 3.11 or newer (standard library only), no network and no package install.

| File | What it checks | Playbook control |
|---|---|---|
| [`check-pins.py`](./check-pins.py) | every dependency in `package.json` (with its overrides), `requirements*.txt`, `pyproject.toml` and `Cargo.toml` (with `[patch]`) is an exact pin, or allowlisted with a reason; optional pnpm release-age and no-install-script settings; optional hash-pinned pip files; required settings such as `.npmrc` `save-exact=true` | [C01](../../security/supply-chain-playbook.md#c01-exact-pins), [C04](../../security/supply-chain-playbook.md#c04-minimum-release-age-and-trust-policy), [C05](../../security/supply-chain-playbook.md#c05-no-dependency-install-or-build-scripts) |
| [`artifact-manifest.py`](./artifact-manifest.py) | a committed generated file matches its source: sha256 manifest, orphans, one-sided edits, deterministic rebuild | [C06](../../security/supply-chain-playbook.md#c06-generated-artifacts-with-a-hash-manifest) |
| [`check-remote-assets.py`](./check-remote-assets.py) | web sources load nothing from another host | [C08](../../security/supply-chain-playbook.md#c08-no-hot-linked-remote-assets) |
| [`check-workflow-permissions.py`](./check-workflow-permissions.py) | every GitHub Actions workflow declares read-only permissions, has no `write-all`, pins actions to a commit, and runs no privileged trigger on the proposed head | [C13](../../security/supply-chain-playbook.md#c13-workflow-files-grant-least-privilege) |
| [`check-controls-table.py`](./check-controls-table.py) | a controls table is true of the tree, and the security policy has no unreplaced placeholder | [C14](../../security/supply-chain-playbook.md#c14-the-controls-table-stays-true) |
| [`inventory.py`](./inventory.py) | counts packages, build scripts, proc-macros, install scripts and source distributions for a cost table | [C10](../../security/supply-chain-playbook.md#c10-dependency-evaluation) |
| [`run-examples.sh`](./run-examples.sh) | runs everything below, replays the adopt path in a fresh git repository, plus six deliberate breakages that must turn red | |
| [`sample/`](./sample/) | a tiny tree (one `package.json`, one `requirements.txt`, one `Cargo.toml`, a generated file, a web page, a workflow, a controls table, a gate list) that passes every check | |
| [`starter/`](./starter/) | the three-row controls table, its declared set and the three wrapper scripts that the adopt path in [`../../security/README.md`](../../security/README.md) copies; the wrappers find the Python tool next to themselves | |

`C01`, `C02`, ... are the control ids of the playbook; the rows listed here are the controls that have a shipped script.

Every checker has a `--self-test`. The self-test applies one mutation at a time (a caret range, a hand-edited output, a
deleted script, a wrong count, a stale allowlist entry) and fails unless each mutation turns the checker red for the
intended reason. A checker whose self-test passes cannot silently stop checking.

## Run it

From the root of the guide:

```sh
sh examples/security/run-examples.sh
```

Expected last line: `examples/security: ALL OK`. To run one piece:

```sh
sh examples/security/sample/scripts/run-gates.sh                 # the sample's one runner: ALL GREEN
python3 -I examples/security/check-pins.py --self-test
python3 -I examples/security/artifact-manifest.py --self-test
python3 -I examples/security/check-remote-assets.py --self-test
python3 -I examples/security/check-workflow-permissions.py --self-test
sh examples/security/sample/scripts/check-controls-table.sh      # also runs its mutation self-test, quietly
```

`python3 -I` runs Python in isolated mode, so a stray `json.py` in the current directory cannot be imported by accident.

## How the sample is wired

`sample/scripts/check-*.sh` are short wrappers that call the Python tools with this sample's paths. They reach the tools in the
parent directory; in your own repository you copy the `.py` file next to the wrapper, which is what [`starter/`](./starter/)'s
wrappers expect. `sample/scripts/run-gates.sh` is the guide's one shared runner
([`../gate-runner/run-gates.sh`](../gate-runner/run-gates.sh), documented in
[`../../documentation/gate-runner.md`](../../documentation/gate-runner.md)) and `sample/scripts/gates.list` is the one list of
gates: the runner refuses to run when a `check-*.sh` exists that the list does not name. `sample/docs/supply-chain.md` is the
controls table the last gate verifies; [`../../security/controls-table.md`](../../security/controls-table.md) explains its format.

Break something and watch it fail, for example `^` in front of a version in `sample/js/package.json`, then
`sh sample/scripts/run-gates.sh`. Undo it with `git checkout` or by hand.
