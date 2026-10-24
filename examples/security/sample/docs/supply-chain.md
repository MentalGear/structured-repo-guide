# Supply-chain controls of the sample project

This is the sample tree's playbook. It is small on purpose: it exists so that the checks in the parent directory have a
real, passing tree to run against. The table below is checked against the tree by `scripts/check-controls-table.sh`.

## Threat model

| # | Threat | Stopped by |
|---|---|---|
| T1 | A new release of a dependency is malicious, or a range lets the next install take it | C01 C02 C03 |
| T2 | A dependency runs code at install time | C03 |
| T3 | A committed generated file drifts from its source, or is edited by hand | C04 |
| T4 | A page loads code or images from a host nobody reviewed | C05 |
| T5 | Git-sourced dependencies resolve to different commits | C06 |

Not defended against: a compromised maintainer of this repository, a malicious version that is already in a lockfile, and
known vulnerabilities in dependencies (C07 is planned).

## Controls

Status is `enforced` (runs as a gate, or a tool enforces it on every install), `manual` (a person runs it at a defined
moment) or `planned` (not built; the row names the design and its script does not exist yet).

| ID | Control | Threat it stops | Enforcing script | Config | Runs in | Status | Evidence |
|---|---|---|---|---|---|---|---|
| C01 | Every dependency in `package.json`, `requirements.txt` and `Cargo.toml` is an exact pin, or allowlisted with a reason | T1: a range takes an untested release | `scripts/check-pins.sh` | `js/package.json`, `py/requirements.txt`, `rust/Cargo.toml`, `pins.allow` | gates | enforced | `check-pins.py --self-test` turns every mutation red |
| C02 | Lockfiles are committed and installs read only them (`pnpm install --frozen-lockfile`, `pip install --require-hashes`, `cargo build --locked`) | T1: an install that rewrites the lock pulls a different build | none (the package managers refuse) | `js/pnpm-lock.yaml`, `rust/Cargo.lock` | install command | enforced | the install command fails when the lock and the manifest disagree |
| C03 | pnpm refuses versions younger than 30 days and runs no dependency install script | T1 T2: a fresh malicious release, a malicious `postinstall` | `scripts/check-pins.sh` | `js/pnpm-workspace.yaml` | gates | enforced | the same script reads both settings and fails if either is weakened |
| C04 | The generated files in `gen/out` match `gen/src` through a manifest of sha256 sums, and rebuild to the same bytes | T3: a one-sided edit of source or output | `scripts/check-artifacts.sh`, `scripts/build-artifacts.sh` | `gen/artifacts.manifest` | gates | enforced | `artifact-manifest.py --self-test` turns every mutation red |
| C05 | The web sources load no remote image, font, stylesheet or script | T4: a third party sees every visitor, or changes what the page runs | `scripts/check-remote-assets.sh` | `web.allow` | gates | enforced | `check-remote-assets.py --self-test` turns every mutation red |
| C06 | Git-sourced dependencies carry one 40-hex `rev`, written at release time | T5: sources resolving to different commits | `scripts/release-stamp.sh` | `rust/Cargo.toml` | release step | manual | `scripts/release-stamp.sh --check` |
| C07 | Advisory scan of every lockfile against a pinned database snapshot | T1: a known vulnerability in a locked version | `scripts/check-advisories.sh` | `advisory-db.rev` | none yet | planned | to be written: the gate reads the snapshot, a separate networked step refreshes it |
| C08 | One gate list and one entry point; a check script that is not in the list fails the run | every threat: a check nobody runs controls nothing | `scripts/run-gates.sh` | none | gates | enforced | the guard at the top of `scripts/run-gates.sh` |
| C09 | This table is true of the tree | drift of this document from the tree | `scripts/check-controls-table.sh` | `docs/supply-chain.md`, `SECURITY.md`, `scripts/supply-chain-scripts.txt` | gates | enforced | `check-controls-table.py --self-test` turns every mutation red |

Counts: 7 enforced, 1 manual, 1 planned.

## Keeping this document true

`scripts/check-controls-table.sh` parses the table above and fails when an `enforced` or `manual` row names a script or
config path that does not exist, when a `planned` row's script already exists, when a script in
`scripts/supply-chain-scripts.txt` is named by no row, when a `gates` row's script is not in `scripts/run-gates.sh`, when
the Counts line is wrong, or when `SECURITY.md` does not link this file.
