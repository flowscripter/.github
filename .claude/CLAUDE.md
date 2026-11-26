# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is the `flowscripter/.github` shared repository. It provides reusable GitHub Actions composite actions and workflow templates consumed across all Flowscripter organization repositories via `uses: flowscripter/.github/actions/<name>@v1` and `workflow_call`.

## Structure

- `actions/` - Composite actions (referenced by workflows in consumer repos)
- `.github/workflows/` - Reusable workflows (triggered via `workflow_call` from consumer repos)
- `workflow-templates/` - Starter templates copied into new repos; paired `.yml` + `.properties.json` files
- `.github/ISSUE_TEMPLATE/` - Issue templates

## Project Types Supported

Each project type has a corresponding check action, test action, and release workflow:

| Type | Check Action | Test Action | Release Workflow |
|------|-------------|-------------|-----------------|
| Bun library | `check-bun-source` | `run-bun-tests` | `release-bun-library` |
| Bun executable | `check-bun-source` | `run-bun-tests` + `run-bun-executable-tests` | `release-bun-executable` |
| Bun webapp | `check-bun-source` | `run-bun-tests` | `release-bun-webapp` |
| Rust library | `check-rust-source` | `run-rust-tests` | `release-rust-library` |
| Bun + Rust FFI library | `check-bun-rust-source` | `run-bun-rust-tests` | `release-bun-rust-library` |
| Bun + Rust WASM library | `check-bun-wasm-rust-source` | `run-bun-wasm-rust-tests` | `release-bun-wasm-rust-library` |

## Key Tooling Conventions

**TypeScript/Bun:**
- Lint: `bunx oxlint index.ts src/ tests/`
- Format check: `bunx oxfmt --check`
- Format fix: `bunx oxfmt`
- Tests: `bun test`
- Coverage: `bun test --coverage --coverage-reporter=lcov > coverage.lcov`
- Docs: `bunx typedoc --readme none index.ts`
- Compile executable: `bun build index.ts --compile --outfile <name>`
- Bundle webapp: `bun run build`

**Rust:**
- Lint: `cargo clippy` (nightly)
- Format check: `cargo fmt -- --check`
- Tests: `cargo test` (nightly)
- Audit: `cargo install cargo-audit && cargo audit`
- Coverage: grcov with `RUSTFLAGS=-Cinstrument-coverage` and `llvm-tools-preview`
- WASM build: `wasm-pack build --target web --no-pack`

**Releases:** All release workflows use `semantic-release` with `conventionalcommits`. Both `docs` and `chore` commit types trigger a `patch` release. The `.releaserc` config is generated inline in the workflow at runtime. Releases require a `PUSH_TO_MAIN_TOKEN` secret; `CARGO_REGISTRY_TOKEN` is needed for Rust crate publishing. `semantic-release-rust` version `1.0.0-alpha.8` is pinned for Rust releases.

## Release Artifact Targets

- **Bun executable:** Linux x64/arm64 (zip+sha256), Windows x64/arm64 (signed zip+sha256), macOS aarch64 (signed+notarized zip+sha256). Also updates Homebrew tap and Winget package.
- **Bun + Rust FFI library:** Linux x64/arm64 (.so), Windows x64/arm64 (signed .dll), macOS (.dylib, signed+notarized). The `ffiLibBaseUri` field in `package.json` is updated to point to the release download URL.

## Executable Functional Tests

Bun executables use Python Behave for functional/BDD tests (`functional_tests/` directory with `pip-requirements.txt`). The executable is compiled to `functional_tests/executable` and the path is set via `EXECUTABLE` env var.

## Webapp Functional Tests

Bun webapps use Python Behave with Firefox + geckodriver for browser-based functional tests.

## Code Signing

- **Windows:** `skymatic/code-sign-action@v1` with `WINDOWS_CODESIGN_CERTIFICATE_P12_BASE64`, `WINDOWS_CODESIGN_CERTIFICATE_PASSWORD`, `WINDOWS_CODESIGN_CERTIFICATE_SHA1` secrets.
- **macOS:** `indygreg/apple-code-sign-action@v1` with notarization via App Store Connect API. Secrets: `APPLE_CODESIGN_CERTIFICATE_P12_BASE64`, `APPLE_CODESIGN_CERTIFICATE_PASSWORD`, `APPLE_APP_STORE_CONNECT_KEY_PEM`, `APPLE_APP_STORE_CONNECT_API_KEY_ID`, `APPLE_APP_STORE_CONNECT_API_ISSUER_UUID`.

## Node.js Setup in Release Workflows

All release workflows install both Bun and Node.js (`lts/*`) because `semantic-release` checks for a Node version even though Bun is used as the runtime.

## Maintenance Automation

- **Default branch:** `main` (renamed from `master`). Consumers reference `@v1`, which is a branch, not a tag.
- **`v1` promotion:** `.github/workflows/update-v1.yml` fast-forwards `v1` to `main` on every push to `main` (`git push origin HEAD:refs/heads/v1`, no force). It authenticates with `PUSH_TO_MAIN_TOKEN` because `GITHUB_TOKEN` cannot update refs that touch `.github/workflows`. There are no pre-promotion gates, so a merge here reaches every consumer immediately. Rollback: `git push origin <good-sha>:v1 --force`.
- **Dependabot:** `.github/dependabot.yml` bumps third-party actions monthly (`/` and `/actions/*`), one PR per action, majors included, commit prefix `chore`.
- **PR title lint:** `.github/workflows/lint-pr-message.yml` is both the reusable workflow (`workflow_call`) and runs on PRs to this repo (`pull_request_target`), so PR titles must be conventional-commit format.
- **Webapp tests:** `run-bun-webapp-tests` uses the Firefox and geckodriver preinstalled on GitHub-hosted runners (`$GECKOWEBDRIVER` is appended to `PATH`); there is no setup-firefox or setup-geckodriver step. `windows-11-arm` is part of the webapp PR matrix.
- **actionlint gate:** `.github/workflows/actionlint.yml` installs the latest actionlint via its download script (no version pin, nothing to bump) and runs it on every PR with no path filter, so it can be a required check named `actionlint`. It does not lint `actions/*/action.yml`.
- **Repo settings tooling:** `scripts/repo-settings.py` (`audit`, `apply`, `new`) with `scripts/repo-types.json` standardises repo options, the `main` ruleset and required checks per project type for all non-archived flowscripter repos (ARM jobs are required checks). `.github/workflows/audit-repo-settings.yml` runs `audit` weekly with the org secret `AUDIT_REPO_TOKEN` (read-only fine-grained PAT; repo merge options are not visible to it, so those are only audited locally with a push-capable token). `apply` and `new` need admin rights (run as `vectronic`, not the machine account). See the `new-flowscripter-repo` skill. `homebrew-tap` is a deliberate audit exception: release-bun-executable pushes formula updates straight to its default branch with `PUSH_TO_MAIN_TOKEN` (no PR), so do not give it a PR ruleset.
- **Agentic workflow:** the design is in `docs/agentic-sdlc.md`, stages, routing, commands and issue forms are in `docs/stages.md`, and the temporary rollout plan is in `docs/agentic-sdlc-rollout.md`. The loop skills and `rules.md` live in `.claude/skills/`; the workspace `.claude/skills` is a symlink to this directory, so this checkout must stay on `main` (branch work goes in worktrees under `~/projects/flowscripter/worktrees/.github/`). The hooks are in `scripts/hooks/` (`guard-gh.py`, with tests in `test_guard_gh.py`, and `worktree.py`). The sweep CLI is `scripts/sweep.py`. `.gitignore` ignores `.claude/*` except `CLAUDE.md` and `skills/`. Shared workflows must keep their required check names (see `scripts/repo-types.json`).
- **Issue forms:** `.github/ISSUE_TEMPLATE/` holds `intent.yml` (Change), `bug.yml` and `task.yml`. No repo has its own templates, so these apply org-wide.
