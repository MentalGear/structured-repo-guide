#!/bin/sh
# check-placeholders.sh -- a copied template has no placeholder left
#
# group: Documentation
#
# Fails when the entry file, the status page or the decisions index still holds a template placeholder (an angle-
# bracket placeholder, YYYY-MM-DD), and when ANY Markdown file of the tree still holds a template's own instruction
# comment (a guide or an item copied from a template, too), because a copied template that was never filled in tells
# the next reader nothing true.
#
# Usage: sh scripts/check-placeholders.sh [FILE...]      (default: the entry file, the status page and the decisions index, those that exist, plus the template comment in every other Markdown file)
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. Only --self-test and --help skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/doc_hygiene.py"
case "${1:-}" in
  --self-test|-h|--help) exec python3 -I "$tool" placeholders "$@" ;;
esac
python3 -I "$tool" placeholders "$@" || exit $?
out=$(python3 -I "$tool" --self-test placeholders 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-placeholders: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
