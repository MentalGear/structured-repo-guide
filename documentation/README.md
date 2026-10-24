# Documentation: keep a repository stating only its current state

**What this is for.** A language-agnostic method for keeping documentation and comments true: the docs describe the
repository as it is, history lives in version control and the tracker and is linked by id, and checks make the
rules hold. Use this half when your docs have grown stale, when comments narrate old bugs, when an agent entry file
has become a wall of rules, or when you are starting a repository and want to avoid all of that.

It is a standalone guide. Nothing in it depends on a particular language, framework or project. The scripts need only
`sh` and Python 3 (standard library).

## The method in one paragraph

Write down the current state only. Give every rule one home and link to it. Generate any document that is a function of
something else, and check that it is fresh. Keep a short entry file that only points. Keep one status page and one
decisions index. Put history in version control and in tracker items, and cite items by id from code. When a problem shows
up twice, fix the class with a check, and put existing debt in a baseline that can only shrink.

## Read in this order

| Document | Read it to learn |
|---|---|
| [`principles.md`](./principles.md) | The eight rules everything else applies. Start here. |
| [`layout.md`](./layout.md) | The target docs tree, what goes in each directory, how to keep cited paths and headings stable. |
| [`history-in-comments.md`](./history-in-comments.md) | The archive / link / fold rule for comments, with before and after in six languages, what counts as history, markers for exceptions. |
| [`tracker-as-files.md`](./tracker-as-files.md) | The backlog as one file per item, with front matter, ids that comments cite, and generated open and done indexes. |
| [`generated-docs.md`](./generated-docs.md) | Generating a checks catalogue from script headers, with a freshness check. The same shape for any generated page. |
| [`ratchets.md`](./ratchets.md) | Shrink-only baselines: how a strict check lands in a codebase that already violates it. |
| [`cleanup-playbook.md`](./cleanup-playbook.md) | A one-time cleanup of a repository full of historical docs and comments, step by step, with verification. |

Runnable code: [`../examples/documentation/`](../examples/documentation/README.md). Copyable files:
[`../templates/AGENTS.md`](../templates/AGENTS.md), [`../templates/STATUS.md`](../templates/STATUS.md),
[`../templates/backlog-item.md`](../templates/backlog-item.md), [`../templates/decisions.md`](../templates/decisions.md).

## Adopt it in five minutes

Starting point: a repository with a `scripts/` directory and Python 3. Each step is a command you can run now. Commit
after step 5.

**1. Copy the scripts and templates.**

```sh
G=/path/to/structured-repo-guide        # this repository
cp $G/examples/documentation/*.py $G/examples/documentation/check-*.sh scripts/
mkdir -p docs/backlog/done scripts/baselines
cp $G/templates/AGENTS.md AGENTS.md     # or CLAUDE.md, CONTRIBUTING.md: the name your tool reads
cp $G/templates/STATUS.md $G/templates/decisions.md docs/
cp $G/examples/documentation/sample/docs/README.md docs/README.md   # the docs map: edit its rows to match your docs
```

**2. Write your first item** from [`../templates/backlog-item.md`](../templates/backlog-item.md) as
`docs/backlog/001-<slug>.md`: fill the front matter and the three sections, then generate the indexes.

```sh
python3 -I scripts/backlog_index.py --write       # writes docs/backlog.md and docs/backlog-done.md
python3 -I scripts/backlog_index.py --check       # exit 0: files and indexes agree
```

**3. Freeze today's debt** so it cannot grow. Both commands write a baseline under `scripts/baselines/`.

```sh
sh scripts/check-history-comments.sh --update-baseline    # comment lines that retell history, per file
sh scripts/check-comment-refs.sh --update-baseline        # dead item ids and dead paths cited in comments
sh scripts/check-history-comments.sh                      # exit 0: nothing new
```

**4. Give each check script a header and generate the catalogue.** The first paragraph of the header comment is the
entry (see [`generated-docs.md`](./generated-docs.md#script-headers)).

```sh
python3 -I scripts/docs_catalogue.py --write              # writes docs/checks.md from scripts/check-*
sh scripts/check-docs-catalogue.sh                        # exit 0: the page is fresh
sh scripts/check-doc-links.sh --skip templates            # exit 0: every doc link resolves
```

**5. Run them from your one entry point.** Add these lines wherever your project runs its checks:

```sh
sh scripts/check-history-comments.sh
sh scripts/check-comment-refs.sh
sh scripts/check-doc-links.sh --skip templates
sh scripts/check-docs-catalogue.sh
sh scripts/check-backlog-index.sh
```

Then edit `AGENTS.md` and `docs/STATUS.md` (fill the placeholders, delete the template comments), commit, and tell your
agents to read `AGENTS.md`. From now on a new history comment, a dead citation, a broken link, a stale catalogue or an
index edited by hand turns the run red.

For a repository that already has years of docs and comments, continue with
[`cleanup-playbook.md`](./cleanup-playbook.md).

## Prove the scripts work

From the root of this repository. Exit 0 and a final `ALL GREEN` mean every self-test went red on its planted violation
and every check is green on the sample:

```sh
sh examples/documentation/run-all.sh
```

The same, piece by piece:

```sh
python3 -I examples/documentation/comment_scan.py --self-test        # 43 cases: history and refs, six languages
python3 -I examples/documentation/check_doc_links.py --self-test     # 12 cases: files, anchors, code fences
python3 -I examples/documentation/docs_catalogue.py --self-test      # 9 cases: freshness, thin, no header
python3 -I examples/documentation/backlog_index.py --self-test       # 14 cases: front matter, ids, folders, index

S=examples/documentation/sample
sh examples/documentation/check-history-comments.sh --root $S        # OK (2 baselined history lines in 1 files, none new)
sh examples/documentation/check-comment-refs.sh     --root $S        # OK (2 baselined dead references, none new)
sh examples/documentation/check-doc-links.sh        --root $S        # OK
sh examples/documentation/check-docs-catalogue.sh   --root $S        # OK
sh examples/documentation/check-backlog-index.sh    --root $S        # OK
```

This guide obeys its own rules. Check every link in it, templates excepted (their links are relative to the place you
copy them to):

```sh
python3 -I examples/documentation/check_doc_links.py --skip templates      # run from the repository root
```

## Using it with agents

An agent entry file is the highest-leverage page in the repository, because it is read at the start of every session. The
template [`../templates/AGENTS.md`](../templates/AGENTS.md) holds a screen of rules that apply to every change and pointers
to the rest. Three habits keep agents and contributors aligned with the method:

- Say in the entry file: "read the status page first".
- Say: "run the one entry point before every commit; green is `ALL GREEN` and exit 0".
- Say: "comments state the current reason and cite the item; history goes to the item".

The checks do the enforcing, so the rules in the entry file never have to be policed by hand.
