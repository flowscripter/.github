# 0001: Agentic Development Workflow

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

Most work on the flowscripter repos is done by a local Claude Code agent acting as the machine account `vectronic-claude`. The repos are public, so issues, comments and pull requests from anyone can reach the agent. Nick needs to approve every change and to keep an audit trail, without driving each step himself.

## Decision

- Work flows from an issue, through a spec and plan when needed, to implementation, release and verification, as described in [agentic-sdlc.md](../agentic-sdlc.md) and [stages.md](../stages.md).
- Nick approves by merging. The `main` ruleset requires one approval. It dismisses that approval when later commits change the PR's diff, and keeps it when the branch is updated from `main`. Org owners can always bypass it, so their release tokens and their own PRs keep working.
- The agent's token is fine-grained, limited to the flowscripter org, and has no workflow-file, administration or secrets permission. A local `PreToolUse` hook catches merges, default-branch pushes and writes outside the org before they reach GitHub.
- Only Nick's comments are instructions. Markers count only on text authored by `vectronic-claude`.
- Agent configuration other than `CLAUDE.md` and `.claude/skills/` is never committed, and only Nick or the agent may change agent instructions. The `agent-config` check enforces both.

## Consequences

- No change reaches `main`, `v1` or the Homebrew tap without an org owner.
- The agent can't fix workflow files itself. It prepares the change on a local branch, and Nick pushes it.
- Dependency-update PRs need Nick's approval before auto-merge completes.
