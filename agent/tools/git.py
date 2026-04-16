"""Git tools: checkpoint, rollback, diff, commit."""

from __future__ import annotations

import subprocess
from datetime import datetime


def _git(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {output}")
    return output


def git_checkpoint(prefix: str = "chkpt", cwd: str | None = None) -> str:
    """Stage all changes and create a checkpoint commit."""
    _git(["add", "-A"], cwd=cwd)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    msg = f"{prefix}: {timestamp}"
    return _git(["commit", "-m", msg, "--allow-empty"], cwd=cwd)


def git_rollback(ref: str, cwd: str | None = None) -> str:
    """Hard-reset the working tree to ref."""
    return _git(["reset", "--hard", ref], cwd=cwd)


def git_diff(cwd: str | None = None) -> str:
    """Return the current unstaged diff."""
    return _git(["diff"], cwd=cwd)


def git_commit(message: str, cwd: str | None = None) -> str:
    """Stage all changes and create a commit with the given message."""
    _git(["add", "-A"], cwd=cwd)
    return _git(["commit", "-m", message, "--allow-empty"], cwd=cwd)
