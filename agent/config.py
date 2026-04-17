"""TaskConfig: data model for task.yaml + CLI overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Union

import yaml

CapabilityValue = Union[bool, Literal["confirm"]]
ANTHROPIC_MODEL_ENV = "ANTHROPIC_MODEL"
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_DOTENV_PATH = ".env"


class Mode(str, Enum):
    SAFE = "safe"
    BALANCED = "balanced"
    FULL_AUTO = "full-auto"


@dataclass
class WorkspaceConfig:
    root: str = "./"
    # Empty list means "anywhere inside root is writable" (still subject to blocked_paths).
    writable_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(
        default_factory=lambda: [
            ".env",
            ".env.*",
            "secrets/**",
            "~/.ssh/**",
            "~/.aws/**",
            "/etc/**",
            "/System/**",
            "/usr/**",
        ]
    )


@dataclass
class Capabilities:
    read_project_code: CapabilityValue = True
    write_project_code: CapabilityValue = True
    run_tests: CapabilityValue = True
    delete_files: CapabilityValue = False
    install_dependencies: CapabilityValue = False
    network_access: CapabilityValue = False
    write_outside_workspace: CapabilityValue = False


@dataclass
class CommandsConfig:
    allow: list[str] = field(
        default_factory=lambda: [
            "git status",
            "git diff",
            "rg",
            "cat",
            "pytest",
            "npm test",
            "pnpm test",
            "pnpm build",
        ]
    )
    deny: list[str] = field(
        default_factory=lambda: [
            "sudo",
            "chmod",
            "chown",
            "dd",
            "mkfs",
            "fdisk",
            "curl | sh",
            "wget | sh",
        ]
    )


@dataclass
class ApprovalsConfig:
    require_for: list[str] = field(default_factory=list)


@dataclass
class RollbackConfig:
    git_checkpoint: bool = False
    save_patch: bool = False
    trash_instead_of_delete: bool = False


@dataclass
class GitConfig:
    auto_checkpoint: bool = True
    checkpoint_prefix: str = "chkpt"


@dataclass
class TaskConfig:
    project: str = "./"
    goal: str = ""
    model: str = DEFAULT_MODEL
    mode: Mode = Mode.BALANCED
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    capabilities: Capabilities = field(default_factory=Capabilities)
    commands: CommandsConfig = field(default_factory=CommandsConfig)
    approvals: ApprovalsConfig = field(default_factory=ApprovalsConfig)
    rollback: RollbackConfig = field(default_factory=RollbackConfig)
    git: GitConfig = field(default_factory=GitConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TaskConfig":
        """Load config from a YAML file; starts from mode preset then applies overrides."""
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        mode = Mode(data.pop("mode", Mode.BALANCED.value))
        config = _preset(mode)

        for key in ("project", "goal", "model"):
            if key in data:
                setattr(config, key, data.pop(key))

        _nested: dict[str, type[Any]] = {
            "workspace": WorkspaceConfig,
            "capabilities": Capabilities,
            "commands": CommandsConfig,
            "approvals": ApprovalsConfig,
            "rollback": RollbackConfig,
            "git": GitConfig,
        }
        for attr, klass in _nested.items():
            if attr in data:
                setattr(config, attr, klass(**data.pop(attr)))

        return config

    def apply_overrides(self, **kwargs: Any) -> None:
        """Merge CLI overrides into config; None values and unknown keys are ignored."""
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "mode":
                self.mode = Mode(value)
            elif hasattr(self, key):
                setattr(self, key, value)

    def effective_model(self) -> str:
        """Return the model selected for API calls, preferring ANTHROPIC_MODEL."""
        return os.environ.get(ANTHROPIC_MODEL_ENV, self.model)


def load_env_file(path: str | Path = DEFAULT_DOTENV_PATH) -> None:
    """Load KEY=VALUE pairs from a .env file without overriding existing variables."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = _clean_env_value(value)


def _clean_env_value(value: str) -> str:
    """Remove surrounding whitespace and simple matching quotes from an env value."""
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned


# ---------------------------------------------------------------------------
# Mode presets
# ---------------------------------------------------------------------------


def _preset(mode: Mode) -> TaskConfig:
    """Return a TaskConfig pre-populated with defaults for the given mode."""
    if mode == Mode.SAFE:
        return TaskConfig(
            mode=mode,
            capabilities=Capabilities(
                delete_files=False,
                install_dependencies=False,
                network_access=False,
            ),
            commands=CommandsConfig(
                deny=[
                    "rm",
                    "sudo",
                    "chmod",
                    "chown",
                    "dd",
                    "mkfs",
                    "fdisk",
                    "curl | sh",
                    "wget | sh",
                ],
            ),
            approvals=ApprovalsConfig(require_for=[]),
            rollback=RollbackConfig(
                git_checkpoint=False,
                save_patch=False,
                trash_instead_of_delete=False,
            ),
        )

    if mode == Mode.BALANCED:
        return TaskConfig(
            mode=mode,
            capabilities=Capabilities(
                delete_files="confirm",
                install_dependencies="confirm",
                network_access="confirm",
            ),
            commands=CommandsConfig(
                deny=[
                    "sudo",
                    "chmod",
                    "chown",
                    "dd",
                    "mkfs",
                    "fdisk",
                    "curl | sh",
                    "wget | sh",
                ],
            ),
            approvals=ApprovalsConfig(
                require_for=[
                    "delete_file",
                    "dependency_change",
                    "lockfile_change",
                    "migration",
                    "ci_change",
                    "network_access",
                    "sensitive_file_access",
                ]
            ),
            rollback=RollbackConfig(
                git_checkpoint=True,
                save_patch=True,
                trash_instead_of_delete=True,
            ),
        )

    # full-auto
    return TaskConfig(
        mode=mode,
        capabilities=Capabilities(
            delete_files=True,
            install_dependencies=True,
            network_access=True,
        ),
        commands=CommandsConfig(
            allow=[
                "git status",
                "git diff",
                "rg",
                "cat",
                "pytest",
                "npm test",
                "pnpm test",
                "pnpm build",
                "pip install",
                "npm install",
                "pnpm install",
                "rm",
            ],
            deny=[
                "sudo",
                "chmod",
                "chown",
                "dd",
                "mkfs",
                "fdisk",
                "curl | sh",
                "wget | sh",
            ],
        ),
        approvals=ApprovalsConfig(require_for=[]),
        rollback=RollbackConfig(
            git_checkpoint=True,
            save_patch=True,
            trash_instead_of_delete=True,
        ),
    )
