#!/bin/sh
# check-history-comments.sh -- comments describe the current state, not the history
#
# group: Documentation
#
# Fails when a source file gains a comment line that retells history: a date, a commit hash or a phrase that
# narrates a change. The retelling goes stale, and the tracker item already carries the story. Old debt sits in a
# shrink-only baseline.
#
# Usage: sh scripts/check-history-comments.sh [--inventory | --update-baseline [--allow-grow]] [--root DIR]
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. --inventory and --update-baseline skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/comment_scan.py"
case "${1:-}" in
  --inventory|--update-baseline|--self-test|-h|--help) exec python3 -I "$tool" history "$@" ;;
esac
python3 -I "$tool" history "$@" || exit $?
out=$(python3 -I "$tool" --self-test history 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-history-comments: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
