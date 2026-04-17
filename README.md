# Code Agent

Code Agent is a Python-based autonomous coding agent powered by Claude. It is designed to inspect a target repository, plan implementation steps, make code changes, run validation commands, self-correct when possible, and preserve safety boundaries through a policy engine.

The current implementation focuses on the foundation: CLI configuration, policy enforcement, tool registration, file/shell/git tools, planning, memory, and a Claude-driven execution loop.

## What It Does

- Loads task configuration from `task.yaml`.
- Accepts CLI overrides for project, goal, mode, and config path.
- Builds a system prompt from the configured tools and policy.
- Decomposes the goal into execution steps.
- Calls Claude through the Anthropic Python SDK.
- Lets Claude request registered tools.
- Runs tool calls through the policy guard.
- Stores message history in `.agent_state.json`.
- Prints a planner summary when execution finishes.

## Repository Layout

```text
code-agent/
├── agent/
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # task.yaml model and mode presets
│   ├── core.py              # Claude API loop and tool dispatch
│   ├── memory.py            # JSON-backed message memory
│   ├── planner.py           # step decomposition and retry tracking
│   ├── policy.py            # path, command, and capability guardrails
│   ├── prompts.py           # system prompt construction
│   └── tools/
│       ├── registry.py      # @tool registration and JSON schema generation
│       ├── files.py         # file tools
│       ├── git.py           # git tools
│       └── shell.py         # shell command tool
├── docs/
│   └── agent_platform_product_spec.md
├── tests/
├── task.yaml
├── pyproject.toml
├── agent_policy.md
└── CLAUDE.md
```

## Requirements

- Python 3.11 or newer.
- An Anthropic API key.

## Installation

From the repository root:

```bash
pip install -e ".[dev]"
```

Set your Anthropic API key:

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=claude-opus-4-7
```

The local `.env` file is ignored by git, so your API key stays out of commits.

## Quick Start

Run the agent with a one-off goal:

```bash
agent \
  --project ./some-repo \
  --goal "add unit tests for the auth module" \
  --mode balanced
```

Or run through Python:

```bash
python -m agent \
  --project ./some-repo \
  --goal "add unit tests for the auth module" \
  --mode balanced
```

Use a custom config file:

```bash
agent \
  --config task.yaml \
  --goal "fix the failing policy tests"
```

Show CLI help:

```bash
agent --help
```

## Configuration

The default config file is `task.yaml`.

```yaml
project: ./
goal: ""

# The runtime model is loaded from ANTHROPIC_MODEL in .env.
# Uncomment only if you want a config fallback when ANTHROPIC_MODEL is unset.
# model: claude-opus-4-7

mode: balanced

workspace:
  root: ./
  blocked_paths:
    - .env
    - .env.*
    - secrets/**
    - ~/.ssh/**
    - ~/.aws/**
    - /etc/**
    - /System/**
    - /usr/**

git:
  auto_checkpoint: true
  checkpoint_prefix: "chkpt"
```

You can set `goal` directly in `task.yaml`, or pass it at runtime with `--goal`.

CLI values override config values:

```bash
agent --project ./repo --goal "fix auth bug" --mode safe
```

## Permission Modes

Code Agent supports three policy modes.

| Mode | Intended Use | Behavior |
|---|---|---|
| `safe` | Shared or production-adjacent workspaces | Most restrictive; deletion, dependency installs, and network access are blocked. |
| `balanced` | Normal development | Risky operations require confirmation through policy rules. |
| `full-auto` | Isolated sandboxes or disposable environments | Allows more automation, while blocked paths and denied commands remain protected. |

Blocked paths such as `.env`, `secrets/**`, `~/.ssh/**`, `/etc/**`, `/System/**`, and `/usr/**` are protected regardless of mode.

Denied command patterns such as `sudo`, `chmod`, `chown`, `dd`, `mkfs`, `fdisk`, `curl | sh`, and `wget | sh` are also blocked by default.

## Common Usage Patterns

Run against the current repository:

```bash
agent --goal "add tests for the shell policy guard"
```

Run against another repository:

```bash
agent \
  --project /path/to/target-repo \
  --goal "refactor the user service and keep behavior unchanged"
```

Use the safest mode:

```bash
agent \
  --project ./repo \
  --goal "review and explain the test failures" \
  --mode safe
```

Use full automation only in an isolated workspace:

```bash
agent \
  --project ./throwaway-sandbox \
  --goal "upgrade dependencies and fix resulting tests" \
  --mode full-auto
```

## Development Commands

Install dev dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run a single test:

```bash
pytest tests/test_tools.py -v
```

Lint:

```bash
ruff check .
```

Format:

```bash
ruff format .
```

Type check:

```bash
mypy agent/
```

## Adding a Tool

Tools are registered with the `@tool` decorator in `agent/tools/registry.py`.

To add a new tool:

1. Create or edit a module in `agent/tools/`.
2. Define a typed function.
3. Add a precise one-line docstring.
4. Decorate it with `@tool`.
5. Import the module from `agent/tools/__init__.py` so it registers at startup.
6. Add tests for the tool and policy behavior.

Example:

```python
from agent.tools.registry import tool


@tool
def read_metadata(path: str) -> str:
    """Read project metadata from a file."""
    ...
```

Runtime-only parameters such as `guard` are injected by the tool dispatcher and are not exposed to Claude in the tool schema.

## Safety Model

The model is not trusted to enforce safety on its own.

Before tool execution, the platform checks:

- Whether a path is inside the allowed workspace.
- Whether a path matches blocked patterns.
- Whether a command matches denied patterns.
- Whether a requested capability is allowed, blocked, or requires confirmation.

This keeps policy enforcement in deterministic Python code instead of relying only on model instructions.

## Current Limitations

- Interactive approval handling is still an implementation area to keep improving.
- Network tools are not enabled by default.
- The product spec in `docs/agent_platform_product_spec.md` describes future multi-agent expansion beyond the current Code Agent foundation.
- The agent requires a valid Anthropic API key for real execution.

## Future Direction

The long-term architecture is a shared agent platform with multiple specialized agents:

- Code Agent for implementation.
- Code Review Agent for structured review.
- Interview Preparing Agent for coaching and preparation workflows.

See `docs/agent_platform_product_spec.md` for the full extension spec.
