# Supply-chain playbook: the controls

This is the list of controls that keep what you depend on, what you build and what you ship from changing without a decision.
Use it when you set up a repository, when you add a dependency, and when you review a pull request that touches a manifest, a
lockfile, a generated file or a script. For each control it gives the reason, the setting or script per ecosystem (Cargo, npm
and pnpm, pip), and how the control is verified, because a control nobody verifies is a wish.

Read [`threat-model.md`](./threat-model.md) first if you want to know what each control stops. The ids (C01 to C14) are the
ids used in [`controls-table.md`](./controls-table.md) and in the runnable checks under
[`../examples/security/`](../examples/security/README.md).

## The approach in one paragraph

Turn each risk into a small, deterministic script that works offline and exits non-zero. Put every script in one list that runs
before every commit (one entry point, one list, and a guard that fails when a check script exists that the list does not run).
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
| Cargo | `serde = "=1.0.200"` or `{ version = "=1.0.200", default-features = false }`. A git dependency names a 40-hex `rev`, never a `branch` or `tag` (they move). |
| npm, pnpm | `"left-pad-ish": "1.3.0"` in `package.json`, no `^` or `~`. Set `"packageManager": "pnpm@10.28.0"` so every machine runs the same pnpm. |
| pip | `requests==2.32.3` in `requirements.txt`. Add hashes (below) for the strongest form. No `>=`, `~=`, `==2.*`, no `name @ url`, no `-e`. |

Libraries are the one place where exact pins everywhere hurt: a consumer's resolver cannot find a version that satisfies your
`=` pin and another library's. For a published library, pin exactly the few dependencies that carry code risk (parsers,
anything that runs at build time), and for the rest require that the version floor you declare equals the version in your
lockfile, so the oldest release a consumer may pick is the one your tests ran on. `check-pins.py --cargo-lock Cargo.lock` is
that mode.

**Verified by.** [`check-pins.py`](../examples/security/check-pins.py) reads `package.json`, `requirements*.txt` and
`Cargo.toml` and fails on every dependency that is not exact. An exception is a line `path|name|reason` in an allowlist; the
reason is required and an entry that matches nothing fails. Its `--self-test` applies a mutation per rule (a caret, a tag, a git source, a missing `rev`, a lowered release age, a stale allowlist entry) and requires each to turn it red.

## C02 Lockfiles committed and verified offline

**Why.** A manifest says what you asked for. The lockfile says what you got, with checksums. A lock that no longer matches
its manifest gets silently rewritten by the next install, and the rewrite is a change nobody reviewed. This happens most with
the lockfiles nobody builds routinely: a detached example crate, a tool folder.

**How.** Commit every lockfile (`Cargo.lock`, `pnpm-lock.yaml` or `package-lock.json`, hashed `requirements.txt`). Verify that
each one still resolves against its manifest without touching the network:

```sh
# Cargo: every committed Cargo.lock agrees with its Cargo.toml. A dependency missing from the local
# cache is not a failure (resolution against the lock happens before any download).
fail=0
for lock in $(git ls-files '*Cargo.lock'); do
  dir=$(dirname "$lock")
  err=$(cargo metadata --locked --offline --format-version 1 --manifest-path "$dir/Cargo.toml" 2>&1 >/dev/null) && continue
  case "$err" in *"--offline was specified"*) continue ;; esac
  echo "stale or broken: $lock: $(printf '%s\n' "$err" | tail -1)"; fail=1
done
exit $fail
```

For npm and pnpm the check is the frozen install itself (C03). For pip the hashed requirements file is the lock; check that
every line carries a hash with `check-pins.py --pip-require-hashes`. Regenerating a pip lock needs the network, so do it in a
deliberate refresh step, never in a gate.

**Verified by.** The script above in your gate list. A lock that would have to change makes it red.

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

**Verified by.** Each tool fails the frozen install when the lock and the manifest disagree. Add one gate that catches the
hand-made mistake: after the gates run, `git diff --exit-code -- <every lockfile>` must be empty, so a gate or a script that
rewrote a lock turns the run red.

## C04 Minimum release age

**Why.** Most malicious releases of a popular package are noticed and pulled within hours to days. A rule that refuses
anything younger than N days means you adopt a version only after the community has had that time to look at it. Thirty days
is a reasonable default for tooling and applications; choose your own number and write it down.

**How.**

| Ecosystem | Setting |
|---|---|
| pnpm 10.16 or newer | in `pnpm-workspace.yaml`: `minimumReleaseAge: 43200` (minutes, 30 days). An urgent security patch is let through one package at a time with `minimumReleaseAgeExclude`, each entry with a reason comment, removed once the release is old enough. |
| pip with uv | `uv pip compile --exclude-newer <date>` limits candidates to releases uploaded before the date. Set the date to today minus your window when you refresh the lock. |
| npm, Cargo, pip without uv | The resolver has no equivalent that this guide has verified. Use the update bot's delay (Dependabot `cooldown`, Renovate `minimumReleaseAge`; confirm the key in the bot's documentation) so an aged version is the only one it proposes, and for a manual bump read the publish date first: `npm view <pkg> time --json`, `https://pypi.org/pypi/<name>/<version>/json` (`urls[].upload_time_iso_8601`), `https://crates.io/api/v1/crates/<name>/<version>` (`version.created_at`). |

A release-age rule protects a resolution step. A frozen install of an already locked version trusts the lock. Treat the lock
update as the moment the rule applies.

**Verified by.** For pnpm, `check-pins.py --pnpm-workspace pnpm-workspace.yaml --min-release-age 43200` fails when the setting
is missing or lowered. For the others the control is `manual` until you script the publish-date check; say so in the table.

## C05 No dependency install or build scripts

**Why.** A package that runs code when you install or build it runs with your privileges, on your developers' machines and in
CI, before any review of its behaviour. This is the mechanism of most malicious-package incidents: a clean-looking release adds
one new transitive dependency whose install or build script does the harm.

**How.**

| Ecosystem | What runs, and how to stop it |
|---|---|
| pnpm 10 | Dependency lifecycle scripts do not run unless listed. Keep the allowlist explicitly empty in `pnpm-workspace.yaml`: `onlyBuiltDependencies: []`. If a package truly needs a build step, list that one package with a reason comment. |
| npm | `ignore-scripts=true` in `.npmrc`; `npm ci --ignore-scripts`. |
| pip | A source distribution runs the project's build code at install. `pip install --only-binary :all:` refuses them; a wheel runs nothing at install. |
| Cargo | `build.rs` and procedural macros run at compile time and cannot be switched off. Control them by counting and by allowlist: `inventory.py cargo` reports crates with a build script and proc-macro crates; a dependency-policy tool (`cargo-deny` `bans.build`) can fail on a new one. A library of your own should have no `build.rs` at all (commit generated code, C06). |

**Verified by.** pnpm: `check-pins.py` fails when `onlyBuiltDependencies` is not the empty list. pip: the frozen install in C03
uses `--only-binary :all:`. Cargo: the count of build scripts is a number in your cost table (C10); a rise is a decision.

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

**Verified by.** [`artifact-manifest.py`](../examples/security/artifact-manifest.py) in the gate list; its `--self-test` covers a
source edit, an output edit, a new source, an orphan, a deletion, a stale entry, a missing manifest, and the manifest-rewritten
hand edit.

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

**Verified by.** The script itself, in the gate list, with its allowlist and a stale-entry failure. Mutate a copy (add a
transitive dependency to the lock, enable a feature, add a `v-html`) and confirm each turns it red.

## C08 No hot-linked remote assets

**Why.** An image, font, stylesheet or script loaded from another host sends every visitor's request to that party, lets that
party change what your page shows or runs, and makes your page fail when theirs does. Fonts and avatars from public CDNs are the
usual cases. Bundle the file or inline it.

**How.** Ship the font, the image and the stylesheet with the site. Use `data:` URIs or local files for demo images. Allow an
exception only where the point of the page is a request that cannot succeed (a deliberate broken-image demo), with a reason.

**Verified by.** [`check-remote-assets.py`](../examples/security/check-remote-assets.py): it flags `src`, `srcset` and `poster`
attributes, `<link href>`, CSS `url(...)` and `@import` that point at `http(s)://` or `//host`. The allowlist is
`file-suffix|exact-url|reason`; a stale entry fails. It does not read `<script>` bodies for `fetch(...)` calls; if you load
scripts at runtime, extend it or add a Content-Security-Policy and test that.

## C09 Registry and source URLs pinned

**Why.** Some tools resolve a bare package name in a default registry even when you pointed them at your own. A second index
lets a public package with the same name as your private one win ("dependency confusion"). A source URL spelled three ways
across a README, a manifest and a template drifts, and one of them ends up pointing somewhere else.

**How.**

- **One constant.** The URL of your registry or git source is a single string in one file. Every other spelling (install
  commands in the README, manifests, templates, the CLI default) must equal it, and one script compares them.
- **pip:** one `--index-url`; never `--extra-index-url` (a second index is a confusion path), `--find-links` or
  `--trusted-host`. `check-pins.py` fails on all three.
- **npm and pnpm:** one `registry=` in `.npmrc`; scoped registries only for your own scope; no git or tarball dependencies
  (`check-pins.py` rejects them in your manifest; pnpm's `blockExoticSubdeps: true` is meant to reject them among transitive dependencies, so confirm the setting name in the pnpm settings reference for your version).
- **Cargo:** `[registries]` and `[source]` in `.cargo/config.toml` name the one allowed source; a dependency-policy tool's
  `sources` check (`unknown-registry = "deny"`, `unknown-git = "deny"`) fails on any other. Prefer a `rev` over a `branch`.
- **A manifest that names a git dependency by bare name** is resolved elsewhere by some tools. Use the object form with the
  explicit URL and have the script reject the bare form.

**Verified by.** A script that reads the constant and every spelling and fails on a difference, plus `check-pins.py` for the
index and source rules above. Which spellings exist depends on your layout, so this one is a script you write; the pattern is
the same as C14: parse, compare, fail.

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
| `date-lib` 0.3.47 | 204 call sites in 2 modules | +6 packages behind a feature; 1 proc-macro | `unsafe` in the local-offset code, parses no input | 1 maintainer for 6 packages | 2 of 83 components | keep, already feature-gated; trim the macros feature |
| `markup-parser` =0.13.4 | 1 import | +4 packages, no build script | parses untrusted text | 3 maintainers | 1 component | keep, own component, exact pin (C07) |
| `icon-set` =0.1.0 | 12 icons used | +1 package; a `build.rs` in every consumer build | build script runs on the consumer's machine | young, 1 human maintainer | 30 of 83 components | replace: lift the 12 SVGs |

These rows are illustrative, not data. Blast radius is how many of your packages or entry points pull the dependency in.

**Measuring.** [`inventory.py`](../examples/security/inventory.py) reads what your package manager already prints:

```sh
cargo metadata --locked --offline --format-version 1 | python3 -I inventory.py cargo
npm install --package-lock-only --ignore-scripts && python3 -I inventory.py npm < package-lock.json
pip install --dry-run --ignore-installed --quiet --report - -r requirements.txt | python3 -I inventory.py pip
cargo tree -e normal --prefix none -p <your-crate> | sort -u | wc -l     # unique packages in what consumers compile
```

Measure the closure your users install, not the whole workspace: a docs site, a test folder and a desktop build can add
hundreds of packages no consumer ever compiles. Record what you could not measure (bytes per package, compile time, the full
advisory list) in the table instead of guessing.

**Verified by.** Review, not a script: the table is a decision record. Make it harder to skip by adding a check that every
direct dependency in a manifest has a row (a register file with one entry per dependency, schema-checked, a version bump
re-opens the entry). Counts of build scripts and proc-macros are shrink-only ratchets: a baseline that may fall, never rise.

## C11 Release stamping

**Why.** A commit cannot contain its own hash. A git-sourced dependency pinned by `rev` therefore cannot name the commit that
publishes it until after that commit exists. Without a rule, a repository's registry entries, its starter template and its
library crate resolve to different commits, and a user builds something you never tested.

**How.** A release script takes the commit hash and writes it as the one `rev` into every git-sourced dependency entry and
the starter template. In development the field is unstamped. The tree is either all unstamped or all one 40-hex value.
The script refuses a commit whose library code differs from the tree being stamped, and has a `--check` that reports any
disagreement and a `--remove` that returns to the development state.

**Verified by.** The `--check` mode in the gate list (all unstamped or all equal), and the release step itself as a `manual`
control. [`sample/scripts/release-stamp.sh`](../examples/security/sample/scripts/release-stamp.sh) is a short version.

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

## C13 Rules for automation and review

**Why.** CI jobs and automated agents run your install and build steps, hold your tokens, and read text from the outside. They
widen every earlier risk: a pull request can propose code that a workflow runs, and an agent can be told, by text in an issue or
a web page, to install a package. [`agents-and-automation.md`](./agents-and-automation.md) has the full rules. In short:

- Workflows triggered by pull requests from forks get no secrets and read-only tokens. Never check out and run a fork's code in
  a privileged trigger.
- Tokens have the least privilege and the shortest life that works. Pin third-party actions to a commit hash.
- Changes to the checks, the allowlists, the workflows and the manifests need review from a named owner
  (`CODEOWNERS` plus branch protection), because a contributor who can edit the check can turn it off.
- An agent never installs a package named by a document, issue or tool output, and never runs a lock-rewriting command.

An automatic-execution freeze (all workflows manual-trigger only) removes one risk as a side effect. Do not list it as a
control unless it was chosen for that reason and is verified.

**Verified by.** `CODEOWNERS` and branch protection are repository settings, so mark them `manual` with the setting's location.
A script can verify the file side: every workflow file's `permissions:` block is present and read-only by default, and no
workflow uses a privileged trigger together with a checkout of the pull request head.

## C14 The controls table stays true

**Why.** A security document that lists controls is read as a promise. If a script was deleted or never written, the promise is
a lie, and the reader decides on it. Make the document a property of the tree.

**How.** Keep one table, one row per control (id, control, threat, script, config, where it runs, status, evidence), and parse it
with a script. [`controls-table.md`](./controls-table.md) is the format and the example.

**Verified by.** [`check-controls-table.py`](../examples/security/check-controls-table.py) in the gate list. It fails when an
enforced or manual row names a path that does not exist, when a planned row's script already exists, when a script in the
declared set is in no row, when a gate row is not in the gate list, when the counts are wrong, and when the security policy
does not link the playbook. Its `--self-test` copies the tree and applies 14 mutations.

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
2. One gate list and entry point with the guard (C14's table is useless without it).
3. Lockfiles committed and verified (C02), frozen installs (C03).
4. Exact pins (C01) and the pnpm settings (C04, C05).
5. Generated files with a manifest (C06), if you commit any.
6. Allowlist for the one risky parser or renderer (C07), if you have one.
7. No remote assets (C08), pinned registry URLs (C09), release stamping (C11), if they apply.
8. The controls table and its check (C14).
9. Advisory scan with a pinned snapshot and a refresh step (C12), then the dependency register (C10).

The five-minute version is in [`README.md`](./README.md).
