#!/usr/bin/env python3
"""Mechanical parts of the flowscripter sweep, as JSON for the sweep skill.

  sweep.py scope [--days N]      in-scope repos
  sweep.py board                 project 4 Status field, options and items
  sweep.py thread REPO NUMBER    an issue and every PR referencing it, with comments.
                                 Text from untrusted authors is replaced by author, link and length.
  sweep.py transitions           deterministic board moves (see docs/stages.md)
  sweep.py release REPO          latest tag, package version and npm dist-tags.latest
  sweep.py metrics [FILE]        time per stage and fix round trips from transitions.jsonl

Judgement (what an ask means, whether a comment is a question, flakes) stays with the model.
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ORG = "flowscripter"
PROJECT = 4
PROJECT_ID = "PVT_kwDOAmWn-s4BlVVW"
NICK = "vectronic"
BOT = "vectronic-claude"
TRUSTED = {NICK, BOT}
MARKER = "<!-- flowscripter-agent:v1 -->"
SUBISSUE = re.compile(r"<!-- flowscripter-subissue:([^ ]+) -->")
BOT_ERA = "2026-10-01T00:00:00Z"
COMMAND = re.compile(r"(?m)^\s*/(approve|go|park|revise)\b(.*)$")
METRICS = os.path.expanduser("~/.local/state/flowscripter/transitions.jsonl")
GH_TIMEOUT = 120
REFS = re.compile(r"(?i)\brefs\s+(?:%s/([\w.-]+))?#(\d+)\b" % ORG)
PR_FIELDS = "number,state,title,url,body,isDraft"


def gh(*args):
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh %s timed out after %ss" % (" ".join(args[:3]), GH_TIMEOUT)) from None
    if p.returncode != 0:
        raise RuntimeError((p.stderr.strip().splitlines() or ["gh failed"])[0])
    return p.stdout


def gh_json(*args):
    return json.loads(gh(*args) or "null")


def gh_pages(path):
    """REST list endpoint, all pages, as one list."""
    out = gh("api", "--paginate", path, "--jq", ".[] | tojson")
    return [json.loads(line) for line in out.split("\n") if line.strip()]


# Pure functions: no I/O, covered by test_sweep.py.

def is_ours(c):
    """A comment counts as the bot's when the bot wrote it, or Nick's account wrote it with the marker before the bot account existed."""
    return c["author"] == BOT or (c["author"] == NICK and c["at"] < BOT_ERA and MARKER in (c.get("body") or ""))


def is_nicks(c):
    """Nick's comments and non-approving reviews. An approval is his merge, not an ask."""
    return c["author"] == NICK and not is_ours(c) and not (c.get("kind") == "review" and c.get("state") == "APPROVED")


def nick_review(comments):
    """Nick's newest submitted review: {state, at, url}, or None."""
    reviews = [c for c in comments if c["author"] == NICK and c.get("kind") == "review"]
    r = max(reviews, key=lambda c: c["at"], default=None)
    return {"state": r.get("state"), "at": r["at"], "url": r.get("url")} if r else None


def redact(c):
    """Untrusted text never reaches the model: keep who, where and how long."""
    if c["author"] in TRUSTED:
        return c
    return {"author": c["author"], "at": c["at"], "url": c.get("url"), "length": len(c.get("body") or ""),
            "untrusted": True}


def summarize(comments):
    """comments: issue and PR comments and reviews, each {author, at, body}. Returns the trust facts the transitions use."""
    ours = [c for c in comments if is_ours(c)]
    nicks = [c for c in comments if is_nicks(c)]
    last_ours = max((c["at"] for c in ours), default="")
    last_nick = max((c["at"] for c in nicks), default="")
    commands = []
    for c in sorted(nicks, key=lambda c: c["at"]):
        if c["at"] > last_ours:
            commands += [{"command": m.group(1), "detail": m.group(2).strip(), "at": c["at"], "url": c.get("url")}
                         for m in COMMAND.finditer(c.get("body") or "")]
    newest_ours = max(ours, key=lambda c: c["at"], default=None)
    decided = (newest_ours is not None and newest_ours["author"] == BOT
               and "Decided with Nick in session" in (newest_ours.get("body") or "")
               and newest_ours["at"] > last_nick)
    newest_nick = max(nicks, key=lambda c: c["at"], default=None)
    return {
        "bot_commented": bool(ours),
        "last_ours": last_ours or None,
        "last_nick": last_nick or None,
        "last_nick_url": newest_nick.get("url") if newest_nick else None,
        "nick_last_word": bool(last_nick) and last_nick > last_ours,
        "commands": commands,
        "latest_command": commands[-1]["command"] if commands else None,
        "decided_in_session": decided,
        "nick_review": nick_review(comments),
        "untrusted_authors": sorted({c["author"] for c in comments if c["author"] not in TRUSTED}),
    }


def subissue_parent(issue):
    """Parent ref for a bot-opened sub-issue, or None. Only the bot's own issues can carry the marker."""
    if issue["author"] != BOT:
        return None
    m = SUBISSUE.search(issue.get("body") or "")
    return m.group(1) if m else None


def transition(card, issue, facts):
    """Deterministic move for one issue, or None.

    card: {status} or None when the issue is not on the board.
    issue: {repo, number, author, state, body}.
    facts: summarize() output.
    Returns {to, report, reason}; to=None means no move, report is a needs-tag or None.
    """
    status = card["status"] if card else None
    sub = subissue_parent(issue)
    if issue["state"] != "OPEN":
        if status not in (None, "Done"):
            return {"to": "Done", "report": None, "reason": "issue closed"}
        return None
    if status == "Done":
        return {"to": None, "report": "decision", "reason": "card is Done but the issue is still open"}
    if facts["latest_command"] == "park" and status != "Backlog":
        return {"to": "Backlog", "report": None, "reason": "/park by Nick"}
    if status is None:
        if issue["author"] == NICK or sub:
            report = "pickup" if not facts["bot_commented"] or facts["nick_last_word"] else None
            return {"to": "Backlog", "report": report, "reason": "new issue" + (" (sub-issue of %s)" % sub if sub else "")}
        if issue["author"] == BOT:
            return {"to": "Review", "report": "fix" if facts["nick_last_word"] else None, "reason": "bot proposal"}
        return None
    if status == "Backlog":
        if facts["latest_command"] == "go" or not facts["bot_commented"]:
            return {"to": None, "report": "pickup", "reason": "/go" if facts["latest_command"] == "go" else "not picked up yet"}
        return None
    if status in ("Review", "Verification") and (facts["nick_last_word"] or facts["decided_in_session"]):
        cmd = facts["latest_command"]
        return {"to": "In Progress", "report": "fix" if status == "Verification" else (cmd or "fix"),
                "reason": "Nick has the last word" + (" (/%s)" % cmd if cmd else "")}
    return None


def pr_refs(pr_repo, body):
    """Issues a PR body references with Refs #N (its own repo) or Refs flowscripter/<repo>#N, as {(repo, n)}."""
    return {(m.group(1) or pr_repo, int(m.group(2))) for m in REFS.finditer(body or "")}


def index_refs(prs):
    """prs: [{repo, number, state, title, url, isDraft, body}]. Returns {(repo, n): [pr summary]} by referenced issue."""
    out = defaultdict(list)
    for p in prs:
        for ref in sorted(pr_refs(p["repo"], p.get("body"))):
            out[ref].append({"repo": p["repo"], "number": p["number"], "state": p["state"].upper(),
                             "title": p["title"], "url": p["url"], "draft": p.get("isDraft", False)})
    return out


def stage_metrics(lines):
    """lines: transitions.jsonl records. Returns seconds per stage and fix round trips per issue."""
    by_issue = defaultdict(list)
    for r in lines:
        by_issue[r["issue"]].append(r)
    per_stage = defaultdict(list)
    round_trips = {}
    for issue, rs in by_issue.items():
        rs.sort(key=lambda r: r["ts"])
        for a, b in zip(rs, rs[1:]):
            dt = (parse_ts(b["ts"]) - parse_ts(a["ts"])).total_seconds()
            per_stage[a["to"]].append(dt)
        round_trips[issue] = sum(1 for r in rs if r["from"] in ("Review", "Verification") and r["to"] == "In Progress")
    return {
        "stage_seconds_median": {s: sorted(v)[len(v) // 2] for s, v in per_stage.items()},
        "stage_samples": {s: len(v) for s, v in per_stage.items()},
        "fix_round_trips": round_trips,
    }


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# I/O.

def cmd_scope(days=45):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    repos = gh_json("repo", "list", ORG, "--limit", "200", "--no-archived", "--json", "name,pushedAt,isFork")
    out = []
    for r in repos:
        if r["isFork"]:
            continue
        reason = "pushed since %s" % since[:10] if r["pushedAt"] >= since else None
        if not reason:
            n = gh_json("issue", "list", "-R", "%s/%s" % (ORG, r["name"]), "--state", "open", "--limit", "1",
                        "--search", "author:%s author:%s" % (NICK, BOT), "--json", "number")
            reason = "open trusted issue" if n else None
        if reason:
            out.append({"name": r["name"], "pushedAt": r["pushedAt"], "reason": reason})
    return sorted(out, key=lambda r: r["name"])


def cmd_board():
    fields = gh_json("project", "field-list", str(PROJECT), "--owner", ORG, "--format", "json")["fields"]
    status = next(f for f in fields if f["name"] == "Status")
    items = gh_json("project", "item-list", str(PROJECT), "--owner", ORG, "--format", "json", "--limit", "1000")["items"]
    cards = []
    for it in items:
        c = it.get("content") or {}
        if c.get("type") != "Issue":
            continue
        cards.append({"item_id": it["id"], "repo": c["repository"].split("/")[-1], "number": c["number"],
                      "url": c["url"], "status": it.get("status")})
    return {"project_id": PROJECT_ID, "status_field_id": status["id"],
            "options": {o["name"]: o["id"] for o in status["options"]}, "cards": cards}


def issue_comments(repo, number):
    base = "repos/%s/%s/issues/%s/comments?per_page=100" % (ORG, repo, number)
    return [{"author": c["user"]["login"], "at": c["created_at"], "body": c["body"], "url": c["html_url"], "kind": "comment"}
            for c in gh_pages(base)]


def pr_activity(repo, number):
    out = issue_comments(repo, number)
    for r in gh_pages("repos/%s/%s/pulls/%s/reviews?per_page=100" % (ORG, repo, number)):
        if r.get("submitted_at"):
            out.append({"author": r["user"]["login"], "at": r["submitted_at"], "body": r.get("body") or "",
                        "url": r["html_url"], "kind": "review", "state": r["state"]})
    for c in gh_pages("repos/%s/%s/pulls/%s/comments?per_page=100" % (ORG, repo, number)):
        out.append({"author": c["user"]["login"], "at": c["created_at"], "body": c["body"], "url": c["html_url"],
                    "kind": "inline", "path": c.get("path"), "line": c.get("line"), "reply_to": c.get("in_reply_to_id")})
    return out


def referencing_prs(repo, number):
    """PRs in any flowscripter repo whose body has Refs #N (same repo) or Refs flowscripter/<repo>#N.

    Uses two search calls, so callers that look up many issues use repo_prs and index_refs instead.
    """
    found = [dict(p, repo=p["repository"]["name"]) for p in
             gh_json("search", "prs", "--owner", ORG, "%s#%s" % (repo, number), "--json",
                     "repository," + PR_FIELDS, "--limit", "100") or []]
    found += [dict(p, repo=repo) for p in
              gh_json("pr", "list", "-R", "%s/%s" % (ORG, repo), "--state", "all", "--search", "#%s" % number,
                      "--json", PR_FIELDS, "--limit", "100") or []]
    out, seen = [], set()
    for p in index_refs(found).get((repo, int(number)), []):
        if (p["repo"], p["number"]) not in seen:
            seen.add((p["repo"], p["number"]))
            out.append(p)
    return out


def repo_prs(repo):
    """Every PR in a repo, any state, listed without the search API."""
    return [dict(p, repo=repo) for p in
            gh_json("pr", "list", "-R", "%s/%s" % (ORG, repo), "--state", "all", "--limit", "1000",
                    "--json", PR_FIELDS) or []]


def cmd_thread(repo, number, refs=None):
    """refs: an index_refs() index to look up referencing PRs in, or None to search for them."""
    i = gh_json("api", "repos/%s/%s/issues/%s" % (ORG, repo, number))
    issue = {"repo": repo, "number": int(number), "title": i["title"], "author": i["user"]["login"],
             "state": i["state"].upper(), "url": i["html_url"], "body": i["body"] or ""}
    on_issue = issue_comments(repo, number)
    everything = list(on_issue)
    prs = referencing_prs(repo, number) if refs is None else [dict(p) for p in refs.get((repo, int(number)), [])]
    for p in prs:
        activity = pr_activity(p["repo"], p["number"])
        everything += activity
        p["activity"] = [redact(c) for c in activity]
    facts = summarize(everything)
    if issue["author"] not in TRUSTED:
        issue["body"] = None
    return {"issue": issue, "comments": [redact(c) for c in on_issue], "prs": prs, "facts": facts}


def cmd_transitions():
    board = cmd_board()
    cards = {(c["repo"], c["number"]): c for c in board["cards"]}
    moves = []
    seen = set()
    scope = [r["name"] for r in cmd_scope()]
    for repo in scope:
        for author in (NICK, BOT):
            for i in gh_json("issue", "list", "-R", "%s/%s" % (ORG, repo), "--state", "open", "--author", author,
                             "--limit", "200", "--json", "number") or []:
                seen.add((repo, i["number"]))
    for c in board["cards"]:
        if c["status"] != "Done":
            seen.add((c["repo"], c["number"]))
    prs = []
    for repo in sorted(set(scope) | {r for r, _ in seen}):
        prs += repo_prs(repo)
    refs = index_refs(prs)
    for repo, number in sorted(seen):
        t = cmd_thread(repo, number, refs)
        card = cards.get((repo, number))
        m = transition(card, t["issue"], t["facts"])
        if m:
            if m["to"]:
                m["option_id"] = next((oid for name, oid in board["options"].items()
                                       if name.casefold() == m["to"].casefold()), None)
            moves.append(dict(m, issue="%s#%s" % (repo, number), url=t["issue"]["url"],
                              **({"from": card["status"]} if card else {"from": None}),
                              item_id=card["item_id"] if card else None,
                              untrusted_authors=t["facts"]["untrusted_authors"]))
    return {"options": board["options"], "status_field_id": board["status_field_id"], "moves": moves}


def cmd_release(repo):
    out = {"repo": repo}
    try:
        out["latest_tag"] = gh_json("api", "repos/%s/%s/releases/latest" % (ORG, repo))["tag_name"]
    except RuntimeError:
        out["latest_tag"] = None
    try:
        pkg = json.loads(base64.b64decode(gh_json("api", "repos/%s/%s/contents/package.json" % (ORG, repo))["content"]))
        out["package"], out["version_on_main"] = pkg.get("name"), pkg.get("version")
        if pkg.get("name") and not pkg.get("private"):
            url = "https://registry.npmjs.org/-/package/%s/dist-tags" % pkg["name"].replace("/", "%2F")
            with urllib.request.urlopen(url, timeout=15) as r:
                out["npm_latest"] = json.load(r).get("latest")
    except (RuntimeError, OSError, ValueError, KeyError):
        pass
    return out


def cmd_metrics(path=METRICS):
    if not os.path.exists(path):
        return {"error": "no metrics file at %s" % path}
    with open(path) as f:
        return stage_metrics([json.loads(line) for line in f if line.strip()])


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "scope":
        res = cmd_scope(int(args[1]) if args[:1] == ["--days"] else 45)
    elif cmd == "board":
        res = cmd_board()
    elif cmd == "thread" and len(args) == 2:
        res = cmd_thread(*args)
    elif cmd == "transitions":
        res = cmd_transitions()
    elif cmd == "release" and len(args) == 1:
        res = cmd_release(args[0])
    elif cmd == "metrics":
        res = cmd_metrics(*args[:1])
    else:
        print(__doc__)
        return 2
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
