#!/bin/sh
# run-all.sh -- prove every example script works: self-tests first, then each check on the sample tree
#
# Usage: sh examples/documentation/run-all.sh      (from anywhere; needs only sh and python3)
#
# Part 1 runs the --self-test of every script: each plants a violation in a throwaway tree and requires the check
# to go red. Part 2 runs the checks on examples/documentation/sample/, which is clean apart from one baselined
# file of old debt, then proves the sample's own check scripts pass. Exit 0 and "ALL GREEN" mean all of it held.
set -u
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sample="$here/sample"
rc=0
step() { printf '\n== %s\n' "$1"; shift; "$@" || { echo "RED: $*" >&2; rc=1; }; }

for s in comment_scan check_doc_links docs_catalogue backlog_index; do
  step "self-test: $s" python3 -I "$here/$s.py" --self-test
done
step "history comments (sample)"  sh "$here/check-history-comments.sh" --root "$sample"
step "comment references (sample)" sh "$here/check-comment-refs.sh" --root "$sample"
step "relative links (sample)"    sh "$here/check-doc-links.sh" --root "$sample"
step "checks catalogue (sample)"  sh "$here/check-docs-catalogue.sh" --root "$sample"
step "backlog index (sample)"     sh "$here/check-backlog-index.sh" --root "$sample"
step "sample's own checks"        sh -c "cd '$sample' && sh scripts/run-checks.sh"

printf '\n'
if [ "$rc" -eq 0 ]; then echo "ALL GREEN"; else echo "RED (see above)" >&2; fi
exit "$rc"
