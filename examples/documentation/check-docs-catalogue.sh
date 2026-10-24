#!/bin/sh
# check-docs-catalogue.sh -- the checks catalogue matches the script headers
#
# group: Documentation
#
# Fails when the generated catalogue of checks differs from what the headers of the check scripts say, or when a
# header has no usable description, because a hand-edited or forgotten catalogue lies about what is enforced.
#
# Usage: sh scripts/check-docs-catalogue.sh [--scripts GLOB] [--out FILE] [--root DIR]      (regenerate with: python3 -I scripts/docs_catalogue.py --write)
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$here/docs_catalogue.py" --check "$@"
