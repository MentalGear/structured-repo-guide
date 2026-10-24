# Checks

Generated from the header of each `scripts/check-*` by the catalogue generator; its `--check` fails when this page differs
from the generated text. **Do not edit it by hand.** Each script's header is the full account (escape-hatch markers,
baselines, self-tests); this page prints its first paragraph and links the script.

## Source hygiene

**`check-final-newline.sh`** ([`scripts/check-final-newline.sh`](../scripts/check-final-newline.sh)): Fails when a file under src/ does not end with a newline, because the next appended line would join the last one and the diff would show a change to a line nobody touched.

**`check-no-tabs.sh`** ([`scripts/check-no-tabs.sh`](../scripts/check-no-tabs.sh)): Fails when a file under src/ contains a tab character, because tab width differs by editor and a diff then shows alignment that the file does not have.

## Tracker

**`check-todo-has-id.sh`** ([`scripts/check-todo-has-id.sh`](../scripts/check-todo-has-id.sh)): Fails when a TODO under src/ does not read TODO(backlog N), because a TODO with no item is a promise nobody tracks, and the item is where its reason, its options and its owner live.
