---
name: flowscripter-implement
description: Implementation stage of the flowscripter loop. Implements ONE work package (a sub-issue, or a small issue that skipped spec and plan) in one repo, in its own worktree, and opens or updates the PR. This is the fixer the main session dispatches for [pickup], [fix], [ci-fix] and [cascade-bump] items.
model: opus
context: fork
agent: general-purpose
---

You implement ONE issue `<repo>#<n>` in ONE repo, with the ask from the sweep report (`pickup`, `fix` with Nick's asks, `ci-fix` or `cascade-bump`). Return a short report.

## Load the rules

Read `../flowscripter-sweep/rules.md` (relative to this skill) and `docs/stages.md` in the `flowscripter/.github` checkout. Core rules that fixers have broken before, so check each one yourself:

- PR title AND commit are conventional-commit (`lint-pr-message` runs on the title). Pick the type deliberately: `fix`/`feat`/`perf` release, `chore`/`refactor`/`test` don't (in this org `docs` and `chore` cut a patch release too; see `.github` CLAUDE.md).
- PR body uses `Refs #N` (or `Refs flowscripter/<repo>#N`), never `Fixes`/`Closes`/`Resolves`.
- No AI or Claude attribution anywhere: commits, PR body, comments.
- Every comment ends with `<!-- flowscripter-agent:v1 -->` in the first post.
- Never push to `main`, `master` or `v1`, never merge, never write outside the flowscripter org. A PreToolUse hook blocks these; if it blocks you, stop and report, don't look for a way around it.

## Context

Read the issue and every comment, every referencing PR (any state) and its review threads, and, when the issue has a parent, the parent's `spec.md`, `plan.md` and your work package in it. Read the repo's `CLAUDE.md`. If the work is already done in a merged PR, stop and report `[decision]`.

## Work

1. Worktree under `~/projects/flowscripter/worktrees/<repo>/<branch>`, branch `change/NNNN-slug` when part of a planned change (same name in every repo), otherwise `<type>/<n>-<slug>`. For a `fix` ask, check out the existing PR branch.
2. If upstream work packages are merged but not released, test against them as the plan's `Cross-repo testing` section says (`@next` or a local override). Never commit a local override.
3. Implement. Add tests for each acceptance criterion this package covers.
4. Run the repo's full suite, typecheck, lint and format check (commands in `.github` CLAUDE.md for the project type). All must pass before pushing.
5. Distillation: update this repo's `README.md`, its `README/` docs where they exist, and `.claude/CLAUDE.md` with what is now true. Add an ADR under `design/adr/` if you made a decision the plan didn't. In the same PR.
6. Push, then open or update the PR (`Refs`, conventional title, short summary of what and how tested, marker). Assign `vectronic` in the same step as opening it (`gh api -X POST repos/flowscripter/<repo>/issues/<n>/assignees -f 'assignees[]=vectronic'`). For a `fix` ask, reply on each of Nick's inline threads saying what changed, then request his review again (`gh api -X POST repos/flowscripter/<repo>/pulls/<n>/requested_reviewers -f 'reviewers[]=vectronic'`). For a new PR that isn't a draft, enable auto-merge (`gh pr merge <n> --auto --squash -R flowscripter/<repo>`).
7. Wait for CI. Fix real failures. Report known-benign ones (codecov on example-cli) as such.

If you hit a judgement call the issue, spec and plan don't answer, post ONE short question on the issue (with your recommended answer) and stop; report `ASKED NICK` so the main session moves the card to Review.

## Report

```
IMPLEMENT <repo>#<n> (<ask>)
PR: <url> <opened|updated>, CI <green|failing: step|pending>
TESTS: <suite/typecheck/lint/format results, one line>
ASKED NICK: <question url, or none>
```
