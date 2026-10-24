#!/bin/sh
# check-doc-links.sh -- every relative link in the docs resolves
#
# group: Documentation
#
# Fails when a relative link or a heading anchor in a Markdown file points at nothing, because a moved file or a
# renamed heading would otherwise break the docs without a sound.
#
# Usage: sh scripts/check-doc-links.sh [--skip PREFIX] [--no-anchors] [--root DIR]
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$here/check_doc_links.py" "$@"
