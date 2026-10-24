#!/bin/sh
# check-remote-assets.sh -- the web sources load nothing from another host
#
# Fails when a page, stylesheet or script under the web folder loads an image, font, stylesheet or script from another
# host, because that host then sees every visitor and can change what the page shows or runs.
#
# Usage: sh scripts/check-remote-assets.sh      (from anywhere; the wrapper finds its own tree)
#
# Edit `roots` to the folders that hold your pages and styles. A folder that does not exist is skipped, and when none
# exists the gate says so instead of passing silently. `web.allow` (file-suffix|exact-url|reason) is used when it exists.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
roots="web public static site"
set --
for d in $roots; do [ -d "$root/$d" ] && set -- "$@" "$root/$d"; done
if [ $# -eq 0 ]; then
  echo "check-remote-assets: OK -- none of [$roots] exists, nothing to scan (edit roots in this script)"
  exit 0
fi
[ -f "$root/web.allow" ] && set -- --allow "$root/web.allow" "$@"
exec python3 -I "$here/check-remote-assets.py" "$@"
