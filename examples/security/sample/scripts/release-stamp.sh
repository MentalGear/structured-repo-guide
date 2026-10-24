#!/bin/sh
# Release step (manual): git-sourced dependencies are pinned by `rev`. A commit cannot contain its own
# hash, so the rev is written at release time.
#   scripts/release-stamp.sh --check     every `rev` in rust/Cargo.toml is one 40-hex value (or none is stamped)
#   scripts/release-stamp.sh <sha>       write <sha> into every `rev = "..."` of rust/Cargo.toml
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
manifest="$root/rust/Cargo.toml"
case "${1:-}" in
  --check)
    revs=$(grep -oE 'rev[[:space:]]*=[[:space:]]*"[^"]*"' "$manifest" | sed 's/.*"\(.*\)"/\1/' | sort -u)
    [ -n "$revs" ] || { echo "release-stamp: OK -- no git dependency in $manifest"; exit 0; }
    [ "$(printf '%s\n' "$revs" | wc -l)" -eq 1 ] || { echo "release-stamp: FAIL -- the revs disagree:" >&2; printf '%s\n' "$revs" >&2; exit 1; }
    printf '%s\n' "$revs" | grep -qE '^[0-9a-f]{40}$' || { echo "release-stamp: FAIL -- rev is not a 40-hex commit: $revs" >&2; exit 1; }
    echo "release-stamp: OK -- every git dependency is pinned to $revs" ;;
  [0-9a-f]*)
    printf '%s' "$1" | grep -qE '^[0-9a-f]{40}$' || { echo "release-stamp: want a 40-hex commit" >&2; exit 2; }
    sed "s/\(rev[[:space:]]*=[[:space:]]*\"\)[^\"]*\"/\1$1\"/" "$manifest" > "$manifest.tmp" && mv "$manifest.tmp" "$manifest"
    echo "release-stamp: wrote $1" ;;
  *) echo "usage: release-stamp.sh --check | <40-hex sha>" >&2; exit 2 ;;
esac
