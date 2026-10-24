# Documentation: keep a repository stating only its current state

**What this is for.** A language-agnostic method for keeping documentation and comments true: the docs describe the
repository as it is, history lives in version control and the tracker and is linked by id, and checks make the
rules hold. Use this half when your docs have grown stale, when comments narrate old bugs, when an agent entry file
has become a wall of rules, or when you are starting a repository and want to avoid all of that.

It is a standalone guide. Nothing in it depends on a particular language, framework or project.

## Prerequisites

- `sh` (POSIX) and `awk`, both on every Unix.
- Python 3.8 or newer, standard library only; the scripts are tested on 3.8 to 3.13. (The security half's pin checker reads
  TOML and needs 3.11 or newer.)
- `git`: the adoption path and the cleanup playbook use `git ls-files`, `git grep` and `git mv`, and the runner names the
  commit it ran on. The scripts run without it, and use it when present so that `.gitignore` decides what they scan.
- No network, no package install.

## Words used in this guide

Defined here once, used the same way everywhere. Every other page of this guide uses these words as defined here and links to
this table instead of defining them again.

| Word | Meaning |
|---|---|
| **entry file** | The short file an agent or a new contributor reads first: `AGENTS.md`, `CLAUDE.md` or `CONTRIBUTING.md`, whichever name your tool reads. |
| **check** | One script, `scripts/check-<name>.sh`, that exits non-zero when one rule is broken, and has a `--self-test` that proves it can. |
| **gate**, **runner**, **gate list** | A gate is one line of the runner's list: a check, or a plain command such as `cargo test`. The runner (`scripts/run-gates.sh`) runs every gate; the gate list (`scripts/gates.list`) is the one place that names them. "The runner" is the one command to run before a commit. See [`gate-runner.md`](./gate-runner.md). |
| **baseline**, **ratchet** | A baseline is a committed file that records the violations that exist today. A ratchet is a check that accepts exactly what the baseline records and fails when the baseline could shrink but has not: the debt only goes down. See [`ratchets.md`](./ratchets.md). |
| **item**, **tracker** | An item is one unit of work or one decision's reasoning, a file with an id. The tracker is the directory of items (`docs/backlog/`). |
| **owner** | The person who decides what is deleted, kept or shipped: a maintainer, a team lead, or on a solo project, you. |
| **helper**, **work stream** | A helper is a person or an agent doing one piece of a larger job; a work stream is that piece, with its own set of files that no other stream touches. |

## The method in one paragraph

Write down the current state only. Give every rule one home and link to it. Generate any document that is a function of
something else, and check that it is fresh. Keep a short entry file that only points. Keep one status page and one
decisions index. Put history in version control and in tracker items, and cite items by id from code. When a problem shows
up twice, fix the class with a check, and put existing debt in a baseline that can only shrink. Run every check from one
runner, and keep every rule in the repository.

## Read in this order

| Document | Read it to learn |
|---|---|
| [`principles.md`](./principles.md) | The nine rules everything else applies. Start here. |
| [`layout.md`](./layout.md) | The target docs tree, what goes in each directory, how to keep cited paths and headings stable. |
| [`history-in-comments.md`](./history-in-comments.md) | The archive / link / fold rule for comments, with before and after in six languages, what counts as history, markers for exceptions. |
| [`tracker-as-files.md`](./tracker-as-files.md) | The backlog as one file per item, with front matter, ids that comments cite, and generated open and done indexes. |
| [`generated-docs.md`](./generated-docs.md) | Generating a checks catalogue from the gate list and the script headers, with a freshness check. The same shape for any generated page. |
| [`ratchets.md`](./ratchets.md) | Shrink-only baselines: how a strict check lands in a codebase that already violates it, and how a check proves it can fail. |
| [`gate-runner.md`](./gate-runner.md) | The one runner and the one gate list: exit codes, the guard that no check is left out, reuse, and making the full run affordable. |
| [`cleanup-playbook.md`](./cleanup-playbook.md) | A one-time cleanup of a repository full of historical docs and comments, step by step, with verification. |

Runnable code: [`../examples/documentation/`](../examples/documentation/README.md) and
[`../examples/gate-runner/`](../examples/gate-runner/README.md). Copyable files:
[`../templates/AGENTS.md`](../templates/AGENTS.md), [`../templates/STATUS.md`](../templates/STATUS.md),
[`../templates/backlog-item.md`](../templates/backlog-item.md), [`../templates/decisions.md`](../templates/decisions.md),
[`../templates/history-in-comments.md`](../templates/history-in-comments.md).

## Adopt it in five minutes

Starting point: a git repository with Python 3.8 or newer and a shell. Each step is a command you can run now; the sample under
[`../examples/documentation/sample/`](../examples/documentation/sample/AGENTS.md) shows the result. Commit after step 5. If you
have your own `scripts/check-*.sh`, give each a header and a line in `scripts/gates.list` too, or the runner refuses to run
(that is its job: [`gate-runner.md`](./gate-runner.md)).

**1. Copy the scripts, the runner and the templates.** `GUIDE` is the path of this repository; the same variable is used in
the security half.

```sh
GUIDE=/path/to/structured-repo-guide
mkdir -p scripts/baselines docs/backlog/done docs/guides
cp $GUIDE/examples/documentation/*.py $GUIDE/examples/documentation/check-*.sh scripts/
cp $GUIDE/examples/gate-runner/run-gates.sh $GUIDE/examples/gate-runner/gates.list scripts/
cp $GUIDE/templates/AGENTS.md AGENTS.md     # or CLAUDE.md, CONTRIBUTING.md: the name your tool reads
cp $GUIDE/templates/STATUS.md $GUIDE/templates/decisions.md docs/
cp $GUIDE/templates/history-in-comments.md docs/guides/
cp $GUIDE/examples/documentation/sample/docs/README.md docs/README.md
```

The entry file and the docs map are **examples to adapt**, not finished files. Adapt the map now: drop the row for the archive
(you have none yet) and add a row for the guide you just copied.

```sh
grep -v 'archive/README.md' docs/README.md > docs/README.new && mv docs/README.new docs/README.md
printf '%s\n' '| [`guides/history-in-comments.md`](./guides/history-in-comments.md) | The rule for comments: archive, link, fold. |' >> docs/README.md
```

**2. Write your first item** from [`../templates/backlog-item.md`](../templates/backlog-item.md). The template is ready to run
as item 1: copy it to `docs/backlog/001-<slug>.md` (`NNN-slug.md`: three digits, a hyphen, a few lower-case words), edit
its title and sections, set `updated` to today, delete its comment. Then generate the indexes. `--write` writes **both**
`docs/backlog.md` and `docs/backlog-done.md`.

```sh
cp $GUIDE/templates/backlog-item.md docs/backlog/001-adopt-the-doc-checks.md
python3 -I scripts/backlog_index.py --write       # writes docs/backlog.md and docs/backlog-done.md
python3 -I scripts/backlog_index.py --check       # exit 0: files and indexes agree
```

**3. Freeze today's debt** so it cannot grow. Each command writes a baseline under `scripts/baselines/`.

```sh
sh scripts/check-history-comments.sh --update-baseline    # comment lines that retell history, per file
sh scripts/check-comment-refs.sh --update-baseline        # dead item ids and dead paths cited in comments
sh scripts/check-dated-headings.sh --update-baseline      # dated headings in living docs
sh scripts/check-history-comments.sh                      # exit 0: nothing new
```

**4. Generate the catalogue.** `scripts/gates.list` already lists the eight checks you copied under a `Documentation` group;
add your own checks to it (a check script is described by its header; a plain command by the comment lines above its entry).
Then:

```sh
python3 -I scripts/docs_catalogue.py --write              # writes docs/checks.md from the gate list and the script headers
sh scripts/check-docs-catalogue.sh                        # exit 0: the page is fresh
sh scripts/check-doc-links.sh                             # exit 0: every doc link resolves
sh scripts/check-doc-map.sh                               # exit 0: every doc under docs/ is in the map
```

Add `docs/checks.md` as a row of the map if it is not there (the sample map has it).

**5. Make the entry file and the status page yours, then run the runner.** Open `AGENTS.md`, `docs/STATUS.md` and
`docs/decisions.md`: fill every `<placeholder>`, make each command and link true of your repository, delete the template
comments. That includes the template comment at the top of the copied `docs/guides/history-in-comments.md`:
`check-placeholders` finds a template comment in any Markdown file and fails while one is left.

```sh
sh scripts/check-placeholders.sh                          # exit 0: no placeholder or template comment left
sh scripts/run-gates.sh                                   # the one runner: ends with ALL GREEN, exit 0
```

Commit, and tell your agents to read `AGENTS.md`. From now on a new history comment, a dead citation, a broken link, a doc
nobody linked, a stale catalogue, an index edited by hand or a placeholder left behind turns the runner red. (The `--skip templates` used to check *this*
repository is not part of your commands: its templates' links are relative to the place you copy them to, and yours has no
`templates/` directory to skip.)

For a repository that already has years of docs and comments, continue with
[`cleanup-playbook.md`](./cleanup-playbook.md). To adopt the security half as well, add its checks to the same
`scripts/gates.list` ([`gate-runner.md`](./gate-runner.md#one-runner-for-both-halves)).

## Prove the scripts work

From the root of this repository. Exit 0 and a final `ALL GREEN` mean every self-test went red on its planted violation
and every check is green on the sample:

```sh
sh examples/documentation/run-all.sh
```

The same, piece by piece (every case prints `ok`; the last line says `OK`):

```sh
python3 -I examples/documentation/comment_scan.py --self-test        # history and refs, six languages, citation guard
python3 -I examples/documentation/check_doc_links.py --self-test     # files, anchors, code fences
python3 -I examples/documentation/docs_catalogue.py --self-test      # freshness, thin, no header, list-driven and glob
python3 -I examples/documentation/backlog_index.py --self-test       # front matter, ids, folders, index
python3 -I examples/documentation/doc_hygiene.py --self-test         # placeholders, doc map, dated headings
sh examples/gate-runner/run-gates.sh --self-test                     # exit codes, guards, reuse

S=examples/documentation/sample
sh examples/documentation/check-history-comments.sh --root $S        # OK (2 baselined history lines in 1 files, none new)
sh examples/documentation/check-comment-refs.sh     --root $S        # OK (2 baselined dead references, none new)
sh examples/documentation/check-doc-links.sh        --root $S        # OK
sh examples/documentation/check-docs-catalogue.sh   --root $S        # OK
sh examples/documentation/check-backlog-index.sh    --root $S        # OK
sh examples/documentation/check-placeholders.sh     --root $S        # OK
sh examples/documentation/check-doc-map.sh          --root $S        # OK
sh examples/documentation/check-dated-headings.sh   --root $S        # OK
```

This guide obeys its own rules. Check every link in it, templates excepted (their links are relative to the place you
copy them to, so this flag is for this repository and not for yours):

```sh
python3 -I examples/documentation/check_doc_links.py --skip templates      # run from the repository root
```

## Using it with agents

An agent entry file is the highest-leverage page in the repository, because it is read at the start of every session. The
template [`../templates/AGENTS.md`](../templates/AGENTS.md) holds a screen of rules that apply to every change and pointers
to the rest. Four habits keep agents and contributors aligned with the method:

- Say in the entry file: "read the status page first".
- Say: "run `sh scripts/run-gates.sh` before every commit; green is `ALL GREEN` and exit 0, and a partial run is not a pass".
- Say: "rules and procedures go in this repository, not in a session".
- Say: "comments state the current reason and cite the item; history goes to the item".

The checks do the enforcing, so the rules in the entry file never have to be policed by hand.
