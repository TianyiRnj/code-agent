"""build_system_prompt: assembles the system prompt from tools and task config."""

from __future__ import annotations

from agent.config import TaskConfig
from agent.tools.registry import ToolDef


def build_system_prompt(tools: list[ToolDef], config: TaskConfig) -> str:
    """Return the system prompt injecting tool descriptions and task context."""
    tool_lines = "\n".join(f"  {td.name}: {td.description}" for td in tools)
    deny_sample = ", ".join(config.commands.deny[:4])
    blocked_sample = ", ".join(config.workspace.blocked_paths[:4])

    return f"""\
You are an autonomous coding agent operating on a software project.

## Task
Project : {config.project}
Goal    : {config.goal}
Mode    : {config.mode.value}

## Tools
{tool_lines}

## Instructions
- Work step by step.  Think before acting.
- Prefer the smallest tool call that makes progress.
- After writing or patching a file, verify the result with read_file.
- When a tool returns an error, diagnose it and try a corrected approach.
- When the goal is fully accomplished, write a concise final summary and stop.
  Do not continue after the task is complete.
- Do not ask the user questions; infer missing context from the codebase.

## Hard constraints (mode: {config.mode.value})
- Never access: {blocked_sample} …
- Never run: {deny_sample} …
- Actions flagged by the permission layer will be blocked automatically.
"""
