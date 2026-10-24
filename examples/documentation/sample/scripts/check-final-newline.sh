#!/bin/sh
# check-final-newline.sh -- every source file ends with a newline
#
# group: Source hygiene
#
# Fails when a file under src/ does not end with a newline, because the next appended line would join the last
# one and the diff would show a change to a line nobody touched.
#
# Usage: sh scripts/check-final-newline.sh      (run from the repository root)
set -eu
bad=0
for f in $(find src -type f); do
  if [ -s "$f" ] && [ "$(tail -c 1 "$f" | wc -l)" -eq 0 ]; then
    echo "check-final-newline: $f has no final newline" >&2
    bad=1
  fi
done
[ "$bad" -eq 0 ] || exit 1
echo "check-final-newline: OK"
