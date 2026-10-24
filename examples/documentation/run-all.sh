#!/bin/sh
# run-all.sh -- prove every example script works: self-tests first, then each check on the sample tree
#
# Usage: sh examples/documentation/run-all.sh      (from anywhere; needs only sh and python3)
#
# Part 1 runs the --self-test of every script: each plants a violation in a throwaway tree and requires the check
# to go red. Part 2 runs the checks on examples/documentation/sample/, which is clean apart from one baselined
# file of old debt, then runs the sample's own runner and proves its copy of the gate runner is the shared one.
# Exit 0 and "ALL GREEN" mean all of it held.
set -u
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sample="$here/sample"
runner="$here/../gate-runner/run-gates.sh"
rc=0
step() { printf '\n== %s\n' "$1"; shift; "$@" || { echo "RED: $*" >&2; rc=1; }; }

# The tools are comments and code too: copied into a repository's scripts/, they must pass the history and reference checks
# with no baseline, or an adopter's first baseline would hold the tools' own lines.
copied_tools_are_clean() {
  d=$(mktemp -d "${TMPDIR:-/tmp}/tools-own-checks.XXXXXX") || return 1
  mkdir -p "$d/scripts" "$d/docs/backlog"
  cp "$here"/*.py "$here"/check-*.sh "$runner" "$here/../gate-runner/gates.list" "$d/scripts/"
  cp "$sample/docs/backlog/002-evict-cache-by-size.md" "$d/docs/backlog/"
  cp "$sample/docs/README.md" "$sample/docs/STATUS.md" "$sample/docs/decisions.md" "$d/docs/"
  (cd "$d" && python3 -I scripts/backlog_index.py --write >/dev/null &&
   sh scripts/check-history-comments.sh && sh scripts/check-comment-refs.sh)
  r=$?
  rm -rf "$d"
  return $r
}

# A wrapper must go red when its tool's self-test fails, even though the check itself passes (a stub tool: check passes,
# --self-test fails). Without this, "the wrapper runs the self-test" is a claim nobody has seen fail.
wrapper_catches_a_rotted_selftest() {
  d=$(mktemp -d "${TMPDIR:-/tmp}/rotted-selftest.XXXXXX") || return 1
  cp "$here/check-doc-links.sh" "$d/"
  printf 'import sys\nsys.exit(1 if "--self-test" in sys.argv else 0)\n' > "$d/check_doc_links.py"
  out=$(sh "$d/check-doc-links.sh" 2>&1); r=$?
  rm -rf "$d"
  [ "$r" -eq 1 ] && printf '%s' "$out" | grep -q "self-test failed" && echo "ok: a failing self-test turned the wrapper red" && return 0
  echo "the wrapper stayed green (rc $r) on a failing self-test" >&2
  return 1
}

for s in comment_scan check_doc_links docs_catalogue backlog_index doc_hygiene; do
  step "self-test: $s" python3 -I "$here/$s.py" --self-test
done
step "self-test: gate runner" sh "$runner" --self-test
step "a wrapper goes red when its self-test fails" wrapper_catches_a_rotted_selftest
step "history comments (sample)"   sh "$here/check-history-comments.sh" --root "$sample"
step "comment references (sample)" sh "$here/check-comment-refs.sh" --root "$sample"
step "relative links (sample)"     sh "$here/check-doc-links.sh" --root "$sample"
step "checks catalogue (sample)"   sh "$here/check-docs-catalogue.sh" --root "$sample"
step "backlog index (sample)"      sh "$here/check-backlog-index.sh" --root "$sample"
step "placeholders (sample)"       sh "$here/check-placeholders.sh" --root "$sample"
step "doc map (sample)"            sh "$here/check-doc-map.sh" --root "$sample"
step "dated headings (sample)"     sh "$here/check-dated-headings.sh" --root "$sample"
step "the tools pass their own history and reference checks when copied" copied_tools_are_clean
step "sample's copy of the runner is the shared one" cmp "$runner" "$sample/scripts/run-gates.sh"
step "sample's own gates"          sh -c "cd '$sample' && sh scripts/run-gates.sh"

printf '\n'
if [ "$rc" -eq 0 ]; then echo "ALL GREEN"; else echo "RED (see above)" >&2; fi
exit "$rc"
