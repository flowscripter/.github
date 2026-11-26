# 0003: Consumers Use the `v1` Branch of the Shared Workflows

- **Status:** Accepted
- **Date:** 2026-11-25 (recording a decision already in place)

## Context

Every repo calls the reusable workflows and composite actions in this repo. Pinning each consumer to a tag or SHA would mean a bump PR in every repo for every shared change.

## Decision

- Consumers reference `flowscripter/.github/...@v1`, which is a branch, not a tag.
- The `update-v1` workflow fast-forwards `v1` to `main` on every push to `main`.
- A ruleset lets only org owners update, delete or force-push `v1`, and lets only org owners create tags in this repo, so a `v1` tag can't shadow the branch.
- Third-party actions used inside the shared workflows are pinned to commit SHAs.

## Consequences

- A merge to `main` here reaches every repo at once, with no promotion gate. Test risky changes from a branch ref (`@<branch>`) in a template repo first.
- To roll back, an org owner runs `git push origin <good-sha>:v1 --force`.
- A major breaking change would need a `v2` branch, and a migration of the consumers.
