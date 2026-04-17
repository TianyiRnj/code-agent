# Agent Platform Product Spec

This document describes a future extension direction for the agent platform: one shared execution platform that can run multiple specialized agents with different responsibilities, permissions, workflows, and output schemas.

The goal is not to define a loose concept. This is an implementation-oriented product spec that can be used directly as a blueprint for future development.

## 1. Overall Architecture

The platform is organized as one shared runtime with three specialized agents on top.

```text
                +---------------------+
                |   Agent Platform    |
                |---------------------|
                | Runner              |
                | Policy Engine       |
                | Planner             |
                | Memory              |
                | Approval Gate       |
                | Git / Patch / Undo  |
                | Tool Layer          |
                +----------+----------+
                           |
        +------------------+------------------+
        |                  |                  |
+---------------+  +---------------+  +-------------------+
| Code Agent    |  | Review Agent  |  | Interview Agent   |
+---------------+  +---------------+  +-------------------+
```

The platform owns execution, safety, memory, tool dispatch, approvals, rollback, and reporting. Each agent owns its own purpose, prompt, schema, policy profile, and workflow.

## 2. Agent Definitions

### 2.1 Code Agent

The Code Agent is an execution-oriented agent.

#### Responsibilities

- Understand the target codebase.
- Generate an execution plan.
- Modify source code.
- Run tests and builds.
- Self-correct after failures.
- Output a patch and final summary.

#### Input Schema

```yaml
project_path: string
goal: string

options:
  profile: safe | balanced | full_auto
  max_iterations: number
  test_strategy: fast | full
  allow_network: boolean
```

#### Output Schema

```yaml
status: success | partial | blocked

plan:
  - step: string

execution_log:
  - step: string
    action: string
    result: success | fail

changes:
  files_modified:
    - path: string
      summary: string

validation:
  tests: passed | failed | skipped
  lint: passed | failed | skipped
  build: passed | failed | skipped

patch: string

risks:
  - string

rollback:
  branch: string
  revert_command: string
```

#### Permission Model

| Capability | Status |
|---|---|
| Read project files | Allowed |
| Write project files | Allowed |
| Execute shell commands | Allowed, controlled |
| Git operations | Allowed |
| Delete files | Requires approval |
| Modify dependencies | Requires approval |
| Network access | Disabled by default |
| System files | Blocked |
| Secrets | Blocked |

#### Workflow

1. Discover
   - Scan the repository.
   - Detect the stack.
   - Find test and build commands.

2. Plan
   - Break the goal into ordered implementation steps.

3. Execute Loop
   - For each step:
     - Apply the code change.
     - Run targeted validation.
     - Fix errors if validation fails.
     - Create a git checkpoint when appropriate.

4. Guard Check
   - If a risky action is requested, pause and request approval.

5. Finalize
   - Run final validation.
   - Generate a unified diff patch.
   - Output the final summary.

### 2.2 Code Review Agent

The Code Review Agent is an audit-oriented agent.

#### Responsibilities

- Analyze a diff, pull request, branch, or working tree.
- Find bugs, risks, inconsistencies, and missing tests.
- Produce a structured review.
- Optionally generate fix suggestions.

#### Input Schema

```yaml
project_path: string

review_target:
  type: working_tree | diff | branch | pr
  value: string

review_focus:
  - correctness
  - security
  - performance
  - maintainability
  - test_coverage

mode: review_only | suggest | fix
```

#### Output Schema

```yaml
summary:
  verdict: looks_good | needs_attention | request_changes

findings:
  - severity: high | medium | low
    file: string
    line: number
    category: correctness | security | performance
    issue: string
    impact: string
    suggestion: string

coverage:
  missing_tests:
    - string

risks:
  - string

suggested_patch: string
```

#### Permission Model

The Review Agent should use a stricter permission model than the Code Agent.

| Capability | Status |
|---|---|
| Read project files | Allowed |
| Read diffs | Allowed |
| Write files | Blocked by default |
| Shell commands | Read-only commands only |
| Git operations | Diff and log only |
| Network access | Blocked |
| Secrets | Blocked |

#### Workflow

1. Load Context
   - Read repository metadata.
   - Read the target diff, branch, PR, or working tree.

2. Impact Analysis
   - Identify affected modules.
   - Trace dependencies and call paths.

3. Review Passes
   - Correctness.
   - Edge cases.
   - Error handling.
   - Security.
   - Performance.
   - Test coverage.

4. Risk Aggregation
   - Summarize critical issues and residual risk.

5. Output Structured Review
   - Return findings first, ordered by severity.

### 2.3 Interview Preparing Agent

The Interview Preparing Agent is a coaching-oriented agent.

#### Responsibilities

- Generate interview preparation plans.
- Run mock interviews.
- Critique candidate answers.
- Perform gap analysis.
- Track ongoing training progress.

#### Input Schema

```yaml
candidate:
  background: string
  experience_years: number
  target_role: string

job:
  company: string
  description: string

mode: plan | mock | critique | gap_analysis

options:
  difficulty: easy | medium | hard
  round: coding | system_design | behavioral
```

#### Output Schema

```yaml
mode: plan | mock | critique | gap_analysis

plan:
  topics:
    - string
  schedule:
    - day: number
      focus: string

mock:
  question: string
  follow_ups:
    - string

critique:
  strengths:
    - string
  weaknesses:
    - string
  improved_answer: string

gaps:
  - area: string
    recommendation: string
```

#### Permission Model

The Interview Agent should use the lightest permission model.

| Capability | Status |
|---|---|
| File read/write | Optional |
| Shell commands | Blocked |
| Network access | Optional |
| Secrets | Blocked |

#### Workflow

1. Understand Candidate
2. Map Job Requirements
3. Generate Strategy
4. Produce Output
5. Track Progress with optional memory

## 3. Proposed Directory Structure

```text
agent-platform/
|
+-- core/
|   +-- runner/
|   |   +-- executor.py
|   |   +-- sandbox.py
|   |
|   +-- policy/
|   |   +-- engine.py
|   |   +-- rules.py
|   |
|   +-- planner/
|   |   +-- planner.py
|   |
|   +-- memory/
|   |   +-- store.py
|   |
|   +-- approval/
|   |   +-- gate.py
|   |
|   +-- tools/
|   |   +-- file_tool.py
|   |   +-- shell_tool.py
|   |   +-- git_tool.py
|   |
|   +-- reporting/
|       +-- formatter.py
|
+-- agents/
|   +-- code_agent/
|   |   +-- prompt.md
|   |   +-- workflow.py
|   |   +-- schema.py
|   |   +-- policy.yaml
|   |
|   +-- review_agent/
|   |   +-- prompt.md
|   |   +-- workflow.py
|   |   +-- schema.py
|   |   +-- policy.yaml
|   |
|   +-- interview_agent/
|       +-- prompt.md
|       +-- workflow.py
|       +-- schema.py
|       +-- policy.yaml
|
+-- profiles/
|   +-- safe.yaml
|   +-- balanced.yaml
|   +-- full_auto.yaml
|
+-- configs/
|   +-- agent.yaml
|
+-- cli/
    +-- main.py
```

## 4. Unified Configuration File

Example: `configs/agent.yaml`

```yaml
agent: code_agent

project: /workspace/project

goal: "implement login retry limit and add tests"

profile: balanced

limits:
  max_iterations: 20

policy:
  allow_network: false
  allow_delete: false
  allow_dependency_changes: ask

paths:
  writable:
    - src/**
    - tests/**
  blocked:
    - .env
    - .env.*
    - secrets/**
    - ~/.ssh/**
    - /etc/**
    - /System/**
    - /usr/**

commands:
  allow:
    - pytest
    - npm test
    - pnpm build
    - git diff
  deny:
    - rm
    - sudo
    - chmod
    - chown
    - dd

approvals:
  required_for:
    - delete_file
    - dependency_change
    - network_access

rollback:
  git_checkpoint: true
  save_patch: true
  trash_instead_of_delete: true
```

## 5. Profile Examples

Example: `profiles/safe.yaml`

```yaml
allow_network: false
allow_delete: false
allow_dependency_changes: false
```

Example: `profiles/balanced.yaml`

```yaml
allow_network: ask
allow_delete: ask
allow_dependency_changes: ask
```

Example: `profiles/full_auto.yaml`

```yaml
allow_network: true
allow_delete: true
allow_dependency_changes: true
```

## 6. CLI Usage

Run with a configuration file:

```bash
agent run \
  --config configs/agent.yaml
```

Run with explicit CLI options:

```bash
agent run \
  --agent code_agent \
  --project ./repo \
  --goal "fix auth bug" \
  --profile balanced
```

## 7. Key Design Principles

### 7.1 Do Not Trust the Model

All dangerous operations must be checked by both:

- The policy engine.
- The runner.

The model may request an action, but the platform decides whether the action is allowed.

### 7.2 Every Change Must Be Reversible

The platform must preserve rollback paths through:

- Git checkpoints.
- Patch records.
- Optional trash-based deletion instead of direct removal.

### 7.3 Default to Least Privilege

Each agent should start with the minimum permission set required for its job.

- The Review Agent should be read-only by default.
- The Interview Agent should have no shell access.
- Network access should be explicit, not implicit.

### 7.4 Combine Autonomy with Control

The platform should allow the agent to proceed automatically on low-risk work, while pausing for approval when risk increases.

The target behavior is:

- Automatic execution for safe operations.
- Approval gates for risky operations.
- Hard blocks for secrets, system files, and forbidden commands.

## 8. Summary

This system is a general-purpose agent platform with sandboxing, permissions, approvals, rollback, and structured reporting. On top of that platform, three specialized agents can run with different responsibilities:

- Code Agent for implementation.
- Review Agent for auditing.
- Interview Preparing Agent for coaching.

The practical next implementation target is a minimum viable version of the platform: a Python runner, policy engine, and Code Agent workflow. After that foundation is stable, Claude Code or another model provider can be connected as the reasoning layer.
