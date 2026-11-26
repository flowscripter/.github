# Flowscripter Board Stages and Commands

Shared by the sweep and the stage skills. The full design is in [agentic-sdlc.md](agentic-sdlc.md).

## Stages

| Status | Meaning | Who moves it out |
|---|---|---|
| Backlog | Raised, not started; or parked by `/park` | main session on pickup |
| Spec | spec.md PR being written or waiting on Nick | sweep, when the spec PR is merged -> Plan |
| Plan | plan.md PR being written or waiting on Nick | sweep, when the plan PR is merged and the split is done -> In Progress |
| In Progress | code work under way (parent: while any sub-issue is open) | main session / sweep -> Review |
| Review | waiting on Nick: code PR ready, or a question asked | sweep, on Nick's command or comment |
| Verification | released; agent self-check posted; Nick tests | Nick closes -> Done, or comments -> In Progress |
| Done | closed | - |

Waiting on Nick inside Spec and Plan doesn't move the card to Review: the open docs PR assigned to him is the signal. The report lists those under WAITING ON NICK.

## Issue Forms

Issues are opened with one of three org issue forms. Each has a required field that serves as the acceptance criteria for the work and for the verification check.

| Form | Use it for | Route | Acceptance criteria |
|---|---|---|---|
| Change (`intent.yml`) | features, behaviour changes, anything that may span several repos | full, unless the routing rules below make it short | Acceptance criteria |
| Bug (`bug.yml`) | something that behaves differently from what it should | short | Expected behaviour |
| Task (`task.yml`) | small, well-understood work in one repo: config, dependencies, docs | short | Done when |

## Routing at pickup

The main session picks the route when it takes a Backlog card:

- **Full** (Backlog -> Spec -> Plan -> In Progress): a Change issue that lists more than one repo, or `repos.yaml` shows the affected repo has dependents that need a code change (not just a bump), or the change is a `feat`.
- **Short** (Backlog -> In Progress): every Bug and Task issue, and a Change issue in one repo with no API change. Also every `ci-fix` card and every sub-issue (its spec and plan are the parent's).
- **System issues** never take the full route: CI failures (`flowscripter-ci-failure` marker, start In Progress), the monthly `flowscripter-security-rescan` issue and other bot proposals (start in Review, as today).

Spec and plan PRs are titled `docs(spec): <slug>` and `docs(plan): <slug>`. They only touch docs-only paths, so merging them runs no build and cuts no release (see [Docs-Only Changes](agentic-sdlc.md#docs-only-changes)).

The pickup comment says which route and why in one line. Nick overrides with `/go` (take the short route, or skip the remaining gates) or `/revise spec` (send it back to Spec).

## Commands in Nick's comments

A command is a line by `vectronic` that starts with the command, on the issue or any referencing PR. Text after it on the same line, and the rest of the comment, is the detail. Commands take precedence over free-form inference. The newest command wins.

| Command | Effect |
|---|---|
| `/approve` | Accept what the agent last proposed in this thread: a bot proposal issue, a recommended answer to a question, a plan posted as a comment. Does not replace merging a spec or plan PR: merge is the gate. |
| `/go` | Start or continue now. On Backlog: pick up, short route. On Spec/Plan: skip remaining gates, go to In Progress. On Review with a question pending: proceed with the recommended answer. |
| `/park` | Move to Backlog, stop all work, don't re-pick. Open agent PRs are converted to draft. A later `/go` resumes. |
| `/revise [spec\|plan\|code] <detail>` | Rework the current artifact (or the named one) per the comment and any inline review comments. Moves the card back to that stage if needed. |

A `vectronic` comment with no command keeps today's rule ("Nick has the last word"): it is feedback on the current stage, the sweep moves the card to the working state for that stage and reports the asks. `Decided with Nick in session` comments authored by `vectronic-claude` count as `/approve` plus the listed decisions.

## Report tags

`[pickup]`, `[spec]`, `[plan]`, `[split]`, `[fix]`, `[reply]`, `[cascade-bump]`, `[verify]`, `[decision]`, `[ci-fix]`.

| Tag | Main session runs |
|---|---|
| `spec` | `flowscripter-spec` |
| `plan` | `flowscripter-plan` mode `write` |
| `split` | `flowscripter-plan` mode `split` |
| `pickup`, `fix`, `ci-fix`, `cascade-bump` | `flowscripter-implement` (after choosing the route, for `pickup`) |
| `verify` | `flowscripter-verify` |
| `reply`, `decision` | itself (or an interview, for a decision) |
