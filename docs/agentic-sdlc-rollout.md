# Agentic Development Workflow: Rollout

The changes that put [the agentic development workflow](agentic-sdlc.md) in place. This document is temporary. Delete it, along with `agentic-sdlc-notes.md` and `proposals/`, once every phase is done.

Phases are ordered so that the security gates, the guard hook and the docs-only gate exist before any `.claude` file is committed or any spec PR is merged. Each phase ends with a `CLAUDE.md` and memory update.

## Phase 0: Security Gates

1. **Merge control.** Change the `main` ruleset as agreed with Nick (approvals, approval of the most recent push, bypass). Update `PR_DEFAULTS` and the audit check in `scripts/repo-settings.py`, which currently expect 0 approvals, then run `apply --all`.
2. **Dependency-update PRs.** Change `check-*-dependencies.yml` to match the merge control: which token opens the PR, and who approves it.
3. **Machine account token.** Replace the classic token with a fine-grained token: flowscripter resources only, an expiry date, and no Workflows or Administration permission. Changes to workflow files are made by Nick.
4. **Org Actions settings** (Nick checks these, since the machine account can't read them):
   - require approval to run workflows on PRs from all outside contributors
   - don't let GitHub Actions approve pull requests
   - make the default `GITHUB_TOKEN` read-only
5. **Agent config check.** Add a required check, from a reusable workflow in `.github`, that fails any PR adding or changing agent-loaded configuration other than `CLAUDE.md`, `.claude/CLAUDE.md` and `.claude/skills/**`. Add it to `scripts/repo-types.json`.
6. **Action pinning.** Pin third-party actions to commit SHAs, with Dependabot keeping them current.
7. **Skill rules.** Agents never check out or run code from a branch or PR that `vectronic` or `vectronic-claude` didn't push. Trust markers (`Decided with Nick in session`, `flowscripter-subissue`) count only on text authored by `vectronic-claude`.

**Order.** Merge the `.github` PR that contains steps 1, 2, 5 and 6 first. Then swap `CREATE_PR_TOKEN` and run `repo-settings.py apply --all`. Running `apply` earlier makes `call-lint-pr-message / agent-config` a required check before any workflow reports it, which blocks every PR. Swap the machine account's local token last, because after the swap it can no longer push workflow-file changes.

## Phase 1: Version the Workflow

1. Change `.claude` to the three-line pattern in the `.gitignore` of every `template-*` repo, then open one PR per active repo with the same change and its reviewed `.claude/CLAUDE.md`.
2. In `.github`, commit `docs/stages.md`, `docs/agentic-sdlc.md`, this document, and the README section linking them.
3. Move the live `flowscripter-sweep` and `new-flowscripter-repo` skills into `.github/.claude/skills/` by PR, then replace the workspace `.claude/skills` with a symlink to it.
4. Move the rules out of `project_github_issue_loop.md` into the skills, leaving only volatile state in memory, and drop its security baseline table, which duplicates `security/scan-ledger.json`.

## Phase 2: Guard Hook

1. Commit `scripts/hooks/guard-gh.py` and its test to `.github`, and run the test in CI next to actionlint (a new, non-required check).
2. Add it to `~/.claude/settings.json` after `rtk hook claude`, with `onFailure: "block"`.
3. In a live session, run one blocked command of each kind and one allowed command of each kind.

## Phase 3: Docs-Only Gate

The problem: every repo's release workflow runs on any push to `main` and runs the full check and test matrix, and `docs` commits cut a patch release. Without a gate, merging a spec or plan PR would publish a version with no code change and start cascade bumps. The PR validation workflows would also run the full five-OS matrix for a markdown file.

**Release side.** Change the reusable `release-*.yml` workflows in `.github`. Nothing changes in consumer repos.

1. Add a first job, `changes`. It diffs `github.event.before..github.sha` and outputs `docs-only`. An all-zero `before` (a new branch) or a diff it can't compute counts as not docs-only.
2. Give every other job `needs: changes` and `if: needs.changes.outputs.docs-only != 'true'`. Pushes have no required checks, so the skipped jobs are harmless.

**PR side.** Change the reusable `validate-*-pr.yml` workflows the same way, diffing the PR's base and head. The ruleset requires the matrix-expanded check names (for example `call-validate-bun-library-pr / test (macOS-latest)`, from `scripts/repo-types.json`).

1. GitHub counts a skipped job as passing a required check, but a matrix job skipped by a job-level `if` may not produce its per-OS check names, and the PR would then wait forever.
2. So try the job-level `if` on one template repo first. If the names don't appear, put the condition on each step instead. The runners then start, find nothing to do and pass in seconds, and the check names stay intact.
3. `lint-pr-message` keeps running and is unaffected.

**Rollout.** A merge to `.github` main reaches every consumer at once through `@v1`, with no gate.

1. Test first: open a PR in `template-bun-library` whose callers point at the `.github` branch (`@<branch>`).
2. In that PR, check that a docs-only PR gets green required checks, and that a docs-only merge to the test repo releases nothing.
3. Close it without merging, merge the `.github` change, then check one real docs-only PR in an active repo.

The `.github` repo itself has no release workflow, so a docs-only merge there only moves `v1` forward.

## Phase 4: Intent Form

1. Add `.github/ISSUE_TEMPLATE/intent.yml` (What, Why, Constraints / non-goals, Acceptance criteria, Repos likely affected) and a `config.yml`. Org-level templates apply only to repos with no `.github/ISSUE_TEMPLATE/` of their own, so list the repos that have one and decide per repo.
2. Keep a plain bug form for one-line fixes, so the short route stays cheap.

## Phase 5: Central Documents

1. Write `docs/product.md` (users, principles, out of scope) with Nick, as an interview.
2. Add `docs/adr/0000-template.md`, and record the first org ADRs: this workflow, the docs-only rule, and the `@v1` branch policy.
3. Add `repos.yaml`. Generate the dependency edges from each repo's `package.json`/`Cargo.toml` with a small script, then hand-curate the release order and any edges the script can't see (for example templates).
4. Add `docs/adr/` to a repo only when it gets its first local decision.

## Phase 6: Board

1. In project 4, rename `In progress` to `In Progress` and add `Spec` and `Plan` between Backlog and In Progress. Option ids are looked up by name, so update the sweep skill and memory in the same change.
2. Check that the built-in Item closed and Auto-close workflows still work.

## Phase 7: Stage Skills

1. Commit the four stage skills and apply the sweep changes (`proposals/sweep-split/skills/flowscripter-sweep/CHANGES.md`), by PR to `.github`.
2. Check that the new token can create sub-issues and blocked-by links (`issues/N/sub_issues`, `issues/N/dependencies/blocked_by`).
3. Pilot one real full-route change end to end, preferably one that crosses two repos. Write down every gap and fix the skills before the next one.

## Phase 8: Cross-Repo Pre-Release Testing

1. Start with local overrides in the implement skill's worktrees (`bun link` or a file override, never committed). This needs no CI change.
2. Evaluate a semantic-release prerelease channel later. A `change/*` branch pattern would publish `x.y.z-<slug>.N` builds under a per-change dist-tag, so downstream PR CI can test against them. That means release workflows also trigger on `change/**`, so treat it as a separate decision with its own test repo.

## Phase 9: Mechanical Sweep CLI

1. Write `scripts/sweep.py` in `.github`, in the style of `repo-settings.py`, with JSON output. Subcommands:
   - `scope`: in-scope repos
   - `board`: items, statuses and field ids
   - `refs`: PRs referencing each issue, any state
   - `transitions`: the moves the table says to make
   - `release-state`: tags, `dist-tags.latest` and cascade bumps
   - `assign`: reviewer assignment
   - `metrics`
2. Keep the transition logic a pure function over the fetched state, with unit tests built from recorded fixtures.
3. Pass third-party comments to the model as author, link and length only, never as body text.
4. Change the sweep skill to call the CLI and apply its proposed moves. The model handles only reading Nick's asks, spotting flakes and writing comments.

## Phase 10: Self-Verification and Metrics

1. Turn on `flowscripter-verify` for every card instead of the sweep's verification comment.
2. Turn on transition logging, and review `sweep.py metrics` monthly alongside the security checks.

## Phase 11: Clean Up

Delete this document, `agentic-sdlc-notes.md` and `proposals/` once everything in them is either implemented or recorded as an ADR.

## Coexistence with `scripts/` and `security/`

These phases leave `scripts/security-audit.py`, `security/scan-ledger.json` and their workflows as they are. `scripts/repo-settings.py` changes only in phase 0 (approvals) and phase 0 step 5 (one new required check).

- **Required checks.** The docs-only gate keeps every required check name, so `repo-settings.py audit` sees no drift from it. The `changes` check isn't required, and the audit compares rulesets, not the checks that run. The audit doesn't inspect files, so the template `.gitignore` change doesn't affect it.
- **Admin scripts stay Nick's.** `repo-settings.py apply`/`new` need admin rights and run in Nick's shell as `vectronic`. Stage skills never run them. The guard hook doesn't affect Nick's shell or any Actions workflow (`audit-repo-settings`, `security-alerts`, `security-rescan-issue`), which run on GitHub with their own tokens.
- **Monthly rescan issue.** `security-rescan-issue` opens `security: monthly deep scan due YYYY-MM` in `.github`, authored by the machine account, with `<!-- flowscripter-security-rescan:<month> -->` and the agent marker. The sweep treats it as a system issue: it goes to Review, never takes the full route, and no stage skill runs a scan. `CLAUDE_CREATE_TICKET_TOKEN` is a separate token and isn't changed by phase 0.
- **Security findings.** Issues for findings still come only from Nick and take the short route. The public-detail rules and the accepted-findings ledger in memory still apply.
- **Ledger updates.** After `ledger-add`, `scan-ledger.json` changes reach `main` by PR, as the ruleset already requires.
- **Board.** `repo-settings.py` and `security-audit.py` never touch project 4, so the new statuses and the rename don't affect them.
