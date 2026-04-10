---
name: log-pii-safety
description: >-
  Enforces safe log handling—never overwrite originals; mask or pseudonymize PII
  in sanitized outputs. Use when sanitizing logs, redacting PII, preparing logs
  for sharing, or working with sensitive log data.
---

# Log PII and file safety

Read and follow this skill whenever the task touches log files that may contain sensitive data.

## File safety (`file_safety`)

- Never overwrite original input files.
- Always write sanitized output to a **new** path (e.g. `_redacted` suffix, a dedicated output directory, or an explicit output path/flag).

## PII handling (`pii_handling`)

- Always mask or pseudonymize sensitive data before sharing, committing, or publishing logs.
- Prefer **masking** unless **correlation** across lines or events is required; then use **stable pseudonyms** so the same entity maps consistently in the redacted file.

## Workflow reminder

1. Choose a new output path before writing.
2. Apply redaction (masking or pseudonyms as needed).
3. Verify the original file is unchanged.
