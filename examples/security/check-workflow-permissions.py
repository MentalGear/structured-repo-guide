#!/usr/bin/env python3
"""check-workflow-permissions.py: fail when a CI workflow file is more powerful than it must be.

What it is for: a workflow holds a token and runs code, so its file is where least privilege is
decided. Four properties of the file are checked, with no network and the Python 3 standard
library only (the file is read line by line in the usual block style, not parsed as full YAML):

  1. Permissions are declared. Every workflow has a top-level `permissions:` block, or every
     job has its own. Without one the token gets the repository's default, which may be write.
  2. Nothing is `write-all`, anywhere. A top-level block grants nothing but `read`/`none`
     (read-only by default); a job widens a single scope (`contents: write`) when it must.
  3. No privileged trigger runs proposed code. A workflow triggered by `pull_request_target`
     (runs with secrets and a write token) must not check out the pull request's head
     (`ref:` or `repository:` naming `github.event.pull_request.head`, `github.head_ref` or
     `refs/pull/`); the same for `workflow_run` and `github.event.workflow_run.head`.
  4. Third-party actions are pinned to a full 40-hex commit: `uses: owner/repo@<sha>`. A tag
     moves. Local actions (`./...`) and `docker://` references are not judged; a line that
     carries `# pin-ok: <reason>` is allowed.

Not checked: whether the repository's own setting (Settings, Actions, workflow permissions) is
read-only, whether a pinned commit is the one you reviewed, matrix and reusable-workflow `with:`
indirection, and CI systems other than GitHub Actions (the same four questions apply; write the
check for your system's file format).

Usage:
  check-workflow-permissions.py [--root DIR] [--workflows DIR]     (default .github/workflows)
  check-workflow-permissions.py --self-test

Exit status: 0 clean (or no workflow files), 1 violations, 2 usage.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile

HEAD_REF = re.compile(r"github\.event\.pull_request\.head|github\.head_ref|refs/pull/|github\.event\.workflow_run\.head")
USES = re.compile(r"^\s*-?\s*uses\s*:\s*['\"]?([^\s'\"#]+)")
SHA = re.compile(r"[0-9a-f]{40}")


def indent(line):
    return len(line) - len(line.lstrip(" "))


def strip_comment(line):
    return re.sub(r"(^|\s)#.*$", "", line).rstrip()


def block_indices(lines, i):
    """Indices of the lines indented deeper than lines[i] that follow it (blank lines skipped)."""
    base, out = indent(lines[i]), []
    for k in range(i + 1, len(lines)):
        if not lines[k].strip():
            continue
        if indent(lines[k]) <= base:
            break
        out.append(k)
    return out


def permission_problems(lines, i, where):
    """Problems of one `permissions:` entry at lines[i]; `where` is 'top-level' or 'job NAME'."""
    out = []
    inline = strip_comment(lines[i]).split(":", 1)[1].strip()
    if inline == "write-all":
        out.append(f"{where} permissions are `write-all`; grant the scopes the job needs")
    elif not inline:
        if where == "top-level":
            for k in block_indices(lines, i):
                m = re.match(r"\s*([\w-]+)\s*:\s*write\b", lines[k])
                if m:
                    out.append(f"top-level permissions grant `{m.group(1)}: write`; keep the top level read-only and widen in the one job that needs it")
    return out


def check_file(path):
    try:
        raw = open(path, encoding="utf-8").read().splitlines()
    except (OSError, UnicodeDecodeError) as err:
        return [f"cannot read: {err}"]
    code = [strip_comment(l) for l in raw]
    out = []

    # 1 and 2: declared, and never write-all
    top = next((i for i, l in enumerate(code) if re.match(r"permissions\s*:", l)), None)
    if top is not None:
        out += permission_problems(code, top, "top-level")
    jobs_at = next((i for i, l in enumerate(code) if re.match(r"jobs\s*:\s*$", l)), None)
    job_names, jobs_without = [], []
    if jobs_at is not None:
        body = block_indices(code, jobs_at)
        job_indent = indent(code[body[0]]) if body else 2
        i = jobs_at + 1
        while i < len(code):
            l = code[i]
            if l.strip() and indent(l) == 0:
                break
            m = re.match(r"^ {%d}([\w.-]+)\s*:\s*$" % job_indent, l)
            if m:
                name = m.group(1)
                job_names.append(name)
                at = next((k for k in block_indices(code, i)
                           if re.match(r"^ {%d}permissions\s*:" % (job_indent + 2), code[k])), None)
                if at is None:
                    jobs_without.append(name)
                else:
                    out += permission_problems(code, at, f"job {name}")
            i += 1
    if top is None and jobs_without:
        out.append("no top-level `permissions:` block, and no `permissions:` in job(s) " + ", ".join(jobs_without))
    elif top is None and not job_names:
        out.append("no top-level `permissions:` block")

    # 3: a privileged trigger together with a checkout of the proposed code
    text = "\n".join(code)
    for trigger in ("pull_request_target", "workflow_run"):
        if re.search(r"\b%s\b" % trigger, text):
            for n, l in enumerate(code, 1):
                if re.match(r"\s*-?\s*(ref|repository)\s*:", l) and HEAD_REF.search(l):
                    out.append(f"line {n}: `{trigger}` runs with secrets and must not check out the proposed head ({l.strip()})")

    # 4: third-party actions pinned to a commit
    for n, (c, r) in enumerate(zip(code, raw), 1):
        m = USES.match(c)
        if not m:
            continue
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        if "# pin-ok:" in r and r.split("# pin-ok:", 1)[1].strip():
            continue
        name, _, version = ref.partition("@")
        if not SHA.fullmatch(version):
            out.append(f"line {n}: `{ref}` is not pinned to a 40-hex commit (a tag moves); pin it or add `# pin-ok: <reason>`")
    return out


def workflow_files(root, workflows):
    d = os.path.join(root, workflows)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith((".yml", ".yaml")))


def run(root, workflows):
    problems = []
    files = workflow_files(root, workflows)
    for f in files:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        problems += [f"{rel}: {p}" for p in check_file(f)]
    return problems, len(files)


# ---- self-test ----------------------------------------------------------------------------------

SHA1 = "0123456789abcdef0123456789abcdef01234567"
GOOD = f"""name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{SHA1}
      - uses: ./.github/actions/setup
      - run: sh scripts/run-gates.sh
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@{SHA1}  # pin-ok: kept in step with the tested release
"""


def self_test():
    ran, bad = 0, 0

    def case(name, want, text=GOOD, extra=None):
        nonlocal ran, bad
        ran += 1
        tmp = tempfile.mkdtemp(prefix="workflows-selftest-")
        try:
            d = os.path.join(tmp, ".github", "workflows")
            os.makedirs(d)
            open(os.path.join(d, "ci.yml"), "w", encoding="utf-8").write(text)
            for k, v in (extra or {}).items():
                open(os.path.join(d, k), "w", encoding="utf-8").write(v)
            problems, _ = run(tmp, ".github/workflows")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = (not problems) if want is None else any(want in p for p in problems)
        print(f"  self-test {'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f" -- got {problems[:2]}"))
        bad += 0 if ok else 1

    case("the fixture (top-level read, one write job, pinned actions) is green", None)
    case("no permissions anywhere", "no top-level `permissions:`",
         GOOD.replace("permissions:\n  contents: read\n", "").replace("    permissions:\n      contents: write\n", ""))
    case("every job declares its own permissions and there is no top level is green", None,
         GOOD.replace("permissions:\n  contents: read\njobs:", "jobs:").replace(
             "  test:\n    runs-on: ubuntu-latest\n", "  test:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n"))
    case("one job lacks permissions and there is no top level", "job(s) test",
         GOOD.replace("permissions:\n  contents: read\njobs:", "jobs:"))
    case("top-level write-all", "`write-all`", GOOD.replace("permissions:\n  contents: read\n", "permissions: write-all\n"))
    case("a job with write-all", "job publish permissions are `write-all`",
         GOOD.replace("    permissions:\n      contents: write\n", "    permissions: write-all\n"))
    case("top-level write scope", "top-level permissions grant `contents: write`",
         GOOD.replace("permissions:\n  contents: read\n", "permissions:\n  contents: write\n"))
    case("an empty top-level block is green", None, GOOD.replace("permissions:\n  contents: read\n", "permissions: {}\n"))
    case("pull_request_target with a checkout of the head", "must not check out the proposed head",
         GOOD.replace("  pull_request:\n", "  pull_request_target:\n").replace(
             f"      - uses: actions/checkout@{SHA1}\n",
             f"      - uses: actions/checkout@{SHA1}\n        with:\n          ref: ${{{{ github.event.pull_request.head.sha }}}}\n", 1))
    case("pull_request_target that checks out only the base is green", None,
         GOOD.replace("  pull_request:\n", "  pull_request_target:\n"))
    case("workflow_run checking out the triggering head", "must not check out the proposed head",
         GOOD.replace("  pull_request:\n", "  workflow_run:\n    workflows: [ci]\n").replace(
             f"      - uses: actions/checkout@{SHA1}\n",
             f"      - uses: actions/checkout@{SHA1}\n        with:\n          ref: ${{{{ github.event.workflow_run.head_sha }}}}\n", 1))
    case("an action pinned to a tag", "is not pinned to a 40-hex commit", GOOD.replace(f"actions/checkout@{SHA1}\n", "actions/checkout@v4\n", 1))
    case("an action pinned to a branch", "is not pinned", GOOD.replace(f"actions/checkout@{SHA1}\n", "actions/checkout@main\n", 1))
    case("a pin-ok marker without a reason", "is not pinned",
         GOOD.replace(f"actions/checkout@{SHA1}  # pin-ok: kept in step with the tested release", "actions/checkout@v4  # pin-ok:"))
    case("a tag with a pin-ok reason is green", None,
         GOOD.replace(f"actions/checkout@{SHA1}\n", "actions/checkout@v4  # pin-ok: vendored mirror, reviewed\n", 1))
    case("a second file with the same flaw", "other.yml: no top-level", extra={"other.yml": "name: o\non: push\njobs:\n  a:\n    runs-on: x\n    steps:\n      - run: true\n"})
    if bad:
        print(f"check-workflow-permissions: self-test FAIL ({bad} of {ran} cases wrong)", file=sys.stderr)
        return 1
    print(f"check-workflow-permissions: self-test OK ({ran} cases)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Fail when a workflow file grants more than it needs.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--workflows", default=".github/workflows", help="workflow directory, relative to --root")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    root = os.path.abspath(a.root)
    problems, n = run(root, a.workflows)
    if problems:
        print("check-workflow-permissions: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"check-workflow-permissions: OK -- {n} workflow file(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
