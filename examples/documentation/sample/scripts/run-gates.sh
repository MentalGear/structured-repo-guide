#!/bin/sh
# run-gates.sh -- the one runner: run every gate in scripts/gates.list, print a summary, exit 0 only for a full green run
#
# Runs every gate in the list beside it (gates.list, one gate per line) in order, keeps going after a red one so a
# single run shows every red gate, and ends with ALL GREEN and exit 0 only when every listed gate ran and passed. A
# partial run (--only, --skip, --fast, --stop-on-fail) is never mistaken for the full one: it exits 3.
#
# Usage: sh scripts/run-gates.sh [options]          (from anywhere: the tree is the parent of this script's directory)
#
#   --only REGEX      run only the gates whose name matches REGEX (grep -E)
#   --skip REGEX      skip the gates whose name matches REGEX
#   --fast            skip the gates tagged `slow` (what a contributor runs while editing)
#   --stop-on-fail    stop at the first red gate
#   --no-reuse        trust no stored PASS: run every gate (also GATE_REUSE=0); a fresh result is still stored or dropped
#   --gates FILE      the gate list (default: gates.list next to this script)
#   --log-dir DIR     keep the per-gate logs here (default: a temporary directory, kept only when a gate is red)
#   --list            print each gate (name, tags, group, command) and exit
#   --self-test       build throwaway trees and prove every promise below, then exit
#
# Exit status: 0 every gate ran and passed (ALL GREEN); 1 a gate is red; 2 bad usage, a bad or empty list, or a
# scripts/check-*.sh that is not in the list; 3 green but PARTIAL.
#
# The gate list, one line per gate:
#
#   # group: Source hygiene                     a heading; every gate needs one above it
#   # Any other comment lines directly above a command gate describe it: the catalogue prints them.
#   check-tabs|sh scripts/check-<name>.sh       name | command (run with sh -c from the tree's root)
#   test slow reuse:src,Cargo.toml|cargo test   tags after the name: `slow` (left out by --fast) and
#                                               `reuse:PATH,PATH` (a PASS is stored per hash of those paths)
#
# A check script is described by its own header, a command gate by the comment above it; docs_catalogue.py
# generates the catalogue page from both. A new gate is one line here and nothing else.
#
# Guards, each closing a failure class by construction:
#   1. A scripts/check-*.sh that is not in the list fails the run (exit 2), so a new check cannot stay out of it.
#   2. The summary names the tree the gates ran on (git HEAD plus a hash of every uncommitted change, or "not a git
#      repo"), so a green cannot be quoted for a tree it was not taken on.
#   3. Only a full run prints ALL GREEN. A hidden gate is exit 3 and the word PARTIAL.
#   4. Reuse. A gate tagged `reuse:PATHS` stores its PASS under a key made of its name, its command line, the
#      bytes of every file under PATHS, every file its command names and $GATE_REUSE_SALT (put a toolchain version
#      there). A later run with the same key prints `reused` and does not run it. Only a PASS is stored, a FAIL
#      (even under --no-reuse) deletes the stored PASS, any changed input is a different key, and a tree that
#      changed while the gate ran stores nothing. List every input the gate reads: an input left out is a stale PASS reused. The store is
#      $GATE_REUSE_DIR (default: inside .git, else .gate-reuse in the tree).
set -u

RUNNER_FORMAT=1
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 2
root=$(dirname "$here")
tab=$(printf '\t')

die() { echo "run-gates: $*" >&2; exit 2; }

hash_stdin() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | cut -d ' ' -f 1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 | cut -d ' ' -f 1
  else cksum | tr ' ' '-'; fi
}

# ------------------------------------------------------------------------------------------------ self-test
self_test() {
  case "$0" in /*) me=$0 ;; *) me=$PWD/$0 ;; esac
  work=$(mktemp -d "${TMPDIR:-/tmp}/run-gates-test.XXXXXX") || exit 2
  trap 'rm -rf "$work"' EXIT HUP INT TERM
  fails=0
  n=0
  genv=""   # extra environment (NAME=value ...) for the next go call
  # A tree: scripts/run-gates.sh (a copy of this file), scripts/gates.list from $2, and the files in $3 (name=content, ;-separated)
  mk() { # $1 = tree name, $2 = list text
    t="$work/$1"
    mkdir -p "$t/scripts" "$t/src"
    cp "$me" "$t/scripts/run-gates.sh"
    printf '%s\n' "$2" > "$t/scripts/gates.list"
    printf 'ok\n' > "$t/src/a.txt"
  }
  # run the copy in tree $1 with the remaining arguments; sets rc and out
  go() {
    t="$work/$1"; shift
    out=$(env GIT_CEILING_DIRECTORIES="$work" GATE_REUSE_DIR="$t/.store" $genv sh "$t/scripts/run-gates.sh" --log-dir "$work/logs/$(basename "$t")" "$@" 2>&1)
    rc=$?
  }
  expect() { # $1 = name, $2 = want rc, $3 = text that must appear ("" for none), $4 = text that must not appear
    n=$((n + 1))
    good=1
    [ "$rc" -eq "$2" ] || good=0
    [ -z "${3:-}" ] || printf '%s' "$out" | grep -Fq -- "$3" || good=0
    [ -z "${4:-}" ] || ! printf '%s' "$out" | grep -Fq -- "$4" || good=0
    if [ "$good" = 1 ]; then echo "  ok   $1 (rc $rc, want $2)"; else
      fails=$((fails + 1)); echo "  FAIL $1 (rc $rc, want $2; wanted '${3:-}', unwanted '${4:-}')"
      printf '%s\n' "$out" | sed 's/^/    | /'
    fi
  }
  lines() { [ -f "$1" ] && wc -l < "$1" | tr -d ' ' || echo 0; }
  expect_eq() { # $1 = name, $2 = got, $3 = want
    n=$((n + 1))
    if [ "$2" = "$3" ]; then echo "  ok   $1 ($2)"; else fails=$((fails + 1)); echo "  FAIL $1 (got $2, want $3)"; fi
  }

  base='# group: One
good|true
# group: Two
# a command gate is described by the comment above it
other|sh -c "echo hello"'
  mk green "$base"
  go green
  expect "a full green run prints ALL GREEN and exits 0" 0 "ALL GREEN" "PARTIAL"
  expect "the summary names a tree that is not a git repo" 0 "not a git repo"

  mk red "$base
bad|sh -c 'echo broken >&2; exit 4'"
  go red
  expect "a red gate exits 1, names it and shows its output" 1 "RED: bad" "ALL GREEN"
  expect "the failing gate's log tail is printed" 1 "broken"

  mk unlisted "$base"
  printf '#!/bin/sh\nexit 0\n' > "$work/unlisted/scripts/check-forgotten.sh"
  go unlisted
  expect "a check script missing from the list exits 2 and runs nothing" 2 "check-forgotten.sh" ">> good"

  mk listed "$base
fresh|sh scripts/check-fresh.sh"
  printf '#!/bin/sh\nexit 0\n' > "$work/listed/scripts/check-fresh.sh"
  go listed
  expect "a listed check script is accepted (with arguments in the command too)" 0 "ALL GREEN"

  mk partial "$base"
  go partial --only '^good$'
  expect "--only runs a subset: exit 3, PARTIAL, no ALL GREEN" 3 "PARTIAL" "ALL GREEN"
  go partial --skip '^other$'
  expect "--skip runs a subset: exit 3" 3 "PARTIAL" "ALL GREEN"
  go partial --only '^nothing-matches$'
  expect "--only that matches no gate is bad usage" 2 "matches no gate"
  go partial --no-such-option
  expect "an unknown option is bad usage" 2 "unknown option"
  go partial --only
  expect "an option without its value is bad usage" 2 "needs a value"

  mk fast "# group: One
quick|true
# group: Two
# takes minutes
lengthy slow|sh -c 'echo ran >> ran.log'"
  go fast --fast
  expect "--fast leaves out a slow gate: exit 3, never ALL GREEN" 3 "PARTIAL" "ALL GREEN"
  expect_eq "--fast really did not run the slow gate" "$(lines "$work/fast/ran.log")" 0
  go fast
  expect "the full run includes the slow gate" 0 "ALL GREEN"
  expect_eq "the full run ran the slow gate once" "$(lines "$work/fast/ran.log")" 1

  mk stop "# group: One
first|false
second|sh -c 'echo ran >> ran.log'"
  go stop --stop-on-fail
  expect "--stop-on-fail stops at the first red gate: exit 1" 1 "RED: first"
  expect_eq "--stop-on-fail did not run the second gate" "$(lines "$work/stop/ran.log")" 0
  go stop
  expect_eq "without it every gate runs and the second one ran" "$(lines "$work/stop/ran.log")" 1

  mk dup "# group: One
same|true
same|true"
  go dup
  expect "a duplicate gate name is bad usage" 2 "duplicate"
  mk nogroup "same|true"
  go nogroup
  expect "a gate with no group heading above it is bad usage" 2 "group"
  mk badline "# group: One
this line has no pipe"
  go badline
  expect "a list line without a pipe is bad usage" 2 "name|command"
  mk empty "# group: One"
  go empty
  expect "an empty list is bad usage, never a green" 2 "no gates"

  mk listing "$base"
  go listing --list
  expect "--list prints the names" 0 "good"

  # reuse
  mk reuse "# group: One
# counts its runs
counted reuse:src|sh -c 'echo run >> runs.log'
# fails every time
failing reuse:src|sh -c 'echo run >> fruns.log; exit 1'"
  go reuse
  go reuse
  expect_eq "reuse: an identical second run did not run the PASS gate again" "$(lines "$work/reuse/runs.log")" 1
  expect "reuse: the second run says reused and the summary lists it" 1 "reused (stored PASS" "reused: 0"
  expect_eq "reuse: a FAIL is never stored (it ran both times)" "$(lines "$work/reuse/fruns.log")" 2
  printf 'changed\n' > "$work/reuse/src/a.txt"
  go reuse
  expect_eq "reuse: a changed input runs the gate again" "$(lines "$work/reuse/runs.log")" 2
  go reuse --no-reuse
  expect_eq "reuse: --no-reuse runs it again" "$(lines "$work/reuse/runs.log")" 3
  genv="GATE_REUSE=0"; go reuse; genv=""
  expect_eq "reuse: GATE_REUSE=0 runs it again" "$(lines "$work/reuse/runs.log")" 4
  go reuse
  expect_eq "reuse: the PASS stored by the earlier real run is still reused" "$(lines "$work/reuse/runs.log")" 4
  printf 'x\n' > "$work/reuse/src/new-file.txt"
  go reuse
  expect_eq "reuse: a new file under the input path is a different key" "$(lines "$work/reuse/runs.log")" 5
  genv="GATE_REUSE_SALT=toolchain-2"; go reuse; genv=""
  expect_eq "reuse: the salt (toolchain) is part of the key" "$(lines "$work/reuse/runs.log")" 6

  mk flaky "# group: One
# passes unless the file fail-now exists
flaky reuse:src|sh -c 'echo r >> flaky.log; test ! -f fail-now'"
  go flaky
  go flaky
  expect_eq "reuse: a stored PASS is reused until something changes" "$(lines "$work/flaky/flaky.log")" 1
  : > "$work/flaky/fail-now"
  go flaky --no-reuse
  expect "reuse: --no-reuse runs the gate and a FAIL is red" 1 "RED: flaky"
  rm -f "$work/flaky/fail-now"
  go flaky
  expect_eq "reuse: a FAIL deleted the stored PASS, so the next run really runs" "$(lines "$work/flaky/flaky.log")" 3
  for f in "$work/flaky/.store"/*; do printf 'FAIL\tx\t1\n' > "$f"; done
  go flaky
  expect_eq "reuse: a stored entry that is not a PASS is never reused" "$(lines "$work/flaky/flaky.log")" 4

  mk reuseall "# group: One
# changes its own inputs while it runs
mutating reuse:src|sh -c 'echo changed >> src/a.txt'"
  go reuseall
  go reuseall
  expect "reuse: a tree changed under a running gate stores nothing" 0 "nothing stored" "reused ("

  # the tree label in a git repository
  if command -v git >/dev/null 2>&1; then
    mk gitted "$base"
    g="$work/gitted"
    if (cd "$g" && git init -q . && git add -A && git -c user.name=t -c user.email=t@example.invalid commit -q -m first) >/dev/null 2>&1; then
      head=$(git -C "$g" rev-parse --short HEAD)
      go gitted
      expect "git tree: the summary names HEAD" 0 "$head"
      one=$(printf '%s' "$out" | sed -n 's/.*diff-hash \([0-9a-f]*\).*/\1/p' | head -n 1)
      go gitted
      two=$(printf '%s' "$out" | sed -n 's/.*diff-hash \([0-9a-f]*\).*/\1/p' | head -n 1)
      expect_eq "git tree: the same tree gives the same diff hash" "$two" "$one"
      printf 'edit\n' >> "$g/src/a.txt"
      go gitted
      three=$(printf '%s' "$out" | sed -n 's/.*diff-hash \([0-9a-f]*\).*/\1/p' | head -n 1)
      [ -n "$three" ] && [ "$three" != "$one" ] && r=different || r=same
      expect_eq "git tree: an uncommitted edit changes the diff hash" "$r" different
    else
      echo "  skip git tree cases (git could not commit here)"
    fi
  else
    echo "  skip git tree cases (no git)"
  fi

  if [ "$fails" -eq 0 ]; then echo "run-gates --self-test: OK ($n cases)"; exit 0; fi
  echo "run-gates --self-test: $fails FAILED of $n"
  exit 1
}

# ------------------------------------------------------------------------------------------------ options
only="" skip="" fast=0 stop_on_fail=0 list_only=0 log_dir="" reuse=1 gates_file="$here/gates.list"
[ "${GATE_REUSE:-1}" = 0 ] && reuse=0
need() { [ "$1" -ge 2 ] || die "$2 needs a value"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --only) need $# --only; only=$2; shift 2 ;;
    --skip) need $# --skip; skip=$2; shift 2 ;;
    --fast) fast=1; shift ;;
    --stop-on-fail) stop_on_fail=1; shift ;;
    --no-reuse) reuse=0; shift ;;
    --gates) need $# --gates; gates_file=$2; shift 2 ;;
    --log-dir) need $# --log-dir; log_dir=$2; shift 2 ;;
    --list) list_only=1; shift ;;
    --self-test) self_test ;;
    -h|--help) sed -n '2,/^set -u$/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

# ------------------------------------------------------------------------------------------------ the gate list
[ -f "$gates_file" ] || die "no gate list at $gates_file"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/run-gates.XXXXXX") || die "cannot create a temporary directory"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM PIPE
parsed="$tmp/gates.tsv"

# One line per gate: name TAB tags (separated by ";", "-" for none) TAB group TAB command. A malformed line is
# reported as `!line-number TAB text` and fails the run.
awk '
  /^[ \t]*$/ { next }
  /^[ \t]*#/ {
    s = $0; sub(/^[ \t]*#[ \t]*/, "", s)
    if (s ~ /^group:/) { sub(/^group:[ \t]*/, "", s); group = s }
    next
  }
  {
    p = index($0, "|")
    if (p == 0) { print "!" NR "\tneeds the form name|command: " $0; next }
    head = substr($0, 1, p - 1); cmd = substr($0, p + 1)
    gsub(/^[ \t]+/, "", head); gsub(/[ \t]+$/, "", head)
    gsub(/^[ \t]+/, "", cmd); gsub(/[ \t]+$/, "", cmd)
    n = split(head, w, /[ \t]+/)
    if (w[1] !~ /^[A-Za-z0-9_.-]+$/) { print "!" NR "\tbad gate name " w[1]; next }
    if (cmd == "") { print "!" NR "\tgate " w[1] " has no command"; next }
    if (group == "") { print "!" NR "\tgate " w[1] " has no `# group:` heading above it"; next }
    tags = ""
    for (i = 2; i <= n; i++) tags = tags (i > 2 ? ";" : "") w[i]
    print w[1] "\t" (tags == "" ? "-" : tags) "\t" group "\t" cmd
  }' "$gates_file" > "$parsed"

bad=$(sed -n 's/^!//p' "$parsed")
if [ -n "$bad" ]; then
  printf '%s\n' "$bad" | while IFS="$tab" read -r ln msg; do echo "run-gates: $gates_file line $ln: $msg" >&2; done
  exit 2
fi
total=$(wc -l < "$parsed" | tr -d ' ')
[ "$total" -gt 0 ] || die "no gates in $gates_file"
dups=$(cut -f 1 "$parsed" | sort | uniq -d | tr '\n' ' ')
[ -z "$dups" ] || die "duplicate gate name(s) in $gates_file: $dups"

if [ "$list_only" = 1 ]; then
  while IFS="$tab" read -r name tags group cmd; do printf '%s\t%s\t%s\t%s\n' "$name" "$tags" "$group" "$cmd"; done < "$parsed"
  exit 0
fi

# Guard 1: every scripts/check-*.sh is in the list
unlisted=""
for f in "$root"/scripts/check-*.sh; do
  [ -e "$f" ] || continue
  rel="scripts/$(basename "$f")"
  awk -F '\t' -v f="$rel" '{ n = split($4, w, /[ \t]+/); for (i = 1; i <= n; i++) if (w[i] == f) found = 1 } END { exit !found }' "$parsed" \
    || unlisted="$unlisted $rel"
done
[ -z "$unlisted" ] || die "scripts not in the gate list (add a line to $(basename "$gates_file")):$unlisted"

# Selection
if [ -n "$only" ] && ! cut -f 1 "$parsed" | grep -Eq -- "$only"; then die "--only '$only' matches no gate"; fi
selected() { # $1 = name, $2 = tags
  [ -z "$only" ] || printf '%s\n' "$1" | grep -Eq -- "$only" || return 1
  [ -z "$skip" ] || ! printf '%s\n' "$1" | grep -Eq -- "$skip" || return 1
  [ "$fast" = 0 ] || case ";$2;" in *";slow;"*) return 1 ;; esac
  return 0
}

# ------------------------------------------------------------------------------------------------ the tree
git_ok=0
if command -v git >/dev/null 2>&1 && git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then git_ok=1; fi

tree_state() { # prints: <head> <dirty paths> <diff hash>
  if [ "$git_ok" = 0 ]; then echo "not a git repo"; return; fi
  head=$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo "no-commits")
  dirty=$(git -C "$root" status --porcelain -- . 2>/dev/null | wc -l | tr -d ' ')
  dh=$( {
          git -C "$root" diff HEAD -- . 2>/dev/null
          git -C "$root" ls-files -o --exclude-standard -- . 2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
            printf '%s %s\n' "$f" "$(hash_stdin < "$root/$f")"
          done
        } | hash_stdin | cut -c 1-12 )
  echo "$head $dirty $dh"
}
state=$(tree_state)
if [ "$git_ok" = 1 ]; then
  set -- $state
  head=$1 dirty=$2 diff_hash=$3
  tree_label="$head (diff-hash $diff_hash, $dirty uncommitted path(s))"
  tree_short="$head"; [ "$dirty" = 0 ] || tree_short="$head+dirty:$diff_hash"
else
  tree_label="not a git repo (a green here names no commit)"
  tree_short="not-a-git-repo"
fi
echo "run-gates: tree $tree_label"

# ------------------------------------------------------------------------------------------------ reuse
if [ -n "${GATE_REUSE_DIR:-}" ]; then store=$GATE_REUSE_DIR
elif [ "$git_ok" = 1 ]; then
  gd=$(git -C "$root" rev-parse --git-dir); case "$gd" in /*) ;; *) gd="$root/$gd" ;; esac
  store="$gd/gate-reuse"
else store="$root/.gate-reuse"; fi

# The key of a gate: name, command, the bytes of every input path, every file the command names, the salt.
gate_key() { # $1 = name, $2 = tags, $3 = command
  set -f   # the command's words are split below and must not be glob-expanded (this runs in a $( ) subshell)
  {
    echo "format $RUNNER_FORMAT"; echo "name $1"; echo "cmd $3"; echo "salt ${GATE_REUSE_SALT:-}"
    {
      printf '%s\n' "$2" | tr ';' '\n' | sed -n 's/^reuse://p' | tr ',' '\n'
      for w in $3; do [ -f "$root/$w" ] && echo "$w"; done
    } | LC_ALL=C sort -u | while IFS= read -r p; do
      [ -n "$p" ] || continue
      if [ -d "$root/$p" ]; then
        (cd "$root" && find "$p" -type f ! -path '*/.git/*' | LC_ALL=C sort | while IFS= read -r f; do printf '%s %s\n' "$f" "$(hash_stdin < "$f")"; done)
      elif [ -f "$root/$p" ]; then printf '%s %s\n' "$p" "$(hash_stdin < "$root/$p")"
      else printf 'missing %s\n' "$p"; fi
    done
  } | hash_stdin | cut -c 1-40
}
reuse_on() { case ";$1;" in *";reuse:"*) mkdir -p "$store" 2>/dev/null ;; *) false ;; esac; }

# ------------------------------------------------------------------------------------------------ run
own_logs=0
if [ -z "$log_dir" ]; then log_dir=$(mktemp -d "${TMPDIR:-/tmp}/run-gates-logs.XXXXXX") || die "cannot create a log directory"; own_logs=1; fi
mkdir -p "$log_dir" || die "cannot create log dir $log_dir"
summary="$tmp/summary.tsv"; : > "$summary"
red="" ran=0 hidden=0 reused=0 reuse_note=""

while IFS="$tab" read -r name tags group cmd; do
  if ! selected "$name" "$tags"; then hidden=$((hidden + 1)); continue; fi
  key=""
  if reuse_on "$tags"; then
    key=$(gate_key "$name" "$tags" "$cmd")
    if [ "$reuse" = 1 ] && [ -f "$store/$key" ] && IFS="$tab" read -r verdict from secs < "$store/$key" && [ "$verdict" = PASS ]; then
      printf '>> %-30s PASS  reused (stored PASS for identical inputs, taken on tree %s, took %ss)\n' "$name" "$from" "$secs"
      printf '%s\tPASS\t0\treused from tree %s\n' "$name" "$from" >> "$summary"
      ran=$((ran + 1)); reused=$((reused + 1)); continue
    fi
  fi
  log="$log_dir/$name.log"
  printf '>> %-30s ' "$name"
  t0=$(date +%s)
  ( cd "$root" && sh -c "$cmd" ) > "$log" 2>&1
  rc=$?
  secs=$(( $(date +%s) - t0 ))
  ran=$((ran + 1))
  if [ "$rc" -eq 0 ]; then status=PASS; else status=FAIL; fi
  printf '%s  %4ss\n' "$status" "$secs"
  printf '%s\t%s\t%s\t%ss\n' "$name" "$status" "$rc" "$secs" >> "$summary"
  if [ -n "$key" ]; then
    if [ "$status" = PASS ]; then
      if [ "$(gate_key "$name" "$tags" "$cmd")" = "$key" ]; then
        printf 'PASS\t%s\t%s\n' "$tree_short" "$secs" > "$store/$key.tmp.$$" && mv -f "$store/$key.tmp.$$" "$store/$key"
      else
        reuse_note="$reuse_note $name"
      fi
    else
      rm -f "$store/$key"
    fi
  fi
  if [ "$status" = FAIL ]; then
    red="$red $name"
    echo "   --- last 25 lines of $log"; tail -n 25 "$log" | sed 's/^/   | /'
    if [ "$stop_on_fail" = 1 ]; then hidden=$((hidden + total - ran)); echo "run-gates: --stop-on-fail"; break; fi
  fi
done < "$parsed"

[ -z "$reuse_note" ] || echo "run-gates: the inputs of$reuse_note changed while it ran -- nothing stored for reuse"

echo
echo "================ run-gates summary (tree $tree_label) ================"
awk -F '\t' '{ printf "%-30s %-5s rc=%-3s %s\n", $1, $2, $3, $4 }' "$summary"
echo "gates run: $ran of $total   red: $(printf '%s' "$red" | wc -w | tr -d ' ')   reused: $reused"
[ "$reused" -eq 0 ] || echo "REUSED: $reused gate(s) were not run now; a PASS was stored for byte-identical inputs. --no-reuse runs them."
if [ -n "$red" ]; then
  echo "RED:$red   (logs in $log_dir)"
  exit 1
fi
[ "$own_logs" = 0 ] || rm -rf "$log_dir"
if [ "$hidden" -gt 0 ] || [ "$ran" -ne "$total" ]; then
  echo "PARTIAL: $ran of $total gates ran, all green -- this is NOT the full run"
  exit 3
fi
echo "ALL GREEN: all $total gates passed on $tree_label"
exit 0
