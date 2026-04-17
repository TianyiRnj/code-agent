"""Planner: decomposes a goal into steps and tracks execution state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Step:
    id: int
    description: str
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    result: str = ""
    error: str = ""


class Planner:
    """Tracks a list of steps and their retry state."""

    MAX_ATTEMPTS: int = 3

    def __init__(self) -> None:
        self._steps: list[Step] = []
        self._cursor: int = 0

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def decompose(self, goal: str) -> None:
        """Initialise with a single top-level step for the goal.

        Future: replace with a Claude API call to produce sub-steps.
        """
        self._steps = [Step(id=0, description=goal)]
        self._cursor = 0

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def current_step(self) -> Step | None:
        """Return the step currently being worked on, or None if done."""
        if self._cursor < len(self._steps):
            return self._steps[self._cursor]
        return None

    def is_complete(self) -> bool:
        """Return True when all steps have been processed."""
        return self._cursor >= len(self._steps)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def mark_running(self, step: Step) -> None:
        """Mark step as actively being worked on."""
        step.status = StepStatus.RUNNING

    def mark_done(self, step: Step, result: str = "") -> None:
        """Mark step as successfully completed."""
        step.status = StepStatus.DONE
        step.result = result
        self._cursor += 1

    def mark_failed(self, step: Step, error: str) -> bool:
        """Record a failure on step.

        Returns True if the step should be retried, False if max attempts
        have been reached (the step is then skipped).
        """
        step.attempts += 1
        step.error = error
        if step.attempts >= self.MAX_ATTEMPTS:
            step.status = StepStatus.FAILED
            self._cursor += 1
            return False
        step.status = StepStatus.PENDING
        return True

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable execution summary."""
        done = sum(1 for s in self._steps if s.status == StepStatus.DONE)
        failed = sum(1 for s in self._steps if s.status == StepStatus.FAILED)
        total = len(self._steps)

        header = f"{'✓' if failed == 0 else '✗'}  {done}/{total} steps completed"
        if failed:
            header += f"  ({failed} failed)"

        lines = [header]
        for s in self._steps:
            icon = "✓" if s.status == StepStatus.DONE else "✗"
            lines.append(f"  {icon}  {s.description}")
            if s.result:
                excerpt = s.result[:120].replace("\n", " ")
                lines.append(f"      → {excerpt}")
            if s.error and s.status == StepStatus.FAILED:
                lines.append(f"      ✗ {s.error[:80]}")

        return "\n".join(lines)
