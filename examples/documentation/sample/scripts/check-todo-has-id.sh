#!/bin/sh
# check-todo-has-id.sh -- a TODO names its tracker item
#
# group: Tracker
#
# Fails when a TODO under src/ does not read TODO(backlog N), because a TODO with no item is a promise nobody
# tracks, and the item is where its reason, its options and its owner live.
#
# Usage: sh scripts/check-todo-has-id.sh      (run from the repository root)
set -eu
if grep -rn "TODO" src | grep -v "TODO(backlog [0-9][0-9]*)"; then
  echo "check-todo-has-id: a TODO without an item id (above)" >&2
  exit 1
fi
echo "check-todo-has-id: OK"
