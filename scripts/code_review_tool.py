import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReviewResult:
    commit: str
    issues: list[str]


_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
_SENSITIVE_KEY_RE = re.compile(r"(?i)\b(password|secret|api[_-]?key)\b")


def _candidate_git_paths() -> list[str]:
    candidates: list[str] = []
    which = shutil.which("git")
    if which:
        candidates.append(which)

    for base in (Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")):
        candidates.append(str(base / "Git" / "cmd" / "git.exe"))

    candidates.append(
        str(Path.home() / "AppData" / "Local" / "Programs" / "Git" / "cmd" / "git.exe")
    )

    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _resolve_git_exe() -> str:
    for candidate in _candidate_git_paths():
        if candidate and Path(candidate).exists():
            return candidate
    return "git"


def _run_git(repo_path: str, args: list[str]) -> str:
    git_exe = _resolve_git_exe()
    try:
        return subprocess.check_output(
            [git_exe, "-C", repo_path, *args],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as e:
        tried = _candidate_git_paths()
        hint = ""
        if tried:
            hint = f" Tried: {', '.join(tried[:4])}" + (" ..." if len(tried) > 4 else "")
        raise RuntimeError("git is not installed or not on PATH." + hint) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.output.strip() or f"git failed: {' '.join(args)}") from e


def _iter_added_lines(diff_text: str) -> list[tuple[str, str]]:
    current_file = "<unknown>"
    added: list[tuple[str, str]] = []
    for raw in diff_text.splitlines():
        m = _DIFF_FILE_RE.match(raw)
        if m:
            current_file = m.group(1)
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append((current_file, raw[1:]))
    return added


def _redact_assignment(line: str) -> str:
    return re.sub(
        r"(?i)\b(password|secret|api[_-]?key)\b(\s*[:=]\s*)(.+)$",
        lambda m: f"{m.group(1)}{m.group(2)}***",
        line,
    )


def _credential_findings_from_added_lines(diff_text: str) -> list[str]:
    findings: list[str] = []
    for file, line in _iter_added_lines(diff_text):
        if _SENSITIVE_KEY_RE.search(line):
            findings.append(f"{file}: {_redact_assignment(line).strip()}")

    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _changed_files(repo_path: str, commit_hash: str) -> list[str]:
    _run_git(repo_path, ["rev-parse", "--verify", commit_hash])
    out = _run_git(repo_path, ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash])
    return [line.strip() for line in out.splitlines() if line.strip()]


def _file_text_at_commit(repo_path: str, commit_hash: str, file_path: str) -> str:
    return _run_git(repo_path, ["show", "--text", f"{commit_hash}:{file_path}"])


def _credential_findings_from_content(repo_path: str, commit_hash: str) -> list[str]:
    findings: list[str] = []
    for file_path in _changed_files(repo_path, commit_hash):
        try:
            text = _file_text_at_commit(repo_path, commit_hash, file_path)
        except RuntimeError:
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            if _SENSITIVE_KEY_RE.search(line):
                findings.append(f"{file_path}:{i}: {_redact_assignment(line).strip()}")

    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _get_diff(repo_path: str, commit_hash: str) -> str:
    _run_git(repo_path, ["rev-parse", "--verify", commit_hash])
    return _run_git(
        repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash]
    )


def code_review_tool(repo_path: str, commit_hash: str) -> ReviewResult:
    diff = _get_diff(repo_path, commit_hash)

    issues: list[str] = []

    if "TODO" in diff or "FIXME" in diff:
        issues.append("Found TODO/FIXME comments in code.")

    if re.search(r"(?m)^\+?\s*print\b", diff):
        issues.append("Found debug print statements.")

    creds = _credential_findings_from_added_lines(diff)
    if not creds:
        creds = _credential_findings_from_content(repo_path, commit_hash)

    if creds:
        issues.append(
            "Potential hardcoded credential detected (redacted):\n  - "
            + "\n  - ".join(creds[:20])
            + ("\n  - ... (truncated)" if len(creds) > 20 else "")
        )

    return ReviewResult(commit=commit_hash, issues=issues)


def _format_result(result: ReviewResult) -> str:
    if not result.issues:
        return f"No issues found in commit {result.commit}."
    return "Issues in commit {}:\n- {}".format(result.commit, "\n- ".join(result.issues))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight checks against a git commit diff.")
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to review")
    args = parser.parse_args()

    try:
        result = code_review_tool(args.repo, args.commit)
        print(_format_result(result))
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ReviewResult:
    commit: str
    issues: list[str]

_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")

# Patterns for credentials and PII
PII_PATTERNS = {
    "password": re.compile(r"(?i)\bpassword\b"),
    "secret": re.compile(r"(?i)\bsecret\b"),
    "api_key": re.compile(r"(?i)\bapi[_-]?key\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\+?\d{10,15}"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}

def _iter_added_lines(diff_text: str) -> list[tuple[str, str]]:
    current_file = "<unknown>"
    added: list[tuple[str, str]] = []
    for raw in diff_text.splitlines():
        m = _DIFF_FILE_RE.match(raw)
        if m:
            current_file = m.group(1)
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append((current_file, raw[1:]))
    return added

def _redact_assignment(line: str) -> str:
    return re.sub(
        r"(?i)\b(password|secret|api[_-]?key)\b(\s*[:=]\s*)(.+)$",
        lambda m: f"{m.group(1)}{m.group(2)}***",
        line,
    )

def _pii_findings(file: str, line: str) -> list[str]:
    findings = []
    for category, pattern in PII_PATTERNS.items():
        if pattern.search(line):
            if category in ("password", "secret", "api_key"):
                findings.append(f"{file}: {_redact_assignment(line).strip()}")
            else:
                findings.append(f"{file}: {category} detected → [REDACTED]")
    return findings

def _credential_findings(diff_text: str) -> list[str]:
    findings: list[str] = []
    for file, line in _iter_added_lines(diff_text):
        findings.extend(_pii_findings(file, line))
    # De-dupe
    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out

def _changed_files(repo_path: str, commit_hash: str) -> list[str]:
    _run_git(repo_path, ["rev-parse", "--verify", commit_hash])
    out = _run_git(repo_path, ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash])
    return [line.strip() for line in out.splitlines() if line.strip()]

def _file_text_at_commit(repo_path: str, commit_hash: str, file_path: str) -> str:
    return _run_git(repo_path, ["show", "--text", f"{commit_hash}:{file_path}"])

def _credential_findings_from_content(repo_path: str, commit_hash: str) -> list[str]:
    findings: list[str] = []
    for file_path in _changed_files(repo_path, commit_hash):
        try:
            text = _file_text_at_commit(repo_path, commit_hash, file_path)
        except RuntimeError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for f in _pii_findings(file_path, line):
                findings.append(f"{file_path}:{i}: {f}")
    # De-dupe
    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out

def _resolve_git_exe() -> str:
    git_exe = shutil.which("git")
    if git_exe:
        return git_exe
    raise RuntimeError("git is not installed or not on PATH.")

def _run_git(repo_path: str, args: list[str]) -> str:
    git_exe = _resolve_git_exe()
    try:
        return subprocess.check_output(
            [git_exe, "-C", repo_path, *args],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.output.strip() or f"git failed: {' '.join(args)}") from e

def _get_diff(repo_path: str, commit_hash: str) -> str:
    _run_git(repo_path, ["rev-parse", "--verify", commit_hash])
    parents_line = _run_git(repo_path, ["rev-list", "--parents", "-n", "1", commit_hash]).strip()
    parts = parents_line.split()
    has_parent = len(parts) > 1
    if has_parent:
        return _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])
    return _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])

def code_review_tool(repo_path: str, commit_hash: str) -> ReviewResult:
    diff = _get_diff(repo_path, commit_hash)
    issues: list[str] = []
    if "TODO" in diff or "FIXME" in diff:
        issues.append("Found TODO/FIXME comments in code.")
    if re.search(r"(?m)^\+?\s*print\b", diff):
        issues.append("Found debug print statements.")
    creds = _credential_findings(diff)
    if not creds:
        creds = _credential_findings_from_content(repo_path, commit_hash)
    if creds:
        issues.append(
            "Potential PII/credential detected (redacted):\n  - "
            + "\n  - ".join(creds[:20])
            + ("\n  - ... (truncated)" if len(creds) > 20 else "")
        )
    return ReviewResult(commit=commit_hash, issues=issues)

def _format_result(result: ReviewResult) -> str:
    if not result.issues:
        return f"No issues found in commit {result.commit}."
    return "Issues in commit {}:\n- {}".format(result.commit, "\n- ".join(result.issues))

def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight checks against a git commit diff.")
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--commit", required=True, help="Commit hash to review")
    args = parser.parse_args()
    try:
        result = code_review_tool(args.repo, args.commit)
        print(_format_result(result))
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())