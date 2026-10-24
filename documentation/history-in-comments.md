# History in comments: archive, link, fold

**What this is for.** A rule and a method for keeping source comments about the code as it is now. Use it when you
write or review a comment, when a check goes red on a retelling comment, and when you sweep a codebase that already
has hundreds of them.

**The rule.** The codebase describes only its current state. A comment says what the code is and why it is that way.
What it was before, which bug found it, who asked and on which day is history. History lives in version control and in
the tracker item, and a comment links to it by id. It does not retell it.

Why this matters:

- A retold history is wrong the day the next change lands. A link stays true.
- Retelling is the bulk of what a reader has to skip to find the current reason.
- A retelling comment gets copied into the next comment, and the story grows.
- An agent that reads "used to be 3px" may restore 3px. Present tense cannot be misread as a to-do.

## Contents

- [The three moves](#the-three-moves)
- [Before and after, in six languages](#before-and-after-in-six-languages)
- [What counts as history](#what-counts-as-history)
- [What is allowed](#what-is-allowed)
- [Markers for deliberate exceptions](#markers-for-deliberate-exceptions)
- [How the check works](#how-the-check-works)
- [Citing an item: what counts as a citation](#citing-an-item-what-counts-as-a-citation)
- [Day to day](#day-to-day)
- [Limits of a line check](#limits-of-a-line-check)
- [The page for your repository](#the-page-for-your-repository)

## The three moves

Do them in this order.

1. **Archive.** Move the story to where history belongs: the tracker item's `## Status` or `## Detail` section, or a
   research note that backs an open item. If the item does not exist, create it. If the story is only "we changed it",
   version control already has it and there is nothing to archive.
2. **Link.** Cite the item by its id: `(backlog 312)`. A path works for a doc that is not an item. Use the citation
   form your reference check understands, so the link is verified.
3. **Fold.** Keep the lasting part in the comment, in present tense: the reason a reader needs to avoid undoing the
   code. A comment that only retells has nothing to fold. Delete it.

One comment, all three moves:

```python
# BEFORE
# Used to retry 5 times; changed to 2 on 2025-03-02 after the outage (see commit 3fa9c21).
RETRIES = 2

# AFTER
# Two retries: a third doubles the load on a struggling backend (backlog 312).
RETRIES = 2
```

- Archive: the outage, the date and the old value of 5 go into item 312's `## Status`.
- Link: `backlog 312`, which the reference check resolves to `docs/backlog/312-*.md`.
- Fold: "a third doubles the load" is the part that stays true as long as the code does.

## Before and after, in six languages

The ideas are the same in every language. Only the comment syntax differs.

**Python**

```python
# BEFORE: previously we cached per process; now we cache per request
cache = RequestCache()

# AFTER
# Per request: a process-wide cache served one user's fragment to another (backlog 41).
cache = RequestCache()
```

**TypeScript**

```ts
// BEFORE: this was a setTimeout until the 2025-02-11 flicker report
requestAnimationFrame(update);

// AFTER
// A frame callback, not a timer: a timer can fire between paints and show a half-updated list (backlog 58).
requestAnimationFrame(update);
```

**Rust**

```rust
/// BEFORE: no longer uses the shared clock since the rewrite in 7c1d9ae.
fn tick(&mut self) {}

/// AFTER
/// Each timeline owns its clock, so pausing one cannot stall another (backlog 77).
fn tick(&mut self) {}
```

**Shell**

```sh
# BEFORE: we now quote "$dir" because it used to break on spaces
rm -rf -- "$dir"

# AFTER
# Quoted and after `--`: a directory name may contain spaces or start with a dash (backlog 19).
rm -rf -- "$dir"
```

**CSS**

```css
/* BEFORE: was 3px, now 2px (clipped in the card) */
.control:focus-visible { box-shadow: 0 0 0 2px currentColor; }

/* AFTER
   2px: a wider ring clips inside an overflow:hidden card (backlog 312). */
.control:focus-visible { box-shadow: 0 0 0 2px currentColor; }
```

**Go**

```go
// BEFORE: formerly returned nil on timeout; fixed after the incident last week
func Fetch(ctx context.Context) (*Page, error) {

// AFTER
// Fetch returns ErrTimeout, never a nil page with a nil error, so a caller cannot mistake a timeout for an empty
// result (backlog 90).
func Fetch(ctx context.Context) (*Page, error) {
```

When the item already holds the story and the comment contains no reason, there is nothing to fold. Delete the whole
comment.

## What counts as history

A comment line is history when it tells how the code changed instead of what it is. The scanner in
[`../examples/documentation/comment_scan.py`](../examples/documentation/comment_scan.py) flags these. Add to its
`PHRASES` table as your codebase finds more.

| Kind | Looks like | Why it is history |
|---|---|---|
| Date | `2025-03-02`, `since March` | Dates the story, not the code. |
| Commit hash | `fixed in 98e7ca1b` | Points at a change, and the tracker item already carries it. |
| "used to" | `used to be 3px` | Names a previous state. |
| "previously", "formerly" | `previously this took the first child` | Same. |
| "no longer" | `no longer uses the shared timer` | Defines the code by what it dropped. |
| "now" with a verb | `now reads the registered item` | Implies a before. |
| "was X, now Y" | `was 3px, now 2px` | A diff in prose. |
| Fix narration | `before the fix`, `was renamed`, `since removed` | A changelog entry in the wrong file. |
| Incident narration | `after the outage`, `we found that` | A post-mortem in the wrong file. |
| Old behaviour | `old behaviour`, `old name`, `kept for old callers` | Names what is gone, and "old" is relative to a day nobody will remember. |
| A fix retold | `was fixed in 1.4`, `fixed in v2.3.1`, `was fixed upstream` | A changelog entry in the wrong file. Say what the code does and link the item. |
| A removal retold | `removed in v3.0`, `deprecated since 2.1` | Same. |
| Leftovers | `leftover from the old parser`, `remnant of the migration` | Defines the code by what surrounds it no more. |
| "We" did something | `we switched to a map`, `we moved it`, `originally written as a loop` | A story told by its author. |
| A narrative TODO | `TODO: tidy this up after the rewrite` | A TODO tied to an event instead of an item. Write `TODO(backlog 12)`. |

Not history, and not flagged:

- The passive sense: `is used to size the panel`, `can be used to anchor it`.
- A state word: `the previously focused element`.
- A colour or a hex literal that looks like a hash: `#abc1234`, `0xdeadbeef`.
- A pinned upstream revision that a file was ported from, in the form `ported from lib/x.py @ 7e4034b`. That is
  provenance (where the code came from), and it is current: the file is that port.

## What is allowed

- **A present-tense reason, plus the tracker link.** "Two retries: a third doubles the load (backlog 312)." This is the
  target shape for any non-obvious choice.
- **Explanatory blocks.** A block comment that says how a module works, what its invariants are and what its edge cases
  are is documentation, not history. It may be long. It stays in present tense.
- **Provenance.** Where a file was ported from, and at which pinned revision. Licences too.
- **Quoted upstream text.** A line from a dependency's changelog that explains a workaround. Mark it
  `history-ok: <reason>`.
- **A date the code needs.** A fixture with a calendar date, a certificate expiry that code compares against. The date
  is data. Mark it, or set `--min-date` so old test data does not count.

Prefer to say what the code does, and let the item say what it stopped doing:

| Instead of | Write |
|---|---|
| `// no longer uses the shared timer` | State what it uses. The item says what it stopped using. |
| `// fixed in 98e7ca1b` | `// (backlog 245)`. The item carries the commit. |
| `// previously this took the first child; now it reads the registered item` | `// reads the registered item, so a wrapper element cannot be mistaken for the first child` |

## Markers for deliberate exceptions

A marker goes on the line itself, with a reason a reviewer can judge:

```ts
// The vendor's changelog says "no longer retries on 429" (2024-06-01). history-ok: quoted from upstream, kept verbatim
```

```python
# See docs/vendor-notes.md. ref-ok: that file lives in the vendor's repository, not this one
```

- `history-ok: <reason>` exempts the line from the history check.
- `ref-ok: <reason>` exempts a citation from the reference check.
- A marker with no reason exempts nothing. The reason is the cost of the exception, and it is reviewed like any other
  line of the diff.
- A pattern that fires on an innocent sentence is a bug in the scanner. Tighten the pattern and add the sentence to
  the scanner's self-test. Do not mark it.

## How the check works

Two checks share one comment extractor, so what counts as a comment is decided in one place. See
[`ratchets.md`](./ratchets.md) for the baseline mechanism.

- **History check** (`check-history-comments.sh`). Counts, per file, the comment lines that carry a date, a commit
  hash or a flagged phrase. The counts are in a baseline file, `path<TAB>count`. It fails when a file's count rises,
  when a new file has any, and when a count fell while the baseline still allows the old number (run
  `sh scripts/check-history-comments.sh --update-baseline` to lock the drop in; that is the command in your
  repository once the scripts are copied into `scripts/`).
- **Reference check** (`check-comment-refs.sh`). Every cited tracker id must have a file in the tracker. Every repository
  path that a comment names must exist. Dead ones that predate the check are in a second baseline.

The extractor knows each language's comment syntax from a table keyed by file extension. A comment marker inside a string
is not a comment. A Python docstring is read as a comment. It skips vendored and generated trees, and Markdown, because
docs are where history may live.

The scripts are in [`../examples/documentation/`](../examples/documentation/README.md). Each has a `--self-test` that plants a
violation and requires the check to go red, and each wrapper runs it quietly after the check
([`ratchets.md`](./ratchets.md#the-check-proves-it-can-fail)).

## Citing an item: what counts as a citation

The reference check resolves every `backlog 312` in a comment to a file. The word before the number is a choice (`backlog`,
`issue`, `ticket`), and some of those words are ordinary English: "the second issue 5 times larger" is not a citation. So a
bare `<word> N` is checked only when it is unmistakable, otherwise the check would report dead ids that are quantities:

- it is written with a hash, `issue #312`; or
- the comment block also names the tracker (the tracker directory's name, such as "backlog", or the word "tracker"); or
- N has three or more digits, is at most 25 above the highest existing id (it looks like an id) and does not read as a
  quantity (`issue 450 times`, `issue 30 of 40`).

With the default word, `backlog`, the word itself names the tracker, so every `backlog N` is checked. A project whose word
is `issue` writes `issue #12` in comments and gets exactly the citations it meant checked. A second tracker (defect records,
below) is a second run of the same check with `--tracker docs/issues --word issue --baseline scripts/baselines/issue-refs.tsv`.

## Day to day

- The check went red on your change. It prints the file and each hit line with its reason (`[date]`, `[used to]`).
  Rewrite the line with the three moves. If you cleaned a file so its count fell, run
  `sh scripts/check-history-comments.sh --update-baseline` and commit the baseline file with the change.
- To see all the debt: `check-history-comments.sh --inventory` prints `file:line  reason  text` for every counted line.
  That is the worklist for a sweep. See [`cleanup-playbook.md`](./cleanup-playbook.md).
- A baseline that must grow needs `sh scripts/check-history-comments.sh --update-baseline --allow-grow`, and the commit message says why. Prefer a marker
  with a reason.
- In review, ask of every new comment: "Does this still read true after the next change?" If it narrates, it will not.

## Limits of a line check

- The check sees phrases and dates. It cannot judge whether a present-tense reason is true. Review does that.
- **Green means "no common shape found". It does not mean the comments are clean.** The check knows dates, hashes and a
  list of phrases (the table above). A comment can retell history in words no pattern matches. The patterns catch the common
  shapes; add one when review finds a new shape twice, with its sentence in the scanner's self-test. A reviewer still reads
  the comments in a diff, and a sweep still reads the files it touches: the check keeps what was found from coming back, and
  finds nothing that its patterns do not describe.
- Some patterns trade a few false positives for coverage, and "old" in `kept for old callers` is one of them: "old" ages, so
  the rewrite names the thing ("callers older than v3") and the marker is for the rare line that must stay as it is.
- Code inside a string of another language, and multi-line quoted strings in shell, are not scanned. The gaps only make
  the check more lenient.
- Prose docs are not scanned for narration. Their rule is in [`principles.md`](./principles.md): living docs state the
  current state, and history goes to the archive. One shape is checked by its own ratchet: a dated heading or lead-in
  (`## Status (2025-03-02)`) in a living doc (`check-dated-headings.sh`).

## The page for your repository

Comments cite a guide that says the rule in your words, in your repository, so the rule has a home that does not depend on this
one. Copy [`../templates/history-in-comments.md`](../templates/history-in-comments.md) to `docs/guides/history-in-comments.md`,
adapt its examples to your language, and link it from the entry file. It is one page: the rule, the three moves, the table of
what to write instead, and the markers.
