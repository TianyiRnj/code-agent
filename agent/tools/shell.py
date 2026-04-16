"""Shell tool: run_command with PolicyGuard enforcement."""

from __future__ import annotations

import subprocess

from agent.policy import PolicyGuard


def run_command(
    cmd: str,
    cwd: str | None = None,
    guard: PolicyGuard | None = None,
) -> str:
    """Execute a shell command, enforcing policy rules when a guard is provided."""
    if guard is not None:
        guard.check_command(cmd)

    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"command failed (rc={result.returncode}): {output}")
    return output
