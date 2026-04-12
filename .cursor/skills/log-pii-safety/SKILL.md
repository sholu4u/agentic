---
name: pii-sanitizer
description: >-
  Masks or pseudonymizes sensitive data (emails, phone numbers, API keys,
  passwords, secrets) before code review. Ensures sanitized output is written
  to a new file path.
---

# PII Sanitizer

## When to use
- Before sending code to an LLM reviewer.
- When preparing code for sharing or committing.

## How to run
```bash
python scripts/pii_sanitizer.py <input_file> <output_file>