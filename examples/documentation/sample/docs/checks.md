# Checks

Generated from the gate list `scripts/gates.list` and the headers of the check scripts it names, by the catalogue generator; its
`--check` fails when this page differs from the generated text. **Do not edit it by hand.** A check script is described
by the first paragraph of its own header (the header is the full account: markers, baselines, self-tests) and linked;
a gate that is a plain command is described by the comment lines above its entry in the list. Groups and order are the
list's, and the same run that prints `ALL GREEN` runs every gate below.

## Source hygiene

**`check-final-newline`** ([`scripts/check-final-newline.sh`](../scripts/check-final-newline.sh)): Fails when a file under src/ does not end with a newline, because the next appended line would join the last one and the diff would show a change to a line nobody touched.

**`check-no-tabs`** ([`scripts/check-no-tabs.sh`](../scripts/check-no-tabs.sh)): Fails when a file under src/ contains a tab character, because tab width differs by editor and a diff then shows alignment that the file does not have.

## Tracker

**`check-todo-has-id`** ([`scripts/check-todo-has-id.sh`](../scripts/check-todo-has-id.sh)): Fails when a TODO under src/ does not read TODO(backlog N), because a TODO with no item is a promise nobody tracks, and the item is where its reason, its options and its owner live.

## Build

**`build-syntax`**: Parses the build script without running it, so a syntax error is caught here and not on the first deploy.
