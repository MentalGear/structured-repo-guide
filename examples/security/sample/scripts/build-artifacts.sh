#!/bin/sh
# The ONE way to regenerate gen/out from gen/src. Commit the outputs and gen/artifacts.manifest together.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../artifact-manifest.py" build --root "$root" --manifest gen/artifacts.manifest \
  --src-dir gen/src --out-dir gen/out --src-ext .txt --out-ext .out \
  --build-cmd 'sh gen/build.sh' --tool-version-cmd 'cat gen/VERSION'
