# Supply-chain controls

What this project does about the code it depends on, builds and ships, and what it does not. The table below is checked
against the tree by `scripts/check-controls-table.sh`. Add a control by adding its script, its row, its line in
`scripts/supply-chain-scripts.txt` and its entry in the gate list, in one commit. The ids are those of the
guide's playbook, so a control keeps its number when you add the next one.

## Threat model

| # | Threat | Stopped by |
|---|---|---|
| T1 | A new release of a dependency is malicious, or a range lets the next install take it | C01 |
| T9 | A page loads code, fonts or images from a host nobody reviewed | C08 |
| T12 | This document says a control exists and it does not | C14 |

Not defended against: a compromised maintainer of this repository, a malicious version that is already in a lockfile, and
known vulnerabilities in dependencies. Add a line here for every control you have not built yet.

## Controls

Status is `enforced` (runs as a gate, or a tool enforces it on every install), `manual` (a person runs it at a defined
moment) or `planned` (not built; the row names the design and its script does not exist yet).

| ID | Control | Threat it stops | Enforcing script | Config | Runs in | Status | Evidence |
|---|---|---|---|---|---|---|---|
| C01 | Every dependency in every manifest is an exact pin, or allowlisted with a reason | T1: a range takes an untested release | `scripts/check-pins.sh` | none | gates | enforced | `check-pins.py --self-test` turns every mutation red |
| C08 | The web sources load no remote image, font, stylesheet or script | T9: a third party sees every visitor, or changes what the page runs | `scripts/check-remote-assets.sh` | none | gates | enforced | `check-remote-assets.py --self-test` turns every mutation red |
| C14 | This table is true of the tree | T12: the document drifting from the tree | `scripts/check-controls-table.sh` | `docs/supply-chain.md`, `SECURITY.md`, `scripts/supply-chain-scripts.txt` | gates | enforced | `check-controls-table.py --self-test` turns every mutation red |

Counts: 3 enforced, 0 manual, 0 planned.
