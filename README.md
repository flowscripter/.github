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

The `audit-repo-settings` workflow runs the audit every Monday. A failing run is the signal that something has drifted. It needs an org secret `AUDIT_REPO_TOKEN`: a fine-grained personal access token with the flowscripter org as resource owner, access to all repositories, and read-only permissions for Administration, Actions, Contents and Metadata. Add Dependabot alerts (read) as well, otherwise the alerts check reports that it cannot verify.

### Exceptions

`homebrew-tap` is skipped on purpose: the `release-bun-executable` workflow checks it out with `PUSH_TO_MAIN_TOKEN` and pushes the formula update straight to its default branch, with no pull request. A ruleset requiring pull requests or status checks would block that push, and it has no CI of its own to require. `winget-pkgs` is a fork and is ignored. Both lists, and the `.github` repo's own required checks, are in `scripts/repo-types.json`.
