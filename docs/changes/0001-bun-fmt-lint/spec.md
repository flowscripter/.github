# Use Bun's Built-in Formatter and Linter Instead of oxfmt and oxlint

Refs flowscripter/.github#79

## Problem

Every bun repo formats with oxfmt and lints with oxlint, run through `bunx` from the shared check actions, with both pinned as dev dependencies in each repo. Bun now has its own formatter (`bun fmt`) and linter (`bun lint`), so the two extra tools and their dependencies are no longer needed. Switching to Bun's own tools leaves one toolchain to keep current, and makes the workflows, READMEs and dependencies across the org simpler.

What was found while writing this spec:

- `bun fmt` first shipped in Bun 1.4.4 (https://bun.com/blog/bun-v1.4.4). It formats TOML too, so it can replace `bunx oxfmt Cargo.toml` in the release workflows.
- `bun lint` is documented (https://bun.com/docs/lint), but no stable release has it yet. The latest stable, 1.4.5, answers `bun lint` with `Script not found "lint"`. The canary `1.4.5-canary.20261126.1` reports version 1.4.6 and has `bun lint`.
- `bun lint` honours both `oxlint-disable` and `eslint-disable` comments. By default it exits 0 when it finds only warnings; `--max-warnings=0` makes warnings fail too.
- While `oxlint` or `oxfmt` is in `package.json`, `bun lint` and `bun fmt` hand off to them. They switch to Bun's own rules and style only once both dependencies are removed.
- Bun's default style wraps at 80 columns, where oxfmt wrapped at 100, so the first run reformats most files.

### Current Findings

Measured on each repo's `main` (2026-11-28) with Bun `1.4.6-canary.1`, after removing `oxfmt` and `oxlint` from `package.json`, using the paths the check actions lint today (`index.ts src/ tests/`). oxlint reports 0 errors and 0 warnings in every repo today.

| Repo | `bun lint` errors | `bun lint` warnings | Files reformatted | Lines (+/-) |
| --- | ---: | ---: | ---: | ---: |
| `dynamic-cli-framework` | 21 | 13 | 213 | +7556 / -2392 |
| `dynamic-plugin-framework` | 10 | 2 | 36 | +984 / -329 |
| `plugin-api` | 0 | 1 | 2 | +52 / -16 |
| `io-plugin-s3` | 0 | 1 | 28 | +434 / -137 |
| `cli` | 1 | 0 | 0 | 0 |
| 5 `template-bun-*` repos | 1 each | 0 | 0-2 each | +30 / -8 in all |
| 16 other bun repos | 0 | 0 | 0-48 each | +3895 / -1170 in all |
| **Total (26 repos)** | **37** | **17** | **546** | **+12951 / -4052** |

- All 37 errors are `bun:test/valid-expect`. In the templates and `cli` it's `expect(true);` with no matcher. In the two frameworks it's `expect(promise).rejects.toThrow(...)` without `await`, so those assertions don't run today.
- The 17 warnings: `no-useless-assignment` (6), `prefer-const` (4), `preserve-caught-error` (4), `@typescript-eslint/no-explicit-any` (2), `@typescript-eslint/no-empty-object-type` (1).
- Estimated work to reach 0 errors and 0 warnings: 54 small, local edits in 10 repos, most of them one line (`await`, a real matcher, `const`, `{ cause }`, a narrower type). `bun lint` marks none as auto-fixable. About one PR's work in each of the two frameworks and a few lines elsewhere. Fixing the `valid-expect` errors turns on assertions that never ran, so a few tests could start failing and need a real fix; that's the main uncertainty in the estimate.
- The reformat is mechanical (`bun fmt`), but large: half of it is in `dynamic-cli-framework`.

## Acceptance Criteria

1. No file in any non-archived flowscripter repo refers to oxfmt or oxlint. That covers workflows, actions, `package.json`, `bun.lock`, config files, source comments (`oxlint-disable` directives included), READMEs, `README/` docs, `CLAUDE.md` files and the `.github` docs. Checked with an org-wide search for `oxfmt` and `oxlint` on each repo's `main`.
2. The shared check actions (`check-bun-source`, `check-bun-rust-source`, `check-bun-wasm-rust-source`) run `bun fmt --check` and `bun lint --max-warnings=0`. The step fails when a file needs formatting, or `bun lint` reports any error or any warning. Checked with throwaway branches in a template repo: one with an unformatted file, one with a lint error and one with only a lint warning. Each fails.
3. The shared release workflows that format `Cargo.toml` (`release-bun-rust-library`, `release-rust-library`) use `bun fmt` instead of `bunx oxfmt`, and a release from each still succeeds.
4. The minimum Bun version is 1.4.6, the first stable release with `bun lint`. No work starts until 1.4.6 is released, and canary Bun is never used in CI. Every workflow and action that runs `bun fmt` or `bun lint` installs Bun 1.4.6 or newer. If the installed Bun is older, the job fails with a message that names 1.4.6.
5. The check names the rulesets require are unchanged: `scripts/repo-settings.py audit` reports no drift in required checks.
6. Every bun repo's PR validation workflow fails on a formatting issue, a lint error or a lint warning, and the failing step fails a required check, so the PR can't be merged. Checked on the PRs from criterion 2.
7. Every bun repo's validation and check jobs pass on `main` after the switch, with 0 lint errors and 0 lint warnings. The 37 errors and 17 warnings in Current Findings are fixed in code, not disabled. A disable comment is allowed only with a reason on the same line, and Nick approves each one in review.
8. `oxfmt` and `oxlint` are removed from the dev dependencies of every bun repo, and any oxfmt or oxlint config file is deleted.
9. Every bun repo uses Bun's default formatter style and default lint rules: no `[fmt]` or `[lint]` section in `bunfig.toml`, and no other formatter or linter config.
10. In each repo, the reformatting from the switch lands in its own commit, with no behaviour or config changes in it (proposed: a `style:` commit, or a separate `style:` PR). The lint fixes land in a separate commit from the reformat.
11. The `.github` docs and `.claude/CLAUDE.md` (Key Tooling Conventions) give the new lint (`bun lint --max-warnings=0`), format check (`bun fmt --check`) and format fix (`bun fmt`) commands.
12. Each bun repo's development docs (`README.md`, or `README/development.md` where it exists) say how to format, check formatting and lint with Bun, and that warnings fail the check.
13. A local git hook runs `bun fmt` and `bun lint --max-warnings=0` on the staged files before each commit, and no local git hook refers to oxfmt or oxlint. The only one today is the global `~/.config/git/hooks/pre-push`.
14. The loop rules (`.claude/skills/flowscripter-sweep/rules.md`), the `flowscripter-implement` skill and `.github` `.claude/CLAUDE.md` tell Claude to run `bun fmt` and then `bun lint --max-warnings=0` in a bun repo before every commit, not only before a push, and to commit only when both are clean. The rule says this holds whether or not a git hook is installed, and whether or not the commit skips hooks.
15. (proposed) The Claude Code guard hook (`~/.claude/hooks/guard-gh.py`) enforces criterion 14: it blocks a `git commit` by Claude in a bun repo when `bun fmt --check` or `bun lint --max-warnings=0` fails, and the block message names the failing command. Checked by trying to commit an unformatted file and a file with a lint warning.
16. (proposed) No bun repo's check job on `main` fails during the rollout. Shared actions and repos are changed in an order that keeps every `main` green.

## Non-goals

- Changing Rust formatting and linting (`cargo fmt`, `cargo clippy`).
- Renaming or restructuring the check jobs, or changing the rulesets.
- Turning on lint rules or type-aware linting beyond what `bun lint` does by default, or tuning the default formatter style.
- Archived repos (for example `mpeg-sdl-tool`).
- Behaviour changes in any repo's code.

## Affected Repos

Repos are listed from the current repo graph and from a search of local clones of `main` for `oxfmt` and `oxlint`. No package API changes, so the dependency edges matter only for the release order. They don't create code changes in dependents.

- **`.github`** (home repo): the three `check-bun-*` actions, the `release-bun-rust-library` and `release-rust-library` workflows (`bunx oxfmt Cargo.toml`), `.claude/CLAUDE.md`, the loop rules and `flowscripter-implement` skill (criterion 14), and the Bun version guard in the workflows and actions. The workflow-file changes can't be pushed with the machine token, so Nick pushes them (ADR 0001). Consumers pick up a merge here immediately through `v1` (ADR 0003), so this repo goes first, and its change has to keep repos that haven't switched yet passing (criterion 13).
- **Templates**: `template-bun-library`, `template-bun-executable`, `template-bun-webapp`, `template-bun-rust-library` and `template-bun-wasm-rust-library` (the last also has an `oxlint-disable` comment in `src/lib.ts`). Each has the dev dependencies, `bun.lock`, README references and one `valid-expect` error. New repos start from these templates.
- **Libraries**: `bun-ffi-loader`, `dynamic-plugin-framework` (12 lint findings), `dynamic-cli-framework-api`, `dynamic-cli-framework` (34 lint findings, the largest reformat, and `oxlint-disable` comments in `src/` and `tests/`), `example-plugin-api`, `plugin-api`, `runtime`, `pluggable-io-framework-api`, `pluggable-io-framework`, `io-plugin-filesystem`, `io-plugin-filesystem-native`, `io-plugin-http`, `io-plugin-s3` and `flowscripter-io-cli-hash-native`. Each has the dev dependencies, `bun.lock` and README or `README/development.md` references.
- **Executables, apps and examples**: `cli`, `example-cli`, `example-cli-plugin`, `example-host-application`, `example-plugin`, `flowscripter-io-cli` and `io-gateway-http`, for the same reasons.
- **Not affected**: `docs`, `homebrew-tap` and `template-rust-library` have no references. `template-rust-library` picks up the `release-rust-library` change from `.github` without a change of its own.
- **Outside the repos**: Nick's global git hooks (`~/.config/git/hooks/`), for criterion 13, and the Claude Code guard hook (`~/.claude/hooks/guard-gh.py`), for criterion 15.

## Open Questions

Nick answered the earlier questions on the PR review (2026-11-28): wait for Bun 1.4.6 and make it the minimum (criterion 4); use Bun's default style (criterion 9); gate on 0 warnings as well as errors (criteria 2, 6 and 7).

1. **Where should the pre-commit git hook live?** Today the only hook is the global `~/.config/git/hooks/pre-push`, which isn't in any repo and runs oxfmt and oxlint on changed files at push time. Recommended: replace it with a global `pre-commit` hook that runs `bun fmt --staged` and `bun lint --staged --max-warnings=0` in bun repos. Commit a copy to `.github` (`scripts/git-hooks/pre-commit`) so it's versioned and documented, and Nick installs it. No per-repo hook tooling (husky, lefthook) is added. Claude's own check (criteria 14 and 15) doesn't depend on it.
2. **Should the guard hook enforce the commit rule (criterion 15), or is the written rule enough?** Recommended: enforce it. A rule in the skills can be missed by a subagent, and the guard hook already runs on every Bash call. The check adds well under a second per commit (`bun lint` took 20 ms on the largest repo).
