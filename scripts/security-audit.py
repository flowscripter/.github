#!/usr/bin/env python3
"""Security checks for the flowscripter org.

  alerts  - fail if any repo has open high/critical Dependabot alerts, any open
            CodeQL or secret scanning alert, or has drifted from the org
            security configuration. Needs GH_TOKEN with read access to alerts
            and repository administration.
  rescan  - open the monthly "deep scan due" issue in flowscripter/.github
            (deduplicated by month marker). Needs GH_TOKEN allowed to create
            issues as the machine account.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ORG = "flowscripter"
EXCLUDE = {"winget-pkgs"}
WANT = {
    "secret_scanning": "enabled",
    "secret_scanning_push_protection": "enabled",
    "dependabot_security_updates": "enabled",
}


def gh(*args, check=True):
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed: {p.stderr.strip()}")
    return p


def obj(path):
    p = gh("api", path, check=False)
    return json.loads(p.stdout) if p.returncode == 0 else None


def items(path):
    """Flattened list from a paginated endpoint; None if unreadable, [] if no analysis."""
    p = gh("api", "--paginate", path, "-q", ".[]", check=False)
    if p.returncode != 0:
        return [] if "no analysis found" in p.stdout + p.stderr else None
    return [json.loads(line) for line in p.stdout.splitlines() if line]


def repos():
    out = gh("repo", "list", ORG, "--no-archived", "--limit", "200", "--json", "name").stdout
    return sorted(r["name"] for r in json.loads(out) if r["name"] not in EXCLUDE)


def audit_repo(name):
    base = f"repos/{ORG}/{name}"
    problems = []

    sa = (obj(base) or {}).get("security_and_analysis")
    if sa is None:
        problems.append("cannot read security settings (token needs Administration: read)")
    else:
        for key, want in WANT.items():
            if sa.get(key, {}).get("status") != want:
                problems.append(f"{key} not {want}")
        if (obj(f"{base}/private-vulnerability-reporting") or {}).get("enabled") is not True:
            problems.append("private vulnerability reporting not enabled")
        if (obj(f"{base}/code-scanning/default-setup") or {}).get("state") != "configured":
            problems.append("CodeQL default setup not configured")

    dep = items(f"{base}/dependabot/alerts?state=open&per_page=100")
    if dep is None:
        problems.append("cannot read Dependabot alerts")
    else:
        bad = [a for a in dep if a["security_advisory"]["severity"] in ("high", "critical")]
        if bad:
            problems.append(f"{len(bad)} open high/critical Dependabot alerts")

    for label, path in (("CodeQL", "code-scanning"), ("secret scanning", "secret-scanning")):
        found = items(f"{base}/{path}/alerts?state=open&per_page=100")
        if found is None:
            problems.append(f"cannot read {label} alerts")
        elif found:
            problems.append(f"{len(found)} open {label} alerts")

    return problems


def cmd_alerts():
    rows = [(r, audit_repo(r)) for r in repos()]
    lines = ["| Repo | Status |", "|---|---|"]
    for r, probs in rows:
        lines.append(f"| {r} | {'ok' if not probs else '; '.join(probs)} |")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(report + "\n")
    if any(p for _, p in rows):
        sys.exit(1)


def cmd_rescan():
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    marker = f"<!-- flowscripter-security-rescan:{month} -->"
    existing = gh("issue", "list", "-R", f"{ORG}/.github", "--state", "all", "--search",
                  f'"flowscripter-security-rescan:{month}" in:body', "--json", "number").stdout
    if json.loads(existing):
        print(f"issue for {month} already exists")
        return
    since = (now - timedelta(days=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = []
    for r in repos():
        p = gh("api", f"repos/{ORG}/{r}/commits?since={since}&per_page=1", check=False)
        if p.returncode == 0 and json.loads(p.stdout):
            changed.append(r)
    listing = "\n".join(f"- {r}" for r in changed) or "- (no repo has new commits)"
    body = (
        f"Monthly deep security scan is due for {month}.\n\n"
        "Repos with commits in the last 35 days:\n\n"
        f"{listing}\n\n"
        "On approval the main session runs the claude-security scan one repo at a time, "
        "diffs finding ids against the accepted list, and opens proposal issues for new findings only.\n\n"
        f"{marker}\n<!-- flowscripter-agent:v1 -->\n"
    )
    gh("issue", "create", "-R", f"{ORG}/.github", "--title",
       f"security: monthly deep scan due {month}", "--body", body)


if __name__ == "__main__":
    cmds = {"alerts": cmd_alerts, "rescan": cmd_rescan}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]]()
