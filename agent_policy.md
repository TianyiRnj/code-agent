# Agent Policy

## Profiles

The agent operates in one of three permission profiles. Set via `task.yaml` (`mode: safe | balanced | full-auto`) or `--mode` CLI flag.

---

### safe

For everyday automated development in shared or production-adjacent environments.

```yaml
mode: safe

workspace:
  root: /workspace/project
  writable_paths:
    - src/**
    - tests/**
    - docs/**
  blocked_paths:
    - .env
    - .env.*
    - secrets/**
    - ~/.ssh/**
    - ~/.aws/**
    - /etc/**
    - /System/**
    - /usr/**

capabilities:
  read_project_code: true
  write_project_code: true
  run_tests: true
  delete_files: false
  install_dependencies: false
  network_access: false
  write_outside_workspace: false

commands:
  allow:
    - git status
    - git diff
    - rg
    - cat
    - pytest
    - npm test
    - pnpm test
    - pnpm build
  deny:
    - rm
    - sudo
    - chmod
    - chown
    - dd
    - mkfs
    - fdisk
    - "curl | sh"
    - "wget | sh"

approvals:
  require_for: []   # nothing requires approval; forbidden actions are hard-blocked
```

---

### balanced

For most day-to-day tasks. Same as `safe` plus the ability to install deps, modify lockfiles, delete workspace files, and call external APIs — each requiring user confirmation.

```yaml
mode: balanced

workspace:
  root: /workspace/project
  writable_paths:
    - src/**
    - tests/**
    - docs/**
  blocked_paths:
    - .env
    - .env.*
    - secrets/**
    - ~/.ssh/**
    - ~/.aws/**
    - /etc/**
    - /System/**
    - /usr/**

capabilities:
  read_project_code: true
  write_project_code: true
  run_tests: true
  delete_files: confirm        # allowed, but requires approval
  install_dependencies: confirm
  network_access: confirm
  write_outside_workspace: false

commands:
  allow:
    - git status
    - git diff
    - rg
    - cat
    - pytest
    - npm test
    - pnpm test
    - pnpm build
  deny:
    - sudo
    - chmod
    - chown
    - dd
    - mkfs
    - fdisk
    - "curl | sh"
    - "wget | sh"

approvals:
  require_for:
    - delete_file
    - dependency_change
    - lockfile_change
    - migration
    - ci_change
    - network_access
    - sensitive_file_access

rollback:
  git_checkpoint: true
  save_patch: true
  trash_instead_of_delete: true
```

---

### full-auto

For isolated / sandboxed environments (CI, containers, ephemeral VMs). Most project operations proceed without confirmation; system paths and secrets remain hard-blocked; rollback is always preserved.

```yaml
mode: full-auto

workspace:
  root: /workspace/project
  writable_paths:
    - "**"
  blocked_paths:
    - .env
    - .env.*
    - secrets/**
    - ~/.ssh/**
    - ~/.aws/**
    - /etc/**
    - /System/**
    - /usr/**

capabilities:
  read_project_code: true
  write_project_code: true
  run_tests: true
  delete_files: true           # no confirmation needed
  install_dependencies: true
  network_access: true
  write_outside_workspace: false

commands:
  allow:
    - git status
    - git diff
    - rg
    - cat
    - pytest
    - npm test
    - pnpm test
    - pnpm build
    - pip install
    - npm install
    - pnpm install
    - rm                       # within workspace only
  deny:
    - sudo
    - chmod
    - chown
    - dd
    - mkfs
    - fdisk
    - "curl | sh"
    - "wget | sh"

approvals:
  require_for: []   # fully automated; blocked_paths still enforced unconditionally

rollback:
  git_checkpoint: true
  save_patch: true
  trash_instead_of_delete: true
```

---

## Summary

| Capability | safe | balanced | full-auto |
|---|---|---|---|
| Read project code | yes | yes | yes |
| Write project code | yes | yes | yes |
| Run tests | yes | yes | yes |
| Delete files | no | confirm | yes |
| Install dependencies | no | confirm | yes |
| Network / external API | no | confirm | yes |
| Write outside workspace | no | no | no |
| System dirs / secrets | blocked | blocked | blocked |
| Git checkpoint | no | yes | yes |
| Save rollback patch | no | yes | yes |

## Enforcement

- `blocked_paths` are **hard-blocked** in all modes — no override, no approval flow.
- `deny` command patterns are **hard-blocked** in all modes.
- `confirm` capabilities pause execution and print the proposed action; the agent resumes only on explicit approval (`y`) or aborts on denial.
- `git_checkpoint` runs automatically before the first destructive operation in a session.
