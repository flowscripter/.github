#!/usr/bin/env python3
"""Claude Code WorktreeCreate / WorktreeRemove hook for flowscripter repos.

Worktrees for repos whose origin is github.com/flowscripter/* go under
~/projects/flowscripter/worktrees/<repo>/<name>, on a new branch claude/<name>
from origin/<default branch>, so they can be opened from a remote VS Code.
For any other repo it prints nothing, and Claude Code creates the worktree as usual.

  worktree.py create    (WorktreeCreate)
  worktree.py remove    (WorktreeRemove; never forces, so uncommitted work is kept)
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.expanduser("~/projects/flowscripter/worktrees")


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)


def flowscripter_repo(cwd):
    top = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if top.returncode != 0:
        return None, None
    main = os.path.dirname(top.stdout.strip())
    url = git(main, "remote", "get-url", "origin").stdout.strip()
    m = re.search(r"github\.com[:/]flowscripter/([^/]+?)(\.git)?$", url)
    return (main, m.group(1)) if m else (None, None)


def create(data):
    main, repo = flowscripter_repo(data.get("cwd") or os.getcwd())
    if not repo:
        return 0
    name = data["name"]
    path = os.path.join(ROOT, repo, name)
    git(main, "fetch", "-q", "origin")
    head = git(main, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").stdout.strip() or "origin/main"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = git(main, "worktree", "add", "-q", "-b", "claude/" + name, path, head)
    if r.returncode != 0:
        print("worktree add failed: " + r.stderr.strip(), file=sys.stderr)
        return 2
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "WorktreeCreate", "worktreePath": path}}))
    return 0


def remove(data):
    path = os.path.realpath(data.get("worktree_path") or "")
    if not path.startswith(os.path.realpath(ROOT) + os.sep) or not os.path.isdir(path):
        return 0
    r = git(path, "worktree", "remove", path)
    if r.returncode != 0:
        print("kept %s: %s" % (path, r.stderr.strip()), file=sys.stderr)
    return 0


if __name__ == "__main__":
    data = json.load(sys.stdin)
    sys.exit({"create": create, "remove": remove}[sys.argv[1]](data))
