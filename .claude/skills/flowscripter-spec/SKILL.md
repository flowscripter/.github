---
name: flowscripter-spec
description: Spec stage of the flowscripter loop. For one intent issue, writes or revises docs/changes/NNNN-slug/spec.md in the home repo as a docs-only PR and keeps the pinned spec comment on the issue current. Invoked by the main session for a [spec] item from the sweep report.
model: opus
context: fork
agent: general-purpose
---

You handle the Spec stage for ONE issue, given as `<repo>#<n>` plus the sweep's one-line ask. Return a short report (format at the end).

## Load the rules

Read `../flowscripter-sweep/rules.md` (relative to this skill) and `docs/stages.md` in the `flowscripter/.github` checkout. The trust, PR and commit rules there all apply.

## Inputs to read first

1. The issue body (Nick's intent, from the org issue form: What, Why, Constraints / non-goals, Acceptance criteria, Repos likely affected). Never edit the issue body.
2. All issue comments and every PR that references the issue, any state, with their threads. If a referencing PR already implements the change, stop and report `[decision]`: never spec work that exists.
3. The home repo's `CLAUDE.md`, `docs/architecture.md`, `docs/adr/`, and the org ADRs and `repos.yaml` in `flowscripter/.github`. Don't reopen a decision an ADR records; cite it.

## Home repo

The repo the issue lives in, unless the issue lists several repos, in which case the spec still goes in the issue's repo (the parent). `NNNN` is the next free 4-digit number in that repo's `docs/changes/`; `slug` is 2-4 kebab-case words from the title. Branch: `change/NNNN-slug` (the same branch name is reused in every repo for this change).

## Write the spec

`docs/changes/NNNN-slug/spec.md`, sections in this order:

- `# <title>` and a `Refs <repo>#<n>` line
- `## Problem` (from What and Why, in your words, short)
- `## Acceptance criteria` (numbered, each one observable and testable; take Nick's, sharpen wording, never drop one; add missing ones marked `(proposed)`)
- `## Non-goals`
- `## Affected repos` (from `repos.yaml` edges, not just the issue's guess; say why each is affected)
- `## Open questions` (only real ones; each with a recommended answer)

No implementation detail beyond what an acceptance criterion needs; that is the plan's job.

## Publish

- Open a docs-only PR in the home repo: title `docs(spec): <slug>`, body `Refs #<n>` plus a 3-line summary and the marker. Assign `vectronic`. Merging it is the spec approval gate.
- Create or edit in place the ONE pinned comment on the issue that starts with `<!-- flowscripter-spec:v1 -->`: stage (Spec, PR open), summary, the acceptance criteria, links to the spec file on the PR branch and the PR, full spec text in `<details>`. End with `<!-- flowscripter-agent:v1 -->`. Find it by the marker; never post a second one.

## Revising (`/revise` or free-form feedback from Nick)

Read every `vectronic` comment and inline review comment on the spec PR newer than our last reply. Address every ask, push to the same branch, reply on each inline thread saying what changed, and update the pinned comment. If an ask conflicts with an ADR, reply quoting the ADR and ask, instead of changing the spec.

## You don't

Merge, move cards (the main session does), write a plan, create sub-issues, or touch code.

## Report

```
SPEC <repo>#<n>
PR: <url> (<opened|updated>)
PINNED: <comment url>
ASKED NICK: <open questions, or none>
NEXT: wait for merge (Spec -> Plan)
```
