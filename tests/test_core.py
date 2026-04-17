"""Tests for agent.core.Agent — Anthropic client is fully mocked."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from agent.config import Mode, _preset
from agent.core import Agent, _anthropic_client_from_env, _extract_text, _fmt_args, _serialise

# ---------------------------------------------------------------------------
# Helpers to build mock API responses
# ---------------------------------------------------------------------------


def _text_block(text: str) -> Any:
    from anthropic.types import TextBlock
    return TextBlock(type="text", text=text)


def _tool_use_block(name: str, args: dict[str, Any], tool_id: str = "tu_1") -> Any:
    from anthropic.types import ToolUseBlock
    return ToolUseBlock(type="tool_use", id=tool_id, name=name, input=args)


def _response(
    stop_reason: str,
    blocks: list[MagicMock],
) -> MagicMock:
    r = MagicMock()
    r.stop_reason = stop_reason
    r.content = blocks
    return r


def _make_agent(tmp_path: Path, goal: str = "add a docstring") -> Agent:
    config = _preset(Mode.FULL_AUTO)
    config.project = str(tmp_path)
    config.goal = goal
    config.model = "claude-opus-4-7"
    return Agent(config, memory_path=str(tmp_path / ".agent_state.json"))


# ---------------------------------------------------------------------------
# Agent.run — text-only response (no tools)
# ---------------------------------------------------------------------------


def test_run_returns_0_on_success(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    done_response = _response("end_turn", [_text_block("All done.")])

    with patch.object(agent, "_call_api", return_value=done_response):
        code = agent.run()

    assert code == 0


def test_anthropic_client_uses_api_key_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")

    with patch("agent.core.anthropic.Anthropic") as client_class:
        _anthropic_client_from_env()

    client_class.assert_called_once_with(api_key="test-api-key")


def test_call_api_uses_model_env(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-from-env")
    agent = _make_agent(tmp_path)
    agent._client = MagicMock()

    agent._call_api("system prompt")

    assert agent._client.messages.create.call_args.kwargs["model"] == "claude-from-env"


def test_run_returns_0_and_marks_step_done(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    done_response = _response("end_turn", [_text_block("Finished.")])

    with patch.object(agent, "_call_api", return_value=done_response):
        agent.run()

    step = agent._planner._steps[0]
    assert step.result == "Finished."


def test_run_saves_messages_to_memory(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    done_response = _response("end_turn", [_text_block("Done.")])

    with patch.object(agent, "_call_api", return_value=done_response):
        agent.run()

    state_file = tmp_path / ".agent_state.json"
    assert state_file.exists()
    import json

    data = json.loads(state_file.read_text())
    assert "messages" in data
    assert len(data["messages"]) > 0


# ---------------------------------------------------------------------------
# Agent.run — tool_use then end_turn
# ---------------------------------------------------------------------------


def test_run_dispatches_tool_and_continues(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)

    # First response: call read_file
    target = tmp_path / "hello.txt"
    target.write_text("hello")
    tool_response = _response(
        "tool_use",
        [_tool_use_block("read_file", {"path": str(target)})],
    )
    done_response = _response("end_turn", [_text_block("Read the file.")])

    responses = iter([tool_response, done_response])
    with patch.object(agent, "_call_api", side_effect=lambda _s: next(responses)):
        code = agent.run()

    assert code == 0


def test_run_appends_tool_result_to_messages(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)

    target = tmp_path / "data.txt"
    target.write_text("content")
    tool_response = _response(
        "tool_use",
        [_tool_use_block("read_file", {"path": str(target)})],
    )
    done_response = _response("end_turn", [_text_block("Done.")])

    responses = iter([tool_response, done_response])
    with patch.object(agent, "_call_api", side_effect=lambda _s: next(responses)):
        agent.run()

    # messages: [user(goal), assistant(tool_use), user(tool_result), assistant(end_turn)]
    user_msgs = [m for m in agent._messages if m["role"] == "user"]
    tool_results = [
        m
        for m in user_msgs
        if isinstance(m["content"], list) and m["content"][0].get("type") == "tool_result"
    ]
    assert len(tool_results) == 1


# ---------------------------------------------------------------------------
# Agent.run — tool error → self-correct → success
# ---------------------------------------------------------------------------


def test_run_retries_after_tool_error(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)

    # Tool call that references a non-existent file → FileNotFoundError
    bad_tool = _response(
        "tool_use",
        [_tool_use_block("read_file", {"path": str(tmp_path / "nope.txt")})],
    )
    # Second attempt: different tool call
    good_file = tmp_path / "ok.txt"
    good_file.write_text("data")
    ok_tool = _response(
        "tool_use",
        [_tool_use_block("read_file", {"path": str(good_file)})],
    )
    done_response = _response("end_turn", [_text_block("Recovered.")])

    responses = iter([bad_tool, ok_tool, done_response])
    with patch.object(agent, "_call_api", side_effect=lambda _s: next(responses)):
        code = agent.run()

    assert code == 0


def test_run_returns_1_after_max_tool_errors(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)

    bad_tool = _response(
        "tool_use",
        [_tool_use_block("read_file", {"path": str(tmp_path / "ghost.txt")})],
    )
    # Always return bad tool calls — 3 attempts then give up
    with patch.object(agent, "_call_api", return_value=bad_tool):
        code = agent.run()

    assert code == 1


# ---------------------------------------------------------------------------
# Agent.run — API error handling
# ---------------------------------------------------------------------------


def test_run_returns_1_on_api_error(tmp_path: Path) -> None:
    import anthropic as _anthropic

    agent = _make_agent(tmp_path)

    with patch.object(
        agent,
        "_call_api",
        side_effect=_anthropic.APIStatusError(
            "rate limit",
            response=MagicMock(status_code=429, headers={}),
            body={},
        ),
    ):
        code = agent.run()

    assert code == 1


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def test_extract_text_from_text_block(tmp_path: Path) -> None:
    from anthropic.types import TextBlock

    tb = MagicMock(spec=TextBlock)
    tb.text = "hello"
    response = _response("end_turn", [tb])
    assert _extract_text(response) == "hello"


def test_extract_text_returns_empty_on_no_text() -> None:
    response = _response("tool_use", [])
    assert _extract_text(response) == ""


def test_serialise_str() -> None:
    assert _serialise("hello") == "hello"


def test_serialise_list() -> None:
    result = _serialise(["a", "b"])
    assert "a" in result
    assert "b" in result


def test_serialise_dict() -> None:
    result = _serialise({"key": "val"})
    assert "key" in result


def test_serialise_fallback() -> None:
    class Unserializable:
        def __repr__(self) -> str:
            return "custom"

    result = _serialise(Unserializable())
    assert "custom" in result


def test_fmt_args_short() -> None:
    result = _fmt_args({"path": "file.py", "content": "x"})
    assert "path" in result
    assert "file.py" in result


def test_fmt_args_truncates_long_value() -> None:
    result = _fmt_args({"content": "x" * 100})
    assert len(result) < 120  # truncated to 40 chars


# ---------------------------------------------------------------------------
# Memory persistence across sessions
# ---------------------------------------------------------------------------


def test_memory_resumed_on_second_run(tmp_path: Path) -> None:
    """Second Agent instantiation with same memory_path picks up prior messages."""
    mem_path = str(tmp_path / ".agent_state.json")

    agent1 = _make_agent(tmp_path)
    agent1._memory._path = Path(mem_path)
    done = _response("end_turn", [_text_block("Done first run.")])
    with patch.object(agent1, "_call_api", return_value=done):
        agent1.run()

    # Second agent reads the same memory file
    agent2 = Agent(agent1.config, memory_path=mem_path)
    agent2._memory.load()
    assert len(agent2._memory.messages()) > 0
