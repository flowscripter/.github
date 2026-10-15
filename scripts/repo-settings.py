#!/usr/bin/env python3
"""Audit and apply the standard settings of flowscripter org repositories.

Uses the gh CLI for all GitHub access (authenticate with GH_TOKEN or gh auth login).

  repo-settings.py audit [--repo NAME] [--json]
  repo-settings.py apply (REPO [--type TYPE] | --all) [--no-codecov] [--dry-run]
  repo-settings.py new NAME TYPE [--no-codecov] [--private] [--dry-run]

Exit codes: 0 clean (warnings allowed), 1 drift found, 2 usage or auth error.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "repo-types.json")) as _f:
    CFG = json.load(_f)

ORG = CFG["org"]
ACTIONS_ID = CFG["github_actions_integration_id"]
CODECOV_ID = CFG["codecov"]["integration_id"]
CODECOV_CHECKS = CFG["codecov"]["checks"]
TYPES = CFG["types"]
SPECIAL = CFG["special"]

REPO_OPTIONS = {
    "default_branch": "main",
    "allow_squash_merge": True,
    "allow_merge_commit": False,
    "allow_rebase_merge": False,
    "allow_auto_merge": True,
    "delete_branch_on_merge": True,
}
SIMPLE_RULES = ["deletion", "non_fast_forward", "required_linear_history"]
PR_DEFAULTS = {
    "allowed_merge_methods": ["squash"],
    "dismiss_stale_reviews_on_push": False,
    "require_code_owner_review": False,
    "require_last_push_approval": False,
    "required_approving_review_count": 0,
    "required_review_thread_resolution": False,
}
DEFAULT_CONDITIONS = {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}


class GhError(Exception):
    pass


def gh(args, body=None):
    p = subprocess.run(
        ["gh"] + args,
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr


def api(path, method="GET", body=None, raw=False):
    args = ["api", path, "-X", method]
    if body is not None:
        args += ["--input", "-"]
    if raw:
        args += ["-H", "Accept: application/vnd.github.raw+json"]
    rc, out, err = gh(args, body)
    if rc != 0:
        raise GhError((err.strip().splitlines() or [out.strip()])[0])
    if raw:
        return out
    return json.loads(out) if out.strip() else {}


def list_repos():
    rc, out, err = gh([
        "api", "--paginate", "orgs/%s/repos?type=all&per_page=100" % ORG,
        "--jq", ".[] | {name, archived, fork} | tojson",
    ])
    if rc != 0:
        raise GhError((err.strip().splitlines() or ["cannot list repos"])[0])
    repos = [json.loads(line) for line in out.splitlines() if line.strip()]
    return sorted((r for r in repos if not r["archived"]), key=lambda r: r["name"])


def audited_repos():
    """Returns (names to audit, {name: reason} that are skipped)."""
    names, skipped = [], {}
    for r in list_repos():
        n = r["name"]
        if n in CFG["ignore"]:
            skipped[n] = "ignored: " + CFG["ignore"][n]
        elif r["fork"]:
            skipped[n] = "ignored: fork"
        elif n in CFG["skip"]:
            skipped[n] = "skipped: " + CFG["skip"][n]
        else:
            names.append(n)
    return names, skipped


def infer_type(repo):
    """Returns a type name, 'special' for repos in the special map, or None."""
    if repo in SPECIAL:
        return "special"
    try:
        files = api("repos/%s/%s/contents/.github/workflows" % (ORG, repo))
    except GhError:
        return None
    by_workflow = {t["workflow"]: name for name, t in TYPES.items()}
    for f in files:
        if not re.fullmatch(r"validate-.*-pr\.ya?ml", f["name"]):
            continue
        text = api("repos/%s/%s/contents/.github/workflows/%s" % (ORG, repo, f["name"]), raw=True)
        m = re.search(r"\.github/workflows/(validate-[a-z-]+-pr)\.ya?ml@", text)
        if m and m.group(1) in by_workflow:
            return by_workflow[m.group(1)]
    return None


def required_checks(repo, rtype):
    if rtype == "special":
        return SPECIAL[repo]["checks"], False
    return TYPES[rtype]["checks"], True


def find_ruleset(repo):
    for s in api("repos/%s/%s/rulesets" % (ORG, repo)):
        if s.get("target") != "branch":
            continue
        det = api("repos/%s/%s/rulesets/%s" % (ORG, repo, s["id"]))
        if "~DEFAULT_BRANCH" in det.get("conditions", {}).get("ref_name", {}).get("include", []):
            return det
    return None


def ruleset_findings(rs, checks, codecov_allowed):
    """Returns a list of (level, message) comparing a ruleset with the canonical one."""
    if rs is None:
        return [("drift", "no ruleset targeting ~DEFAULT_BRANCH")]
    f = []
    if rs.get("enforcement") != "active":
        f.append(("drift", "ruleset enforcement is %s, expected active" % rs.get("enforcement")))
    rules = {r["type"]: r.get("parameters") or {} for r in rs.get("rules", [])}
    for t in SIMPLE_RULES + ["pull_request", "required_status_checks"]:
        if t not in rules:
            f.append(("drift", "ruleset is missing rule: " + t))
    pr = rules.get("pull_request")
    if pr is not None:
        if pr.get("required_approving_review_count") != 0:
            f.append(("drift", "pull_request approvals is %s, expected 0" % pr.get("required_approving_review_count")))
        if pr.get("allowed_merge_methods") != ["squash"]:
            f.append(("drift", "pull_request allowed_merge_methods is %s, expected ['squash']" % pr.get("allowed_merge_methods")))
    sc = rules.get("required_status_checks")
    if sc is not None:
        if sc.get("strict_required_status_checks_policy") is not True:
            f.append(("drift", "required status checks are not strict"))
        have = {c["context"] for c in sc.get("required_status_checks", [])}
        missing = [c for c in checks if c not in have]
        if missing:
            f.append(("drift", "missing required checks: " + ", ".join(missing)))
        allowed = set(checks) | (set(CODECOV_CHECKS) if codecov_allowed else set())
        extra = sorted(have - allowed)
        if extra:
            f.append(("info", "extra required checks: " + ", ".join(extra)))
    return f


def option_diffs(repo_json):
    return {k: v for k, v in REPO_OPTIONS.items() if repo_json.get(k) != v}


def audit_repo(name):
    f = []
    rtype = infer_type(name)
    if rtype is None:
        f.append(("warn", "unknown type: no validate-*-pr workflow calling a known reusable workflow; required checks not audited"))
    try:
        repo = api("repos/%s/%s" % (ORG, name))
        hidden = [k for k in option_diffs(repo) if k not in repo]
        if hidden:
            f.append(("warn", "repo merge options not visible to this token (the API returns them only with push access); not audited: " + ", ".join(hidden)))
        for k, want in option_diffs(repo).items():
            if k in repo:
                f.append(("drift", "%s is %s, expected %s" % (k, repo.get(k), want)))
    except GhError as e:
        f.append(("warn", "unable to read repo settings: %s" % e))

    rc, out, err = gh(["api", "repos/%s/%s/dependabot/alerts?per_page=1&state=open" % (ORG, name)])
    if rc != 0:
        if "disabled" in (out + err).lower():
            f.append(("drift", "Dependabot alerts are disabled"))
        else:
            f.append(("warn", "unable to verify Dependabot alerts: " + ((err.strip().splitlines() or ["?"])[0])))

    try:
        wfs = api("repos/%s/%s/actions/workflows?per_page=100" % (ORG, name)).get("workflows", [])
        for w in wfs:
            if w["state"] == "disabled_inactivity":
                f.append(("drift", "workflow %s is disabled by inactivity (re-enable it: gh workflow enable)" % w["name"]))
            elif w["state"] == "disabled_manually":
                f.append(("warn", "workflow %s is disabled manually" % w["name"]))
    except GhError as e:
        f.append(("warn", "unable to list workflows: %s" % e))

    try:
        rs = find_ruleset(name)
        if rtype is None:
            if rs is None:
                f.append(("drift", "no ruleset targeting ~DEFAULT_BRANCH"))
        else:
            checks, codecov = required_checks(name, rtype)
            f += ruleset_findings(rs, checks, codecov)
    except GhError as e:
        f.append(("warn", "unable to read rulesets: %s" % e))
    return {"repo": name, "type": rtype, "findings": f}


def cmd_audit(args):
    names, skipped = audited_repos()
    if args.repo:
        if args.repo in skipped:
            print("%s: %s" % (args.repo, skipped[args.repo]))
            return 0
        if args.repo not in names:
            print("error: %s is not a non-archived repo in %s" % (args.repo, ORG), file=sys.stderr)
            return 2
        names = [args.repo]
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(audit_repo, names))
    counts = {"drift": 0, "warn": 0}
    drifted = 0
    for r in results:
        levels = [lvl for lvl, _ in r["findings"]]
        counts["drift"] += levels.count("drift")
        counts["warn"] += levels.count("warn")
        drifted += 1 if "drift" in levels else 0
    summary = {"audited": len(results), "repos_with_drift": drifted, "drift": counts["drift"],
               "warnings": counts["warn"], "skipped": len(skipped)}
    if args.json:
        out = {"summary": summary, "skipped": skipped, "repos": [
            {"repo": r["repo"], "type": r["type"],
             "drift": [m for lvl, m in r["findings"] if lvl == "drift"],
             "warnings": [m for lvl, m in r["findings"] if lvl == "warn"],
             "info": [m for lvl, m in r["findings"] if lvl == "info"]} for r in results]}
        print(json.dumps(out, indent=2))
    else:
        for r in results:
            label = "%s [%s]" % (r["repo"], r["type"] or "unknown")
            if not r["findings"]:
                print("%s: ok" % label)
                continue
            print(label)
            for lvl, m in r["findings"]:
                print("  %s: %s" % (lvl.upper() if lvl == "drift" else lvl, m))
        for n, why in sorted(skipped.items()):
            print("%s: %s" % (n, why))
        print("summary: %d audited, %d with drift (%d findings), %d warnings, %d skipped"
              % (summary["audited"], drifted, counts["drift"], counts["warn"], len(skipped)))
    return 1 if drifted else 0


def build_ruleset(existing, checks, include_codecov):
    statuses = [dict(c) for c in
                (next((r["parameters"]["required_status_checks"] for r in existing["rules"]
                       if r["type"] == "required_status_checks"), []) if existing else [])]
    have = {c["context"] for c in statuses}
    wanted = list(checks) + (CODECOV_CHECKS if include_codecov else [])
    for c in wanted:
        if c not in have:
            statuses.append({"context": c,
                             "integration_id": CODECOV_ID if c in CODECOV_CHECKS else ACTIONS_ID})
    old = {r["type"]: r.get("parameters") or {} for r in (existing["rules"] if existing else [])}
    pr = {k: old.get("pull_request", {}).get(k, v) for k, v in PR_DEFAULTS.items()}
    pr["required_approving_review_count"] = 0
    pr["allowed_merge_methods"] = ["squash"]
    sc = {"strict_required_status_checks_policy": True,
          "do_not_enforce_on_create": old.get("required_status_checks", {}).get("do_not_enforce_on_create", False),
          "required_status_checks": statuses}
    canonical = {"pull_request", "required_status_checks"} | set(SIMPLE_RULES)
    rules = [r for r in (existing["rules"] if existing else []) if r["type"] not in canonical]
    rules += [{"type": t} for t in SIMPLE_RULES]
    rules += [{"type": "pull_request", "parameters": pr},
              {"type": "required_status_checks", "parameters": sc}]
    return {
        "name": existing["name"] if existing else "main",
        "target": "branch",
        "enforcement": "active",
        "conditions": existing["conditions"] if existing else DEFAULT_CONDITIONS,
        "rules": rules,
    }


def run_call(method, path, body, dry_run):
    print("%s%s %s" % ("[dry-run] " if dry_run else "", method, path))
    if body is not None:
        print("  " + json.dumps(body, indent=2).replace("\n", "\n  "))
    if not dry_run:
        api(path, method, body)


def apply_repo(name, rtype, no_codecov, dry_run, fresh=False):
    """fresh=True means the repo was just created: skip reading current state."""
    checks, codecov_ok = required_checks(name, rtype)
    base = "repos/%s/%s" % (ORG, name)
    repo, existing = None, None
    if not fresh:
        repo = api(base)
        existing = find_ruleset(name)
    print("== %s [%s]" % (name, rtype))

    wanted = {k: v for k, v in REPO_OPTIONS.items() if k != "default_branch"}
    if repo is None or any(repo.get(k) != v for k, v in wanted.items()):
        run_call("PATCH", base, wanted, dry_run)
    run_call("PUT", base + "/vulnerability-alerts", None, dry_run)

    has_codecov = existing is not None and any(
        c["context"] in CODECOV_CHECKS
        for r in existing["rules"] if r["type"] == "required_status_checks"
        for c in r["parameters"]["required_status_checks"])
    include_codecov = codecov_ok and not no_codecov and (existing is None or has_codecov)
    body = build_ruleset(existing, checks, include_codecov)
    if existing is None:
        run_call("POST", base + "/rulesets", body, dry_run)
    elif [m for lvl, m in ruleset_findings(existing, checks, codecov_ok) if lvl == "drift"]:
        run_call("PUT", "%s/rulesets/%s" % (base, existing["id"]), body, dry_run)
    else:
        print("ruleset already matches")


def cmd_apply(args):
    names, skipped = audited_repos()
    if args.all:
        targets = [(n, infer_type(n)) for n in names]
    else:
        if args.repo in skipped:
            print("error: %s is %s" % (args.repo, skipped[args.repo]), file=sys.stderr)
            return 2
        rtype = args.type or infer_type(args.repo)
        targets = [(args.repo, rtype)]
    for name, rtype in targets:
        if name in SPECIAL:
            rtype = "special"
        if rtype is None or (rtype != "special" and rtype not in TYPES):
            msg = "unknown type for %s: pass --type (%s)" % (name, ", ".join(TYPES))
            if args.all:
                print("warning: " + msg)
                continue
            print("error: " + msg, file=sys.stderr)
            return 2
        apply_repo(name, rtype, args.no_codecov, args.dry_run)
    return 0


def cmd_new(args):
    if args.type not in TYPES:
        print("error: TYPE must be one of: %s" % ", ".join(TYPES), file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.name):
        print("error: invalid repo name", file=sys.stderr)
        return 2
    cmd = ["repo", "create", "%s/%s" % (ORG, args.name),
           "--template", "%s/%s" % (ORG, TYPES[args.type]["template"]),
           "--private" if args.private else "--public"]
    print("%sgh %s" % ("[dry-run] " if args.dry_run else "", " ".join(cmd)))
    if not args.dry_run:
        rc, out, err = gh(cmd)
        if rc != 0:
            print("error: " + err.strip(), file=sys.stderr)
            return 2
    apply_repo(args.name, args.type, args.no_codecov, args.dry_run, fresh=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="read-only drift report")
    a.add_argument("--repo")
    a.add_argument("--json", action="store_true")
    p = sub.add_parser("apply", help="set the standard settings on a repo or all repos")
    p.add_argument("repo", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--type", choices=sorted(TYPES))
    p.add_argument("--no-codecov", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    n = sub.add_parser("new", help="create a repo from a template and apply the settings")
    n.add_argument("name")
    n.add_argument("type")
    n.add_argument("--no-codecov", action="store_true")
    n.add_argument("--private", action="store_true")
    n.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.cmd == "apply" and bool(args.repo) == bool(args.all):
        ap.error("give either REPO or --all")
    rc, _, err = gh(["api", "rate_limit"])
    if rc != 0:
        print("error: gh is not authenticated (set GH_TOKEN or run gh auth login): " + err.strip(), file=sys.stderr)
        return 2
    try:
        return {"audit": cmd_audit, "apply": cmd_apply, "new": cmd_new}[args.cmd](args)
    except GhError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
