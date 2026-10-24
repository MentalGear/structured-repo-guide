#!/bin/sh
# Gate: every dependency in every manifest is an exact pin (or allowlisted with a reason),
# and the pnpm settings keep the 30-day release age and the empty install-script list.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-pins.py" --root "$root" --allow pins.allow \
  --pnpm-workspace js/pnpm-workspace.yaml --min-release-age 43200
