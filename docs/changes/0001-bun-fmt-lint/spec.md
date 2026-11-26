# Use Bun's Built-in Formatter and Linter Instead of oxfmt and oxlint

Refs flowscripter/.github#79

## Problem

Every bun repo formats with oxfmt and lints with oxlint, run through `bunx` from the shared check actions, with both pinned as dev dependencies in each repo. Bun now has its own formatter (`bun fmt`) and linter (`bun lint`), so the two extra tools and their dependencies are no longer needed. Switching to Bun's own tools leaves one toolchain to keep current, and makes the workflows, READMEs and dependencies across the org simpler.

What was found while writing this spec:

- `bun fmt` first shipped in Bun 1.4.4 (https://bun.com/blog/bun-v1.4.4). It formats TOML too, so it can replace `bunx oxfmt Cargo.toml` in the release workflows.
- `bun lint` is documented (https://bun.com/docs/lint), but no stable release has it yet. The latest stable, 1.4.5, answers `bun lint` with `Script not found "lint"`. The canary `1.4.5-canary.20261126.1` reports version 1.4.6 and has `bun lint`.
- `bun lint` honours both `oxlint-disable` and `eslint-disable` comments. Like oxlint today, it exits 0 when it finds only warnings.
- With no config file, `bun fmt` formats like oxfmt only while `oxfmt` is in `package.json`. Once that dependency is removed, it can switch to its other style (Prettier-like), so the first run may reformat files.

## Acceptance Criteria

1. No file in any non-archived flowscripter repo refers to oxfmt or oxlint. That covers workflows, actions, `package.json`, `bun.lock`, config files, source comments (`oxlint-disable` directives included), READMEs, `README/` docs, `CLAUDE.md` files and the `.github` docs. Checked with an org-wide search for `oxfmt` and `oxlint` on each repo's `main`.
2. The shared check actions (`check-bun-source`, `check-bun-rust-source`, `check-bun-wasm-rust-source`) run `bun fmt --check` and `bun lint`. The step fails when a file needs formatting or `bun lint` reports an error. Checked with a throwaway branch in a template repo, which contains one unformatted file and one lint error.
3. The shared release workflows that format `Cargo.toml` (`release-bun-rust-library`, `release-rust-library`) use `bun fmt` instead of `bunx oxfmt`, and a release from each still succeeds.
4. Every workflow and action that runs `bun fmt` or `bun lint` installs a Bun version at least as new as the first stable release that has both commands. If the installed Bun is older, the job fails with a message that names the minimum version.
5. The check names the rulesets require are unchanged: `scripts/repo-settings.py audit` reports no drift in required checks.
6. A PR with a formatting or lint error can't be merged: the failing step fails a required check. Checked on the PR from criterion 2.
7. Every bun repo's validation and check jobs pass on `main` after the switch.
8. `oxfmt` and `oxlint` are removed from the dev dependencies of every bun repo, and any oxfmt or oxlint config file is deleted.
9. In each repo, the reformatting from the switch lands in its own commit, with no behaviour or config changes in it (proposed: a `style:` commit, or a separate `style:` PR).
10. The `.github` docs and `.claude/CLAUDE.md` (Key Tooling Conventions) give the new lint, format check and format fix commands.
11. Each bun repo's development docs (`README.md`, or `README/development.md` where it exists) say how to format, check formatting and lint with Bun.
12. A local git hook runs `bun fmt` and `bun lint` on the staged files before each commit, and no local git hook refers to oxfmt or oxlint. The only one today is the global `~/.config/git/hooks/pre-push`.
13. (proposed) No bun repo's check job on `main` fails during the rollout. Shared actions and repos are changed in an order that keeps every `main` green.

## Non-goals

- Changing Rust formatting and linting (`cargo fmt`, `cargo clippy`).
- Renaming or restructuring the check jobs, or changing the rulesets.
- Turning on new lint rules or type-aware linting beyond what `bun lint` does by default, except where needed to match current behaviour.
- Archived repos (for example `mpeg-sdl-tool`).
- Behaviour changes in any repo's code.

## Affected Repos

Repos are listed from the current repo graph and from a search of local clones of `main` for `oxfmt` and `oxlint`. No package API changes, so the dependency edges matter only for the release order. They don't create code changes in dependents.

- **`.github`** (home repo): the three `check-bun-*` actions, the `release-bun-rust-library` and `release-rust-library` workflows (`bunx oxfmt Cargo.toml`), `.claude/CLAUDE.md`, and the Bun version guard in the workflows and actions. The workflow-file changes can't be pushed with the machine token, so Nick pushes them (ADR 0001). Consumers pick up a merge here immediately through `v1` (ADR 0003), so this repo goes first, and its change has to keep repos that haven't switched yet passing (criterion 13).
- **Templates**: `template-bun-library`, `template-bun-executable`, `template-bun-webapp`, `template-bun-rust-library` and `template-bun-wasm-rust-library` (the last also has an `oxlint-disable` comment in `src/lib.ts`). Each has the dev dependencies, `bun.lock` and README references. New repos start from these templates.
- **Libraries**: `bun-ffi-loader`, `dynamic-plugin-framework`, `dynamic-cli-framework-api`, `dynamic-cli-framework` (which also has `oxlint-disable` comments in `src/` and `tests/`), `example-plugin-api`, `plugin-api`, `runtime`, `pluggable-io-framework-api`, `pluggable-io-framework`, `io-plugin-filesystem`, `io-plugin-filesystem-native`, `io-plugin-http`, `io-plugin-s3` and `flowscripter-io-cli-hash-native`. Each has the dev dependencies, `bun.lock` and README or `README/development.md` references.
- **Executables, apps and examples**: `cli`, `example-cli`, `example-cli-plugin`, `example-host-application`, `example-plugin`, `flowscripter-io-cli` and `io-gateway-http`, for the same reasons.
- **Not affected**: `docs`, `homebrew-tap` and `template-rust-library` have no references. `template-rust-library` picks up the `release-rust-library` change from `.github` without a change of its own.
- **Outside the repos**: Nick's global git hooks (`~/.config/git/hooks/`), for criterion 12.

## Open Questions

1. **`bun lint` isn't in a stable Bun release yet.** Should the switch wait for the first stable release with `bun lint` (expected to be 1.4.6), or go ahead on canary? Recommended: wait. Make that release the minimum for criterion 4, and don't run canary in CI. If Nick wants to start now, the formatter half (`bun fmt`, minimum 1.4.4) could ship first, and oxlint would stay until the stable release.
2. **Where should the pre-commit hook live?** Today the only hook is the global `~/.config/git/hooks/pre-push`, which isn't in any repo and runs oxfmt and oxlint on changed files at push time. Recommended: replace it with a global `pre-commit` hook that runs `bun fmt --staged` and `bun lint --staged` in bun repos. Commit a copy to `.github` (`scripts/git-hooks/pre-commit`) so it's versioned and documented, and Nick installs it. No per-repo hook tooling (husky, lefthook) is added.
3. **Formatter style after oxfmt is removed.** Recommended: use Bun's defaults with no `[fmt]` config, and accept one `style:` reformat commit per repo. Don't set `flavor = "oxfmt"`, which would keep an oxfmt reference and break criterion 1. If the default reformat turns out to be large, set a few `bunfig.toml` `[fmt]` options that match the current style instead.
4. **Should lint warnings fail the check?** Recommended: no. Keep today's oxlint behaviour, where errors fail and warnings don't. Tightening it with `--max-warnings=0` is a separate change.
