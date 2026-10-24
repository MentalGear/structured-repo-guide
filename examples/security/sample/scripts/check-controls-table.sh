#!/bin/sh
# Gate: docs/supply-chain.md is true of this tree (and the checker's own mutation self-test is red where it must be).
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-controls-table.py" --root "$root" --doc docs/supply-chain.md \
  --security SECURITY.md --gate-list scripts/run-gates.sh --declared scripts/supply-chain-scripts.txt \
  --heading '## Threat model' --heading '## Controls' --heading '## Keeping this document true'
