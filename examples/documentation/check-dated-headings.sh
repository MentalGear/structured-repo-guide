#!/bin/sh
# check-dated-headings.sh -- living docs have no dated headings or dated lead-ins
#
# group: Documentation
#
# Fails when a living doc gains a dated heading or a dated lead-in such as a Status paragraph with a date in its
# heading, because such a paragraph is a diary entry that goes stale, and the dated story belongs in the archive or
# the tracker item. Old ones sit in a shrink-only baseline.
#
# Usage: sh scripts/check-dated-headings.sh [--inventory | --update-baseline [--allow-grow]] [--baseline FILE] [--skip PREFIX] [FILE...]
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. --inventory and --update-baseline skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/doc_hygiene.py"
case "${1:-}" in
  --inventory|--update-baseline|--self-test|-h|--help) exec python3 -I "$tool" dated "$@" ;;
esac
python3 -I "$tool" dated "$@" || exit $?
out=$(python3 -I "$tool" --self-test dated 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-dated-headings: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
