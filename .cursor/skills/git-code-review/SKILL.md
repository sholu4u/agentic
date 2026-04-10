---
name: git-code-review
description: >-
  Reviews a specific git commit by scanning its diff for common issues (TODO/FIXME,
  debug prints, and potential hardcoded credentials). Use when the user asks to
  review a commit, check a hash, or run a lightweight code review on recent changes.
---

# Git commit code review (lightweight)

## When to use

Use this skill when the user provides a **repo path** and **commit hash**, or asks you to review a specific commit.

## How to run

Run the local helper script and report the output (do not paste large diffs).

```bash
python scripts/code_review_tool.py --repo "<repo_path>" --commit "<commit_hash>"
```

## Rules for reporting

- Treat diffs as potentially sensitive; summarize issues rather than dumping the diff.
- If you see credential-like strings, recommend rotation/removal and sanitizing logs/artifacts before sharing.

