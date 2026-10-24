#!/bin/sh
# check-pins.sh -- every dependency is an exact pin
#
# Fails when a dependency in package.json, requirements.txt, Cargo.toml or pyproject.toml is a range, a tag or a git
# source without a commit, because the next install would take a release nobody tested, and when the pnpm release age is
# lowered or the install-script list is not empty.
#
# Usage: sh scripts/check-pins.sh      (from anywhere; the wrapper finds its own tree)
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-pins.py" --root "$root" --allow pins.allow \
  --pnpm-workspace js/pnpm-workspace.yaml --min-release-age 43200
