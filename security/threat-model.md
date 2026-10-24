# Threat model: what can be done to you, and what stops it

This document says who can hurt a repository through its dependencies and build, how, and which control in the
[supply-chain playbook](./supply-chain-playbook.md) stops it. Use it to decide which controls your project needs, to review a
pull request that touches a manifest or a script, and to write the threat-model section of your own playbook. It also says
what the controls do not stop, so nobody assumes otherwise.

The model is about code and data you did not write that reaches your build, your repository and your users. It is not a model
of your running application's own security.

Two kinds of id appear below. `C01`, `C02`, ... are controls: each is a section of the playbook and a row of your controls
table. `T1`, `T2`, ... are threats: each is a row of the table "Threats and controls at a glance" at the end of this document,
with the controls that stop it.

## The six actors

Each section lists what the actor can do to you, the controls that stop or limit it, and what is left.

### A dependency

A package you depend on, directly or through another package.

| What it can do | Stopped or limited by | What is left |
|---|---|---|
| A compromised release of a popular package (stolen maintainer account, hijacked publishing token) ships malicious code | exact pins and a lock (C01, C02) so you do not take it by accident; minimum release age (C04) so you do not adopt it in the first hours; advisory scan on a pinned snapshot (C12) after it is known | A malicious version already in your lockfile runs. Nothing reviews the code of a locked version unless you add a trust register. |
| A clean-looking release adds one new transitive dependency, often a typosquat of a real package, whose install or build script does the harm | frozen installs read only the lock (C03); no install scripts (C05); a diff of the lock in review; a count of build scripts that may only fall (C10, C12); no tarball or git source in the lock (C18) | Build scripts and procedural macros in Cargo cannot be switched off, only counted and allowlisted. |
| A package with a name one letter off a real one (typosquat), or a private package name taken on the public registry (dependency confusion) | one registry or index (C09); exact pins reviewed when added; nobody adds a package a document names (C13) | A typo in your own manifest, caught by review only. |
| A package that parses untrusted text or emits markup has a bug that is reachable from outside | a fixed surface for the class: opt-in, exact pin, features off, fixed closure, no raw-markup sink (C07) | Bugs in the parser's allowed features. |
| A maintainer abandons the package, or ownership changes hands | the cost table records owners and release cadence (C10) | A judgement call, not a check. |

### A build step

Anything that runs while you install, build or generate: a package install script, a Cargo `build.rs` or procedural macro, a
Python source-distribution build, a bundler plugin, a code generator.

| What it can do | Stopped or limited by | What is left |
|---|---|---|
| Run arbitrary code with the privileges of the developer or the CI job, before anyone reviews it, and read environment variables and files | no dependency install scripts (C05); `pip --only-binary :all:`; least-privilege workflow tokens and no secrets in install steps (C13, [`agents-and-automation.md`](./agents-and-automation.md)); sandboxed agents | Cargo compile-time code. A library with no `build.rs` of its own does not add one to every consumer. |
| Write into the source tree or the lockfile as a side effect | frozen installs (C03); a check, which you write, that no lock differs from the index after the gates ran (C03) | |
| Fetch more code at build time | offline gates (C12 refresh is separate); one registry (C09) | |

### A generated artifact

A file in the repository that is produced by a tool, not written by hand: a minified bundle, compiled schema, parser table.

| What it can do | Stopped or limited by | What is left |
|---|---|---|
| Drift from its source: the source changes and the artifact is stale, so the release ships old behaviour | manifest of hashes; any one-sided edit is red (C06) | |
| Be edited by hand: the next regeneration erases the fix, or the edit is a backdoor in a file reviewers skip | manifest hash plus deterministic rebuild comparison (C06) | A rebuild comparison needs the recorded generator version; with another version only the hash half runs. |
| Be produced by a compromised generator | the generator version is pinned and recorded (C06, C10); tools are trusted as installed (out of scope, below) | |

### A registry or source

The service that serves packages (a public registry, a mirror, a git host) and the tool's rules for finding a package in it.

| What it can do | Stopped or limited by | What is left |
|---|---|---|
| Serve a package from a source you did not choose: a name with no source is resolved by the tool's default, a second index wins on version number | one source, one URL constant, no extra index, every dependency naming its source where the format allows it (C09); no tarball or git source in the lock (C18) | |
| Move what a name points to: a git branch or tag, a `latest` tag | exact versions and a git `rev` (C01); checksums in the lock (C02) | Compromise of the registry's own infrastructure is out of scope. |
| Remove or yank a version you lock | the refresh step checks that every locked version still exists (C12) | A yanked version still builds from the lock; a deleted one does not. |
| Serve a page's runtime assets (fonts, images, scripts) from a third-party host that you do not control | no hot-linked remote assets (C08) | |

### A contributor

A person who opens a pull request, or has commit access.

| What they can do | Stopped or limited by | What is left |
|---|---|---|
| Add a dependency or loosen a pin in a pull request | the pin check is red (C01); the cost table and review decide additions (C10) | |
| Edit the lockfile to point at a different build | the lock is verified against the manifest (C02); lock diffs are reviewed; no tarball or git source in the lock (C18) | |
| Edit the check, the allowlist, the controls table or a workflow so the problem stops being flagged | review by a named owner on those paths (C19); a stale allowlist entry fails, so removing the cause is the only way to quiet a gate; the controls table check fails when the table and the scripts disagree (C14) | A maintainer who is malicious or compromised. Gates run on code a maintainer writes and cannot review intent. |
| Trigger a workflow that runs their code with your secrets | fork pull requests run with read-only tokens and no secrets; no privileged trigger checks out the head; workflow permissions are read-only by default and actions are pinned (C13, C19) | |
| Ship something that differs from what was tested, by mistake or on purpose: use a package no manifest declares, rely on a feature that builds only with another one on, leave a manifest pointing at another source | declared equals used (C16); optional features built alone (C17); a clean-room consumer install (C15); floors equal to the locked versions and one `rev` (C01, C11) | A consumer's resolver still picks versions inside the ranges you declare. |

### An automated agent

A CI job, a bot or a coding assistant that runs commands and reads text.

| What it can do | Stopped or limited by | What is left |
|---|---|---|
| Install a package that does not exist or is a squat, because a document, issue, web page or its own suggestion named it | the rule that nobody installs a package a text names, checked before adding ([`agents-and-automation.md`](./agents-and-automation.md)); exact pins and the pin check (C01) | |
| Run a lock-rewriting command to make a build pass | frozen installs only (C03); the lock-diff check you write (C03) | |
| Follow instructions that arrive inside content it fetched (prompt injection) | fetched content is data, never instructions; the agent cannot change its own permissions or configuration from such text ([`agents-and-automation.md`](./agents-and-automation.md), rule 3); review of the agent's instruction file as code (C19) | |
| Leak a token, or use one that is too powerful | least-privilege, short-lived tokens; no secrets in install steps; read-only workflow permissions (C13) | |
| Skip a gate because it is slow | one runner whose summary names the tree it ran on, and a commit needs a full green run (the approach in the playbook, [`agents-and-automation.md`](./agents-and-automation.md)) | |

## Threats and controls at a glance

| # | Threat | Where it bites | Controls |
|---|---|---|---|
| T1 | Compromised or typosquatted release of a dependency | your builds and your users' | C01 C02 C03 C04 C09 C12 C18 |
| T2 | Code that runs at install or build time | any machine that builds or installs | C05 C10 |
| T3 | Lockfile drift or a lock that no longer matches its manifest | repository, users | C01 C02 C03 |
| T4 | Dependency growth with no decision | users | C07 C10 C16 C17 |
| T5 | Generated code drifting from its source | users | C06 |
| T6 | Untrusted text reaching output as raw markup | end users | C07 |
| T7 | Install resolving from the wrong registry or source | users | C09 C18 |
| T8 | What users compile differs from what you tested | users | C01 C09 C11 C15 C16 C17 |
| T9 | Third-party code or assets fetched at runtime | visitors | C08 |
| T10 | A workflow running proposed code with privileges | CI | C13 C19 |
| T11 | An agent installing or rewriting what it was told to | repository, CI | C03 C13 C19 |
| T12 | The documentation of the controls being untrue | everyone who relies on it | C14 |

## What this model does not defend against

Say these in your own playbook too. Silence reads as a promise.

- **A malicious or compromised maintainer, account or repository.** Gates run on code a maintainer writes; they do not review intent.
- **A malicious update to a version already in the lockfile.** The lock pins exact bytes; nothing reviews them. A trust
  register (`cargo-vet` style) adds that record. It is a planned layer, not a given.
- **Known vulnerabilities**, until an advisory scan (C12) exists. Say whether it does.
- **Your lock never reaches your users** when you publish a library or an installable template. A consumer's resolver
  re-resolves every transitive dependency within the ranges you declare. You control only what you declare (C01), and a
  clean-room install (C15) shows what a consumer resolves today.
- **Toolchains and tool binaries**: the compiler, package manager, bundler, browsers, and any binary your bootstrap script
  downloads. They are trusted as installed. Pin the version; verify a checksum if you download one.
- **Infrastructure compromise** of a registry or a hosting service.
- **Runtime security of the application** beyond what a control names (for example, the one parser in C07).
- **Availability and secrets management.** This model assumes the repository holds no secrets for a check to find.

Writing the "not defended" list is part of the work. When you add a control, move the line from this list to the table.
