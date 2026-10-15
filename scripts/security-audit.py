#!/usr/bin/env python3
"""Security checks for the flowscripter org.

  alerts  - fail if any repo has open high/critical Dependabot alerts, any open
            CodeQL or secret scanning alert, or has drifted from the org
            security configuration. Needs GH_TOKEN with read access to alerts
            and repository administration.
  rescan  - open the monthly "deep scan due" issue in flowscripter/.github
            (deduplicated by month marker), grouping repos using
            security/scan-ledger.json. Needs GH_TOKEN allowed to create
            issues as the machine account.
  ledger-add <repo> <CLAUDE-SECURITY-REVISION-*.json>
          - record a finished scan in security/scan-ledger.json.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ORG = "flowscripter"
EXCLUDE = {"winget-pkgs"}
LEDGER = os.path.join(os.path.dirname(__file__), "..", "security", "scan-ledger.json")
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
    with open(LEDGER) as f:
        ledger = json.load(f)["repos"]
    baseline, changed, current, deferred = [], [], [], []
    for r in repos():
        e = ledger.get(r)
        if e is None:
            baseline.append(f"{r} (not in ledger, choose an effort)")
        elif e["status"] == "deferred":
            deferred.append(f"{r} ({e.get('reason', 'deferred')})")
        elif e["status"] == "unscanned":
            baseline.append(f"{r} ({e['effort']})")
        else:
            head = gh("api", f"repos/{ORG}/{r}/commits/HEAD", "-q", ".sha", check=False).stdout.strip()
            if head and head != e["commit"]:
                changed.append(f"{r} ({e['effort']}, last scanned {e['scanned']})")
            else:
                current.append(r)

    def section(title, rows):
        return f"**{title}**\n\n" + ("\n".join(f"- {x}" for x in rows) if rows else "- none") + "\n\n"

    listing = (section("Needs baseline", baseline) + section("Changed since last scan", changed)
               + section("Up to date", current) + section("Deferred", deferred))
    body = (
        f"Monthly deep security scan is due for {month}.\n\n"
        "Repos grouped by scan state (security/scan-ledger.json):\n\n"
        f"{listing}"
        "On approval the main session runs the claude-security scan one repo at a time, "
        "diffs finding ids against the accepted list, and opens proposal issues for new findings only.\n\n"
        f"{marker}\n<!-- flowscripter-agent:v1 -->\n"
    )
    gh("issue", "create", "-R", f"{ORG}/.github", "--title",
       f"security: monthly deep scan due {month}", "--body", body)


def cmd_ledger_add(repo, revision_file):
    with open(revision_file) as f:
        j = json.load(f)
    with open(LEDGER) as f:
        data = json.load(f)
    old = data["repos"].get(repo, {})
    findings = j["findings"]
    data["repos"][repo] = {
        "effort": old.get("effort", j["effort"]),
        "status": "scanned",
        "scanned": j["generated_at"][:10],
        "commit": j["revision"]["commit"],
        "branch": j["revision"]["branch"],
        "dirty": j["revision"]["dirty"],
        "scannedEffort": j["effort"],
        "findings": {k: findings[k] for k in ("critical", "high", "medium", "low")},
    }
    with open(LEDGER, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["alerts"] and len(args) == 1:
        cmd_alerts()
    elif args[:1] == ["rescan"] and len(args) == 1:
        cmd_rescan()
    elif args[:1] == ["ledger-add"] and len(args) == 3:
        cmd_ledger_add(args[1], args[2])
    else:
        sys.exit(__doc__)
