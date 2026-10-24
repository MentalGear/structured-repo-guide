# Security: dependencies, builds and the documents that describe them

This half of the guide is about keeping what you depend on, what you build and what you ship from changing without a decision,
and about making the security documentation true. It is language-agnostic: every control is shown for Cargo, npm and pnpm, and
pip side by side, with scripts in POSIX shell and Python 3 (standard library only). Use it when you start a repository, when
you add a dependency, and when you review a change to a manifest, a lockfile, a generated file or a script.

The idea behind all of it: turn each risk into a small offline script that exits non-zero, put every script in one list that
runs before every commit, and write a controls table that a script checks against the tree, so the document cannot lie. When a
problem shows up twice, fix the class with a check, not the instance.

## What is here

| Read | When |
|---|---|
| [`threat-model.md`](./threat-model.md) | You want to know what a dependency, a build step, a generated artifact, a registry, a contributor and an automated agent can do to you, and which control stops what. |
| [`supply-chain-playbook.md`](./supply-chain-playbook.md) | You are choosing or implementing controls: exact pins, lockfiles, release age, no install scripts, frozen installs, generated artifacts, allowlists, remote assets, registry URLs, dependency evaluation, release stamping. |
| [`controls-table.md`](./controls-table.md) | You are writing the table of your controls and want a check that keeps it true. Contains a complete example table. |
| [`vulnerability-reporting.md`](./vulnerability-reporting.md) | You need a private channel for reports, a `SECURITY.md`, and honest response expectations. |
| [`agents-and-automation.md`](./agents-and-automation.md) | You run CI or let an assistant work in the repository. Contains a block to paste into the agent's instructions. |
| [`../templates/SECURITY.md`](../templates/SECURITY.md) | You want the policy file to copy. |
| [`../examples/security/`](../examples/security/README.md) | You want runnable checks and a sample tree to run them against. |

## Adopt it in five minutes

Each step is useful alone. Stop where the cost stops paying. `GUIDE` is the path of this repository's checkout, and the
commands run from the root of your repository. You need `sh` and Python 3.11 or newer.

**1. A private channel and a policy (one minute).** Enable private vulnerability reporting in your host's settings (on GitHub:
Settings, Code security, Private vulnerability reporting). Then:

```sh
GUIDE=/path/to/structured-repo-guide
cp "$GUIDE/templates/SECURITY.md" SECURITY.md      # replace every <ANGLE-BRACKET VALUE>, delete the comment
```

**2. One entry point and one list (one minute).** Copy the checkers you need and the gate runner. The runner lists the
gates and refuses to run when a `scripts/check-*.sh` exists that it does not list.

```sh
mkdir -p scripts
cp "$GUIDE"/examples/security/check-pins.py scripts/
cp "$GUIDE"/examples/security/sample/scripts/run-gates.sh scripts/
cp "$GUIDE"/examples/security/sample/scripts/check-pins.sh scripts/
# the wrapper finds the tool next to the sample; point it at scripts/ and name your own files:
sed 's|"\$root/\.\./check-pins.py"|"$root/scripts/check-pins.py"|' scripts/check-pins.sh > scripts/check-pins.sh.new && mv scripts/check-pins.sh.new scripts/check-pins.sh
```

Open `scripts/run-gates.sh` and cut the `GATES` list down to `scripts/check-pins.sh` for now. Open `scripts/check-pins.sh`
and delete the flags for files you do not have (`--allow pins.allow`, `--pnpm-workspace js/pnpm-workspace.yaml`).

**3. Exact pins, release age, no install scripts (one minute).** Run the gate and read what it lists:

```sh
sh scripts/run-gates.sh
```

Every range, tag and git source is listed with its file and dependency name. Replace each with the version in your lockfile
(`^1.2.0` becomes `1.2.0`; `serde = "1"` becomes `serde = "=1.0.200"`; `requests>=2` becomes `requests==2.32.3`), reinstall from the
lock, and run the gate again. An exception that cannot be fixed goes in `pins.allow` as `path|name|reason`. For pnpm add
`pnpm-workspace.yaml`:

```yaml
minimumReleaseAge: 43200        # minutes: refuse versions younger than 30 days
onlyBuiltDependencies: []       # no dependency runs an install script
```

and pass `--pnpm-workspace pnpm-workspace.yaml` in the wrapper.

**4. Install from the lock only (one minute).** Put these in your setup script and your CI, and in the agent instructions
([`agents-and-automation.md`](./agents-and-automation.md)): `pnpm install --frozen-lockfile` or `npm ci`; `cargo build
--locked`; `pip install --require-hashes --only-binary :all: -r requirements.txt`. Add the offline lock check from
[C02](./supply-chain-playbook.md#c02-lockfiles-committed-and-verified-offline) as a gate.

**5. A controls table that is checked (one minute).** Copy the table and its wrapper, edit the rows to your controls, run it:

```sh
mkdir -p docs
cp "$GUIDE"/examples/security/check-controls-table.py scripts/
cp "$GUIDE"/examples/security/sample/docs/supply-chain.md docs/supply-chain.md
cp "$GUIDE"/examples/security/sample/scripts/check-controls-table.sh scripts/
cp "$GUIDE"/examples/security/sample/scripts/supply-chain-scripts.txt scripts/
sed 's|"\$root/\.\./check-controls-table.py"|"$root/scripts/check-controls-table.py"|' scripts/check-controls-table.sh > scripts/check-controls-table.sh.new && mv scripts/check-controls-table.sh.new scripts/check-controls-table.sh
```

Delete the rows for controls you have not built, or mark them `planned`; list your scripts in
`scripts/supply-chain-scripts.txt`; add `scripts/check-controls-table.sh` to `GATES`. Make `SECURITY.md` contain the path
`docs/supply-chain.md`. Format and rules: [`controls-table.md`](./controls-table.md).

Expect step 5 to be red at first: the sample table names files your repository does not have. Each line the check prints is one edit to make, either to the table or to the tree. After that it keeps telling you about every disagreement.

## Run the examples

The runnable checks and the sample tree are in [`../examples/security/`](../examples/security/README.md). From the root of
this repository:

```sh
sh examples/security/run-examples.sh                              # everything; the last line is "examples/security: ALL OK"
sh examples/security/sample/scripts/run-gates.sh                  # the sample's one entry point; prints "run-gates: ALL GREEN"
python3 -I examples/security/check-pins.py --self-test            # 28 cases, each mutation must turn the check red
python3 -I examples/security/artifact-manifest.py --self-test     # 10 cases
python3 -I examples/security/check-remote-assets.py --self-test   # 8 cases
sh examples/security/sample/scripts/check-controls-table.sh       # OK line, then its 14-mutation self-test, quietly
python3 -I examples/security/check-controls-table.py --root examples/security/sample \
  --doc docs/supply-chain.md --security SECURITY.md --gate-list scripts/run-gates.sh \
  --declared scripts/supply-chain-scripts.txt --heading '## Threat model' --heading '## Controls' --self-test
```

`run-examples.sh` also breaks a copy of the sample five ways (a caret range, a hand-edited generated file, a hot-linked image, a
lowered release age, a deleted control script) and fails unless each one turns a gate red.

## What this does not do

It does not scan for known vulnerabilities, review the code of a locked version, or control Cargo build scripts beyond counting
them. Those are `planned` layers in the [playbook](./supply-chain-playbook.md) (C12) and listed in the
[threat model](./threat-model.md) as not defended. Say the same about your own project: what you do not defend against belongs
in the document next to what you do.
