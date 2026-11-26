#!/usr/bin/env python3
"""PreToolUse guard for Bash calls made by the flowscripter agents.

Blocks (exit 2, reason on stderr, which Claude sees):
  1. merging a PR: `gh pr merge` (including --auto), `gh api .../pulls/N/merge`,
     GraphQL mergePullRequest / enablePullRequestAutoMerge
  2. `git push` to a protected branch (main, master), or with --all / --mirror
  3. GitHub writes (gh write subcommands, non-GET `gh api`, `git push`) whose
     target owner is not flowscripter, or cannot be worked out

Reads are never blocked. Nick's own `! <cmd>` lines don't go through hooks.
"""

import json
import os
import re
import shlex
import subprocess
import sys

OWNER = "flowscripter"
PROJECT_ID = "PVT_kwDOAmWn-s4BlVVW"
PROTECTED = {"main", "master", "v1"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&"}
PREFIXES = {"rtk", "env", "command", "nohup", "time", "exec"}
SHELLS = {"bash", "sh", "zsh"}

GH_WRITES = {
    "issue": {"create", "comment", "edit", "close", "reopen", "delete", "transfer",
              "pin", "unpin", "lock", "unlock", "develop"},
    "pr": {"create", "comment", "edit", "close", "reopen", "ready", "review",
           "merge", "update-branch", "lock", "unlock"},
    "release": {"create", "edit", "delete", "delete-asset", "upload"},
    "repo": {"create", "edit", "delete", "fork", "rename", "archive", "unarchive",
             "sync", "set-default", "deploy-key"},
    "label": {"create", "edit", "delete", "clone"},
    "run": {"rerun", "cancel", "delete"},
    "workflow": {"run", "enable", "disable"},
    "secret": {"set", "delete"},
    "variable": {"set", "delete"},
    "cache": {"delete"},
    "ruleset": set(),
    "project": {"create", "edit", "delete", "close", "copy", "link", "unlink",
                "mark-template", "field-create", "field-delete", "item-add",
                "item-archive", "item-create", "item-delete", "item-edit"},
    "gist": {"create", "edit", "delete", "clone", "rename"},
}
GRAPHQL_MUTATION_ALLOW = {
    "updateProjectV2ItemFieldValue", "addProjectV2ItemById",
    "addSubIssue", "removeSubIssue", "reprioritizeSubIssue",
    "addBlockedBy", "removeBlockedBy",
}


class Blocked(Exception):
    pass


def run_git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def owner_of(spec):
    """Owner from 'owner/repo', 'HOST/owner/repo', a github URL or a git remote URL."""
    s = re.sub(r"^(https?://|ssh://)?(git@)?", "", spec)
    s = re.sub(r"^github\.com[:/]", "", s)
    parts = [p for p in s.split("/") if p]
    return parts[0].lower() if len(parts) >= 2 else None


def remote_owners(cwd):
    names = run_git(cwd, "remote").split()
    return {owner_of(run_git(cwd, "remote", "get-url", "--push", n)) for n in names}


REDIRECT = re.compile(r"^\d*(>>?|<|>\|)$")
REDIRECT_JOINED = re.compile(r"^\d*(>>?|<)\S")


def drop_redirections(argv):
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
        elif REDIRECT.match(a):
            skip = True
        elif not REDIRECT_JOINED.match(a):
            out.append(a)
    return out


def split_commands(command):
    command = re.sub(r"\d*>&\d*-?|&>>?", " > ", command)
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    cmds, cur = [], []
    for tok in lex:
        if tok in SEPARATORS or set(tok) <= set(";&|()\n"):
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        cmds.append(cur)
    return cmds


def strip_prefixes(argv):
    while argv:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", argv[0]) or argv[0] in PREFIXES:
            argv = argv[1:]
        elif argv[0] == "timeout" and len(argv) > 1:
            argv = argv[2:]
        else:
            break
    return argv


def opt(argv, *names):
    for i, a in enumerate(argv):
        for n in names:
            if a == n and i + 1 < len(argv):
                return argv[i + 1]
            if n.startswith("--") and a.startswith(n + "="):
                return a.split("=", 1)[1]
    return None


def check_git(argv, cwd):
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] == "-C" and i + 1 < len(argv):
            cwd = os.path.join(cwd, argv[i + 1])
            i += 2
        elif argv[i] == "-c":
            i += 2
        else:
            i += 1
    if i >= len(argv) or argv[i] != "push":
        return
    args = argv[i + 1:]
    if any(a in ("--all", "--mirror") for a in args):
        raise Blocked("git push --all/--mirror is not allowed")
    flags_with_value = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}
    pos, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif a in flags_with_value:
            skip = True
        elif not a.startswith("-"):
            pos.append(a)
    remote = pos[0] if pos else (run_git(cwd, "config", f"branch.{run_git(cwd, 'branch', '--show-current')}.pushRemote")
                                 or run_git(cwd, "config", "remote.pushDefault") or "origin")
    url = run_git(cwd, "remote", "get-url", "--push", remote) if not re.search(r"[:/]", remote) else remote
    if owner_of(url or "") != OWNER:
        raise Blocked(f"git push to remote '{remote}' ({url or 'unknown url'}): owner is not {OWNER}")
    if re.match(r"^(git@|ssh://)", url):
        raise Blocked(f"git push over SSH ({url}) would authenticate with Nick's SSH key, not the machine account token; "
                      "push to the https:// URL instead")
    refspecs = pos[1:]
    if not refspecs:
        dest = run_git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}")
        dest = dest.split("/", 1)[1] if "/" in dest else run_git(cwd, "branch", "--show-current")
        refspecs = [dest or "HEAD"]
    for spec in refspecs:
        dst = spec.lstrip("+").split(":")[-1]
        if dst == "HEAD":
            dst = run_git(cwd, "branch", "--show-current")
        dst = re.sub(r"^refs/heads/", "", dst)
        if dst in PROTECTED or not dst:
            raise Blocked(f"git push to protected branch '{dst or '(detached/unknown)'}' is not allowed; push a feature branch and open a PR")


def check_gh_api(args, cwd):
    method = (opt(args, "-X", "--method") or "").upper()
    has_fields = any(a in ("-f", "-F", "--field", "--raw-field", "--input") or
                     re.match(r"^--(raw-)?field=|^--input=", a) for a in args)
    write = method not in ("", "GET", "HEAD") or (method == "" and has_fields)
    pos, skip = [], False
    takes_value = {"-X", "--method", "-H", "--header", "-f", "-F", "--field",
                   "--raw-field", "--input", "-q", "--jq", "-t", "--template",
                   "--hostname", "--cache", "-p", "--preview"}
    for a in args:
        if skip:
            skip = False
        elif a in takes_value:
            skip = True
        elif not a.startswith("-"):
            pos.append(a)
    path = (pos[0] if pos else "").lstrip("/")
    if path == "graphql":
        body = " ".join(args)
        if re.search(r"\b(mergePullRequest|enablePullRequestAutoMerge)\b", body):
            raise Blocked("merging PRs (GraphQL) is not allowed; Nick merges")
        if re.search(r"\bmutation\b", body):
            names = set(re.findall(r"\b([a-z][A-Za-z0-9]+)\s*\(\s*input\s*:", body))
            if not names or not names <= GRAPHQL_MUTATION_ALLOW:
                raise Blocked(f"GraphQL mutation not on the allowlist: {sorted(names) or 'unparsed'}")
        return
    if re.search(r"(^|/)pulls/\d+/merge$", path) and write:
        raise Blocked("merging PRs via the API is not allowed; Nick merges")
    if not write:
        return
    m = re.match(r"^(repos|orgs)/([^/{}]+)/", path + "/")
    if not m or m.group(2).lower() != OWNER:
        raise Blocked(f"gh api write to '{path}': target owner is not {OWNER}")


def check_gh(argv, cwd):
    args = argv[1:]
    if not args:
        return
    group = args[0]
    if group == "api":
        return check_gh_api(args[1:], cwd)
    sub = args[1] if len(args) > 1 else ""
    if group == "pr" and sub == "merge":
        flags = set(args[2:])
        if "--admin" in flags or not flags & {"--auto", "--disable-auto"}:
            raise Blocked("only gh pr merge --auto (or --disable-auto) is allowed: GitHub then merges after Nick approves")
    if group not in GH_WRITES:
        return
    if GH_WRITES[group] and sub not in GH_WRITES[group]:
        return
    if group == "gist":
        raise Blocked("gists are owned by the user account, not flowscripter")
    if group == "project":
        owner = opt(args, "--owner")
        pid = opt(args, "--project-id")
        if (owner and owner.lower() == OWNER) or pid == PROJECT_ID:
            return
        raise Blocked(f"gh project write must use --owner {OWNER} or --project-id {PROJECT_ID}")
    repo = opt(args, "-R", "--repo")
    if group == "repo" and not repo:
        cand = [a for a in args[2:] if not a.startswith("-")]
        repo = cand[0] if cand else None
        if sub == "fork":
            raise Blocked("gh repo fork is not allowed")
    if not repo:
        cand = [a for a in args[2:] if a.startswith("https://github.com/")]
        repo = cand[0] if cand else None
    if repo:
        if owner_of(repo) != OWNER:
            raise Blocked(f"gh {group} {sub} targets '{repo}': owner is not {OWNER}")
        return
    owners = remote_owners(cwd)
    if owners != {OWNER}:
        raise Blocked(f"gh {group} {sub} without -R in a checkout whose remotes are {sorted(o or '?' for o in owners) or 'none'}; pass -R {OWNER}/<repo>")


HEREDOC = re.compile(
    r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)(?:\n[ \t]*\2[ \t]*(?=\n|$)|\Z)", re.S)


def strip_heredocs(command):
    """Removes heredoc bodies; returns (command, bodies whose substitutions still expand)."""
    expanding = []

    def keep_head(m):
        if not m.group(1):
            expanding.append(m.group(3))
        return m.group(0)[:m.start(3) - m.start(0)].rstrip("\n") + "\n"
    return HEREDOC.sub(keep_head, command), expanding


def substitutions(text):
    """Bodies of $(...) and backticks outside single quotes."""
    unquoted = re.sub(r"'[^']*'", "''", text)
    return [a or b for a, b in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", unquoted)]


def check(command, cwd, depth=0):
    if depth > 3:
        raise Blocked("nested shell too deep to check")
    command, bodies = strip_heredocs(command)
    for text in [command] + bodies:
        for inner in substitutions(text):
            check(inner, cwd, depth + 1)
    try:
        cmds = split_commands(command)
    except ValueError:
        if re.search(r"\b(gh|git)\b", command):
            raise Blocked("command could not be parsed; simplify the quoting")
        return
    for argv in cmds:
        argv = strip_prefixes(drop_redirections(argv))
        if not argv:
            continue
        name = os.path.basename(argv[0])
        if name == "cd" and len(argv) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(argv[1]))
        elif name in SHELLS and "-c" in argv:
            idx = argv.index("-c")
            if idx + 1 < len(argv):
                check(argv[idx + 1], cwd, depth + 1)
        elif name == "eval":
            check(" ".join(argv[1:]), cwd, depth + 1)
        elif name == "xargs" and any(os.path.basename(a) in ("gh", "git") for a in argv):
            raise Blocked("gh/git through xargs can't be checked; run the commands directly")
        elif name == "git":
            check_git(argv, cwd)
        elif name == "gh":
            check_gh(argv, cwd)


def main():
    data = json.load(sys.stdin)
    if data.get("tool_name") != "Bash":
        return 0
    command = data.get("tool_input", {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()
    try:
        check(command, cwd)
    except Blocked as e:
        print(f"Blocked by flowscripter guard: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
