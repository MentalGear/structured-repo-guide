#!/bin/sh
# check-doc-map.sh -- every doc under docs/ is reachable from the docs map
#
# group: Documentation
#
# Fails when a Markdown file under docs/ cannot be reached from docs/README.md by following relative links, because
# a document that is not in the map does not exist for a new reader, and an unlinked page is where stale
# instructions hide.
#
# Usage: sh scripts/check-doc-map.sh [--map FILE] [--docs DIR] [--skip PREFIX]
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. Only --self-test and --help skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/doc_hygiene.py"
case "${1:-}" in
  --self-test|-h|--help) exec python3 -I "$tool" map "$@" ;;
esac
python3 -I "$tool" map "$@" || exit $?
out=$(python3 -I "$tool" --self-test map 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-doc-map: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
