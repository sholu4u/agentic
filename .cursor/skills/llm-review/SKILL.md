---
name: llm-code-review
description: >-
  Uses an LLM to review commit diffs or file contents for vulnerabilities,
  insecure patterns, and style issues. Complements regex-based scanning.
---

# LLM Code Review

## When to use
- After running the regex scanner (`git-code-review`) to catch hardcoded secrets.
- When the user asks for deeper review, vulnerabilities, or best practices.

## How to run
Run the helper script with repo path and commit hash:

```bash
python scripts/llm_review_tool.py --repo "<repo_path>" --commit "<commit_hash>"