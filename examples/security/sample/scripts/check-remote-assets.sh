#!/bin/sh
# Gate: the web sources load nothing from another host.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-remote-assets.py" --allow "$root/web.allow" "$root/web"
