# Principles

**What this is for.** The few rules that the rest of this guide applies. Read it once before you adopt anything,
and return to it when a decision is unclear: each of the other documents is one of these principles worked out.

## Contents

- [1. Current state only](#1-current-state-only)
- [2. One home per rule](#2-one-home-per-rule)
- [3. Generated beats hand-kept](#3-generated-beats-hand-kept)
- [4. The entry file only points](#4-the-entry-file-only-points)
- [5. One status page](#5-one-status-page)
- [6. A decisions index](#6-a-decisions-index)
- [7. History lives in version control and the tracker](#7-history-lives-in-version-control-and-the-tracker)
- [8. A class gets a check, not a patch](#8-a-class-gets-a-check-not-a-patch)
- [9. Rules live in the repository](#9-rules-live-in-the-repository)
- [How the principles fit together](#how-the-principles-fit-together)

## 1. Current state only

A living document, and a comment in code, says what is true now. It does not say what was true, who changed it or when.

- A reader should never have to decide which sentence is still in force.
- A sentence about the past needs maintenance that nobody does, so it goes stale and misleads.
- "Current" includes the reason for a choice. "Two retries, because a third doubles the load" is current.
  "Two retries, down from five" is history.

Where history goes: [principle 7](#7-history-lives-in-version-control-and-the-tracker). How to keep it out of
comments: [`history-in-comments.md`](./history-in-comments.md).

## 2. One home per rule

Every rule is written in exactly one place. Every other place links to it.

- Two copies of a rule drift. After the drift, nobody knows which one is right.
- When you add a rule, find its home first. If none fits, create the home, then link it from the map in
  [`layout.md`](./layout.md).
- When you are about to paste a rule into a second file, write a link instead.
- A short summary next to a link is fine only if it contains no detail that could disagree. "Run the checks before every
  commit ([`checks.md`](../examples/documentation/sample/docs/checks.md))" is a pointer. A copy of the checks list is not.

Test: change the rule in its home. If any other file now contradicts it, that file held a copy.

## 3. Generated beats hand-kept

If a document is a function of something that already exists, generate it, and add a freshness check so it cannot
drift.

Good candidates: the catalogue of checks (from each check script's header), the backlog indexes (from the item files),
a command reference (from the tool's help text), a table of environment variables (from the config schema).

The construction has three parts:

1. A **source of truth** that people edit: the script header, the item file.
2. A **generator** that is a pure function of the source: no dates, no counts that are not derived, a stable order.
3. A **freshness check** that regenerates in memory and fails when the committed file differs.

The page then carries a line that says it is generated and not to edit it by hand. A new check script or a new item needs no
prose edit anywhere. That also ends a recurring merge conflict: a check list kept by hand in the entry file is edited by
every change that adds a check, so two such changes in flight collide on the same lines, and each change generated instead
touches its own files. Worked through in [`generated-docs.md`](./generated-docs.md) and
[`tracker-as-files.md`](./tracker-as-files.md).

## 4. The entry file only points

An agent or a new contributor reads one short file first (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`: the name
depends on the tool). That file holds the few rules that apply to every change, and a link to the home of everything
else.

- Keep it to one screen of rules. If a rule needs a paragraph of explanation, the paragraph lives in its home and the
  entry file gets a one-line pointer.
- It never lists the checks. A catalogue goes stale; the generated page does not.
- It starts with "read the status page first".
- A new check never edits it.

An entry file that grows past a screen is the sign that principle 2 was broken. Template:
[`../templates/AGENTS.md`](../templates/AGENTS.md).

## 5. One status page

One page says where the project is right now: what is deployed, what runs, what is next, what waits for a
person. It is short, and it is edited at every merge or round change by whoever owns merges.

- It carries a "Last updated" line. A reader who sees an old value knows to distrust it.
- It does not say what each batch contained. The log and the tracker say that.
- Row-level state belongs in the item, not here.

Template: [`../templates/STATUS.md`](../templates/STATUS.md).

## 6. A decisions index

A person's decision ("we do not ship an editor", "releases wait for the owner's sign-off") is easy to lose in a chat
or a thread. Keep one page, one line per decision: the decision, its date, and the item or doc that carries the reasoning.

- Only current decisions are listed. A reversed decision leaves the page and stays in its item.
- The reasoning lives in the item. When the item and the line disagree, the item wins and the line is fixed.
- The date is data here. It says when the decision was made, which a reader needs to judge how much it still binds.

Template: [`../templates/decisions.md`](../templates/decisions.md).

## 7. History lives in version control and the tracker

Nothing is lost by keeping history out of living docs and code, as long as it has a home and a link.

| History | Home | How it is found |
|---|---|---|
| What changed, who, when | Version control (`git log -- <path>`) | The path and the log. |
| Why it changed, the incident, the evidence | The tracker item | The item id, cited from the code. |
| Finished research and old plans | `archive/` | The archive index, and the item that cites it. |

Ids are never renumbered and never reused, so an old citation keeps resolving. A moved document leaves its cited
headings and path stable, or the move rewrites every citation in the same commit
([`layout.md`](./layout.md#keeping-cited-paths-and-headings-stable)).

## 8. A class gets a check, not a patch

When the same problem shows up a second time, it is a class, not a coincidence. Stop patching instances:

1. Find the root cause.
2. Build the fix **by construction**: a check that makes the whole class unable to recur.
3. Say which instances the construction covers, and which it does not.

Existing debt that the check would flag goes in a **ratchet**: a **baseline** (a committed file recording the violations that
exist today) that can only shrink. The check is strict for new code and patient with old code. See
[`ratchets.md`](./ratchets.md).

Every check has a self-test that plants a violation and requires the check to go red, and the wrapper runs it with every
check. A check that has never been seen to fail proves nothing. All the checks run from one **runner** and one list
([`gate-runner.md`](./gate-runner.md)), so no check exists that nobody runs.

## 9. Rules live in the repository

A rule or a procedure that exists only in a chat, in an agent's session, or in a file in someone's home directory is lost
with the session and the person. Write it where the next contributor will read it, and link it from where it applies.

- A rule an agent learned from a correction goes into the entry file or its home doc in the same change, not into a private
  memory that the next agent does not have.
- A procedure ("how to cut a release", "how to run the suite") is a guide under `docs/guides/`, not a message pinned somewhere.
- A tool's configuration that encodes a rule (a check, a hook, a CI file) is committed. Settings that only exist on one
  machine are a hidden dependency: say in the repository what they must be.
- Test: clone the repository into an empty directory with no history of conversations. Can a new contributor, human or agent,
  find every rule that governs a change? If a rule is missing, it lives somewhere it must not.

## How the principles fit together

- A comment cites an item by id (7). The reference check proves the id resolves (8).
- The item files are the source, the index is generated (3), and the index freshness check keeps it honest (8).
- The entry file points to the status page (4, 5), to the decisions index (6) and to the generated catalogue (3).
- Each rule lives once (2), so the entry file stays one screen.
- All of it states the present (1), and the past is one link away (7).
- All of it is in the repository (9), so a clean clone has the rules and the checks that enforce them.
