#!/bin/sh
# check-no-tabs.sh -- no tab characters in source files
#
# group: Source hygiene
#
# Fails when a file under src/ contains a tab character, because tab width differs by editor and a diff then
# shows alignment that the file does not have.
#
# Usage: sh scripts/check-no-tabs.sh      (run from the repository root)
set -eu
tab=$(printf '\t')
if grep -rn "$tab" src; then
  echo "check-no-tabs: tab characters found (above)" >&2
  exit 1
fi
echo "check-no-tabs: OK"
