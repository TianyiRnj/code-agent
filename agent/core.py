"""Agent: drives the Claude API agentic loop with tool dispatch and retry."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic
from anthropic.types import Message, TextBlock, ToolParam, ToolUseBlock

from agent.config import TaskConfig
from agent.memory import MemoryStore
from agent.planner import Planner, Step
from agent.policy import PolicyGuard
from agent.prompts import build_system_prompt
from agent.tools import all_tools, execute

logger = logging.getLogger(__name__)

# Maximum tokens to request per API call.
_MAX_TOKENS = 8192


class Agent:
    """Orchestrates planning, API calls, tool dispatch, and self-correction."""

    def __init__(self, config: TaskConfig, memory_path: str = ".agent_state.json") -> None:
        self.config = config
        self._client = anthropic.Anthropic()
        self._guard = PolicyGuard(config)
        self._planner = Planner()
        self._memory = MemoryStore(memory_path)
        # Conversation history: alternating user/assistant messages.
        self._messages: list[Any] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Execute the agent loop.  Returns 0 on success, 1 on failure."""
        self._memory.load()
        saved = self._memory.messages()
        if saved:
            self._messages = saved
            logger.info("Resumed %d messages from memory.", len(self._messages))

        system = build_system_prompt(all_tools(), self.config)
        self._planner.decompose(self.config.goal)

        exit_code = 0
        while not self._planner.is_complete():
            step = self._planner.current_step()
            if step is None:
                break

            if step.status.value == "pending":
                self._push_user(f"Goal: {step.description}")

            self._planner.mark_running(step)
            success = self._run_step(step, system)
            if not success:
                exit_code = 1
                logger.error("Step %d failed after %d attempts.", step.id, step.attempts)

        print("\n" + self._planner.summary())
        self._memory.set_messages(self._messages)
        self._memory.save()
        return exit_code

    # ------------------------------------------------------------------
    # Inner API loop (one step)
    # ------------------------------------------------------------------

    def _run_step(self, step: Step, system: str) -> bool:
        """Drive the API loop until the step completes or exhausts retries."""
        while True:
            try:
                response = self._call_api(system)
            except anthropic.APIError as exc:
                logger.warning("API error: %s", exc)
                return self._planner.mark_failed(step, f"API error: {exc}") is not False

            self._push_assistant(response)

            if response.stop_reason == "tool_use":
                had_error = self._dispatch_tools(response)
                if had_error:
                    should_retry = self._planner.mark_failed(step, "tool execution error")
                    if not should_retry:
                        return False
                    # Add a self-correction nudge and retry the step
                    self._push_user(
                        "One or more tools returned an error (see results above). "
                        "Diagnose the issue and try a corrected approach."
                    )

            elif response.stop_reason in ("end_turn", "stop_sequence"):
                text = _extract_text(response)
                self._planner.mark_done(step, text)
                return True

            else:
                # max_tokens hit or unexpected stop — treat as a soft failure
                should_retry = self._planner.mark_failed(
                    step, f"unexpected stop_reason={response.stop_reason!r}"
                )
                if not should_retry:
                    return False
                self._push_user("Continue working on the goal.")

    # ------------------------------------------------------------------
    # Anthropic API call
    # ------------------------------------------------------------------

    def _call_api(self, system: str) -> Message:
        """Make a single call to the Claude messages API with prompt caching."""
        return self._client.messages.create(
            model=self.config.model,
            max_tokens=_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=_tool_params(all_tools()),
            messages=self._messages,
        )

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch_tools(self, response: Message) -> bool:
        """Execute all tool_use blocks; append results; return True if any failed."""
        results: list[Any] = []
        had_error = False

        for block in response.content:
            if not isinstance(block, ToolUseBlock):
                continue
            tool_id = block.id
            name = block.name
            args: dict[str, Any] = dict(block.input)

            logger.info("Tool call: %s(%s)", name, _fmt_args(args))
            try:
                raw = execute(name, args, guard=self._guard)
                output = _serialise(raw)
                logger.debug("  → %s", output[:120])
                results.append({"type": "tool_result", "tool_use_id": tool_id, "content": output})
            except Exception as exc:  # noqa: BLE001
                msg = f"{type(exc).__name__}: {exc}"
                logger.warning("  ✗ %s", msg)
                had_error = True
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": msg,
                        "is_error": True,
                    }
                )

        if results:
            self._push_user(results)
        return had_error

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    def _push_user(self, content: Any) -> None:
        self._messages.append({"role": "user", "content": content})

    def _push_assistant(self, response: Message) -> None:
        serializable = [block.model_dump() for block in response.content]
        self._messages.append({"role": "assistant", "content": serializable})


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_text(response: Message) -> str:
    """Return the first text block from a response, or empty string."""
    for block in response.content:
        if isinstance(block, TextBlock):
            return block.text
    return ""


def _serialise(value: Any) -> str:
    """Convert a tool return value to a string suitable for the API."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _fmt_args(args: dict[str, Any]) -> str:
    """Compact one-line representation of tool arguments for logging."""
    parts = []
    for k, v in args.items():
        sv = str(v)
        parts.append(f"{k}={sv[:40]!r}" if len(sv) > 40 else f"{k}={sv!r}")
    return ", ".join(parts)


def _tool_params(tools: list[Any]) -> list[ToolParam]:
    """Convert ToolDef list to the dict format expected by the Anthropic API."""
    return [
        ToolParam(
            name=td.name,
            description=td.description,
            input_schema=td.input_schema,
        )
        for td in tools
    ]
