"""MemoryStore: JSON-backed persistence for conversation history and plan state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    """Persists agent state to a JSON file so sessions can be resumed."""

    def __init__(self, path: str = ".agent_state.json") -> None:
        self._path = Path(path)
        self._data: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load state from disk; silently starts fresh if the file is missing."""
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        """Persist current state to disk."""
        self._path.write_text(json.dumps(self._data, indent=2))

    # ------------------------------------------------------------------
    # Generic key/value store
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for key, or default if not present."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value under key."""
        self._data[key] = value

    # ------------------------------------------------------------------
    # Message history helpers
    # ------------------------------------------------------------------

    def messages(self) -> list[Any]:
        """Return the stored message list (empty list if none saved)."""
        result: Any = self._data.get("messages", [])
        return result if isinstance(result, list) else []

    def set_messages(self, messages: list[Any]) -> None:
        """Replace the stored message list."""
        self._data["messages"] = messages
