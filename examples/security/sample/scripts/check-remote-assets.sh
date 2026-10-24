#!/bin/sh
# check-remote-assets.sh -- the web sources load nothing from another host
#
# Fails when a page, stylesheet or script under the web folder loads an image, font, stylesheet or script from another
# host, because that host then sees every visitor and can change what the page shows or runs.
#
# Usage: sh scripts/check-remote-assets.sh      (from anywhere; the wrapper finds its own tree)
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-remote-assets.py" --allow "$root/web.allow" "$root/web"
