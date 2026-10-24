#!/bin/sh
# The generator: reads $SRC, writes $OUT. Deterministic (same input, same bytes).
tr 'a-z' 'A-Z' < "$SRC" > "$OUT"
