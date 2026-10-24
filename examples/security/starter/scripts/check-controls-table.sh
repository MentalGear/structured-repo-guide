#!/bin/sh
# check-controls-table.sh -- the controls table is true of the tree
#
# Fails when the controls table in docs/supply-chain.md names a script or config path that does not exist, lists a
# planned control whose script exists, leaves a declared script without a row, miscounts, or when SECURITY.md lacks the
# link to the table or still has a template placeholder.
#
# Usage: sh scripts/check-controls-table.sh      (from anywhere; the wrapper finds its own tree)
#
# The gate list is scripts/gates.list; the declared set is scripts/supply-chain-scripts.txt.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
exec python3 -I "$here/check-controls-table.py" --root "$root" --doc docs/supply-chain.md \
  --security SECURITY.md --gate-list scripts/gates.list --declared scripts/supply-chain-scripts.txt \
  --heading '## Threat model' --heading '## Controls'
