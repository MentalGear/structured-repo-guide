#!/bin/sh
# check-backlog-index.sh -- the tracker files and their indexes agree
#
# group: Documentation
#
# Fails when an item file lacks front matter or a section, when an id or a status disagrees with its file name or
# folder, or when a generated index differs from the item files, because the index is only a table over the items.
#
# Usage: sh scripts/check-backlog-index.sh [--dir TRACKER_DIR] [--root DIR]      (regenerate both indexes: python3 -I scripts/backlog_index.py --write)
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. Only --self-test and --help skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/backlog_index.py"
case "${1:-}" in
  --self-test|-h|--help) exec python3 -I "$tool" --check "$@" ;;
esac
python3 -I "$tool" --check "$@" || exit $?
out=$(python3 -I "$tool" --self-test 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-backlog-index: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
