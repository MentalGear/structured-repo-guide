# History in comments

<!--
Template. Copy to docs/guides/history-in-comments.md, replace the two examples with ones in your language, keep the rest,
and link the page from the entry file. The guide behind it is documentation/history-in-comments.md in the guide repository.
Delete this comment.
-->

**What this is for.** The rule for source comments in this repository and how to apply it. Read it before you write a
comment, and when the history check goes red on yours.

**The rule.** The code describes only its current state. A comment says what the code is and why it is that way. What it was
before, which bug found it, who asked and on which day is history. History lives in version control and in the tracker item,
and a comment links to it by id. It does not retell it.

## The three moves

1. **Archive.** Move the story to the tracker item's `## Status` or `## Detail`. If the item does not exist, create it. If the
   story is only "we changed it", version control already has it.
2. **Link.** Cite the item by id: `(backlog 12)`.
3. **Fold.** Keep the lasting part in the comment, in present tense: the reason a reader needs to avoid undoing the code. A
   comment that only retells has nothing to fold. Delete it.

```python
# BEFORE: used to retry 5 times; changed to 2 on 2025-03-02 after the outage (see commit 3fa9c21).
# AFTER:  Two retries: a third doubles the load on a struggling backend (backlog 12).
RETRIES = 2
```

```css
/* BEFORE: was 3px, now 2px (clipped in the card) */
/* AFTER:  2px: a wider ring clips inside an overflow:hidden card (backlog 12). */
```

## Write this, not that

| Instead of | Write |
|---|---|
| `no longer uses the shared timer` | What it uses. The item says what it stopped using. |
| `fixed in 3fa9c21b`, `was fixed in 1.4` | `(backlog 245)`. The item carries the commit and the version. |
| `previously this took the first child; now it reads the registered item` | `reads the registered item, so a wrapper element cannot be mistaken for the first child` |
| `TODO: tidy this up after the rewrite` | `TODO(backlog 31): tidy this up`. A TODO names its item. |

Allowed as written: a present-tense reason, an explanation of how a module works, where a file was ported from at which pinned
revision, and a date the code itself needs (a fixture, a certificate expiry).

## The checks

- `scripts/check-history-comments.sh` counts the comment lines that carry a date, a commit hash or a phrase that narrates a
  change, per file, against `scripts/baselines/history-comments.tsv`. A new one fails. A file that got cleaner must be locked in:
  `sh scripts/check-history-comments.sh --update-baseline`, committed with the change.
- `scripts/check-comment-refs.sh` fails when a comment cites an item id, or a path that starts at a top-level directory
  (or is written `./file`), that does not exist.
- A line that is history on purpose (a quoted upstream changelog) ends with `history-ok: <reason>`; a deliberate dead
  citation with `ref-ok: <reason>`. A marker without a reason exempts nothing.
- A pattern that fires on an innocent sentence is a bug in `scripts/comment_scan.py`: fix the pattern and add the sentence to
  its self-test. Do not mark it.

**Green means "no common shape found", not "clean".** The check knows dates, hashes and a list of phrases. Review still asks
of every new comment: does it read true after the next change? If it narrates, it will not.
