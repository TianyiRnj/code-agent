"""Shell tool: run_command with PolicyGuard enforcement."""

from __future__ import annotations

import subprocess

from agent.policy import PolicyGuard
from agent.tools.registry import tool


@tool
def run_command(
    cmd: str,
    cwd: str | None = None,
    timeout: int = 60,
    guard: PolicyGuard | None = None,
) -> str:
    """Run a shell command and return its combined stdout+stderr output."""
    if guard is not None:
        guard.check_command(cmd)

    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"command failed (rc={result.returncode}): {output.strip()}")
    return output
