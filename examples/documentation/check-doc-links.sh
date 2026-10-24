#!/bin/sh
# check-doc-links.sh -- every relative link in the docs resolves
#
# group: Documentation
#
# Fails when a relative link or a heading anchor in a Markdown file points at nothing, because a moved file or a
# renamed heading would otherwise break the docs without a sound.
#
# Usage: sh scripts/check-doc-links.sh [--skip PREFIX] [--no-anchors] [--root DIR]
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. Only --self-test and --help skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/check_doc_links.py"
case "${1:-}" in
  --self-test|-h|--help) exec python3 -I "$tool" "$@" ;;
esac
python3 -I "$tool" "$@" || exit $?
out=$(python3 -I "$tool" --self-test 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-doc-links: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
