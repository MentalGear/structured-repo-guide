#!/bin/sh
# The one entry point and the one list. Green is `ALL GREEN` with exit 0; anything else is not a pass.
# A gate that is not in this list does not run, so the guard below fails when a scripts/check-*.sh is missing from it.
set -u
cd "$(dirname "$0")/.." || exit 2
GATES="
scripts/check-pins.sh
scripts/check-artifacts.sh
scripts/check-remote-assets.sh
scripts/check-controls-table.sh
"
for f in scripts/check-*.sh; do
  case "$GATES" in
    *"$f"*) ;;
    *) echo "run-gates: $f exists but is not in the gate list" >&2; exit 1 ;;
  esac
done
fail=0
for g in $GATES; do
  if sh "$g"; then :; else echo "run-gates: RED $g" >&2; fail=1; fi
done
[ "$fail" -eq 0 ] || exit 1
echo "run-gates: ALL GREEN"
