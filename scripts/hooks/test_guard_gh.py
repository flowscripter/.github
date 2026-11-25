#!/usr/bin/env python3
"""Runs guard-gh.py against fixture repos. Usage: python3 -I test_guard_gh.py"""

import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-gh.py")


def make_repo(root, name, remotes, branch):
    path = os.path.join(root, name)
    os.makedirs(path)
    git = lambda *a: subprocess.run(["git", "-C", path, *a], check=True, capture_output=True)
    git("init", "-q", "-b", branch)
    for rname, url in remotes.items():
        git("remote", "add", rname, url)
    return path


def run(cmd, cwd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd})
    p = subprocess.run([sys.executable, "-I", HOOK], input=payload, capture_output=True, text=True)
    return p.returncode, p.stderr.strip()


def main():
    root = tempfile.mkdtemp()
    fs = make_repo(root, "fs", {"origin": "https://github.com/flowscripter/example-cli.git"}, "feat-x")
    fs_main = make_repo(root, "fsmain", {"origin": "git@github.com:flowscripter/example-cli.git"}, "main")
    fork = make_repo(root, "fork", {"origin": "https://github.com/flowscripter/winget-pkgs.git",
                                    "upstream": "https://github.com/microsoft/winget-pkgs.git"}, "feat-x")

    cases = [
        # (cwd, command, expect_blocked)
        (fs, "gh pr merge 12 --squash", True),
        (fs, "rtk gh pr merge 12 --auto", True),
        (fs, "cd /tmp && gh pr merge 3", True),
        (fs, "gh api -X PUT repos/flowscripter/example-cli/pulls/4/merge", True),
        (fs, "gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"x\"}) { clientMutationId } }'", True),
        (fs, "bash -c 'gh pr merge 5'", True),
        (fs, "echo $(gh pr merge 5)", True),
        (fs, "git push origin main", True),
        (fs, "git push origin HEAD:main", True),
        (fs, "git push origin +feat-x:refs/heads/main", True),
        (fs, "git push origin HEAD:refs/heads/v1", True),
        (fs, "git push --all origin", True),
        (fs_main, "git push", True),
        (fs_main, "git push origin HEAD", True),
        (fs, "git push https://github.com/someone/else.git feat-x", True),
        (fs, "gh issue comment 5 -R microsoft/winget-pkgs --body hi", True),
        (fs, "gh pr create --repo microsoft/winget-pkgs --title t --body b", True),
        (fork, "gh pr create --title t --body b", True),
        (fs, "gh api -X POST repos/microsoft/winget-pkgs/issues/1/comments -f body=x", True),
        (fs, "gh api repos/microsoft/winget-pkgs/issues/1/comments -f body=x", True),
        (fs, "gh repo fork flowscripter/example-cli", True),
        (fs, "gh gist create notes.md", True),
        (fs, "gh project item-edit --id X --project-id PVT_other --field-id F", True),
        (fs, "gh issue comment 5 --body \"unterminated", True),
        # allowed
        (fs, "gh pr view 12 -R microsoft/winget-pkgs --json state", False),
        (fs, "gh pr list -R microsoft/winget-pkgs --author vectronic --state open", False),
        (fs, "gh api repos/microsoft/winget-pkgs/pulls/449796", False),
        (fs, "gh api repos/flowscripter/example-cli/pulls/4/reviews", False),
        (fs, "git push -u origin feat-x", False),
        (fs, "git push origin HEAD", False),
        (fs, "cd sub; git status && git log --oneline | head", False),
        (fs, "gh pr create -R flowscripter/example-cli --title 'fix: x' --body-file b.md", False),
        (fs, "gh pr create --title 'fix: x' --body-file b.md", False),
        (fs, "gh issue comment https://github.com/flowscripter/example-cli/issues/5 --body-file c.md", False),
        (fs, "gh api -X POST repos/flowscripter/example-cli/issues/5/assignees -f 'assignees[]=vectronic'", False),
        (fs, "gh api -X PUT repos/flowscripter/example-cli/pulls/4/update-branch", False),
        (fs, "gh api -X POST repos/flowscripter/example-cli/issues/5/sub_issues -F sub_issue_id=123", False),
        (fs, "gh project item-edit --id X --project-id PVT_kwDOAmWn-s4BlVVW --field-id F --single-select-option-id O", False),
        (fs, "gh project item-add 4 --owner flowscripter --url https://github.com/flowscripter/example-cli/issues/5", False),
        (fs, "gh run rerun 123 --failed -R flowscripter/example-cli", False),
        (fs, "gh api graphql -f query='query { viewer { login } }'", False),
        (fs, "echo 'git push origin main is documented here'", False),
        (fs, "printf 'docs mention `gh pr merge` here' > body.md", False),
        (fs, "python3 - <<'EOF'\nprint('git push origin main')\ngh pr merge 3\nEOF\necho done", False),
        (fs, "cat <<EOF > f\n$(gh pr merge 3)\nEOF", True),
        (fs, "cat <<'EOF' > f\ntext\nEOF\ngh pr merge 3", True),
        (fs, "echo \"`gh pr merge 3`\"", True),
    ]
    failures = 0
    for cwd, cmd, expect in cases:
        code, err = run(cmd, cwd)
        blocked = code == 2
        ok = blocked == expect
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {'BLOCK' if blocked else 'allow'} {cmd}" + (f"  [{err}]" if blocked and not ok else ""))
        if code not in (0, 2):
            print("     unexpected exit", code, err)
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
