"""Unit tests for agent.planner."""

from __future__ import annotations

from agent.planner import Planner, StepStatus

# ---------------------------------------------------------------------------
# decompose
# ---------------------------------------------------------------------------


def test_decompose_creates_one_step() -> None:
    p = Planner()
    p.decompose("add unit tests")
    assert p.current_step() is not None
    assert p.current_step().description == "add unit tests"  # type: ignore[union-attr]


def test_decompose_resets_cursor() -> None:
    p = Planner()
    p.decompose("first goal")
    step = p.current_step()
    assert step is not None
    p.mark_done(step)
    assert p.is_complete()

    p.decompose("second goal")
    assert not p.is_complete()
    assert p.current_step() is not None


# ---------------------------------------------------------------------------
# mark_running / mark_done
# ---------------------------------------------------------------------------


def test_mark_running_sets_status() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_running(step)
    assert step.status == StepStatus.RUNNING


def test_mark_done_advances_cursor() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_done(step, result="all done")
    assert step.status == StepStatus.DONE
    assert step.result == "all done"
    assert p.is_complete()


def test_mark_done_without_result() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_done(step)
    assert step.result == ""
    assert p.is_complete()


# ---------------------------------------------------------------------------
# mark_failed / retry
# ---------------------------------------------------------------------------


def test_first_failure_returns_retry_true() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    should_retry = p.mark_failed(step, "network error")
    assert should_retry is True
    assert step.attempts == 1
    assert step.status == StepStatus.PENDING


def test_second_failure_still_retries() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_failed(step, "err1")
    should_retry = p.mark_failed(step, "err2")
    assert should_retry is True
    assert step.attempts == 2


def test_third_failure_exhausts_retries() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_failed(step, "err1")
    p.mark_failed(step, "err2")
    should_retry = p.mark_failed(step, "err3")
    assert should_retry is False
    assert step.status == StepStatus.FAILED
    assert p.is_complete()


def test_failed_step_stores_last_error() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_failed(step, "first error")
    p.mark_failed(step, "second error")
    p.mark_failed(step, "final error")
    assert step.error == "final error"


def test_max_attempts_equals_three() -> None:
    assert Planner.MAX_ATTEMPTS == 3


# ---------------------------------------------------------------------------
# is_complete / current_step
# ---------------------------------------------------------------------------


def test_not_complete_initially() -> None:
    p = Planner()
    p.decompose("goal")
    assert not p.is_complete()


def test_complete_after_done() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_done(step)
    assert p.is_complete()
    assert p.current_step() is None


def test_complete_after_max_failures() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    for i in range(Planner.MAX_ATTEMPTS):
        p.mark_failed(step, f"err{i}")
    assert p.is_complete()


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


def test_summary_shows_done() -> None:
    p = Planner()
    p.decompose("add tests")
    step = p.current_step()
    assert step is not None
    p.mark_done(step, result="wrote 5 tests")
    s = p.summary()
    assert "1/1" in s
    assert "add tests" in s
    assert "wrote 5 tests" in s


def test_summary_shows_failed() -> None:
    p = Planner()
    p.decompose("risky task")
    step = p.current_step()
    assert step is not None
    for i in range(Planner.MAX_ATTEMPTS):
        p.mark_failed(step, "boom")
    s = p.summary()
    assert "failed" in s.lower() or "✗" in s


def test_summary_truncates_long_result() -> None:
    p = Planner()
    p.decompose("goal")
    step = p.current_step()
    assert step is not None
    p.mark_done(step, result="x" * 300)
    s = p.summary()
    # result line should be present but not the full 300 chars on one line
    assert "x" * 121 not in s  # 120-char cap + "→ " prefix
