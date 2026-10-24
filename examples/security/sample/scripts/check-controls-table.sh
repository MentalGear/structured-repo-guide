#!/bin/sh
# check-controls-table.sh -- the controls table is true of the tree
#
# Fails when the controls table in docs/supply-chain.md names a script or config path that does not exist, lists a
# planned control whose script exists, leaves a declared script without a row, miscounts, or when SECURITY.md lacks the
# link to the table or still has a template placeholder.
#
# Usage: sh scripts/check-controls-table.sh      (from anywhere; the wrapper finds its own tree)
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-controls-table.py" --root "$root" --doc docs/supply-chain.md \
  --security SECURITY.md --gate-list scripts/gates.list --declared scripts/supply-chain-scripts.txt \
  --heading '## Threat model' --heading '## Controls' --heading '## Keeping this document true'
