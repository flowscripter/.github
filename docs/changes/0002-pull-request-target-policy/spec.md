# Keep PR Title Checks Running After the pull_request_target Default Policy

Refs flowscripter/.github#82

## Problem

From 2026-12-02 GitHub blocks workflows triggered by `pull_request_target` in public repositories unless an Actions policy allows the event. The block is by event: it applies even though our workflow never checks out PR code. Until then, runs log a "Workflow execution policy warning (evaluate mode)".

`lint-pr-message.yml` runs on `pull_request_target` in 28 repos: `.github` (the reusable workflow and its own trigger), the `workflow-templates/lint-pr-message.yml` starter, and the caller copied into every other repo. Its `lint` job is the required check `call-lint-pr-message / lint`. If the event is blocked, the check never reports and no PR can merge. No other workflow in the org uses `pull_request_target`.

There are two fixes:

- **Org Actions policy**: an org owner adds a policy that allows `pull_request_target`. No workflow files change.
- **Workflow change**: switch the trigger to `pull_request` in the reusable workflow, the template and all 27 callers. GitHub recommends this when no secrets are needed, and these jobs need only a read token. The trade-off is that `pull_request` runs the workflow file from the PR itself, so a PR could edit its own caller to weaken the check. With `pull_request_target`, the workflow always comes from the base branch.

Both fixes need Nick. The agent's token can't change org settings or push to `.github/workflows/` (ADR 0001).

## Acceptance criteria

1. A `lint-pr-message` run on a PR opened after the change, in any of the 28 repos, logs no "Workflow execution policy warning".
2. (proposed) After 2026-12-02, the required check `call-lint-pr-message / lint` still runs and reports on new PRs in every affected repo, both from same-repo branches and from forks.
3. (proposed) A PR whose title isn't in conventional-commit format still fails `call-lint-pr-message / lint`. The `agent-config` job still fails a PR that changes disallowed agent-config paths.
4. (proposed) A repo created from a `template-*` repo, or from `workflow-templates/lint-pr-message.yml`, gets criteria 1-3 without any per-repo settings step.
5. (proposed) The chosen approach is recorded in `.github/.claude/CLAUDE.md` (the PR title lint bullet), and in an org ADR if it is the policy route.

## Non-goals

- Changing what the PR title lint or the `agent-config` check enforces.
- Renaming the required check, or changing rulesets.
- Repos without `lint-pr-message.yml` (`docs`, `homebrew-tap`, `winget-pkgs`).

## Affected repos

The repo graph lists no package edges for `.github`. Consumers use it through `@v1` workflow refs (ADR 0003), not packages, so the affected set comes from a search of the org for `pull_request_target`:

- `.github`: owns the reusable `lint-pr-message.yml`, which also triggers on `pull_request_target` for its own PRs, and the `workflow-templates/lint-pr-message.yml` starter.
- Policy route: the org's Actions settings only. No repo changes, apart from the docs in `.github`.
- Workflow route: the caller `.github/workflows/lint-pr-message.yml` in each of these 27 repos: bun-ffi-loader, cli, dynamic-cli-framework, dynamic-cli-framework-api, dynamic-plugin-framework, example-cli, example-cli-plugin, example-host-application, example-plugin, example-plugin-api, flowscripter-io-cli, flowscripter-io-cli-hash-native, io-gateway-http, io-plugin-filesystem, io-plugin-filesystem-native, io-plugin-http, io-plugin-s3, pluggable-io-framework, pluggable-io-framework-api, plugin-api, runtime, template-bun-executable, template-bun-library, template-bun-rust-library, template-bun-wasm-rust-library, template-bun-webapp, template-rust-library. Nick would push all 27.

## Open questions

1. **Policy or workflow change?** Recommended: the org Actions policy, scoped to `pull_request_target` for the `lint-pr-message.yml` workflows, or to all repos if the UI can't scope by workflow. It is one settings change Nick can make before 2026-12-02. It needs no pushes to 27 repos, and it keeps the base-branch workflow that makes `agent-config` hard to tamper with. If it is later revisited, the workflow route is the fallback.
2. **Does an allow policy clear the evaluate-mode warning (criterion 1)?** The GitHub docs say only that a configured policy replaces the default. Recommended: Nick applies the policy, then the agent opens a test PR in one repo and checks the run log. If the warning persists, fall back to the workflow route and tell Nick before 2026-12-02.
