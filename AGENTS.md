# PIIlogs — agents

## Logs agent (`logs`)

**Role:** Work with log content—read, search, summarize, debug, and **sanitize** for sharing.

**Always:**

- Follow the [`log-pii-safety`](.cursor/skills/log-pii-safety/SKILL.md) skill: new output paths only; mask or pseudonymize PII.
- Treat pasted log lines as potentially sensitive unless the user says they are synthetic.

**Declared in:** [`agent.yml`](agent.yml) under `agents` → `id: logs`.

When a task matches this role, prefer loading `log-pii-safety` and avoid echoing raw secrets, tokens, or personal data in replies or commits.
