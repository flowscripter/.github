# Replace Codecov with In-House Coverage Reporting

Refs flowscripter/.github#81

## Problem

Coverage is reported through Codecov, a second provider with its own setup and token. It often fails to report, and because `codecov/patch` and `codecov/project` are required checks, a missing result blocks PRs (bun-ffi-loader#10, for example). Repos with naturally low coverage, such as API-only packages, need special cases in the repo rules to get past it.

We still want coverage in PRs, a coverage gate and a README badge, but produced entirely inside our own GitHub Actions from the lcov file CI already writes (`bun test --coverage` for Bun, grcov for Rust), with no external service.

## Acceptance Criteria

1. On every PR, the job summary of the `check` job shows total line coverage and patch coverage (the share of coverable changed lines that are covered), each as a percentage and as covered/coverable line counts. This holds for every repo type: Bun (lcov from `bun test --coverage`) and Rust (lcov from grcov).
2. A PR whose total or patch coverage is below the repo's threshold fails the `check` job, and the summary says which threshold failed and by how much. A PR at or above both thresholds passes.
3. A repo sets its own total and patch thresholds in a file in the repo. A repo that sets nothing gets the org default. A repo can set a low minimum, or turn the gate off; with the gate off the summary still reports coverage.
4. After a release, the README shows a coverage badge with the coverage measured for that release, without any external service, and without a commit to `main`.
5. No workflow, composite action, ruleset, secret, README or config file in the org refers to Codecov (including `CODECOV_TOKEN`, `codecov.yml`, the `codecov` section of `scripts/repo-types.json` and the `--no-codecov` option of `scripts/repo-settings.py`), and `repo-settings.py audit` reports no drift.
6. A PR on `bun-ffi-loader` can merge after Nick approves it, because it is no longer waiting for a codecov result.
7. A PR on `example-cli` can merge once approved, because its coverage threshold is set to a low percentage.
8. The badges in each repo's README on `main` reflect the current state of `main` (latest release for version and coverage, latest run for build) and do not depend on a third-party image service, so they render whenever GitHub itself does.
9. (proposed) A PR from a fork, which has no write token and no secrets, gets the same coverage summary and the same pass/fail result as a PR from a branch in the repo. Nothing is posted as a PR comment.
10. (proposed) A PR that changes no coverable lines passes the patch gate, and the summary shows patch coverage as not applicable.
11. (proposed) The required check names in every ruleset are unchanged, apart from the two codecov contexts, which are removed. The gate adds no new check.
12. (proposed) No third-party action is added for coverage reporting, gating or badge generation in any job that holds secrets.
13. (proposed) A repo created with `repo-settings.py new` from any `template-*` repo gets coverage reporting, the org default thresholds and a working coverage badge after its first release, with no extra setup.
14. (proposed) The `.github` README describes the coverage step, the threshold settings and the badges, and an org ADR in `docs/adr/` records the move away from Codecov.

## Non-Goals

- Coverage history, trends or graphs.
- PR comments or review annotations for coverage.
- Any third-party coverage or badge service.
- New coverage instrumentation: each repo type reports the lcov it produces today (see open question 6).
- Changing test frameworks or how tests are run.

## Affected Repos

From the current repo graph. The shared workflows reach every consumer through the `v1` branch ([ADR 0003](../../adr/0003-v1-branch-for-shared-workflows.md)), so no repo needs a dependency bump and there is no package cascade. Changes to any `.github/workflows/` file, here or in a consumer, have to be pushed by Nick ([ADR 0001](../../adr/0001-agentic-development-workflow.md)).

- **`.github`** (home): the coverage step in the `check-*-source` composite actions replaces the Codecov upload; the `validate-*-pr` and `release-*` reusable workflows lose `CODECOV_TOKEN` and gain threshold settings and badge publishing; `scripts/repo-settings.py` and `scripts/repo-types.json` lose the codecov handling; README and a new ADR.
- **`template-bun-library`, `template-bun-executable`, `template-bun-webapp`, `template-rust-library`, `template-bun-rust-library`, `template-bun-wasm-rust-library`**: new repos are created from them (AC 13), so they carry the README badges and threshold settings. Each currently has a Codecov README badge.
- **Every other repo that calls a `validate-*-pr` workflow** (ruleset contexts, README badges, threshold settings where the default doesn't fit):
  - bun-library type: `bun-ffi-loader` (AC 6), `dynamic-cli-framework`, `dynamic-cli-framework-api`, `dynamic-plugin-framework`, `example-cli-plugin`, `example-plugin`, `example-plugin-api`, `io-gateway-http`, `io-plugin-filesystem`, `io-plugin-http`, `io-plugin-s3`, `pluggable-io-framework`, `pluggable-io-framework-api`, `plugin-api`, `runtime`.
  - bun-executable type: `example-cli` (AC 7, low threshold because its example commands are not unit-tested by design), `cli`, `example-host-application`, `flowscripter-io-cli`.
  - bun-rust-library type: `flowscripter-io-cli-hash-native`, `io-plugin-filesystem-native`.
  - API-only packages such as `dynamic-cli-framework-api`, `pluggable-io-framework-api`, `example-plugin-api` and `plugin-api` are the likely users of a low threshold or the gate turned off (AC 3).
- **Not affected**: `homebrew-tap` and `docs` (no validate workflow and no coverage), and `mpeg-sdl-tool` (archived).

## Open Questions

1. **Where do thresholds live?** Recommended: as inputs on the repo's caller workflow, `.github/workflows/validate-*-pr.yml` (for example `coverage-total-min`, `coverage-patch-min`, and `coverage-gate: false` to turn the gate off), with the org default as the input default in the shared reusable workflow. This is what the issue prefers, and it keeps the settings next to the check they control. The cost is that the machine token can't edit those files, so a threshold change in a repo needs Nick to push it. The alternative is a small non-workflow file such as `.github/coverage.json`, which the agent could change through a normal PR.
2. **What is the org default?** Recommended: 80% total and 80% patch. The plan measures every repo's current coverage and sets a per-repo threshold wherever the default would fail today, so no repo starts red.
3. **Where is the coverage badge served from?** Recommended: the release workflow generates `coverage.svg` itself (no third-party action) and force-pushes it as a single commit to an orphan `badges` branch with the `PUSH_TO_MAIN_TOKEN` it already holds. The README points at `https://raw.githubusercontent.com/flowscripter/<repo>/badges/coverage.svg`. That needs no commit to `main`, works for every repo type, and is served by GitHub. GitHub Pages is the alternative, but only four of the six release workflows publish Pages, and every Pages deploy replaces the whole site. raw.githubusercontent.com caches for about five minutes, so the badge can lag a release by that long.
4. **How should the other badges be driven?** Recommended, so that every badge is served by GitHub (AC 8): build uses GitHub's own workflow badge (`https://github.com/flowscripter/<repo>/actions/workflows/<file>/badge.svg?branch=main`); version is generated by the release workflow into the same `badges` branch as coverage; docs and license become static SVGs written to that branch by the same step. Links stay as today (releases page, workflow page, docs site, `LICENSE`).
5. **What does the coverage badge link to?** Recommended: the release workflow's runs on `main` (`https://github.com/flowscripter/<repo>/actions/workflows/<release-file>?query=branch%3Amain`). The newest run's job summary has the coverage table for that release. A per-file HTML report would need Pages, which not every type has.
6. **Should Bun + Rust repos also measure their Rust code?** Today `check-bun-rust-source` and `check-bun-wasm-rust-source` report only the Bun lcov, and grcov runs only for the `rust-library` type. Recommended: keep that as is for this change, so the work is a like-for-like replacement of Codecov; adding Rust coverage to those types can be a separate issue.
7. **Line or branch coverage?** grcov is run with `--branch`, Bun reports lines and functions. Recommended: gate and badge on line coverage only, which both tools report the same way.
