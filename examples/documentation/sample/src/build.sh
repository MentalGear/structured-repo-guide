#!/bin/sh
# Build output goes to dist/, which is never committed (docs/decisions.md).
set -eu
mkdir -p dist
cp -R src dist/
