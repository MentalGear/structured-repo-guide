#!/bin/sh
# Runs every example against the sample tree, runs every self-test, replays the adopt path of security/README.md in a
# fresh git repository, then breaks a copy of the sample six ways and requires the gates to turn red.
# Needs sh, tar, git and python3 (3.11 or newer).
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
$py "$here/check-workflow-permissions.py" --self-test | tail -1
$py "$here/check-controls-table.py" --root "$here/sample" --doc docs/supply-chain.md --security SECURITY.md \
  --gate-list scripts/gates.list --declared scripts/supply-chain-scripts.txt \
  --heading '## Threat model' --heading '## Controls' --self-test | tail -1

step "the security documents agree with the tree"
doc_fail() { echo "  FAIL docs: $*" >&2; exit 1; }
# A count written into prose goes stale the moment a case is added: the self-test prints its own count.
if grep -nE '[0-9]+[ -](cases?|mutations?)\b' "$here/../../security/"*.md "$here/README.md" >/dev/null; then
  grep -nE '[0-9]+[ -](cases?|mutations?)\b' "$here/../../security/"*.md "$here/README.md" >&2
  doc_fail "a hard-coded self-test count"
fi
echo "  ok   no document hard-codes a self-test count"
# One name for the group: the documents say `Security`, so the sample's gate list does too.
grep -q '^# group: Security$' "$here/sample/scripts/gates.list" || doc_fail "the sample gate list is not in the Security group"
if grep -rn 'group: Supply chain' "$here/sample" "$here/starter" "$here/../../security" >/dev/null 2>&1; then doc_fail "a security group named Supply chain"; fi
echo "  ok   the sample's group is Security, as security/README.md says"
# An example table must not state as enforced what the playbook marks unverified.
if grep -n '^| C04 .*trustPolicy' "$here/../../security/controls-table.md" "$here/sample/docs/supply-chain.md" "$here/starter/docs/supply-chain.md" >/dev/null 2>&1; then
  doc_fail "an example controls-table row states trustPolicy enforcement as fact"
fi
echo "  ok   no example table row states an unverified pnpm setting as enforced"

step "the sample's copy of the runner is the shared one"
cmp "$here/../gate-runner/run-gates.sh" "$here/sample/scripts/run-gates.sh"
echo "  ok   examples/security/sample/scripts/run-gates.sh is byte-identical to examples/gate-runner/run-gates.sh"

step "the sample tree: one runner, every gate"
sh "$here/sample/scripts/run-gates.sh"

step "the adopt path (security/README.md, steps 1 to 5) in a fresh git repository"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
guide=$(cd "$here/../.." && pwd)
ad="$tmp/adopt"
mkdir -p "$ad/scripts" "$ad/docs" "$tmp/remote"
# A project with no lockfile: a JavaScript manifest and a Python requirements file with ranges, and a git dependency on a branch.
# The "remote" is a local repository, so `git ls-remote` can be run for real.
git -C "$tmp/remote" init -q
git -C "$tmp/remote" -c user.name=t -c user.email=t@localhost -c commit.gpgsign=false commit -q --allow-empty -m init
git -C "$tmp/remote" branch -M main
git -C "$ad" init -q
printf '{ "name": "app", "private": true, "dependencies": { "left-pad": "^1.3.0" } }\n' > "$ad/package.json"
printf 'requests>=2.0\n' > "$ad/requirements.txt"
printf '[package]\nname = "app"\nversion = "0.1.0"\n[dependencies]\nforked = { git = "file://%s/remote", branch = "main" }\n' "$tmp" > "$ad/Cargo.toml"
# Step 2: the one runner of the repository, its list, and the first check.
cp "$guide/examples/gate-runner/run-gates.sh" "$here/check-pins.py" "$here/starter/scripts/check-pins.sh" "$ad/scripts/"
printf '# group: Security\ncheck-pins|sh scripts/check-pins.sh\n' >> "$ad/scripts/gates.list"
must_fail() { # description, expected text in the output, command...
  d=$1; want=$2; shift 2
  if out=$("$@" 2>&1); then echo "  FAIL $d: stayed green" >&2; exit 1; fi
  case "$out" in *"$want"*) echo "  ok   $d -> red ($want)" ;; *) echo "  FAIL $d: red without \"$want\":" >&2; echo "$out" >&2; exit 1 ;; esac
}
must_pass() { # description, command...
  d=$1; shift
  if out=$("$@" 2>&1); then echo "  ok   $d -> green"; else echo "  FAIL $d:" >&2; echo "$out" >&2; exit 1; fi
}
(
  cd "$ad"
  must_fail "step 3: ranges and a git branch are listed" "not an exact version" sh scripts/check-pins.sh
  sed 's/\^1.3.0/1.3.0/' package.json > package.json.new && mv package.json.new package.json
  sed 's/>=2.0/==2.32.3/' requirements.txt > requirements.txt.new && mv requirements.txt.new requirements.txt
  must_fail "step 3: the git dependency still needs a rev" "needs \`rev\`" sh scripts/check-pins.sh
  rev=$(git ls-remote "file://$tmp/remote" refs/heads/main | cut -f1)
  sed "s|branch = \"main\"|rev = \"$rev\"|" Cargo.toml > Cargo.toml.new && mv Cargo.toml.new Cargo.toml
  must_pass "step 3: a rev read with git ls-remote" sh scripts/check-pins.sh
  must_pass "step 3: the runner's full run is ALL GREEN" sh scripts/run-gates.sh

  cp "$guide/templates/SECURITY.md" SECURITY.md
  cp "$here/check-controls-table.py" "$here/check-remote-assets.py" scripts/
  cp "$here/starter/scripts/check-controls-table.sh" "$here/starter/scripts/check-remote-assets.sh" \
     "$here/starter/scripts/supply-chain-scripts.txt" scripts/
  cp "$here/starter/docs/supply-chain.md" docs/
  must_fail "step 5: the runner refuses while the new check scripts are not in its list" "not in the gate list" sh scripts/run-gates.sh
  must_fail "step 5: the unedited policy template" "placeholder" sh scripts/check-controls-table.sh
  printf '# Security policy\n\nReport privately to security@example.invalid.\n\nControls: [docs/supply-chain.md](./docs/supply-chain.md).\n' > SECURITY.md
  must_fail "step 5: the new gates are not in the list yet" "is not in the gate list" sh scripts/check-controls-table.sh
  printf 'check-remote-assets|sh scripts/check-remote-assets.sh\ncheck-controls-table|sh scripts/check-controls-table.sh\n' >> scripts/gates.list
  must_pass "step 5: the starter table is true of the tree" sh scripts/check-controls-table.sh
  must_pass "step 5: the full run is ALL GREEN" sh scripts/run-gates.sh
  must_pass "step 5: remote assets (no web folder: says so)" sh scripts/check-remote-assets.sh
  sed 's/^| T9 .*$//; s/^| C08 .*$//; s/3 enforced/2 enforced/' docs/supply-chain.md > docs/supply-chain.md.new && mv docs/supply-chain.md.new docs/supply-chain.md
  must_fail "step 5: deleting the C08 rows but not the declared script" "is in no controls-table row" sh scripts/check-controls-table.sh
  grep -v check-remote-assets scripts/supply-chain-scripts.txt > scripts/s.new && mv scripts/s.new scripts/supply-chain-scripts.txt
  rm scripts/check-remote-assets.sh scripts/check-remote-assets.py
  grep -v check-remote-assets scripts/gates.list > scripts/g.new && mv scripts/g.new scripts/gates.list
  must_pass "step 5: the table trimmed to two controls" sh scripts/check-controls-table.sh
  must_pass "step 5: and the full run is still ALL GREEN" sh scripts/run-gates.sh
)

step "the sample tree under the shared runner (examples/gate-runner/run-gates.sh) instead of its own"
mkdir -p "$tmp/shared"
cp -R "$here/." "$tmp/shared/"
cp "$guide/examples/gate-runner/run-gates.sh" "$tmp/shared/sample/scripts/run-gates.sh"
if ! (cd "$tmp/shared/sample" && sh scripts/run-gates.sh > "$tmp/shared.log" 2>&1); then cat "$tmp/shared.log" >&2; exit 1; fi
tail -2 "$tmp/shared.log"

step "the inventory, on inline fixtures (no package manager needed)"
printf '%s' '{"packages":[{"source":"registry+x","targets":[{"kind":["custom-build"]},{"kind":["lib"]}]},{"source":"registry+x","targets":[{"kind":["proc-macro"]}]},{"source":null,"targets":[{"kind":["lib"]}]}]}' \
  | $py "$here/inventory.py" cargo
printf '%s' '{"packages":{"":{},"node_modules/a":{"hasInstallScript":true},"node_modules/b":{}}}' | $py "$here/inventory.py" npm
printf '%s' '{"install":[{"download_info":{"url":"https://h/a-1.whl"}},{"download_info":{"url":"https://h/b-1.tar.gz"}}]}' \
  | $py "$here/inventory.py" pip

step "the manual control"
sh "$here/sample/scripts/release-stamp.sh" --check

step "break a copy of the sample six ways; every break must turn a gate red"
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

reset; sed '/^permissions:/,/^  contents: read/d' "$tmp/security/sample/.github/workflows/ci.yml" > "$tmp/p" && mv "$tmp/p" "$tmp/security/sample/.github/workflows/ci.yml"
expect_red "a workflow with no permissions block" scripts/check-workflow-permissions.sh

printf '\nexamples/security: ALL OK\n'
