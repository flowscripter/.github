---
name: flowscripter-verify
description: Verification stage of the flowscripter loop. For one issue whose PRs are merged, released and cascaded, installs the released build, checks each acceptance criterion itself, and posts the verification comment with results and the steps for Nick. Invoked by the main session for a [verify] item from the sweep report.
model: sonnet
context: fork
agent: general-purpose
---

You verify ONE issue `<repo>#<n>` (a parent intent or a standalone issue). The sweep has already confirmed every referencing PR is merged, released, and cascaded to the end product. Read `../flowscripter-sweep/rules.md` (relative to this skill) and `docs/stages.md` in the `flowscripter/.github` checkout.

## Steps

1. Collect: the acceptance criteria (spec.md if there is one, otherwise the issue form), the merged PRs, and the released versions (release tag, npm `dist-tags.latest`, Homebrew formula version, downstream bump).
2. Install the released build in a scratch directory, never from a local checkout: `bunx <pkg>@<version>` / `npm view` for libraries, the release zip or `brew install flowscripter/tap/<name>` for executables. Confirm the installed version matches the released one.
3. For each acceptance criterion, run the check that shows it: the command, its output (trimmed), PASS or FAIL. Where a criterion can't be checked here (Windows, macOS signing, winget), mark it `NICK` with exact steps.
4. Check the distillation happened: the durable files named in the plan were updated in the merged PRs. Missing ones are a FAIL.

## Post

ONE comment on the issue: what was fixed, the merged PRs, released versions, the per-criterion table (criterion, how checked, result), and for Nick the exact commands to repeat the check plus the `NICK` items. End with `<!-- flowscripter-agent:v1 -->`. Update the pinned `<!-- flowscripter-spec:v1 -->` comment's stage line if there is one.

## Report

```
VERIFY <repo>#<n>
RESULT: <all pass | fail: criteria ...>
COMMENT: <url>
NEXT: <Verification (Nick tests NICK items) | In Progress [fix]: what failed>
```

The main session moves the card: all PASS -> Verification; any FAIL -> In Progress and dispatches `flowscripter-implement` with the failure.
