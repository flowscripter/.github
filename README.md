# .github

![reactorcat](reactorcat.gif)

## Repository Settings

Every non-archived repository in the org follows the same settings: squash merge only, auto-merge on, branches deleted on merge, Dependabot alerts on, and a `main` ruleset that requires a pull request, linear history, no deletion or force-push, and strict status checks for the project type. `scripts/repo-types.json` holds the required checks for each type (bun-library, bun-executable, bun-webapp, rust-library, bun-rust-library, bun-wasm-rust-library). The type of an existing repo is inferred from the `validate-*-pr` workflow it calls. The codecov checks are optional.

```bash
python3 scripts/repo-settings.py audit [--repo NAME] [--json]
python3 scripts/repo-settings.py apply REPO [--type TYPE] [--no-codecov] [--dry-run]
python3 scripts/repo-settings.py apply --all [--dry-run]
python3 scripts/repo-settings.py new NAME TYPE [--no-codecov] [--private] [--dry-run]
```

`audit` is read-only and exits 1 when anything has drifted. It also reports workflows disabled by inactivity. `apply` and `new` change settings, so run them as a repository admin with `gh` logged in as yourself. `new` creates the repo from `template-TYPE` and then applies the settings. Secrets live at org level, so nothing is added per repo.

### Scheduled Audit

The `audit-repo-settings` workflow runs the audit every Monday. A failing run is the signal that something has drifted. It needs an org secret `AUDIT_REPO_TOKEN`: a fine-grained personal access token with the flowscripter org as resource owner, access to all repositories, and read-only permissions for Administration, Actions, Contents and Metadata. Add Dependabot alerts, Code scanning alerts and Secret scanning alerts (all read) as well. Otherwise the alerts checks report that they cannot verify.

### Exceptions

`homebrew-tap` is skipped on purpose: the `release-bun-executable` workflow checks it out with `PUSH_TO_MAIN_TOKEN` and pushes the formula update straight to its default branch, with no pull request. A ruleset requiring pull requests or status checks would block that push, and it has no CI of its own to require. `winget-pkgs` is a fork and is ignored. Both lists, and the `.github` repo's own required checks, are in `scripts/repo-types.json`.

## Security

- **Org Configuration:** the org security configuration "Flowscripter Standard" is attached to every repo and is the default for new repos. It turns on Dependabot alerts and security updates, secret scanning with push protection, private vulnerability reporting and CodeQL default setup.
- **Security Policy:** `SECURITY.md` in this repo is the default policy for every repo without its own. It points reporters to private vulnerability reporting.

### Monthly Checks

Both workflows run on the 1st of each month and can also be started by hand.

- `security-alerts` fails when any non-archived repo has an open high or critical Dependabot alert, any open CodeQL or secret scanning alert, or has drifted from the org security configuration. A failing run is the signal to triage.
- `security-rescan-issue` opens one issue titled `security: monthly deep scan due YYYY-MM`. It groups repos as Needs baseline, Changed since last scan, Up to date or Deferred, using `security/scan-ledger.json`. It does nothing if the issue for that month already exists.

`security-alerts` uses `AUDIT_REPO_TOKEN`. `security-rescan-issue` needs an org secret `CLAUDE_CREATE_TICKET_TOKEN`: a fine-grained personal access token created by the machine account, with the flowscripter org as resource owner, and Issues (read and write), Contents (read) and Metadata (read) permissions. Both tokens expire, so renew them before then.

### Scan Ledger

`security/scan-ledger.json` records, for each repo, the scan effort, the commit and date of the last `claude-security` scan, and finding counts by severity. It holds no finding details. Repos missing from the ledger are listed as needing a baseline scan. A repo with status `deferred` is skipped.

```bash
python3 scripts/security-audit.py alerts
python3 scripts/security-audit.py rescan
python3 scripts/security-audit.py ledger-add REPO CLAUDE-SECURITY-REVISION-SHA.json
```

`ledger-add` records a finished scan from the revision file in the scan output directory. `alerts` and `rescan` need the tokens above, so they are normally left to the workflows.
