#!/bin/sh
# Gate: the committed generated files match their sources and the manifest (and rebuild identically).
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../artifact-manifest.py" check --root "$root" --manifest gen/artifacts.manifest \
  --src-dir gen/src --out-dir gen/out --src-ext .txt --out-ext .out \
  --build-cmd 'sh gen/build.sh' --tool-version-cmd 'cat gen/VERSION'
