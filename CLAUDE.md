# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the agent (uses task.yaml config)
python -m agent

# Run with a one-off goal (overrides task.yaml goal)
python -m agent --project ./myrepo --goal "add unit tests for auth module"

# Run tests
pytest

# Run a single test
pytest tests/test_agent.py::test_name -v

# Lint and format
ruff check .
ruff format .

# Type check
mypy --strict agent/
```

## Project Overview

This is a **fully autonomous coding agent** powered by Claude. Given a project path and a goal, it plans, executes, self-corrects, and commits — without human input except for high-risk approvals.

**Input contract:**
- `task.yaml` — long-term rules, permissions, defaults (committed to the repo)
- `--project` / `--goal` CLI flags — per-run overrides
- Interactive prompts — only for high-risk operations (destructive shell commands, external pushes)

**What the agent does, end-to-end:**
1. Loads config (`task.yaml` + CLI overrides)
2. Reads the target project to understand its structure
3. Decomposes the goal into ordered plan steps
4. Executes steps: edits files, runs shell commands, calls APIs
5. On failure, marks the step failed and retries (max 3 attempts)
6. Creates git checkpoints before destructive changes
7. Prints a summary and exits when all steps are done

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| AI SDK | `anthropic` (official Python SDK) |
| Linting | `ruff check` |
| Formatting | `ruff format` |
| Type checking | `mypy --strict` |
| Testing | `pytest` |
| Package | `pip install -e ".[dev]"` |
| Default model | `claude-opus-4-7` (override: `ANTHROPIC_MODEL` env var) |

## Directory Structure

```
code-agent/
├── agent/
│   ├── __init__.py
│   ├── __main__.py        # CLI entry point; parses args, loads task.yaml, starts loop
│   ├── core.py            # Agent class: API calls, tool dispatch, message history
│   ├── config.py          # TaskConfig dataclass; merges task.yaml + CLI overrides
│   ├── planner.py         # Decomposes goal into steps; tracks status; retries
│   ├── memory.py          # JSON persistence; load()/save() across turns
│   ├── prompts.py         # build_system_prompt(tools, task_config) → str
│   └── tools/
│       ├── __init__.py    # ALL_TOOLS list; auto-registration
│       ├── files.py       # read_file, write_file, patch_file, list_dir
│       ├── shell.py       # run_command (approval gate for high-risk patterns)
│       ├── git.py         # git_checkpoint, git_rollback, git_diff, git_commit
│       └── web.py         # web_search, http_get (off by default)
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_planner.py
│   └── test_tools.py
├── task.yaml              # Long-term config and permission rules
├── pyproject.toml
└── CLAUDE.md
```

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `__main__.py` | Parse CLI (`--project`, `--goal`, `--config`), load `TaskConfig`, call `Agent.run()` |
| `config.py` | `TaskConfig` dataclass; merges `task.yaml` defaults with CLI overrides |
| `core.py` | `Agent` class — drives the agentic loop: API → tool dispatch → result → repeat |
| `planner.py` | Decomposes goal into steps; tracks `pending/running/done/failed`; retries up to 3× |
| `memory.py` | `MemoryStore` — JSON-backed state; persists conversation + plan across turns |
| `prompts.py` | `build_system_prompt(tools, task_config)` — injects tool list + task context |
| `tools/files.py` | `read_file`, `write_file`, `patch_file`, `list_dir` |
| `tools/shell.py` | `run_command` — executes shell; blocks high-risk patterns unless approved |
| `tools/git.py` | `git_checkpoint`, `git_rollback`, `git_diff`, `git_commit` |
| `tools/web.py` | `web_search`, `http_get` — disabled by default; enable in `task.yaml` |

## Agentic Loop

```
Agent.run()
  └─ build_system_prompt()
  └─ planner.decompose(goal) → [step1, step2, ...]
  └─ loop:
       ├─ call Claude API (messages + ALL_TOOLS)
       ├─ tool_use response → execute tool → append result → continue
       ├─ text response + steps remaining → inject next step, continue
       ├─ text response + no steps remaining → print summary, exit 0
       └─ tool error → planner.mark_failed(step); retry (max 3); else exit 1
```

## Configuration: task.yaml

```yaml
project: ./
goal: ""                   # overridden by --goal CLI flag
model: claude-opus-4-7

permissions:
  web_access: false         # must be true to enable tools/web.py
  shell_approval:           # shell patterns that require interactive confirmation
    - "rm -rf"
    - "git push"
    - "pip install"

git:
  auto_checkpoint: true     # commit snapshot before each destructive operation
  checkpoint_prefix: "chkpt"
```

## Naming Conventions

| Target | Convention | Example |
|---|---|---|
| Files | `snake_case.py` | `task_config.py` |
| Classes | `PascalCase` | `Agent`, `MemoryStore`, `TaskConfig` |
| Functions / variables | `snake_case` | `run_command`, `current_step` |
| Constants | `UPPER_SNAKE_CASE` | `ALL_TOOLS`, `DEFAULT_MODEL` |
| Tool functions | verb phrase | `read_file`, `git_checkpoint` |
| Test functions | `test_<what>_<condition>` | `test_run_command_blocks_rm_rf` |

## Tool System

- Each tool is a typed `def` decorated with `@tool`
- The docstring becomes Claude's tool description — write it precisely
- All parameters must be type-annotated; types generate the JSON schema sent to the API
- To add a tool: implement in `agent/tools/<name>.py`, import it in `tools/__init__.py`, add to `ALL_TOOLS`
- High-risk tools check `config.permissions` before executing; prompt user if a match is found
- `git_checkpoint()` is called automatically before any destructive tool execution

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | Anthropic API authentication |
| `ANTHROPIC_MODEL` | `claude-opus-4-7` | Model override |
| `AGENT_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

## Development Conventions

- `ruff check .` and `ruff format .` must pass before every commit
- `mypy --strict agent/` must pass with zero errors
- One file per tool group; split only when a file exceeds ~200 lines
- All public functions and classes have type annotations and a one-line docstring
- Tests live in `tests/`; shared fixtures go in `conftest.py`
- Never skip `git_checkpoint()` before destructive operations

---

# Autonomous Code Agent Manual

## Role

You are an autonomous code agent operating on a single project workspace.

Your inputs are:
- `PROJECT_PATH`
- `GOAL`

Your job is to:
1. inspect the repository
2. infer architecture and conventions
3. make a short plan
4. implement the goal
5. validate changes
6. self-correct when possible
7. stop only when done, blocked, or a guarded action requires approval

## Operating Style

- Be highly autonomous.
- Do not ask unnecessary questions.
- Infer missing context from the codebase.
- Keep changes minimal and targeted.
- Reuse existing patterns.
- Prefer incremental progress over large rewrites.

## Execution Loop

1. Read repository structure and key config files.
2. Infer stack, tooling, and commands.
3. Write a concise plan.
4. Execute one step at a time.
5. After each meaningful change:
   - inspect diffs
   - run relevant validation
   - fix issues
6. Repeat until goal is achieved or blocked.

## Validation

Always prefer the smallest useful validation first:
- targeted tests
- lint for touched files
- narrow build/test scope
- full validation only when necessary

## File Safety

You may modify only files inside the project workspace.

Never read, write, print, or upload:
- `.env`, `.env.*`
- `secrets/**`
- `**/*.pem`, `**/*.key`, `**/id_rsa`
- `~/.ssh/**`, `~/.aws/**`, `~/.config/**`
- OS/system files
- files outside the workspace

## Forbidden Actions

Never do the following:
- destructive delete
- `sudo`
- modifying system directories
- destructive git commands
- reading sensitive credential files
- exfiltrating local content
- using network access unless explicitly allowed

## Guarded Actions

Pause and request approval before:
- deleting files
- changing dependencies or lockfiles
- running migrations
- changing CI/CD
- writing outside repo root
- using network access
- touching any sensitive or secret-like file

## Editing Rules

- Do not refactor unrelated code.
- Do not rename files/modules unless required.
- Preserve existing style and conventions.
- Add or update tests when behavior changes.
- Document non-obvious decisions in comments only when necessary.

## Checkpoints

Before major edits:
- create a checkpoint

After major edits:
- summarize changed files
- summarize validation outcome
- make the change reversible

## Final Output

Return:
- inferred stack
- execution plan
- files changed
- validations run
- outcome
- remaining risks
- any approvals needed
