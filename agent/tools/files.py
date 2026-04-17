"""File system tools: read, write, patch, list — with PolicyGuard enforcement."""

from __future__ import annotations

from pathlib import Path

from agent.policy import PolicyGuard
from agent.tools.registry import tool


@tool
def read_file(path: str, guard: PolicyGuard | None = None) -> str:
    """Read the full text content of a file at path."""
    if guard is not None:
        guard.check_path(path, write=False)
    return Path(path).read_text()


@tool
def write_file(path: str, content: str, guard: PolicyGuard | None = None) -> str:
    """Write content to a file, creating parent directories as needed."""
    if guard is not None:
        guard.check_path(path, write=True)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes to {path}"


@tool
def patch_file(path: str, old: str, new: str, guard: PolicyGuard | None = None) -> str:
    """Replace the first occurrence of old with new in the file at path."""
    if guard is not None:
        guard.check_path(path, write=True)
    text = Path(path).read_text()
    if old not in text:
        raise ValueError(f"patch target not found in {path!r}")
    Path(path).write_text(text.replace(old, new, 1))
    return f"patched {path}"


@tool
def list_dir(path: str = ".", guard: PolicyGuard | None = None) -> list[str]:
    """Return a sorted list of entry paths inside a directory."""
    if guard is not None:
        guard.check_path(path, write=False)
    return sorted(str(p) for p in Path(path).iterdir())
