#!/bin/sh
# check-backlog-index.sh -- the tracker files and their indexes agree
#
# group: Documentation
#
# Fails when an item file lacks front matter or a section, when an id or a status disagrees with its file name or
# folder, or when a generated index differs from the item files, because the index is only a table over the items.
#
# Usage: sh scripts/check-backlog-index.sh [--dir TRACKER_DIR] [--root DIR]      (regenerate with: python3 -I scripts/backlog_index.py --write)
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$here/backlog_index.py" --check "$@"
