#!/bin/sh
# check-workflow-permissions.sh -- workflows grant least privilege
#
# Fails when a workflow file declares no permissions, grants write-all or a top-level write scope, lets a privileged
# trigger check out the proposed head, or uses an action that is not pinned to a commit, because the token and secrets
# of a job are only as safe as its file.
#
# Usage: sh scripts/check-workflow-permissions.sh      (from anywhere; the wrapper finds its own tree)
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -I "$root/../check-workflow-permissions.py" --root "$root"
