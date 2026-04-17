"""PolicyGuard: enforces workspace, path, and command policies from TaskConfig."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Callable

from agent.config import CapabilityValue, TaskConfig

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PolicyError(Exception):
    """Base class for all policy violations."""


class BlockedPathError(PolicyError):
    """Path is unconditionally blocked — no override, no approval flow."""


class DeniedCommandError(PolicyError):
    """Command matches a deny rule — no override, no approval flow."""


class ConfirmationDeniedError(PolicyError):
    """User denied a confirmation prompt for a guarded action."""


# ---------------------------------------------------------------------------
# Capability → command-pattern mapping
# ---------------------------------------------------------------------------

# Maps capability name → list of command substrings that exercise that capability.
_CAPABILITY_PATTERNS: dict[str, list[str]] = {
    "install_dependencies": [
        "pip install",
        "npm install",
        "pnpm install",
        "yarn add",
        "poetry add",
        "poetry install",
    ],
    "network_access": ["curl ", "wget ", "http://", "https://"],
    "delete_files": ["rm "],
}


# ---------------------------------------------------------------------------
# PolicyGuard
# ---------------------------------------------------------------------------


class PolicyGuard:
    """Checks paths and commands against a TaskConfig and enforces the policy."""

    def __init__(
        self,
        config: TaskConfig,
        prompter: Callable[[str], str] | None = None,
    ) -> None:
        self._config = config
        # Inject a custom prompter for tests; default falls back to input().
        self._prompt: Callable[[str], str] = prompter or input

    # ------------------------------------------------------------------
    # Path enforcement
    # ------------------------------------------------------------------

    def check_path(self, path: str | Path, *, write: bool = False) -> None:
        """Raise BlockedPathError if path violates workspace policy.

        Always enforces blocked_paths.  For writes, also enforces
        write_outside_workspace and writable_paths (if non-empty).
        """
        # Check both the symlink-resolved path and the non-resolved absolute path.
        # On macOS /etc is a symlink to /private/etc; patterns like /etc/** must
        # still match the path as the user wrote it.
        p_abs = Path(path).expanduser().absolute()
        p_resolved = p_abs.resolve()

        for pattern in self._config.workspace.blocked_paths:
            if _path_matches(p_abs, pattern) or _path_matches(p_resolved, pattern):
                raise BlockedPathError(f"path blocked by policy: {path!r}  (rule: {pattern!r})")

        if not write:
            return

        p = p_resolved
        root = Path(self._config.workspace.root).resolve()

        if not self._config.capabilities.write_outside_workspace:
            if not _is_under(p, root):
                raise BlockedPathError(f"write outside workspace is not allowed: {path!r}")

        writable = self._config.workspace.writable_paths
        if writable:
            rel = p.relative_to(root) if _is_under(p, root) else p
            rel_str = str(rel)
            if not any(_rel_matches(rel_str, pat) for pat in writable):
                raise BlockedPathError(f"path is not in writable_paths: {path!r}")

    # ------------------------------------------------------------------
    # Command enforcement
    # ------------------------------------------------------------------

    def check_command(self, cmd: str) -> None:
        """Raise DeniedCommandError if cmd is hard-blocked.

        For commands that exercise a 'confirm' capability, pause and prompt
        the user; raise ConfirmationDeniedError if they decline.
        For commands that exercise a False capability, raise DeniedCommandError.
        """
        for pattern in self._config.commands.deny:
            if _cmd_contains(cmd, pattern):
                raise DeniedCommandError(f"command denied by policy: {cmd!r}  (rule: {pattern!r})")

        for cap_name, patterns in _CAPABILITY_PATTERNS.items():
            cap_value: CapabilityValue = getattr(self._config.capabilities, cap_name, True)
            if not any(_cmd_contains(cmd, pat) for pat in patterns):
                continue
            if cap_value == "confirm":
                self.request_confirm(
                    f"run: {cmd!r}",
                    detail=f"requires capability: {cap_name}",
                )
            elif cap_value is False:
                raise DeniedCommandError(
                    f"capability {cap_name!r} is disabled (mode={self._config.mode.value}): {cmd!r}"
                )

    # ------------------------------------------------------------------
    # Confirmation prompt
    # ------------------------------------------------------------------

    def request_confirm(self, action: str, detail: str = "") -> None:
        """Print a proposed action and prompt for 'y' approval.

        Raises ConfirmationDeniedError if the user does not confirm.
        """
        detail_str = f"  ({detail})" if detail else ""
        msg = f"\n[approval required] {action}{detail_str}\nProceed? [y/N] "
        answer = self._prompt(msg).strip().lower()
        if answer != "y":
            raise ConfirmationDeniedError(f"user denied: {action!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _path_matches(resolved: Path, pattern: str) -> bool:
    """Return True if resolved path matches a blocked_paths-style pattern.

    Absolute patterns (starting with / or ~) are matched against the full path.
    Relative patterns like 'secrets/**' match any directory component of the path.
    Simple name patterns like '.env.*' match the filename only.
    """
    expanded_pat = str(Path(pattern).expanduser())
    path_str = str(resolved)

    if expanded_pat.endswith("/**"):
        prefix = expanded_pat[:-3]
        if prefix.startswith("/"):
            # Absolute prefix: path must start with it.
            return path_str == prefix or path_str.startswith(prefix + "/")
        # Relative prefix (e.g. "secrets"): match any directory component.
        return (
            path_str == prefix
            or path_str.startswith(prefix + "/")
            or ("/" + prefix + "/") in path_str
            or path_str.endswith("/" + prefix)
        )

    if "/" in expanded_pat or expanded_pat.startswith("~"):
        return fnmatch.fnmatch(path_str, expanded_pat)

    # Pattern has no path separator — match against filename only.
    return fnmatch.fnmatch(resolved.name, pattern)


def _rel_matches(rel_str: str, pattern: str) -> bool:
    """Return True if a workspace-relative path matches a writable_paths pattern."""
    if pattern == "**":
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel_str == prefix or rel_str.startswith(prefix + "/")
    return fnmatch.fnmatch(rel_str, pattern)


def _is_under(path: Path, root: Path) -> bool:
    """Return True if path is inside root (or equal to root)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _cmd_contains(cmd: str, pattern: str) -> bool:
    """Return True if cmd matches pattern (case-insensitive).

    Patterns with ' | ' are treated as pipeline checks: each part must appear
    in a separate pipeline stage in order.  E.g. 'curl | sh' matches
    'curl https://example.com/setup.sh | sh' but not 'curl https://example.com'.
    """
    lower_cmd = cmd.lower()
    lower_pat = pattern.lower()

    if " | " not in lower_pat:
        if " " not in lower_pat:
            # Single-token deny pattern: use word-boundary matching so that
            # "dd" blocks the dd command but not "yarn add" or "poetry add".
            return bool(re.search(r"(?<!\w)" + re.escape(lower_pat) + r"(?!\w)", lower_cmd))
        return lower_pat in lower_cmd

    cmd_stages = [s.strip() for s in lower_cmd.split("|")]
    pat_parts = [s.strip() for s in lower_pat.split("|")]

    stage_idx = 0
    for part in pat_parts:
        matched = False
        while stage_idx < len(cmd_stages):
            if part in cmd_stages[stage_idx]:
                stage_idx += 1
                matched = True
                break
            stage_idx += 1
        if not matched:
            return False
    return True
