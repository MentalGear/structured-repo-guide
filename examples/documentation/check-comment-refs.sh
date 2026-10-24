#!/bin/sh
# check-comment-refs.sh -- every id and path a comment cites exists
#
# group: Documentation
#
# Fails when a comment cites a tracker item id or a repository path that does not exist, because a dead citation
# sends the reader nowhere. Old dead citations sit in a shrink-only baseline.
#
# Usage: sh scripts/check-comment-refs.sh [--inventory | --update-baseline [--allow-grow]] [--tracker DIR] [--word WORD] [--baseline FILE]
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. --inventory and --update-baseline skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/comment_scan.py"
case "${1:-}" in
  --inventory|--update-baseline|--self-test|-h|--help) exec python3 -I "$tool" refs "$@" ;;
esac
python3 -I "$tool" refs "$@" || exit $?
out=$(python3 -I "$tool" --self-test refs 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-comment-refs: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
