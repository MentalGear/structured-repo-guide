#!/bin/sh
# check-artifacts.sh -- committed generated files match their sources
#
# Fails when a committed generated file differs from the manifest of hashes written by the build script, or from what
# its source rebuilds to, because a one-sided edit of a source or an output ships old behaviour or hides a hand-made
# change.
#
# Usage: sh scripts/check-artifacts.sh      (from anywhere; the wrapper finds its own tree)
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../artifact-manifest.py" check --root "$root" --manifest gen/artifacts.manifest \
  --src-dir gen/src --out-dir gen/out --src-ext .txt --out-ext .out \
  --build-cmd 'sh gen/build.sh' --tool-version-cmd 'cat gen/VERSION'
