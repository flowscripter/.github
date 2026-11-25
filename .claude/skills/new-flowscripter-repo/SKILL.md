---
name: new-flowscripter-repo
description: Create a new repo in the flowscripter GitHub org with the standard settings (squash-only, auto-merge, main ruleset with required checks) or audit/fix settings drift across the org. Use whenever the user wants a new flowscripter repo, a new project from one of the template-* repos, or asks whether repos have consistent settings or disabled workflows.
---

The org has no org-level rulesets (Free plan) and template repos copy files, not settings. Standard settings are applied by `scripts/repo-settings.py` in the `flowscripter/.github` repo (local clone: `/home/nick/projects/flowscripter/.github`). Check the script exists on `origin/main` before relying on it; it landed via a PR in `.github` and may not be merged yet.

## Commands (run from the `.github` clone)

- New repo from a template: `python3 scripts/repo-settings.py new <name> <type> [--no-codecov] [--private] [--dry-run]`
- Fix one repo or all: `python3 scripts/repo-settings.py apply <repo> [--type T] [--no-codecov] [--dry-run]` or `apply --all`
- Audit (read-only, exit 1 on drift): `python3 scripts/repo-settings.py audit [--repo NAME] [--json]`

Types: `bun-library`, `bun-executable`, `bun-webapp`, `rust-library`, `bun-rust-library`, `bun-wasm-rust-library`. Each maps to `flowscripter/template-<type>`. `--no-codecov` is for API-only repos with no coverage upload.

## Rules

- `new` and `apply` need admin rights. Claude sessions run as the machine account `vectronic-claude`, which is NOT admin, so the write calls fail with 404. Use `--dry-run` to show the plan, then give Nick the exact command to run in his own terminal (his shell is authenticated as `vectronic`). Never use `!` in the session for these, because it uses the machine account token.
- Do not add secrets to new repos: all secrets (`CREATE_PR_TOKEN`, `PUSH_TO_MAIN_TOKEN`, code-signing, `CODECOV_TOKEN`) are org-level.
- The weekly `audit-repo-settings` workflow in `.github` runs the audit with the org secret `AUDIT_REPO_TOKEN`; a failing run is picked up by `/flowscripter-sweep` as a `ci:` issue.
- After creating a repo, tell Nick it still needs: first PR to produce the required check names, and (for new repos) adding it to the project board scope is automatic via the sweep.
