#!/bin/sh
# check-pins.sh -- every dependency is an exact pin
#
# Fails when a dependency in package.json, requirements.txt, Cargo.toml or pyproject.toml is a range, a tag or a git
# source without a commit, because the next install would take a release nobody tested, and when the pnpm release age is
# lowered or the install-script list is not empty.
#
# Usage: sh scripts/check-pins.sh      (from anywhere; the wrapper finds its own tree)
#
# Optional files are used when they exist: pins.allow (path|name|reason lines) and pnpm-workspace.yaml at the root
# (release age, no install scripts). For a Cargo library add `--cargo-lock Cargo.lock`; for pip files that carry hashes add
# `--pip-require-hashes`; for another pnpm folder add another `--pnpm-workspace PATH`; to keep a setting from being removed add
# `--require-setting .npmrc:save-exact=true`; for the one private Cargo registry a dependency may name add
# `--cargo-registry NAME`.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
set -- --root "$root"
[ -f "$root/pins.allow" ] && set -- "$@" --allow pins.allow
[ -f "$root/pnpm-workspace.yaml" ] && set -- "$@" --pnpm-workspace pnpm-workspace.yaml
exec python3 -I "$here/check-pins.py" "$@"
