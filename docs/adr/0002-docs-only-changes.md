# 0002: Docs-Only Changes Skip Builds and Releases

- **Status:** Proposed (accepted once the docs-only gate is merged)
- **Date:** 2026-11-25

## Context

Every repo's release workflow runs the full check and test matrix on each push to `main`, and in this org `docs` and `chore` commits cut a patch release. Specs, plans, ADRs and agent context are committed as PRs, so without an exception every one of them would publish a version with no code change and start cascade bumps.

## Decision

A change is docs-only when every changed file matches `design/**`, `.claude/**` or `CLAUDE.md`. Per-repo specs, plans and ADRs live in `design/`, because `docs/` is the gitignored typedoc output. For a docs-only change, the shared validation workflows skip their build and test steps but still report every required check, and the shared release workflows skip all their jobs.

## Consequences

- Spec and plan PRs merge without building, tagging or publishing anything.
- A skipped docs commit appears in the notes of the next real release, and never raises it above patch.
- Any other file in the PR (including `README.md` or other `docs/` files) makes the change a normal one.
