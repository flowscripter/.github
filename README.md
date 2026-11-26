# .github

![reactorcat](reactorcat.gif)

## Agentic Development Workflow

Most work on the flowscripter repos is done by a local Claude Code agent acting as `vectronic-claude`. Each change starts as an issue on the org project board. For larger changes the agent writes a spec and a plan, each as a docs-only PR. Cross-repo work is split into one sub-issue per repo, linked by blocked-by relationships.

The agent implements each sub-issue as a PR and, once it is released, checks the result itself. Nick approves at each gate by merging, and steers with `/approve`, `/go`, `/park` and `/revise` in comments. The agent never merges and never pushes to a default branch, and a local hook enforces both. Merging a docs-only PR runs no build and cuts no release.

- [Board stages, routing and commands](docs/stages.md)
- [Design](docs/agentic-sdlc.md)
- [Rollout plan](docs/agentic-sdlc-rollout.md) (temporary, removed once the rollout is done)

## Repository Settings

Every non-archived repository in the org follows the same settings:

* squash merge only
* auto-merge on
* branches deleted on merge
* Dependabot alerts on
* a `main` ruleset that requires a pull request with one approval (re-approval after any later push), linear history, no deletion or force-push, and strict status checks for the project type. Org owners can always bypass it. Release workflows rely on that: they push the version commit to `main` with `PUSH_TO_MAIN_TOKEN`, which belongs to an org owner. It also lets Nick merge his own PRs. `vectronic-claude` has the write role, not owner, so its PRs need Nick's approval.
* the `agent-config` check (part of `lint-pr-message`), which fails a PR that adds agent configuration other than `CLAUDE.md` and `.claude/skills/`, or that changes agent instructions when it was not opened by `vectronic` or `vectronic-claude`.

Third-party actions in the shared workflows and actions are pinned to commit SHAs, and Dependabot keeps the pins current. Dependency-update PRs are opened by `vectronic-claude` with auto-merge on, so they merge once Nick approves them.

The type of an existing repo is inferred from the `validate-*-pr` workflow it calls. `scripts/repo-types.json` holds the required checks for each repository type:

* bun-library
* bun-executable
* bun-webapp
* rust-library
* bun-rust-library
* bun-wasm-rust-library.

The codecov checks are optional.

#### Scheduled Audit

`repo-settings.py` is used to ensure consistency of repo settings:

```bash
python3 scripts/repo-settings.py audit [--repo NAME] [--json]
python3 scripts/repo-settings.py apply REPO [--type TYPE] [--no-codecov] [--dry-run]
python3 scripts/repo-settings.py apply --all [--dry-run]
python3 scripts/repo-settings.py new NAME TYPE [--no-codecov] [--private] [--dry-run]
```

`audit` is read-only and exits 1 when anything has drifted. It also reports workflows disabled by inactivity. 

`apply` and `new` change settings so need to be run as a repository admin with `gh` logged in as yourself.

`new` creates the repo from `template-TYPE` and then applies the settings. Secrets live at org level, so nothing is added per repo.

The `audit-repo-settings` workflow runs the audit every Monday. A failing run is the signal that something has drifted. 

It needs an org secret `AUDIT_REPO_TOKEN`: a fine-grained personal access token with the flowscripter org as resource owner, access to all repositories, and read-only permissions for Administration, Actions, Contents and Metadata. Dependabot alerts, Code scanning alerts and Secret scanning alerts (all read) are needed as well.

#### Exceptions

`homebrew-tap` is skipped on purpose: the `release-bun-executable` workflow checks it out with `PUSH_TO_MAIN_TOKEN` and pushes the formula update straight to its default branch, with no pull request. A ruleset requiring pull requests or status checks would block that push, and it has no CI of its own to require.

#### Restricted Refs

Some refs are pushed only by automation running with `PUSH_TO_MAIN_TOKEN`, which belongs to an org owner. `restricted_refs` in `scripts/repo-types.json` gives each one a ruleset that blocks updates, deletion and force pushes for everyone except org owners:

* `.github` branch `v1`, which every repo's workflows load from and `update-v1` moves forward
* `.github` tags (there are none, and a tag named `v1` would be confused with the branch)
* `homebrew-tap` default branch, which `release-bun-executable` updates

`apply` creates these rulesets, including for `homebrew-tap`, which is otherwise skipped, and `audit` checks them. An org owner can still roll `v1` back with `git push origin <good-sha>:v1 --force`.

`winget-pkgs` is a fork and is ignored.

There exceptions and the `.github` repo's own specific checks are in `scripts/repo-types.json`.

## Security

- **Org Configuration:** the org security configuration "Flowscripter Standard" is attached to every repo and is the default for new repos. It turns on Dependabot alerts and security updates, secret scanning with push protection, private vulnerability reporting and CodeQL default setup.
- **Security Policy:** `SECURITY.md` in this repo is the default policy for every repo without its own. It points reporters to private vulnerability reporting.

#### Monthly Checks

The following workflows run on the 1st of each month and can also be started by hand.

- `security-alerts` fails when any non-archived repo has an open high or critical Dependabot alert, any open CodeQL or secret scanning alert, or has drifted from the org security configuration. A failing run is the signal to triage.
- `security-rescan-issue` opens one issue titled `security: monthly deep scan due YYYY-MM`. It groups repos as Needs baseline, Changed since last scan, Up to date or Deferred, using `security/scan-ledger.json`. It does nothing if the issue for that month already exists.

`security-alerts` uses `AUDIT_REPO_TOKEN`. `security-rescan-issue` needs an org secret `CLAUDE_CREATE_TICKET_TOKEN`: a fine-grained personal access token created by the machine account, with the flowscripter org as resource owner, and Issues (read and write), Contents (read) and Metadata (read) permissions. Both tokens expire, so renew them before then.

#### Scan Ledger

`security/scan-ledger.json` records, for each repo, the scan effort, and the commit and date of the last `claude-security` scan. It holds no findings and no finding counts: the repos are public, and even a count would show where an unfixed problem is. `ledger-add` prints the counts so they can be kept locally with the scan report. Repos missing from the ledger are listed as needing a baseline scan. A repo with status `deferred` is skipped.

`security-audit.py` is used to manage the ledger:

```bash
python3 scripts/security-audit.py alerts
python3 scripts/security-audit.py rescan
python3 scripts/security-audit.py ledger-add REPO CLAUDE-SECURITY-REVISION-SHA.json
```

`ledger-add` records a finished scan from the revision file in the scan output directory.

`alerts` and `rescan` need the tokens above, so they are normally left to the workflows.
