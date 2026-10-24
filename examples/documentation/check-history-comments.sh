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
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$here/comment_scan.py" history "$@"
