#!/bin/sh
# check-comment-refs.sh -- every id and path a comment cites exists
#
# group: Documentation
#
# Fails when a comment cites a tracker item id or a repository path that does not exist, because a dead citation
# sends the reader nowhere. Old dead citations sit in a shrink-only baseline.
#
# Usage: sh scripts/check-comment-refs.sh [--inventory | --update-baseline [--allow-grow]] [--tracker DIR] [--word WORD]
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$here/comment_scan.py" refs "$@"
