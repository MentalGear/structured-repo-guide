#!/bin/sh
# check-docs-catalogue.sh -- the checks catalogue matches the gate list and the script headers
#
# group: Documentation
#
# Fails when the generated catalogue of checks differs from what the gate list and the headers of the check scripts
# say, when a gate has no usable description, or when a check script is missing from the list, because a hand-edited
# or forgotten catalogue lies about what is enforced.
#
# Usage: sh scripts/check-docs-catalogue.sh [--gates FILE | --scripts GLOB] [--out FILE] [--root DIR]      (regenerate: python3 -I scripts/docs_catalogue.py --write)
#
# Without a maintenance flag it checks, then runs the tool's --self-test quietly: a check that has never been seen to
# fail proves nothing, so a self-test that rots turns this red too. Only --self-test and --help skip the self-test.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tool="$here/docs_catalogue.py"
case "${1:-}" in
  --self-test|-h|--help) exec python3 -I "$tool" --check "$@" ;;
esac
python3 -I "$tool" --check "$@" || exit $?
out=$(python3 -I "$tool" --self-test 2>&1) || {
  printf '%s\n' "$out" >&2
  echo "check-docs-catalogue: FAIL -- its --self-test failed, so this check can no longer be trusted to go red" >&2
  exit 1
}
