#!/bin/sh
# Runs every example against the sample tree, runs every self-test, then breaks a copy of the sample five
# ways and requires the gates to turn red. Needs sh, tr and python3 (3.11 or newer).
#
# Usage: examples/security/run-examples.sh        Exit status: 0 when everything behaves as documented.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
py="python3 -I"

step() { printf '\n== %s\n' "$*"; }

step "self-tests (each mutation must turn its checker red)"
$py "$here/check-pins.py" --self-test | tail -1
$py "$here/artifact-manifest.py" --self-test | tail -1
$py "$here/check-remote-assets.py" --self-test | tail -1
$py "$here/check-controls-table.py" --root "$here/sample" --doc docs/supply-chain.md --security SECURITY.md \
  --gate-list scripts/run-gates.sh --declared scripts/supply-chain-scripts.txt \
  --heading '## Threat model' --heading '## Controls' --self-test | tail -1

step "the sample tree: one entry point, every gate"
sh "$here/sample/scripts/run-gates.sh"

step "the inventory, on inline fixtures (no package manager needed)"
printf '%s' '{"packages":[{"source":"registry+x","targets":[{"kind":["custom-build"]},{"kind":["lib"]}]},{"source":"registry+x","targets":[{"kind":["proc-macro"]}]},{"source":null,"targets":[{"kind":["lib"]}]}]}' \
  | $py "$here/inventory.py" cargo
printf '%s' '{"packages":{"":{},"node_modules/a":{"hasInstallScript":true},"node_modules/b":{}}}' | $py "$here/inventory.py" npm
printf '%s' '{"install":[{"download_info":{"url":"https://h/a-1.whl"}},{"download_info":{"url":"https://h/b-1.tar.gz"}}]}' \
  | $py "$here/inventory.py" pip

step "the manual control"
sh "$here/sample/scripts/release-stamp.sh" --check

step "break a copy of the sample five ways; every break must turn a gate red"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM
expect_red() { # name, gate script (relative to the copy's sample dir)
  if (cd "$tmp/security/sample" && sh "$2" >/dev/null 2>&1); then
    echo "  FAIL $1: $2 stayed green" >&2; exit 1
  fi
  echo "  ok   $1 -> red"
}
reset() { rm -rf "$tmp/security"; mkdir -p "$tmp/security"; cp -R "$here/." "$tmp/security/"; }

reset; sed 's/"left-pad-ish": "1.3.0"/"left-pad-ish": "^1.3.0"/' "$tmp/security/sample/js/package.json" > "$tmp/p" && mv "$tmp/p" "$tmp/security/sample/js/package.json"
expect_red "a caret range in package.json" scripts/check-pins.sh

reset; printf 'tampered\n' >> "$tmp/security/sample/gen/out/greeting.out"
expect_red "a hand edit of a generated file" scripts/check-artifacts.sh

reset; printf '<img src="https://cdn.example.com/photo.png" alt="">\n' >> "$tmp/security/sample/web/index.html"
expect_red "a hot-linked remote image" scripts/check-remote-assets.sh

reset; sed 's/^minimumReleaseAge: 43200/minimumReleaseAge: 4320/' "$tmp/security/sample/js/pnpm-workspace.yaml" > "$tmp/p" && mv "$tmp/p" "$tmp/security/sample/js/pnpm-workspace.yaml"
expect_red "a weakened release-age setting" scripts/check-pins.sh

reset; rm "$tmp/security/sample/scripts/check-remote-assets.sh"
expect_red "a documented control whose script was deleted" scripts/check-controls-table.sh

printf '\nexamples/security: ALL OK\n'
