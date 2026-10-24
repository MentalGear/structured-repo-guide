<!--
Template. Copy this file to the root of your repository as SECURITY.md and replace every <ANGLE-BRACKET VALUE>.
Delete this comment. Guidance: security/vulnerability-reporting.md of structured-repo-guide.

Turn the playbook path in the last section into a real Markdown link to your playbook file, written as a relative path such
as ./docs/supply-chain.md. The controls-table check requires that SECURITY.md contains that path.
-->

# Security policy

## Reporting a vulnerability

Please report a suspected vulnerability **privately**, not in a public issue or pull request.

Use <PRIVATE CHANNEL: for GitHub, "GitHub's private vulnerability reporting for this repository: open the Security tab of
<OWNER/REPOSITORY> and choose **Report a vulnerability**" (a private advisory visible only to you and the maintainers); or
"email <security@your-domain>">. Include what is affected (<a component, a package, the CLI, a dependency, the site>), how to
reproduce it, and the version or commit.

If <the Report a vulnerability button is not offered>, private reporting is not switched on yet: open a public issue that says
only that you have a security report and asks for a private channel, and put **no details** in it.

## What to expect

- We acknowledge a report within <N> days.
- We tell you whether we can reproduce it, and how serious we think it is, once we know.
- We fix it on the timeline the severity and the work need, keep you informed, and publish an advisory when the fix is
  available. If you need a deadline, <90 days> is our default; tell us in your first message.
- We credit you in the advisory unless you ask us not to.

<DELETE what you cannot keep. Do not promise a fix time, a bounty, or legal safe harbour you have not agreed.>

## Supported versions

<There is no tagged release yet; security fixes go to the default branch only.>
<OR a table:>

| Version | Supported |
|---|---|
| <latest release> | yes |
| <older> | no |

## What this covers

<Two or three sentences: what the project is, what its supply-chain defence consists of in plain words, and, in one sentence,
what is not yet covered. Do not put counts here: the table has them.>

The threat model, the full controls table (what each control stops, the script that enforces it, and whether it is enforced,
manual or planned) and what is deliberately out of scope are in `<PATH-TO-YOUR-PLAYBOOK, for example docs/supply-chain.md>`.
