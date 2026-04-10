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


def _iter_added_lines(diff_text: str) -> list[tuple[str, str]]:
    """
    Return (file, line) pairs for lines added in the diff.

    We intentionally avoid returning removed/context lines and avoid dumping raw diff.
    """
    current_file = "<unknown>"
    added: list[tuple[str, str]] = []
    for raw in diff_text.splitlines():
        m = _DIFF_FILE_RE.match(raw)
        if m:
            current_file = m.group(1)
            continue

        # Added lines in unified diff start with '+', but exclude headers like '+++ b/file'.
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append((current_file, raw[1:]))
    return added


def _redact_assignment(line: str) -> str:
    """
    Redact common 'key = value' / 'key:value' / 'key=value' patterns without revealing values.
    """
    return re.sub(
        r"(?i)\b(password|secret|api[_-]?key)\b(\s*[:=]\s*)(.+)$",
        lambda m: f"{m.group(1)}{m.group(2)}***",
        line,
    )


def _credential_findings(diff_text: str) -> list[str]:
    findings: list[str] = []
    for file, line in _iter_added_lines(diff_text):
        if re.search(r"(?i)\b(password|secret|api[_-]?key)\b", line):
            findings.append(f"{file}: {_redact_assignment(line).strip()}")
    # De-dupe while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _changed_files(repo_path: str, commit_hash: str) -> list[str]:
    """
    List files changed by a commit.
    """
    _run_git(repo_path, ["rev-parse", "--verify", commit_hash])
    out = _run_git(
        repo_path, ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash]
    )
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return files


def _file_text_at_commit(repo_path: str, commit_hash: str, file_path: str) -> str:
    """
    Read file contents at a specific commit.

    We force text output so we can scan even if git considers the diff "binary".
    """
    return _run_git(repo_path, ["show", "--text", f"{commit_hash}:{file_path}"])


def _credential_findings_from_content(repo_path: str, commit_hash: str) -> list[str]:
    """
    Scan the *resulting file contents* at commit time for sensitive keys.
    """
    findings: list[str] = []
    for file_path in _changed_files(repo_path, commit_hash):
        try:
            text = _file_text_at_commit(repo_path, commit_hash, file_path)
        except RuntimeError:
            # File may be deleted/renamed; skip if we can't read it at this commit.
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            if re.search(r"(?i)\b(password|secret|api[_-]?key)\b", line):
                findings.append(f"{file_path}:{i}: {_redact_assignment(line).strip()}")

    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _candidate_git_paths() -> list[str]:
    # Prefer PATH first, then common Git for Windows locations.
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


def _get_diff(repo_path: str, commit_hash: str) -> str:
    """
    Get a unified diff for a commit.

    Notes:
    - We force text output (`--text`) because Windows encodings / attributes can cause
      git to classify a file as binary and omit the patch contents, which breaks
      content-based scanning.
    - We use `git show` so the initial commit works (no `~1`).
    """
    _run_git(repo_path, ["rev-parse", "--verify", commit_hash])

    # `rev-list --parents -n 1 <commit>` returns: <commit> <parent1> <parent2> ...
    parents_line = _run_git(repo_path, ["rev-list", "--parents", "-n", "1", commit_hash]).strip()
    parts = parents_line.split()
    has_parent = len(parts) > 1

    if has_parent:
        # Show only the patch for this commit (compared to its parent), no commit message header.
        return _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])

    # Root commit: show patch against empty tree.
    return _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])


def code_review_tool(repo_path: str, commit_hash: str) -> ReviewResult:
    """
    Run a simple code review on the given commit by scanning its diff.
    """
    diff = _get_diff(repo_path, commit_hash)

    issues: list[str] = []

    if "TODO" in diff or "FIXME" in diff:
        issues.append("Found TODO/FIXME comments in code.")

    # Python debug prints: support both print(...) and bare 'print' (bad legacy / accidental).
    if re.search(r"(?m)^\+?\s*print\b", diff):
        issues.append("Found debug print statements.")

    creds = _credential_findings(diff)
    if not creds:
        # If the diff is "binary" (no patch text), fall back to scanning file contents.
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
    parser = argparse.ArgumentParser(
        description="Run lightweight checks against a git commit diff."
    )
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

