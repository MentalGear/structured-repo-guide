# Security: dependencies, builds and the documents that describe them

This half of the guide is about keeping what you depend on, what you build and what you ship from changing without a decision,
and about making the security documentation true. It is language-agnostic: every control is shown for Cargo, npm and pnpm, and
pip side by side, with scripts in POSIX shell and Python 3 (standard library only). Use it when you start a repository, when
you add a dependency, and when you review a change to a manifest, a lockfile, a generated file or a script.

The idea behind all of it: turn each risk into a small offline script that exits non-zero, put every script in one list that
runs before every commit, and write a controls table that a script checks against the tree, so the document cannot lie. When a
problem shows up twice, fix the class with a check, not the instance.

**Ids.** A control is numbered `C01`, `C02`, ...: each is a section of the [playbook](./supply-chain-playbook.md) and a row of
the controls table. A threat is numbered `T1`, `T2`, ...: each is a row of the [threat model](./threat-model.md) and names the
controls that stop it. An id is never reused for something else.

## What is here

| Read | When |
|---|---|
| [`threat-model.md`](./threat-model.md) | You want to know what a dependency, a build step, a generated artifact, a registry, a contributor and an automated agent can do to you, and which control stops what. |
| [`supply-chain-playbook.md`](./supply-chain-playbook.md) | You are choosing or implementing controls: exact pins, lockfiles, release age, no install scripts, frozen installs, generated artifacts, allowlists, remote assets, registry URLs, dependency evaluation, release stamping, workflow permissions, a clean-room install. It ends with the settings that depend on your tool's version. |
| [`controls-table.md`](./controls-table.md) | You are writing the table of your controls and want a check that keeps it true. Contains a complete example table. |
| [`vulnerability-reporting.md`](./vulnerability-reporting.md) | You need a private channel for reports, a `SECURITY.md`, and honest response expectations. |
| [`agents-and-automation.md`](./agents-and-automation.md) | You run CI or let an assistant work in the repository. Contains a block to paste into the agent's instructions. |
| [`../templates/SECURITY.md`](../templates/SECURITY.md) | You want the policy file to copy. |
| [`../examples/security/`](../examples/security/README.md) | You want runnable checks, a full sample tree to run them against, and a three-row starter to copy. |

## Adopt it in five minutes

Each step is useful alone. Stop where the cost stops paying. `GUIDE` is the path of this repository's checkout, and the
commands run from the root of your repository, which must be a git repository. You need `sh` and Python 3.11 or newer.

**1. A private channel and a policy (one minute).** Enable private vulnerability reporting in your host's settings (on GitHub:
Settings, Code security, Private vulnerability reporting). Then:

```sh
GUIDE=/path/to/structured-repo-guide
cp "$GUIDE/templates/SECURITY.md" SECURITY.md
```

Open `SECURITY.md`, replace every `<...>` with real text, delete the `<!-- TEMPLATE ... -->` comment at the top, and make the
last paragraph link your supply-chain document (step 5 creates `docs/supply-chain.md`). Step 5's check fails while a placeholder
or the comment is left, so an unedited template cannot pass.

**2. One runner for the whole repository (one minute).** A repository has exactly one gate runner, shared by the documentation
checks and these: [`examples/gate-runner/run-gates.sh`](../examples/gate-runner/run-gates.sh), documented in
[`documentation/gate-runner.md`](../documentation/gate-runner.md). It runs the gates in its list, `scripts/gates.list` (one
`name|command` line per gate under a `# group:` heading), and refuses to run when a `scripts/check-*.sh` exists that the list
does not name. So you add each security check to that list and you never cut the list down: a check that is not in it either
does not run or makes the runner refuse.

```sh
mkdir -p scripts
cp "$GUIDE"/examples/gate-runner/run-gates.sh scripts/        # once per repository: skip if the documentation checks put it there
cp "$GUIDE"/examples/security/check-pins.py scripts/
cp "$GUIDE"/examples/security/starter/scripts/check-pins.sh scripts/
printf '# group: Security\ncheck-pins|sh scripts/check-pins.sh\n' >> scripts/gates.list   # creates the list, or adds to yours
```

The wrapper finds `check-pins.py` next to itself and uses `pins.allow` and `pnpm-workspace.yaml` at the repository root when
they exist, so there is nothing to edit.

**3. Exact pins, release age, no install scripts (one minute).** Run the one gate and read what it lists:

```sh
sh scripts/check-pins.sh
```

Every range, tag and git source is listed with its file and dependency name. Fix them in this order:

- **No lockfile yet?** Make one first, so transitive versions are recorded, and commit it. Each command needs the network
  once: `cargo generate-lockfile`; `pnpm install --lockfile-only`; `npm install --package-lock-only --ignore-scripts`; for pip,
  `uv pip compile --generate-hashes requirements.in -o requirements.txt` (or `pip-compile --generate-hashes`), which writes a
  fully pinned, hashed `requirements.txt`; the input may be a `pyproject.toml` instead of `requirements.in`. Keep the ranges
  you want resolved in `requirements.in` (the check does not read that name) and pin `pyproject.toml` entries to what the
  output says.
- **A range or tag:** replace it with the version in the lock (`^1.2.0` becomes `1.2.0`; `serde = "1"` becomes
  `serde = "=1.0.200"`; `requests>=2` becomes `requests==2.32.3`), reinstall from the lock, run the gate again.
- **A git dependency:** it needs a real 40-hex commit. Ask the remote for it, never type one from memory:
  `git ls-remote <url> refs/heads/main` prints `<40-hex>  refs/heads/main` (for an annotated tag ask for
  `'refs/tags/<tag>^{}'`); put the first column in `rev`. The check only tests the shape, so an invented hash passes the gate
  and fails your next build: the `git ls-remote` is the proof.
- **An exception that cannot be fixed:** one line in `pins.allow`, `path|name|reason`, with the reason. An entry that matches
  nothing fails the run.

For pnpm add `pnpm-workspace.yaml` at the root (the wrapper then checks it), and for every package manager that reads it an
`.npmrc`:

```yaml
minimumReleaseAge: 43200        # minutes: refuse versions younger than 30 days
onlyBuiltDependencies: []       # no dependency runs an install script
```

```text
save-exact=true
```

To keep the `.npmrc` line from being removed, add `set -- "$@" --require-setting .npmrc:save-exact=true` above the `exec` line
of `scripts/check-pins.sh`. Settings that depend on your pnpm version (`trustPolicy: no-downgrade`, `blockExoticSubdeps`) are in
the playbook's [Unverified](./supply-chain-playbook.md#unverified-confirm-for-your-version) section: confirm one for your
version before you add it, then require it the same way (`--require-setting pnpm-workspace.yaml:trustPolicy=no-downgrade`).
The example checks Cargo, npm and pnpm, and pip files; for Go, Maven, Gradle, Ruby, PHP and .NET the method applies but these
scripts do not read your files.

**4. Install from the lock only (one minute).** Put these in your setup script and your CI, and in the agent instructions
([`agents-and-automation.md`](./agents-and-automation.md)): `pnpm install --frozen-lockfile` or `npm ci`; `cargo build
--locked`; `pip install --require-hashes --only-binary :all: -r requirements.txt`. For Cargo, add the offline lock check
pattern from [C02](./supply-chain-playbook.md#c02-lockfiles-committed-and-verified-offline) as a gate; it is a snippet to
adapt, not a shipped script.

**5. A controls table that is checked (one minute).** The starter is a complete, true table with three controls (C01 exact
pins, C08 no remote assets, C14 this table is true). Copy it:

```sh
mkdir -p docs
cp "$GUIDE"/examples/security/check-controls-table.py "$GUIDE"/examples/security/check-remote-assets.py scripts/
cp "$GUIDE"/examples/security/starter/scripts/check-controls-table.sh scripts/
cp "$GUIDE"/examples/security/starter/scripts/check-remote-assets.sh scripts/
cp "$GUIDE"/examples/security/starter/scripts/supply-chain-scripts.txt scripts/
cp "$GUIDE"/examples/security/starter/docs/supply-chain.md docs/
```

Then make exactly these edits. The check names every one you miss:

1. **`scripts/gates.list`:** add two lines under the Security group, `check-remote-assets|sh scripts/check-remote-assets.sh` and
   `check-controls-table|sh scripts/check-controls-table.sh`.
2. **The controls table in `docs/supply-chain.md`:** delete the rows of controls you do not have. Keep all three if you have
   web pages; with none, delete the C08 row (and see edit 4).
3. **The threat-model table in the same file:** it cites control ids, and an id with no row is an error. Delete or retarget the
   threat rows whose controls you deleted.
4. **The declared set `scripts/supply-chain-scripts.txt`:** one line per control script; delete the line of a script you
   dropped (and its file).
5. **The `Counts:` line:** run the check, copy the numbers it prints.
6. **`SECURITY.md`:** it contains `docs/supply-chain.md` as a link and no placeholder.

```sh
sh scripts/check-controls-table.sh
```

If you kept all three rows and finished steps 1 to 4, it is green once `SECURITY.md` is filled in and the gate list names
the three scripts. Add a control later by adding its script, its row, its line in the declared set, its `gates.list` line and the
new `Counts:` in one commit. Format and rules: [`controls-table.md`](./controls-table.md). Finish with the whole list:

```sh
sh scripts/run-gates.sh
```

## Run the examples

The runnable checks, the full sample tree and the starter are in [`../examples/security/`](../examples/security/README.md).
From the root of this repository:

```sh
sh examples/security/run-examples.sh                              # everything; the last line is "examples/security: ALL OK"
sh examples/security/sample/scripts/run-gates.sh                  # the sample's one runner; ends with ALL GREEN
python3 -I examples/security/check-pins.py --self-test            # 49 cases, each mutation must turn the check red
python3 -I examples/security/artifact-manifest.py --self-test     # 10 cases
python3 -I examples/security/check-remote-assets.py --self-test   # 8 cases
python3 -I examples/security/check-workflow-permissions.py --self-test   # 16 cases
sh examples/security/sample/scripts/check-controls-table.sh       # OK line, then its 16-mutation self-test, quietly
python3 -I examples/security/check-controls-table.py --root examples/security/sample \
  --doc docs/supply-chain.md --security SECURITY.md --gate-list scripts/gates.list \
  --declared scripts/supply-chain-scripts.txt --heading '## Threat model' --heading '## Controls' --self-test
```

`run-examples.sh` also breaks a copy of the sample six ways (a caret range, a hand-edited generated file, a hot-linked image, a
lowered release age, a deleted control script, a workflow with no `permissions:`) and fails unless each one turns a gate red, and
it replays the adopt path above in a fresh git repository: an unedited policy template is red, a project with no lockfile and
a git dependency is walked to green.

## What this does not do

It does not scan for known vulnerabilities, review the code of a locked version, or control Cargo build scripts beyond counting
them. Those are `planned` layers in the [playbook](./supply-chain-playbook.md) (C12) and listed in the
[threat model](./threat-model.md) as not defended. The example scripts read Cargo, npm and pnpm, and pip files, GitHub Actions
workflow files and web sources; other ecosystems and CI systems need the same checks written for their formats. Say the same
about your own project: what you do not defend against belongs in the document next to what you do.
