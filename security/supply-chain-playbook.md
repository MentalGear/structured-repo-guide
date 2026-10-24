# Supply-chain playbook: the controls

This is the list of controls that keep what you depend on, what you build and what you ship from changing without a decision.
Use it when you set up a repository, when you add a dependency, and when you review a pull request that touches a manifest, a
lockfile, a generated file or a script. For each control it gives the reason, the setting or script per ecosystem (Cargo, npm
and pnpm, pip), and how the control is verified, because a control nobody verifies is a wish.

Read [`threat-model.md`](./threat-model.md) first if you want to know what each control stops. The ids (C01 to C19) are the
ids used in [`controls-table.md`](./controls-table.md) and in the runnable checks under
[`../examples/security/`](../examples/security/README.md). An id is never reused or renumbered: a new control takes the next
number, so the sections below run in id order, not in topic order.

**What is shipped and what is a pattern.** Each control says how it is verified. "Shipped" means a script in
[`../examples/security/`](../examples/security/README.md) with a `--self-test`. "Pattern" means the section describes the check
and, where useful, a snippet that you adapt and test yourself; nothing in the guide runs it. A setting that depends on the
version of your tool carries an [unverified](#unverified-confirm-for-your-version) mark unless the section says it was run.

**Ecosystems.** The shipped scripts read Cargo, npm and pnpm, and pip files. The method (read the manifest, fail on whatever
is not exact, allow an exception only with a reason) applies equally to Go, Maven, Gradle, Ruby, PHP, .NET and the rest; the
example scripts do not read those files, so for them you write the same check for their manifest format.

## The approach in one paragraph

Turn each risk into a small, deterministic script that works offline and exits non-zero. Put every script in one list that runs
before every commit (one runner, one list, and a guard that fails when a check script exists that the list does not run;
the runner is [`../examples/gate-runner/run-gates.sh`](../examples/gate-runner/run-gates.sh), documented in
[`../documentation/gate-runner.md`](../documentation/gate-runner.md)).
Where a rule needs a human decision, record the exception in a reasoned allowlist next to the script, and make an allowlist
entry that no longer matches anything fail the run, so exceptions cannot rot. Where the package manager already enforces a
property (a frozen install, a release-age setting), use its setting and add a check that the setting stays. List what you
have not built as `planned`, with the design, instead of leaving it out. Give every script a `--self-test` that applies
mutations and requires each to turn it red.

When the same problem shows up twice, it is a class. Do not fix instances. Find the cause and add the check that makes the
whole class unable to recur. Existing debt goes in a baseline that may only shrink.

## Status words

Used in every table in this guide.

- `enforced`: runs as a gate on every change, or a tool enforces it on every install.
- `manual`: exists, run by a person at a defined moment (a release step, a pre-merge install smoke test).
- `planned`: not built. The row names the design. Its script must not exist yet.

## C01 Exact pins

**Why.** A range (`^1.2.0`, `>=2`, `latest`, a bare Cargo version) lets the next install take a release nobody tested. A git
branch or a URL lets the bytes change under you. An exact version, with a lockfile that records checksums, means the code that
ran in your tests is the code that ships.

**How.**

| Ecosystem | Exact pin |
|---|---|
| Cargo | `serde = "=1.0.200"` or `{ version = "=1.0.200", default-features = false }`. A git dependency names a 40-hex `rev`, never a `branch` or `tag` (they move). `[patch.*]` and `[replace]` entries obey the same rule: a patch is a dependency. |
| npm, pnpm | `"left-pad-ish": "1.3.0"` in `package.json`, no `^` or `~`. Set `"packageManager": "pnpm@10.28.0"` so every machine runs the same pnpm. Put `save-exact=true` in `.npmrc` so `add` writes exact versions (pnpm read it in the version named under [Unverified](#unverified-confirm-for-your-version)). Overrides (`overrides`, `resolutions`, `pnpm.overrides`) replace what a dependency asked for: pin them too. |
| pip | `requests==2.32.3` in `requirements.txt` or in `pyproject.toml` (`[project] dependencies`, optional dependencies, dependency groups, `build-system.requires`). Add hashes (below) for the strongest form. No `>=`, `~=`, `==2.*`, no `name @ url`, no `-e`. |

**No lockfile yet.** Exact pins in a manifest cover only your direct dependencies. Generate the lock first, so every
transitive version is recorded, then read your direct versions from it and commit both. Each command needs the network once:

| Ecosystem | Generate the lock without installing |
|---|---|
| Cargo | `cargo generate-lockfile` |
| pnpm | `pnpm install --lockfile-only` |
| npm | `npm install --package-lock-only --ignore-scripts` |
| pip | `uv pip compile --generate-hashes requirements.in -o requirements.txt`, or `pip-compile --generate-hashes requirements.in` (pip-tools); the input can also be a `pyproject.toml`, and the output is a fully pinned, hashed `requirements.txt` (the pin check reads `requirements*.txt`, not `requirements.in`, so the ranges you want resolved can live in the `.in` file) |

**A git dependency needs a real `rev`.** Ask the remote for the commit instead of copying a hash from a web page:

```sh
git ls-remote https://host/org/repo.git refs/heads/main        # prints "<40-hex>  refs/heads/main"
git ls-remote https://host/org/repo.git 'refs/tags/v1.2.0^{}'  # an annotated tag: the ^{} line is the commit
```

Take the first column and write it as the `rev`. The pin check validates the shape (40 lowercase hex characters) and cannot
tell a real commit from an invented one: a made-up `rev` passes the check and fails at the first build. A fetch of that commit
is the proof, so do it once when you write the `rev`, and again in the release step (C11).

Libraries are the one place where exact pins everywhere hurt: a consumer's resolver cannot find a version that satisfies your
`=` pin and another library's. For a published library, pin exactly the few dependencies that carry code risk (parsers,
anything that runs at build time), and for the rest require that the version floor you declare equals the version in your
lockfile, so the oldest release a consumer may pick is the one your tests ran on. `check-pins.py --cargo-lock Cargo.lock` is
that mode. A Python library's `pyproject.toml` declares ranges on purpose: pass the files you do want checked with
`--pip`/`--pyproject` (an explicit list turns off discovery), or allowlist each entry with its reason.

**Verified by.** Shipped: [`check-pins.py`](../examples/security/check-pins.py) reads `package.json` (dependencies, dev and
optional dependencies, `overrides`, `resolutions`, `pnpm.overrides`), `requirements*.txt`, `pyproject.toml`, `Cargo.toml`
(dependency tables, `[patch.*]`, `[replace]`) and the `overrides:` and `catalog`/`catalogs` mappings of `pnpm-workspace.yaml`
(a `catalog:` reference in a `package.json` is followed to the nearest workspace file), and fails on every dependency that is
not exact. A Cargo dependency that names `registry` or `registry-index` is red unless `--cargo-registry NAME` allows that one
source. `--require-setting FILE:KEY=VALUE` keeps a line such as `.npmrc:save-exact=true` from being removed. An
exception is a line `path|name|reason` in an allowlist; the reason is required and an entry that matches nothing fails.
Its `--self-test` applies a mutation per rule (a caret, a tag, a git source, a missing `rev`, a `[patch]` on a branch, a range
in an override, a pyproject range, a lowered release age, a stale allowlist entry) and requires each to turn it red.

**Not read by the example script, so unchecked:** Go, Maven, Gradle, Ruby, PHP and .NET manifests; `Pipfile`, `setup.py`,
`setup.cfg`, Poetry's `[tool.poetry]` tables and pip constraints files; `peerDependencies` (a contract for consumers, skipped
on purpose); `yarn.lock`; the contents of lockfiles (C18). Whatever you use that is on this list needs its own check.

## C02 Lockfiles committed and verified offline

**Why.** A manifest says what you asked for. The lockfile says what you got, with checksums. A lock that no longer matches
its manifest gets silently rewritten by the next install, and the rewrite is a change nobody reviewed. This happens most with
the lockfiles nobody builds routinely: a detached example crate, a tool folder.

**How.** Commit every lockfile (`Cargo.lock`, `pnpm-lock.yaml` or `package-lock.json`, hashed `requirements.txt`). Verify that
each one still resolves against its manifest without touching the network.

Pattern, not a shipped script. Cargo resolves against the lock before it downloads anything, so `--locked --offline` tells a
stale lock from a good one when the registry index is in the local cache (run `cargo fetch --locked` in your setup step). On a
cold cache it cannot tell, and says so:

```sh
# Cargo: every committed Cargo.lock agrees with its Cargo.toml.
fail=0
for lock in $(git ls-files '*Cargo.lock'); do
  dir=$(dirname "$lock")
  err=$(cargo metadata --locked --offline --format-version 1 --manifest-path "$dir/Cargo.toml" 2>&1 >/dev/null) && continue
  case "$err" in
    *"but --offline was specified"*) continue ;;   # crate files not downloaded: the lock itself was consistent
    *"cannot update the lock file"*) echo "stale lock: $lock" ;;
    *) echo "cannot check $lock (cold registry cache? run cargo fetch first): $(printf '%s\n' "$err" | head -1)" ;;
  esac
  fail=1
done
exit $fail
```

The messages matched are cargo's own wording and can change between versions; they were run against the cargo named in
[Unverified](#unverified-confirm-for-your-version). Your own self-test of the script (copy a repository, add a dependency to a
manifest without updating the lock, expect red) is what keeps it honest.

For npm and pnpm the check is the frozen install itself (C03). For pip the hashed requirements file is the lock; check that
every line carries a hash with `check-pins.py --pip-require-hashes`. Regenerating a pip lock needs the network, so do it in a
deliberate refresh step, never in a gate.

**Verified by.** The snippet above, turned into your own script and listed in your gate list. A lock that would have to change
makes it red.

## C03 Frozen installs only

**Why.** `pnpm add`, `pnpm update`, a plain `npm install`, `cargo update` and `pip install foo` all change what the project
depends on as a side effect of "just getting it to build". CI, agents and new contributors should only ever read the lock.

**How.**

| Ecosystem | Install from the lock only | Never, outside a deliberate dependency change |
|---|---|---|
| Cargo | `cargo build --locked`, `cargo test --locked` (`--frozen` adds `--offline`) | `cargo update`, `cargo add` |
| pnpm | `pnpm install --frozen-lockfile` | `pnpm add`, `pnpm update`, plain `pnpm install` |
| npm | `npm ci` | `npm install <pkg>`, `npm update` |
| pip | `pip install --require-hashes -r requirements.txt` (add `--only-binary :all:` to refuse source distributions) | `pip install <pkg>`, `pip install -U` |

Write the rule into the bootstrap script and into the instructions of every contributor and agent (see
[`agents-and-automation.md`](./agents-and-automation.md)). A dependency change is its own commit that touches the manifest and
the lock together and states why.

**Verified by.** Each tool fails the frozen install when the lock and the manifest disagree (with pnpm 10.28.0 a frozen install
with no lock fails). The hand-made mistake, a gate or a script that rewrote a lock, needs a check you write: after the other
gates ran, no lockfile may differ from the index. Pattern, not a shipped script; make it the last entry of your gate list, and
`git add` a deliberate lock change before running the gates, because the comparison is against what is staged:

```sh
locks=$(git ls-files '*Cargo.lock' '*pnpm-lock.yaml' '*package-lock.json' '*requirements*.txt')
[ -z "$locks" ] || git diff --exit-code --quiet -- $locks || { echo "a lockfile changed while the gates ran"; exit 1; }
```

The `[ -z "$locks" ]` guard matters: `git diff --` with no path compares the whole tree.

## C04 Minimum release age and trust policy

**Why.** Most malicious releases of a popular package are noticed and pulled within hours to days. A rule that refuses
anything younger than N days means you adopt a version only after the community has had that time to look at it. Thirty days
is a reasonable default for tooling and applications; choose your own number and write it down.

**How.**

| Ecosystem | Setting |
|---|---|
| pnpm 10.16 or newer [unverified](#unverified-confirm-for-your-version) | in `pnpm-workspace.yaml`: `minimumReleaseAge: 43200` (minutes, 30 days). An urgent security patch is let through one package at a time with `minimumReleaseAgeExclude`, each entry with a reason comment, removed once the release is old enough. Also `trustPolicy: no-downgrade`, which is meant to fail an install when a package's trust evidence is weaker than that of its earlier releases (what it refuses exactly: [unverified](#unverified-confirm-for-your-version)). |
| pip with uv | `uv pip compile --exclude-newer <date>` limits candidates to releases uploaded before the date. Set the date to today minus your window when you refresh the lock. |
| npm, Cargo, pip without uv | The resolver has no equivalent that this guide has verified; your tool's newer releases may have one, so read your version's configuration reference. Meanwhile use the update bot's delay (Dependabot `cooldown`, Renovate `minimumReleaseAge`; confirm the key in the bot's documentation) so an aged version is the only one it proposes, and for a manual bump read the publish date first: `npm view <pkg> time --json`, `https://pypi.org/pypi/<name>/<version>/json` (`urls[].upload_time_iso_8601`), `https://crates.io/api/v1/crates/<name>/<version>` (`version.created_at`). |

A release-age rule protects a resolution step. A frozen install of an already locked version trusts the lock: with pnpm 10.28.0
an install from an existing lock succeeded under a minimum age far longer than the age of every locked version, while a fresh
resolution under the same setting failed. Treat the lock update as the moment the rule applies.

**Verified by.** Shipped for pnpm: `check-pins.py --pnpm-workspace pnpm-workspace.yaml --min-release-age 43200` fails when
`minimumReleaseAge` is missing or lowered, and `--require-setting pnpm-workspace.yaml:trustPolicy=no-downgrade` fails when that
line is removed. For the others the control is `manual` until you script the publish-date check; say so in the table.

## C05 No dependency install or build scripts

**Why.** A package that runs code when you install or build it runs with your privileges, on your developers' machines and in
CI, before any review of its behaviour. This is the mechanism of most malicious-package incidents: a clean-looking release adds
one new transitive dependency whose install or build script does the harm.

**How.**

| Ecosystem | What runs, and how to stop it |
|---|---|
| pnpm 10 | Dependency lifecycle scripts do not run unless listed. Keep the allowlist explicitly empty in `pnpm-workspace.yaml`: `onlyBuiltDependencies: []`. If a package truly needs a build step, list that one package with a reason comment. (With pnpm 10.28.0, installing a package that has an install script printed "Ignored build scripts" and ran none.) |
| npm | `ignore-scripts=true` in `.npmrc`; `npm ci --ignore-scripts` ([unverified](#unverified-confirm-for-your-version)). |
| pip | A source distribution runs the project's build code at install. `pip install --only-binary :all:` refuses them; a wheel runs nothing at install. |
| Cargo | `build.rs` and procedural macros run at compile time and cannot be switched off. Control them by counting and by allowlist: `inventory.py cargo` reports crates with a build script and proc-macro crates; a dependency-policy tool (`cargo-deny`'s `bans`, with its build-script check, [unverified](#unverified-confirm-for-your-version)) can fail on a new one. A library of your own should have no `build.rs` at all (commit generated code, C06). |

**Verified by.** Shipped for pnpm: `check-pins.py` fails when `onlyBuiltDependencies` is not the empty list. pip: the frozen
install in C03 uses `--only-binary :all:`. Cargo: the count of build scripts is a number in your cost table (C10); a rise is a
decision.

## C06 Generated artifacts with a hash manifest

**Why.** If you commit a generated file (a minified bundle, a compiled grammar, a lookup table), two failures become possible.
The source is edited and the artifact is not regenerated, so the next release ships old behaviour. Or the artifact is edited by
hand, so the next regeneration erases the fix, or the edit is a backdoor reviewed as an unreadable blob. Committing the
generated file also means consumers need no build script, which removes a build-time code runner from every consumer (C05).

**How.** A manifest, written only by the build script, records the sha256 of every source and every output, and the version of
the generator:

```text
tool upcase-1
src 237e41...  greeting.txt
out 49d9be...  greeting.out
```

`artifact-manifest.py build` regenerates every output and rewrites the manifest. Commit the sources, the outputs and the
manifest together. `artifact-manifest.py check` fails on a source whose hash changed, an output whose hash changed, a source
or output missing from the manifest, an output with no source (an orphan), and a manifest entry for a file that is gone. When
the generator is deterministic and its version equals the recorded one, `check` also rebuilds into a temporary directory and
compares bytes, which catches a hand edit that also rewrote the manifest. A different generator version skips the rebuild half
and says so, because a different minifier may emit different bytes. The hash half still holds.

**Verified by.** Shipped: [`artifact-manifest.py`](../examples/security/artifact-manifest.py) in the gate list; its
`--self-test` covers a source edit, an output edit, a new source, an orphan, a deletion, a stale entry, a missing manifest, and
the manifest-rewritten hand edit.

## C07 Allowlists for high-risk dependency classes

**Why.** Some dependencies parse untrusted input or produce markup: Markdown and HTML parsers and renderers, XML and YAML
loaders, template engines, image and archive decoders, serializers with code-execution features. A bug or a malicious change
there is reachable from the outside. For these classes a general "pins and locks" policy is not enough. Fix the surface.

**How.** Pick the one place in the code that is allowed to use the class, then make the following facts checks:

1. **Opt-in.** Only an allowlisted module or package may declare the dependency. A copy-paste cannot make an unrelated
   component depend on a parser.
2. **Exact pin, features off.** The dependency is pinned exactly with default features off (`default-features = false` in
   Cargo, only the extras you name in pip, no optional add-ons in npm), and only the features you name are on.
3. **Fixed closure.** The lockfile entry for the dependency may depend only on the packages you listed. A new transitive
   dependency of the parser fails the check and needs a decision.
4. **Restricted API surface.** The code may call only the allowlisted options (for a Markdown parser: tables and
   strikethrough on; raw HTML, footnotes, metadata blocks, math and heading attributes off), and never the renderer that emits
   raw HTML.
5. **No raw-markup escape hatch.** Grep for the framework's raw-HTML sink (`dangerous_inner_html`, `innerHTML`, `v-html`,
   `|safe`, `Markup(`) and fail on any use outside an allowlisted file.

Each fact is a few lines of script over the manifest, the lockfile and the sources. Write them as one script per class with the
allowlist and the pinned closure at the top.

**Verified by.** Pattern: the script you write, in the gate list, with its allowlist and a stale-entry failure. Mutate a copy
(add a transitive dependency to the lock, enable a feature, add a `v-html`) and confirm each turns it red.

## C08 No hot-linked remote assets

**Why.** An image, font, stylesheet or script loaded from another host sends every visitor's request to that party, lets that
party change what your page shows or runs, and makes your page fail when theirs does. Fonts and avatars from public CDNs are the
usual cases. Bundle the file or inline it.

**How.** Ship the font, the image and the stylesheet with the site. Use `data:` URIs or local files for demo images. Allow an
exception only where the request itself is the point (a fixture that must demonstrate a failed load), with a reason.

**Verified by.** Shipped: [`check-remote-assets.py`](../examples/security/check-remote-assets.py): it flags `src`, `srcset` and
`poster` attributes, `<link href>`, `href` and `xlink:href` on SVG `<image>`, `<use>`, `<feImage>` and `<script>`, `<object data>`,
CSS `url(...)`, `@import` and strings in `image-set(...)`, and module imports (`import ... from`, `import "..."`,
`import("...")`, `export ... from`) that point at `http(s)://` or `//host`. The allowlist is `file-suffix|exact-url|reason`; a
stale entry fails. It does not follow a URL that a script builds at runtime or hands to `fetch`, `XMLHttpRequest`,
`WebSocket`, `new Worker`, `importScripts` or `new URL`, and it does not read `<meta http-equiv="refresh">`; if you load
resources that way, extend it or add a Content-Security-Policy and test that.

## C09 Registry and source URLs pinned

**Why.** A package name with no source is resolved from whatever source the tool defaults to, which may not be the one you
meant. A second index lets a public package with the same name as your private one win ("dependency confusion"). A source URL
spelled three ways across a README, a manifest and a template drifts, and one of them ends up pointing somewhere else.

**How.**

- **One constant.** The URL of your registry or git source is a single string in one file. Every other spelling (install
  commands in the README, manifests, templates, the CLI default) must equal it, and one script compares them.
- **pip:** one `--index-url`; never `--extra-index-url` (a second index is a confusion path), `--find-links` or
  `--trusted-host`. `check-pins.py` fails on all three.
- **npm and pnpm:** one `registry=` in `.npmrc`; scoped registries only for your own scope; no git or tarball dependencies
  (`check-pins.py` rejects them in your manifest; pnpm's `blockExoticSubdeps: true` is meant to reject them among transitive
  dependencies, [unverified](#unverified-confirm-for-your-version)).
- **Cargo:** `[registries]` and `[source]` in `.cargo/config.toml` name the one allowed source; a dependency-policy tool's
  `sources` check (`unknown-registry = "deny"`, `unknown-git = "deny"`, [unverified](#unverified-confirm-for-your-version))
  fails on any other. Prefer a `rev` over a `branch`.
- **A dependency without its source.** Where the manifest format lets a dependency name its source explicitly, always do, and
  have a script reject an entry that does not, so a default can never fill the gap.

**Verified by.** Shipped for the manifest side of the rules above: `check-pins.py` fails on a pip `--extra-index-url`,
`--find-links` or `--trusted-host`, on an npm git or tarball dependency, on a Cargo git dependency without a `rev`, and on a
Cargo dependency that names a registry other than the ones you pass with `--cargo-registry`. It does not read `.npmrc`'s
`registry=` lines, `.cargo/config.toml`'s `[registries]` and `[source]`, or `pip.conf`, and it does not read transitive
dependencies (C18). The comparison of every spelling of your URL and the config files above are patterns, because which
spellings exist depends on your layout: parse, compare, fail, the same pattern as C14.

## C10 Dependency evaluation

**Why.** Every dependency is code you run and a maintainer you trust. Before adding one, and when reviewing existing ones, decide
deliberately. Without numbers the decision is an impression.

**How.** Judge on two kinds of risk and one cost:

- **Code risk:** what the code can do to you. It runs at build time (build script, proc-macro, install script), it contains
  `unsafe` or native code, it parses untrusted input, it touches the network, the file system or user data.
- **Channel risk:** how likely a bad release is. One maintainer or many, released by hand or from CI, recent ownership change,
  a young package, a long gap in releases.
- **Cost:** transitive package count, compile time, shipped bytes.

Take the first rung of this ladder that resolves the reason (cheapest and most reversible first):

1. **Drop** it (unused, or only for something you can delete).
2. **Feature-gate** it (only the users of that module pay), or **turn off an unused feature** of it.
3. **Pin exactly** (C01). Fixes channel risk, not code risk.
4. **Replace** it with the standard library, a platform API or a few lines of your own.
5. **Lift** it (copy the small slice you use into your tree). Fixes channel risk and removes a package from advisory scans, so
   only for a small, stable slice, and then scan the lifted code like a dependency: a header naming
   `lifted-from: package@version`, an advisory check against that version, licence and `unsafe` review. Lifting does not
   reduce code risk, you now own the same code.
6. **Keep** it.

**Veto.** Hard-to-get-right domains stay a library, even if a rule says to lift them: time zones, colour science, cryptography,
parsers, the framework itself. The veto exempts them from lifting, not from the controls of C05 and C07.

**The cost table.** One row per direct dependency. Counts come from the tool, not from memory.

| Dependency | Use (call sites) | Cost (packages, build scripts, proc-macros) | Code risk | Channel risk | Blast radius | Outcome |
|---|---|---|---|---|---|---|
| `date-lib` 2.4.1 | 190 call sites in 2 modules | +5 packages behind a feature; 1 proc-macro | `unsafe` in the local-offset code, parses no input | 1 maintainer for 5 packages | 2 of 40 modules | keep, already feature-gated; trim the macros feature |
| `markup-parser` =1.8.0 | 1 import | +4 packages, no build script | parses untrusted text | 3 maintainers | 1 module | keep, isolated in one module, exact pin (C07) |
| `icon-set` =0.2.0 | 12 icons used | +1 package; a `build.rs` in every consumer build | build script runs on the consumer's machine | young, 1 human maintainer | 25 of 40 modules | replace: lift the 12 SVGs |

These rows are illustrative, not data. Blast radius is how many of your packages or entry points pull the dependency in.

**Measuring.** Shipped: [`inventory.py`](../examples/security/inventory.py) reads what your package manager already prints (the
commands were run with the tool versions named in [Unverified](#unverified-confirm-for-your-version)):

```sh
cargo fetch --locked && cargo metadata --locked --offline --format-version 1 | python3 -I inventory.py cargo
npm install --package-lock-only --ignore-scripts && python3 -I inventory.py npm < package-lock.json
pip install --dry-run --ignore-installed --quiet --report - -r requirements.txt | python3 -I inventory.py pip
cargo tree -e normal --prefix none -p <your-crate> | sort -u | wc -l     # unique packages in what consumers compile
```

Measure the closure your users install, not the whole workspace. A workspace's lock holds everything the workspace builds
(tooling, examples, tests, other targets); a consumer installs a closure that is usually much smaller, and that is the number
the cost table needs. Record what you could not measure (bytes per package, compile time, the full advisory list) in the table
instead of guessing.

**Verified by.** Review, not a script: the table is a decision record. Make it harder to skip by adding a check that every
direct dependency in a manifest has a row (a register file with one entry per dependency, schema-checked, a version bump
re-opens the entry). Counts of build scripts and proc-macros are shrink-only ratchets: a baseline that may fall, never rise.

## C11 Release stamping

**Applies to** projects that publish installable templates or git-sourced registries, or any dependency that another project
takes by git `rev`. Skip it otherwise.

**Why.** A commit cannot contain its own hash. A git-sourced dependency pinned by `rev` therefore cannot name the commit that
publishes it until after that commit exists. Without a rule, a repository's registry entries, its starter template and its
library crate resolve to different commits, and a user builds something you never tested.

**How.** A release script takes the commit hash and writes it as the one `rev` into every git-sourced dependency entry and
the starter template. In development the field is unstamped. The tree is either all unstamped or all one 40-hex value.
The script refuses a commit whose library code differs from the tree being stamped, and has a `--check` that reports any
disagreement and a `--remove` that returns to the development state.

**Verified by.** The `--check` mode in the gate list (all unstamped or all equal), and the release step itself as a `manual`
control. Shipped, short version: [`sample/scripts/release-stamp.sh`](../examples/security/sample/scripts/release-stamp.sh).
`--check` validates the shape of the `rev`; `git ls-remote` proves the commit exists (see C01).

## C12 Advisory scan against a pinned snapshot

**Why.** Known vulnerabilities and yanked versions in what you lock are the cheapest class to find. But the answer changes with
the calendar: a gate that asks the network "is anything vulnerable today?" is red on a tree nobody touched. A gate must give one
verdict for one tree.

**How.** Split the work in two.

- **The gate** reads a committed snapshot of the advisory database (a revision pin) and the lockfile and reports. It is offline
  and deterministic. Tools that fit: `cargo-deny` (`advisories`, plus `bans`, `sources` and `licenses` in one run) for Cargo,
  `osv-scanner` over `Cargo.lock`, `pnpm-lock.yaml` and `requirements.txt` for all three. Use one tool per ecosystem, not two
  that read the same database.
- **The refresh** is a separate, networked script, never in the gate list. It advances the snapshot pin, re-runs the scan, and
  checks that every locked version still exists on the registry (a yank or a deletion). Its output is a committed diff. A
  refresh may turn the gate red; that is the intended signal.

Start with the cheap, offline classes first (bans on new build scripts, allowed sources, allowed licences), then advisories,
then an exact-version trust register (`cargo-vet`) if the closure justifies the work.

**Verified by.** Mark this `planned` in the controls table until the script exists. When it lands, the controls-table check
makes you flip the row.

## C13 Workflow files grant least privilege

**Why.** CI jobs and automated agents run your install and build steps, hold your tokens, and read text from the outside. They
widen every earlier risk: a pull request can propose code that a workflow runs, and an agent can be told, by text in an issue or
a web page, to install a package. [`agents-and-automation.md`](./agents-and-automation.md) has the full rules for agents; they
are policy for a person or an agent to follow, and what checks them is the controls they lean on (C01 for a new dependency,
C03 for a rewritten lock) and the agent's own configuration. The rules for the workflow files themselves are four, and all
four are checkable from the file:

- Every workflow declares `permissions:`, read-only at the top level, widened per job.
- Nothing is `write-all`.
- A workflow triggered by a pull request from a fork gets no secrets and a read-only token; a privileged trigger
  (`pull_request_target` and its equivalents) never checks out and runs the proposed head.
- Third-party actions are pinned to a commit hash, not a tag.

(The trigger and token behaviour described here is GitHub Actions'; confirm it for your CI system, [unverified](#unverified-confirm-for-your-version).)
An automatic-execution freeze (all workflows manual-trigger only) removes one risk as a side effect. Do not list it as a
control unless it was chosen for that reason and is verified.

**Verified by.** Shipped for GitHub Actions: [`check-workflow-permissions.py`](../examples/security/check-workflow-permissions.py)
reads `.github/workflows/*.yml` and fails on a workflow with no `permissions:` at the top or in every job, a `write-all`, a
write scope at the top level (block or flow-style map), a privileged trigger that checks out the head (a `ref:` or
`repository:` naming it, or a `run:` step that names it or fetches it by hand, such as `gh pr checkout` or `pull/<n>/head`),
and an action not pinned to 40 hex (with a `# pin-ok: <reason>` escape). Its `--self-test` plants each flaw. It reads the
file, not the repository's own Actions setting, and it does not read other CI systems: for those, write the same four
questions against their format. It also does not follow a head that reaches a step through an indirection (an `env:` value or
a step output that holds the head ref, a reusable workflow, a script that runs `git` itself, an artifact that a
`workflow_run` workflow downloads); keep the privileged workflow free of steps that run proposed code at all, and treat the
check as a net for the direct forms.

## C14 The controls table stays true

**Why.** A security document that lists controls is read as a promise. If a script was deleted or never written, the promise is
a lie, and the reader decides on it. Make the document a property of the tree.

**How.** Keep one table, one row per control (id, control, threat, script, config, where it runs, status, evidence), and parse it
with a script. [`controls-table.md`](./controls-table.md) is the format and the example; a three-row table you can copy is
[`starter/docs/supply-chain.md`](../examples/security/starter/docs/supply-chain.md).

**Verified by.** Shipped: [`check-controls-table.py`](../examples/security/check-controls-table.py) in the gate list. It fails
when an enforced or manual row names a path that does not exist, when a planned row's script already exists, when a script in
the declared set is in no row, when a gate row is not in the gate list, when the counts are wrong, and when the security policy
does not link the playbook or still holds a template placeholder. Its `--self-test` copies the tree and applies one mutation at a time.

## C15 A clean-room consumer install

**Why.** What your users compile is not what your tests compile. In your repository every dependency is already declared
somewhere, the workspace unifies features, caches are warm and sources point at your own checkout. A user starts from an empty
project, adds your package the way your instructions say, and builds. The two can differ by a missing file, an undeclared
dependency, a feature that only builds with another switched on, a manifest that still names upstream's source. Nothing
inside the repository can see that, because the repository is the one place where it works.

**How.** A script that does what a user does, in a place that cannot see your tree:

1. Copy the working tree (tracked and untracked files, honouring the ignore file, so uncommitted edits are tested) into a
   throwaway directory, and make it a git repository if the install reads git.
2. Rewrite every source URL in the copy (registry, git dependency, template) to the copy, because otherwise the install reads
   upstream's published version, not the tree under test.
3. Create the consumer project the way a user starts one, with none of your dependencies pre-declared: not the project your
   own template pre-fills, a bare one.
4. Install every installable unit the way the instructions tell a user to (a package-manager add, a registry client, a copy
   step), from the copy.
5. Build or type-check the consumer with an absolute scratch build directory and a cache directory inside the scratch
   directory (a stale cache from an earlier run must never be reused), with incremental build state off where the tool has it.
6. Delete everything on exit.

Pattern, not a shipped script. The copy step, with `tar` (GNU or BSD) so it does not depend on `cp --parents`; a tracked
file that you deleted and did not commit makes `tar` complain, so stage or restore it first:

```sh
work=$(mktemp -d) && trap 'rm -rf "$work"' EXIT
mkdir "$work/src"
git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf - | tar -xf - -C "$work/src"
```

It is slow and large (a cold build of the consumer), so it is a `manual` control: run it whenever the manifest of an
installable unit, its file list or its dependencies change, and before a release. A fast static approximation that runs in the
gates (C16) catches most of what it would find.

**Verified by.** `manual`: the script's exit status, quoted in the pull request that changed an installable unit. Threat T8.

## C16 Declared equals used

**Why.** An installable unit (a package, a plugin, a component directory) ships with a manifest that says what it needs. When a
source file uses a package that the manifest does not name, the unit compiles in your repository, where something else declared
it, and fails in a consumer's. The declared set understates what really builds, which also understates what you ask consumers
to trust.

**How.** For every shipped unit, compute the external packages its own sources import and require each one to appear in the
unit's own manifest, or in the manifest of a unit it depends on (the dependency closure the installer brings along). Skip the
standard library and whatever the consumer is known to own (the framework itself). The scan is language-specific: Rust `use
name::` and `name::path`, JavaScript and TypeScript `import ... from 'name'` and `require('name')`, Python `import name` and
`from name import` (an import name can differ from the distribution name: keep a small table). The reverse direction, a declared
package that nothing uses, is a cost to every consumer, so report it too and decide whether it fails.

Pattern, not a shipped script: the scan is small but depends on your layout. Put it in the gate list, keep a reasoned allowlist
for names that are deliberately undeclared, and mutate a copy (delete one declared package, expect red).

**Verified by.** The script you write, in the gate list, and C15 as the slow proof behind it. Threats T8 and T4.

## C17 Optional features build alone

**Why.** A package with optional features lets a consumer pay only for what they use. In your own workspace every build turns on
the union of features, so a module that quietly depends on another module's optional dependency compiles for you and breaks for a
consumer who enabled only the feature they asked for. The cost the feature gate promised is then also false: everyone pays for
the dependency.

**How.** Build the package on its own, outside the workspace's unification: with no optional feature, with each optional
feature alone, and with all of them together. Read the list of features from the manifest so that a new feature is covered the
day it appears. In Cargo that is `cargo check -p <crate> --no-default-features` plus `--features <f>` for each `f` (a feature
that only forwards to another feature of the same crate needs no run of its own), and `--all-targets` for the empty set so tests
and benches are included. For npm entry points and Python extras the equivalent is a clean install in a scratch directory per
extra or per entry point (`pip install '.[extra]'`, an import of each subpath export) with only what that one declares.

Pattern, not a shipped script. It compiles the package, so it is a build gate: give it an absolute scratch build directory and
run it with the other build gates, not in the fast set.

**Verified by.** The script you write; mutate a copy by using an optional dependency from a module that is not behind its
feature, expect red. Threats T4 and T8.

## C18 No tarball or git resolution in the lockfile

**Why.** A pin check reads manifests. The lockfile is what is actually fetched, and a transitive dependency can be resolved from a
tarball URL or a git source even when every direct dependency is a registry release: the lock then names bytes that a
registry's immutability and checksum rules do not cover.

**How.** Read each lockfile and fail on any resolved source that is not the one registry you allow: in `pnpm-lock.yaml` a
resolution with a `tarball:` URL or a `type: git` entry, in `package-lock.json` a `resolved` that is not your registry's host,
in `Cargo.lock` a `source` that is not the registry's index (a `git+` source needs the `rev` check of C01 and an allowlist
entry), in a hashed `requirements.txt` a line that is a URL rather than `name==version`. Where the package manager can block
this itself (pnpm's `blockExoticSubdeps`), use the setting and add this check so the setting cannot be removed unnoticed. The
lockfile field names above are from memory of the formats, [unverified](#unverified-confirm-for-your-version).

`planned`: the design is above and no script ships. When it lands, list its script in the table; the controls-table check then
makes you flip the row. Threats T1 and T7.

## C19 Named owners review the controls

**Why.** A contributor who can edit a check, an allowlist or a workflow can turn it off. Review by a named owner on those paths
is the control; the repository host enforces it, not a script in the tree.

**How.** `CODEOWNERS` names an owner for the check scripts, the allowlists, the controls table, the workflow files and the
manifests, and branch protection requires that owner's review. Fork pull requests run without secrets (C13).

**Verified by.** `manual`: the settings live in the repository host. The controls-table row names `CODEOWNERS` as its config
(so deleting the file turns the table check red) and says where the branch-protection setting is. Threats T10 and T11.

## Unverified, confirm for your version

Settings and commands that depend on a tool's version. Each line says whether the author of this guide ran it, and against
which version. A line under "Not run" is the guide's best knowledge: read your version's documentation before relying on
it, and when you confirm one, test it with a mutation (remove the setting, expect the install or the check to change).

Run, with the versions named:

- **pnpm 10.28.0:** the setting names `minimumReleaseAge`, `minimumReleaseAgeExclude`, `onlyBuiltDependencies`, `trustPolicy`,
  `blockExoticSubdeps` and `trustPolicyExclude` appear in that release. `onlyBuiltDependencies: []` ran no install script of
  a dependency that has one ("Ignored build scripts"). `minimumReleaseAge` made a fresh resolution fail, and did not stop
  a `--frozen-lockfile` install of an existing lock. `save-exact=true` in `.npmrc` made `pnpm add` write an exact version.
  `pnpm install --frozen-lockfile` with no lock fails.
- **cargo 1.97.0:** the two messages the C02 snippet matches (`cannot update the lock file` for a stale lock, `but --offline was
  specified` for a crate not downloaded), and that a cold registry index fails `--locked --offline` with `no matching package
  named`.
- **uv 0.11.32:** `uv pip compile --exclude-newer <date> --generate-hashes` pins every dependency, with hashes, to releases before
  the date.
- **npm 10.9.4 and pip 24.0:** the `inventory.py` commands in C10 produce input the script reads.

Not run:

- **When each pnpm setting first exists:** `minimumReleaseAge` in 10.16 and `trustPolicy` in 10.21 are the versions this guide
  was given; `blockExoticSubdeps` has no version stated at all.
- **What `trustPolicy: no-downgrade` and `blockExoticSubdeps: true` actually refuse**, and whether `trustPolicyExclude` is the
  way to except one package.
- **That pnpm reads `save-exact` from `.npmrc` in every version** (it did in 10.28.0), and that `onlyBuiltDependencies` is still
  the setting's name in newer majors.
- **npm** `ignore-scripts=true` in `.npmrc` and `npm ci --ignore-scripts`; **pip** `--require-hashes` and `--only-binary :all:`
  (standard options, not run).
- **cargo-deny**: that `bans` can fail on a new build script, and the keys `unknown-registry` and `unknown-git` under `sources`.
- **Dependabot `cooldown` and Renovate `minimumReleaseAge`:** the key names and where they go.
- **A Cargo minimum-publish-age setting:** whether your Cargo has one and what it is called.
- **Lockfile field names in C18:** `tarball`, `type: git`, `resolved`, `source`.
- **GitHub:** the menu path to private vulnerability reporting, and the behaviour of `pull_request_target`, fork tokens and
  `permissions:` defaults described in C13.

## Decisions to take once and write down

- **Vendoring.** Copying a dependency's source into your tree moves the review burden onto you and keeps a malicious release
  after the registry removes it. A lockfile with checksums already pins the exact bytes. Prefer a lockfile plus review of each
  update over vendored copies, and lift only a small slice (C10).
- **Gates are offline and deterministic.** What changes with the calendar (new advisories, yanks, publisher changes) lives in a
  separate refresh step that writes a snapshot (C12).
- **Ratchets, not budgets.** A budget with headroom creeps. A baseline that may only shrink, with a reasoned allowlist and a
  failing stale entry, does not.
- **Tools are trusted as installed.** The compiler, the package manager, the bundler and browsers are outside this playbook.
  Pin their versions (`packageManager`, a toolchain file, a recorded generator version in the C06 manifest) and verify a
  checksum when you download a binary in a bootstrap script. State this as out of scope in the threat model.

## Adopt in this order

Each step is useful alone. Stop where the cost stops paying.

1. A private reporting channel and a `SECURITY.md` ([`vulnerability-reporting.md`](./vulnerability-reporting.md)).
2. One gate list and runner with the guard, shared with the documentation checks (C14's table is useless without it).
3. Lockfiles committed and verified (C02), frozen installs (C03).
4. Exact pins (C01) and the pnpm settings (C04, C05).
5. Generated files with a manifest (C06), if you commit any.
6. Allowlist for the one risky parser or renderer (C07), if you have one.
7. No remote assets (C08), pinned registry URLs (C09), and release stamping (C11) if you publish installable templates or
   git-sourced registries.
8. Workflow files that grant least privilege (C13) and named owners (C19), if you run CI.
9. The controls table and its check (C14).
10. If you ship installable units: declared equals used (C16), optional features built alone (C17), and the clean-room
    consumer install (C15).
11. Advisory scan with a pinned snapshot and a refresh step (C12), lockfile source check (C18), then the dependency register
    (C10).

The five-minute version is in [`README.md`](./README.md).
