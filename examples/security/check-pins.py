#!/usr/bin/env python3
"""check-pins.py: fail when a dependency is not pinned to an exact version.

What it is for: a range (`^1.2.0`, `>=2`, `latest`, a bare crate version) lets the next install
take a release nobody tested, and a git or URL source lets the bytes change under you. This
check reads the dependency tables of three manifest kinds and fails on every dependency that is
not exact, unless a reasoned allowlist entry says why. No network, Python 3.11+ standard library.

Rules:
  package.json (dependencies, devDependencies, optionalDependencies; peerDependencies are a
    contract for consumers and are skipped)
      exact `1.2.3` (a pre-release suffix is fine), `npm:alias@1.2.3`, or a local `workspace:`,
      `file:`, `link:`, `portal:` spec. Ranges, tags, git, URL and tarball specs are red.
      The override tables (`overrides`, nested ones included, `resolutions`, `pnpm.overrides`) are
      read the same way: an override replaces what a dependency asked for, so a range there
      re-opens every pin below it. `$name` references and `-` (remove) are fine.
  pyproject.toml (`[project] dependencies`, `[project.optional-dependencies]`,
    `[dependency-groups]`, `[build-system] requires`)
      each entry is `name==1.2.3` like a requirements line. A published library declares ranges
      on purpose: pass the files to check with `--pyproject`/`--pip`, or allowlist, for those.
  requirements.txt (any file named requirements*.txt)
      `name==1.2.3` (extras and `;` markers allowed, `--hash=` options ignored). `>=`, `~=`,
      `==1.*`, no version, `name @ url`, `-e` editable installs, `--extra-index-url`,
      `--find-links` and `--trusted-host` are red (an extra index is a dependency-confusion
      path). `-r`, `-c`, `--index-url` lines are ignored. With `--pip-require-hashes` every
      requirement also needs `--hash=sha256:...` (the mode `pip install --require-hashes` enforces).
  Cargo.toml (dependencies, dev-dependencies, build-dependencies, workspace.dependencies, and
    the same under target.*)
      `=1.2.3`; `{ workspace = true }` and `{ path = ".." }` are fine; `git` needs a 40-hex `rev`;
      anything else is red. `[patch.<source>]` and `[replace]` entries follow the same rules: a patch
      with `git` and a `branch` replaces a pinned crate with whatever the branch points at. With `--cargo-lock Cargo.lock` (the library mode) a caret or bare
      `1.2.3` is also fine when it equals a version of that crate in the lock, so the floor a
      consumer may resolve is exactly the version the checks ran on.
  pnpm-workspace.yaml (`--pnpm-workspace FILE`, repeatable)
      `minimumReleaseAge` is at least `--min-release-age` minutes (default 43200, 30 days) and
      `onlyBuiltDependencies` is the explicit empty list `[]` (no dependency runs an install script).
      An `overrides:` mapping, when present, must hold exact versions.
  Required settings (`--require-setting FILE:KEY=VALUE`, repeatable)
      FILE is relative to --root. A `.yaml`/`.yml` file is read for a top-level `key: value`,
      anything else (`.npmrc`) for a `key=value` line. Fails when the file or key is missing or
      the value differs: `--require-setting pnpm-workspace.yaml:trustPolicy=no-downgrade`,
      `--require-setting .npmrc:save-exact=true`. Whether your tool version knows the key is
      for you to confirm; the script only keeps the line from being removed.

Not read, so not checked (the method applies; the script does not cover them): Go, Maven, Gradle,
Ruby, PHP and .NET manifests; `Pipfile`, `setup.py`, `setup.cfg`, `[tool.poetry]` tables and pip
constraints files; `peerDependencies`; `yarn.lock`. The script cannot tell a real git `rev` from a
made-up 40-hex string, and it does not read lockfiles (`--cargo-lock` only reads versions).

Allowlist (`--allow FILE`), one entry per line, `#` starts a comment line:
      relative/path/to/manifest|dependency-name|reason why this cannot be exact
  The reason is required. An entry that matches no violation is stale and fails the run, so
  exceptions cannot outlive the problem.

Usage:
  check-pins.py [--root DIR] [--allow FILE] [--cargo-lock FILE] [--pnpm-workspace FILE]...
                [--min-release-age MINUTES] [--pip-require-hashes] [--npm FILE]... [--pip FILE]...
                [--cargo FILE]... [--pyproject FILE]... [--require-setting FILE:KEY=VALUE]...
  With no --npm/--pip/--cargo/--pyproject, every package.json, requirements*.txt, Cargo.toml and
  pyproject.toml under --root is checked (node_modules, target, .git and virtualenvs skipped).
  check-pins.py --self-test        builds fixtures in a temp dir; every mutation must turn red.

Exit status: 0 clean, 1 violations, 2 usage or unreadable input.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
import tempfile
import shutil

try:
    import tomllib
except ImportError:  # Python < 3.11
    print("check-pins: Python 3.11 or newer is required (tomllib)", file=sys.stderr)
    sys.exit(2)

SEMVER = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
SKIP_DIRS = {"node_modules", "target", ".git", ".venv", "venv", "__pycache__"}


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


# ---- package.json -------------------------------------------------------------------------------

def npm_spec_problem(spec):
    """Why an npm dependency spec is not an exact pin, or None when it is."""
    spec = str(spec).strip()
    if re.fullmatch(SEMVER, spec):
        return None
    if re.match(r"(workspace|file|link|portal):", spec):
        return None
    if spec.startswith("npm:") and re.fullmatch(SEMVER, spec.rsplit("@", 1)[-1]):
        return None
    if re.match(r"(git|git\+\w+|github|gitlab|bitbucket|https?|ssh):|^[\w.-]+/[\w.-]+(#.*)?$", spec):
        return f"non-registry source {spec!r}; use a registry release pinned to x.y.z"
    return f"{spec!r} is not an exact version (x.y.z)"


def npm_override_problems(table, label, prefix=""):
    """Override tables: `name: spec`, or `name: { ".": spec, child: spec }` (npm nests them)."""
    out = []
    for name, spec in (table or {}).items():
        where = f"{prefix}{name}"
        if isinstance(spec, dict):
            out += npm_override_problems(spec, label, prefix=where + " > ")
            continue
        spec = str(spec).strip()
        if spec == "-" or spec.startswith("$"):  # pnpm: remove the dependency; npm: reuse the direct dependency's spec
            continue
        why = npm_spec_problem(spec)
        if why:
            out.append((where, f"{label}: {why}"))
    return out


def check_npm(path):
    out = []
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as err:
        return [("<file>", f"cannot parse: {err}")]
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, spec in (data.get(section) or {}).items():
            why = npm_spec_problem(spec)
            if why:
                out.append((name, f"{section}: {why}"))
    out += npm_override_problems(data.get("overrides"), "overrides")
    out += npm_override_problems(data.get("resolutions"), "resolutions")
    out += npm_override_problems((data.get("pnpm") or {}).get("overrides"), "pnpm.overrides")
    return out


# ---- requirements.txt ---------------------------------------------------------------------------

REQ_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*==\s*([0-9][0-9A-Za-z.!+_-]*)\s*(;.*)?$")
REQ_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def logical_lines(text):
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        yield (buf + line).strip()
        buf = ""
    if buf.strip():
        yield buf.strip()


def pip_requirement_problem(line):
    """Why one PEP 508 requirement (no options, no hashes) is not `name==x.y.z`, or None."""
    m = REQ_PIN.match(line)
    if m and "*" not in m.group(3):
        return None
    return f"{line!r} is not pinned with ==x.y.z"


def check_pip(path, require_hashes=False):
    out = []
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as err:
        return [("<file>", f"cannot read: {err}")]
    for line in logical_lines(text):
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if not line:
            continue
        has_hash = "--hash=" in line
        line = re.sub(r"\s--hash=\S+", "", line).strip()
        if line.startswith("-"):
            opt = line.split()[0].split("=")[0]
            if opt in ("--extra-index-url", "--find-links", "-f", "--trusted-host"):
                out.append((opt, f"{opt} adds a second package source (dependency confusion); use one --index-url"))
            elif opt in ("-e", "--editable"):
                out.append((line.split(None, 1)[1] if " " in line else "-e", "editable install is not a pinned release"))
            continue
        why = pip_requirement_problem(line)
        if why is None:
            if require_hashes and not has_hash:
                m = REQ_PIN.match(line)
                out.append((m.group(1), f"{line!r} has no --hash=sha256:... (pip --require-hashes would refuse the file)"))
            continue
        n = REQ_NAME.match(line)
        out.append((n.group(1) if n else line, why))
    return out


# ---- pyproject.toml -----------------------------------------------------------------------------

def check_pyproject(path):
    out = []
    try:
        doc = tomllib.load(open(path, "rb"))
    except (OSError, tomllib.TOMLDecodeError) as err:
        return [("<file>", f"cannot parse: {err}")]
    groups = [("[project] dependencies", (doc.get("project") or {}).get("dependencies"))]
    for extra, reqs in ((doc.get("project") or {}).get("optional-dependencies") or {}).items():
        groups.append((f"[project.optional-dependencies] {extra}", reqs))
    for group, reqs in (doc.get("dependency-groups") or {}).items():
        groups.append((f"[dependency-groups] {group}", reqs))
    groups.append(("[build-system] requires", (doc.get("build-system") or {}).get("requires")))
    for label, reqs in groups:
        for req in reqs or []:
            if not isinstance(req, str):  # {include-group = "..."}
                continue
            req = req.strip()
            why = pip_requirement_problem(req)
            if why:
                n = REQ_NAME.match(req)
                out.append((n.group(1) if n else req, f"{label}: {why}"))
    return out


# ---- Cargo.toml ---------------------------------------------------------------------------------

def locked_versions(lock_path):
    data = tomllib.load(open(lock_path, "rb"))
    versions = {}
    for pkg in data.get("package", []):
        versions.setdefault(pkg["name"], set()).add(pkg["version"])
    return versions


def dep_tables(doc):
    for key in ("dependencies", "dev-dependencies", "build-dependencies"):
        if key in doc:
            yield key, doc[key]
    ws = doc.get("workspace", {})
    if "dependencies" in ws:
        yield "workspace.dependencies", ws["dependencies"]
    for tname, tgt in (doc.get("target") or {}).items():
        for key in ("dependencies", "dev-dependencies", "build-dependencies"):
            if key in tgt:
                yield f"target.{tname}.{key}", tgt[key]
    # [patch.<source>] swaps a dependency for another source everywhere in the graph; [replace] is its
    # deprecated spelling. Both are held to the rules of an ordinary dependency.
    for source, table in (doc.get("patch") or {}).items():
        yield f"patch.{source}", table
    if "replace" in doc:
        yield "replace", doc["replace"]


def check_cargo(path, lock=None):
    out = []
    try:
        doc = tomllib.load(open(path, "rb"))
    except (OSError, tomllib.TOMLDecodeError) as err:
        return [("<file>", f"cannot parse: {err}")]
    for table, deps in dep_tables(doc):
        for name, spec in deps.items():
            where = f"[{table}]"
            if isinstance(spec, str):
                spec = {"version": spec}
            if spec.get("workspace") is True:
                continue
            if "git" in spec:
                if not re.fullmatch(r"[0-9a-f]{40}", str(spec.get("rev", ""))):
                    out.append((name, f"{where} git dependency needs `rev` = a 40-hex commit (a branch or tag can move)"))
                continue
            if "path" in spec and "version" not in spec:
                continue
            ver = str(spec.get("version", "")).strip()
            if not ver:
                out.append((name, f"{where} has no version: cargo would take the newest release"))
                continue
            if re.fullmatch(r"=\s*" + SEMVER, ver):
                continue
            m = re.fullmatch(r"[\^~]?\s*(" + SEMVER + ")", ver)
            if lock is not None and m:
                crate = spec.get("package", name)
                if m.group(1) in lock.get(crate, ()):
                    continue
                out.append((name, f"{where} {ver!r}: the floor is not a version of {crate} in the lock ({sorted(lock.get(crate, []))})"))
                continue
            out.append((name, f"{where} {ver!r} is not exact (=x.y.z)"))
    return out


# ---- pnpm-workspace.yaml ------------------------------------------------------------------------

def check_pnpm(path, min_age):
    out = []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError as err:
        return [("<file>", f"cannot read: {err}")]
    top, current, overrides = {}, None, {}
    for l in lines:
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*?)\s*(#.*)?$", l)
        if m:
            current = m.group(1)
            top[current] = [m.group(2)] if m.group(2) else []
        elif current == "overrides":
            om = re.match(r"""^\s+("[^"]+"|'[^']+'|[^:\s][^:]*?)\s*:\s*(.*?)\s*(\s#.*)?$""", l)
            if om:
                overrides[om.group(1).strip("\"'")] = om.group(2).strip().strip("\"'")
        elif current and l.lstrip().startswith("- "):
            top[current].append(l.strip())
    age = top.get("minimumReleaseAge")
    if age is None:
        out.append(("minimumReleaseAge", "is not set (a version published an hour ago can be installed)"))
    elif not (len(age) == 1 and age[0].isdigit() and int(age[0]) >= min_age):
        out.append(("minimumReleaseAge", f"is {age}, want an integer >= {min_age} minutes"))
    built = top.get("onlyBuiltDependencies")
    if built is None:
        out.append(("onlyBuiltDependencies", "is not set; write the explicit empty list `[]`"))
    elif built != ["[]"]:
        out.append(("onlyBuiltDependencies", f"is {built}; the list must be empty (no dependency install scripts)"))
    out += npm_override_problems(overrides, "overrides")
    return out


def check_setting(root, spec):
    """`FILE:KEY=VALUE` must hold in FILE (yaml top level, or ini-style key=value)."""
    m = re.fullmatch(r"([^:]+):([^=\s]+)=(.+)", spec)
    if not m:
        return [(spec, "--require-setting wants FILE:KEY=VALUE")]
    f, key, want = m.groups()
    path = os.path.join(root, f)
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return [(f"{f}:{key}", f"{f} does not exist; it must set {key}={want}")]
    got = None
    for l in lines:
        l = re.sub(r"(^|\s)#.*$", "", l).rstrip()
        if f.endswith((".yaml", ".yml")):
            mm = re.match(r"^%s:\s*(.*)$" % re.escape(key), l)
        else:
            mm = re.match(r"^\s*%s\s*=\s*(.*)$" % re.escape(key), l)
        if mm:
            got = mm.group(1).strip().strip("\"'")
    if got is None:
        return [(f"{f}:{key}", f"{key} is not set in {f}; want {want}")]
    if got != want:
        return [(f"{f}:{key}", f"{key} is {got!r} in {f}; want {want}")]
    return []


# ---- allowlist and driver -----------------------------------------------------------------------

def load_allow(path):
    entries, problems = [], []
    if not path or not os.path.exists(path):
        return entries, problems
    for n, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            problems.append(f"{path}:{n}: want `path|name|reason`, with a reason")
            continue
        entries.append(parts)
    return entries, problems


def discover(root):
    npm, pip, cargo, pyproject = [], [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            if f == "package.json":
                npm.append(p)
            elif fnmatch.fnmatch(f, "requirements*.txt"):
                pip.append(p)
            elif f == "Cargo.toml":
                cargo.append(p)
            elif f == "pyproject.toml":
                pyproject.append(p)
    return npm, pip, cargo, pyproject


def run(root, npm, pip, cargo, pyproject, allow_path, lock_path, pnpm_paths, min_age, require_hashes=False, settings=()):
    lock = locked_versions(lock_path) if lock_path else None
    found = []
    for p in npm:
        found += [(rel(root, p), n, m) for n, m in check_npm(p)]
    for p in pip:
        found += [(rel(root, p), n, m) for n, m in check_pip(p, require_hashes)]
    for p in cargo:
        found += [(rel(root, p), n, m) for n, m in check_cargo(p, lock)]
    for p in pyproject:
        found += [(rel(root, p), n, m) for n, m in check_pyproject(p)]
    for p in pnpm_paths:
        found += [(rel(root, p), n, m) for n, m in check_pnpm(p, min_age)]
    for spec in settings:
        found += [(spec.split(":", 1)[0], n, m) for n, m in check_setting(root, spec)]
    entries, problems = load_allow(allow_path)
    used = set()
    for f, n, m in found:
        hit = next((i for i, (ep, en, _) in enumerate(entries) if ep == f and en == n), None)
        if hit is None:
            problems.append(f"{f}: {n}: {m}")
        else:
            used.add(hit)
    for i, (ep, en, reason) in enumerate(entries):
        if i not in used:
            problems.append(f"{allow_path}: stale entry `{ep}|{en}`: it matches no violation, delete it")
    n_files = len(npm) + len(pip) + len(cargo) + len(pyproject) + len(pnpm_paths) + len(set(x.split(':', 1)[0] for x in settings))
    return problems, len(found), len(used), n_files


# ---- self-test ----------------------------------------------------------------------------------

FIXTURE = {
    "js/package.json": json.dumps({"dependencies": {"left": "1.2.3", "local": "workspace:*", "alias": "npm:other@2.0.0"},
                                   "devDependencies": {"tool": "4.5.6-rc.1"}}),
    "py/requirements.txt": "# pins\nrequests==2.32.3 \\\n    --hash=sha256:abc\nflask[async]==3.0.0 ; python_version >= '3.9'\n"
                           "--index-url https://pypi.example/simple\n-r other.txt\n",
    "rust/Cargo.toml": '[package]\nname = "x"\nversion = "0.1.0"\n[dependencies]\nserde = "=1.0.200"\n'
                       'regex = { version = "=1.10.0", default-features = false }\nlocal = { path = "../local" }\n'
                       'shared = { workspace = true }\n'
                       'forked = { git = "https://example.invalid/f", rev = "0123456789abcdef0123456789abcdef01234567" }\n'
                       '[dev-dependencies]\ntempfile = "=3.8.0"\n',
    "rust/Cargo.lock": 'version = 3\n[[package]]\nname = "serde"\nversion = "1.0.200"\n[[package]]\nname = "tempfile"\nversion = "3.8.0"\n',
    "js/pnpm-workspace.yaml": "minimumReleaseAge: 43200\nonlyBuiltDependencies: []\n",
    "py/pyproject.toml": '[project]\nname = "x"\nversion = "0.1.0"\ndependencies = ["requests==2.32.3", "flask[async]==3.0.3; python_version >= \'3.9\'"]\n'
                         '[project.optional-dependencies]\ndev = ["pytest==8.2.0"]\n'
                         '[dependency-groups]\ntest = ["pytest==8.2.0", {include-group = "dev"}]\n'
                         '[build-system]\nrequires = ["setuptools==70.0.0"]\n',
}


def self_test():
    cases_run = 0
    bad = 0

    def case(name, want, files=None, allow=None, lock=False, pnpm=("js/pnpm-workspace.yaml",), hashes=False, settings=()):
        nonlocal cases_run, bad
        cases_run += 1
        tmp = tempfile.mkdtemp(prefix="pins-selftest-")
        try:
            for k, v in {**FIXTURE, **(files or {})}.items():
                p = os.path.join(tmp, k)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "w", encoding="utf-8").write(v)
            ap = None
            if allow is not None:
                ap = os.path.join(tmp, "pins.allow")
                open(ap, "w", encoding="utf-8").write(allow)
            npm, pip, cargo, pyproject = discover(tmp)
            problems, *_ = run(tmp, npm, pip, cargo, pyproject, ap,
                               os.path.join(tmp, "rust/Cargo.lock") if lock else None,
                               [os.path.join(tmp, f) for f in pnpm], 43200, hashes, settings)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = (not problems) if want is None else any(want in p for p in problems)
        print(f"  self-test {'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f" -- got {problems[:2]}"))
        bad += 0 if ok else 1

    def npm_with(**deps):
        return {"js/package.json": json.dumps({"dependencies": deps})}

    case("the fixture (exact pins, local specs, hashes, marker, git rev) is green", None)
    case("npm caret range", "is not an exact version", npm_with(left="^1.2.3"))
    case("npm tag", "is not an exact version", npm_with(left="latest"))
    case("npm wildcard", "is not an exact version", npm_with(left="*"))
    case("npm git source", "non-registry source", npm_with(left="github:owner/repo"))
    case("npm tarball URL", "non-registry source", npm_with(left="https://example.invalid/x.tgz"))
    case("pip >=", "is not pinned with ==", {"py/requirements.txt": "requests>=2.0\n"})
    case("pip wildcard", "is not pinned with ==", {"py/requirements.txt": "requests==2.*\n"})
    case("pip no version", "is not pinned with ==", {"py/requirements.txt": "requests\n"})
    case("pip direct URL", "is not pinned with ==", {"py/requirements.txt": "requests @ https://example.invalid/r.whl\n"})
    case("pip editable", "editable install", {"py/requirements.txt": "-e ./local\n"})
    case("pip extra index", "second package source", {"py/requirements.txt": "--extra-index-url https://x.invalid/simple\nrequests==2.32.3\n"})
    case("pip hashes required and present", None,
         {"py/requirements.txt": "requests==2.32.3 --hash=sha256:aa --hash=sha256:bb\n"}, hashes=True)
    case("pip hashes required and missing", "has no --hash",
         {"py/requirements.txt": "requests==2.32.3\n"}, hashes=True)
    case("cargo caret", "is not exact", {"rust/Cargo.toml": '[dependencies]\nserde = "^1.0.200"\n'})
    case("cargo bare version", "is not exact", {"rust/Cargo.toml": '[dependencies]\nserde = "1.0.200"\n'})
    case("cargo no version", "has no version", {"rust/Cargo.toml": '[dependencies]\nserde = { features = ["derive"] }\n'})
    case("cargo git branch", "needs `rev`", {"rust/Cargo.toml": '[dependencies]\nf = { git = "https://x.invalid/f", branch = "main" }\n'})
    case("cargo target table", "is not exact", {"rust/Cargo.toml": '[target.\'cfg(unix)\'.dependencies]\nlibc = "0.2"\n'})
    case("cargo library mode: floor equals the lock is green", None,
         {"rust/Cargo.toml": '[dependencies]\nserde = "^1.0.200"\n'}, lock=True)
    case("cargo library mode: floor differs from the lock", "not a version of serde in the lock",
         {"rust/Cargo.toml": '[dependencies]\nserde = "^1.0.100"\n'}, lock=True)
    case("pnpm release age too low", "minimumReleaseAge", {"js/pnpm-workspace.yaml": "minimumReleaseAge: 4320\nonlyBuiltDependencies: []\n"})
    case("pnpm release age missing", "is not set", {"js/pnpm-workspace.yaml": "onlyBuiltDependencies: []\n"})
    case("pnpm install scripts allowed", "onlyBuiltDependencies",
         {"js/pnpm-workspace.yaml": "minimumReleaseAge: 43200\nonlyBuiltDependencies:\n  - esbuild\n"})
    case("pnpm install-script list missing", "is not set; write", {"js/pnpm-workspace.yaml": "minimumReleaseAge: 43200\n"})
    # the holes a reviewer found: overrides, patch tables, pyproject
    case("cargo [patch] with a branch", "needs `rev`", {"rust/Cargo.toml": '[dependencies]\nserde = "=1.0.200"\n'
         '[patch.crates-io]\nserde = { git = "https://x.invalid/serde", branch = "main" }\n'})
    case("cargo [patch] with a git rev is green", None, {"rust/Cargo.toml": '[dependencies]\nserde = "=1.0.200"\n'
         '[patch.crates-io]\nserde = { git = "https://x.invalid/serde", rev = "0123456789abcdef0123456789abcdef01234567" }\n'})
    case("cargo [patch] with a range", "is not exact", {"rust/Cargo.toml": '[dependencies]\nserde = "=1.0.200"\n'
         '[patch."https://x.invalid/index"]\nserde = { version = "1.0" }\n'})
    case("cargo [replace]", "needs `rev`", {"rust/Cargo.toml": '[dependencies]\nserde = "=1.0.200"\n'
         '[replace]\n"serde:1.0.200" = { git = "https://x.invalid/serde", tag = "v1" }\n'})
    case("npm overrides with a range", "overrides", {"js/package.json": json.dumps(
         {"dependencies": {"left": "1.2.3"}, "overrides": {"deep": "^2.0.0"}})})
    case("npm nested overrides with a range", "overrides", {"js/package.json": json.dumps(
         {"dependencies": {"left": "1.2.3"}, "overrides": {"left": {".": "1.2.3", "deep": ">=2"}}})})
    case("yarn resolutions with a tag", "resolutions", {"js/package.json": json.dumps(
         {"dependencies": {"left": "1.2.3"}, "resolutions": {"deep": "latest"}})})
    case("pnpm.overrides with a range", "pnpm.overrides", {"js/package.json": json.dumps(
         {"dependencies": {"left": "1.2.3"}, "pnpm": {"overrides": {"deep@^1": "~1.4.0"}}})})
    case("exact overrides, a reference and a removal are green", None, {"js/package.json": json.dumps(
         {"dependencies": {"left": "1.2.3"}, "overrides": {"deep": "2.0.1", "left": "$left"},
          "pnpm": {"overrides": {"other": "-", "pinned@1": "npm:real@1.4.0"}}})})
    case("pnpm-workspace overrides with a range", "overrides", {"js/pnpm-workspace.yaml":
         "minimumReleaseAge: 43200\nonlyBuiltDependencies: []\noverrides:\n  \"@scope/pkg@<2\": \"^2.1.0\"\n"})
    case("pnpm-workspace exact overrides are green", None, {"js/pnpm-workspace.yaml":
         "minimumReleaseAge: 43200\nonlyBuiltDependencies: []\noverrides:\n  '@scope/pkg': 2.1.0  # reason\n"})
    case("a second pnpm-workspace with a low age", "minimumReleaseAge",
         {"web/pnpm-workspace.yaml": "minimumReleaseAge: 10\nonlyBuiltDependencies: []\n"},
         pnpm=("js/pnpm-workspace.yaml", "web/pnpm-workspace.yaml"))
    case("pyproject dependency range", "[project] dependencies", {"py/pyproject.toml":
         '[project]\nname = "x"\nversion = "1"\ndependencies = ["requests>=2"]\n'})
    case("pyproject optional dependency range", "optional-dependencies", {"py/pyproject.toml":
         '[project]\nname = "x"\nversion = "1"\n[project.optional-dependencies]\ndev = ["pytest"]\n'})
    case("pyproject dependency group range", "dependency-groups", {"py/pyproject.toml":
         '[dependency-groups]\ntest = ["pytest~=8.0"]\n'})
    case("pyproject build requirement range", "build-system", {"py/pyproject.toml":
         '[build-system]\nrequires = ["setuptools>=61"]\n'})
    case("a required yaml setting that holds is green", None,
         {"js/pnpm-workspace.yaml": "minimumReleaseAge: 43200\nonlyBuiltDependencies: []\ntrustPolicy: no-downgrade\n"},
         settings=("js/pnpm-workspace.yaml:trustPolicy=no-downgrade",))
    case("a required yaml setting that is missing", "trustPolicy is not set",
         settings=("js/pnpm-workspace.yaml:trustPolicy=no-downgrade",))
    case("a required yaml setting with another value", "want no-downgrade",
         {"js/pnpm-workspace.yaml": "minimumReleaseAge: 43200\nonlyBuiltDependencies: []\ntrustPolicy: off\n"},
         settings=("js/pnpm-workspace.yaml:trustPolicy=no-downgrade",))
    case("a required .npmrc setting that holds is green", None, {"js/.npmrc": "# exact\nsave-exact=true\n"},
         settings=("js/.npmrc:save-exact=true",))
    case("a required .npmrc file that is missing", "does not exist", settings=("js/.npmrc:save-exact=true",))
    case("an allowlisted violation is green", None, npm_with(left="^1.2.3"),
         allow="# reason is mandatory\njs/package.json|left|vendor publishes only ranges; replace by Q3\n")
    case("an allowlist entry that matches nothing is stale", "stale entry", None,
         allow="js/package.json|left|no longer needed\n")
    case("an allowlist entry without a reason", "with a reason", npm_with(left="^1.2.3"), allow="js/package.json|left|\n")
    if bad:
        print(f"check-pins: self-test FAIL ({bad} of {cases_run} cases wrong)", file=sys.stderr)
        return 1
    print(f"check-pins: self-test OK ({cases_run} cases)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Fail on dependencies that are not pinned exactly.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--allow", default="", help="allowlist file (path|name|reason), relative to --root")
    ap.add_argument("--cargo-lock", default="", help="Cargo.lock: allow a caret/bare floor equal to a locked version")
    ap.add_argument("--pnpm-workspace", action="append", default=[],
                    help="pnpm-workspace.yaml to check for release age and install scripts (repeatable)")
    ap.add_argument("--min-release-age", type=int, default=43200, help="minutes (default 43200 = 30 days)")
    ap.add_argument("--pip-require-hashes", action="store_true", help="every requirement line carries --hash=sha256:...")
    ap.add_argument("--npm", action="append", default=[])
    ap.add_argument("--pip", action="append", default=[])
    ap.add_argument("--cargo", action="append", default=[])
    ap.add_argument("--pyproject", action="append", default=[])
    ap.add_argument("--require-setting", action="append", default=[], metavar="FILE:KEY=VALUE",
                    help="a setting that must hold in FILE (yaml top level or key=value), repeatable")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    root = os.path.abspath(a.root)
    j = lambda p: os.path.join(root, p) if p else ""
    npm, pip, cargo = [j(p) for p in a.npm], [j(p) for p in a.pip], [j(p) for p in a.cargo]
    pyproject = [j(p) for p in a.pyproject]
    if not (npm or pip or cargo or pyproject):
        npm, pip, cargo, pyproject = discover(root)
    problems, n_found, n_allowed, n_files = run(root, npm, pip, cargo, pyproject, j(a.allow), j(a.cargo_lock),
                                                [j(p) for p in a.pnpm_workspace], a.min_release_age, a.pip_require_hashes,
                                                a.require_setting)
    if problems:
        print("check-pins: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"check-pins: OK -- {n_files} file(s) checked, {n_found} violation(s), all {n_allowed} allowlisted with a reason")
    return 0


if __name__ == "__main__":
    sys.exit(main())
