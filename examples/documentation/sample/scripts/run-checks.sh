#!/bin/sh
# run-checks.sh -- run every check in scripts/check-*.sh and print ALL GREEN only when all of them pass
#
# The one command a contributor runs before a commit: it runs each check script in order, keeps going after a
# failure so one run shows every red check, and exits 1 if any failed.
#
# Usage: sh scripts/run-checks.sh      (run from the repository root)
set -u
rc=0
for s in scripts/check-*.sh; do
  sh "$s" || { echo "RED: $s" >&2; rc=1; }
done
[ "$rc" -eq 0 ] && echo "ALL GREEN"
exit "$rc"
