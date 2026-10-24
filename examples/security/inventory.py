#!/usr/bin/env python3
"""inventory.py: count what a dependency set brings, for the cost table of a dependency decision.

What it is for: deciding whether to keep, gate, replace or drop a dependency needs numbers, not
impressions: how many packages the closure has, how many run code at install or build time,
how many are source distributions. This reads the machine-readable output your package manager
already produces and prints the counts. It writes nothing and needs no network itself, Python 3
standard library only. Run it before and after a change and put the two numbers in the table.

  cargo metadata --locked --offline --format-version 1 | inventory.py cargo
      external crates, crates with a build script, proc-macro crates (code that runs on the
      machine that compiles)
  npm install --package-lock-only --ignore-scripts && inventory.py npm < package-lock.json
      packages in the lock and those that declare an install script (`hasInstallScript`)
  pip install --dry-run --ignore-installed --quiet --report - -r requirements.txt | inventory.py pip
      packages to install and those delivered as a source distribution (building one runs the
      project's build code; prefer wheels: `pip install --only-binary :all:`)

Exit status: 0 on success, 2 on unreadable input.
"""

import json
import sys


def cargo(data):
    ext = [p for p in data["packages"] if p.get("source")]
    kinds = lambda p: {k for t in p["targets"] for k in t["kind"]}
    return [("external crates", len(ext)),
            ("with a build script", sum("custom-build" in kinds(p) for p in ext)),
            ("proc-macro crates", sum("proc-macro" in kinds(p) for p in ext))]


def npm(data):
    pk = {k: v for k, v in data.get("packages", {}).items() if k}
    return [("packages in the lock", len(pk)),
            ("declaring an install script", sum(bool(v.get("hasInstallScript")) for v in pk.values()))]


def pip(data):
    inst = data.get("install", [])
    sdist = [i for i in inst if not i["download_info"]["url"].endswith(".whl")]
    return [("packages to install", len(inst)), ("as a source distribution", len(sdist))]


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("cargo", "npm", "pip"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        data = json.load(sys.stdin)
        rows = {"cargo": cargo, "npm": npm, "pip": pip}[sys.argv[1]](data)
    except (ValueError, KeyError) as err:
        print(f"inventory: cannot read {sys.argv[1]} input: {err}", file=sys.stderr)
        return 2
    for label, n in rows:
        print(f"{label:32} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
