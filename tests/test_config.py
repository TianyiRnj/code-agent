"""Tests for agent.config."""

from __future__ import annotations

import pytest

from agent.config import Mode, TaskConfig, _preset


def test_default_mode_is_balanced() -> None:
    assert TaskConfig().mode == Mode.BALANCED


def test_from_yaml_loads_mode(tmp_path: pytest.TempdirFactory) -> None:
    f = tmp_path / "task.yaml"  # type: ignore[operator]
    f.write_text("mode: safe\nproject: ./\ngoal: test")  # type: ignore[union-attr]
    config = TaskConfig.from_yaml(f)  # type: ignore[arg-type]
    assert config.mode == Mode.SAFE


def test_from_yaml_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        TaskConfig.from_yaml("/nonexistent/task.yaml")


def test_from_yaml_empty_file_gives_balanced_defaults(tmp_path: pytest.TempdirFactory) -> None:
    f = tmp_path / "task.yaml"  # type: ignore[operator]
    f.write_text("")  # type: ignore[union-attr]
    config = TaskConfig.from_yaml(f)  # type: ignore[arg-type]
    assert config.mode == Mode.BALANCED


def test_safe_preset_has_rm_in_deny() -> None:
    config = _preset(Mode.SAFE)
    assert any("rm" in d for d in config.commands.deny)


def test_safe_preset_capabilities_are_false() -> None:
    config = _preset(Mode.SAFE)
    assert config.capabilities.delete_files is False
    assert config.capabilities.install_dependencies is False
    assert config.capabilities.network_access is False


def test_balanced_preset_delete_is_confirm() -> None:
    config = _preset(Mode.BALANCED)
    assert config.capabilities.delete_files == "confirm"
    assert config.capabilities.install_dependencies == "confirm"
    assert config.capabilities.network_access == "confirm"


def test_full_auto_preset_capabilities_are_true() -> None:
    config = _preset(Mode.FULL_AUTO)
    assert config.capabilities.delete_files is True
    assert config.capabilities.install_dependencies is True
    assert config.capabilities.network_access is True


def test_balanced_preset_has_rollback_enabled() -> None:
    config = _preset(Mode.BALANCED)
    assert config.rollback.git_checkpoint is True
    assert config.rollback.save_patch is True


def test_apply_overrides_sets_goal_and_mode() -> None:
    config = TaskConfig()
    config.apply_overrides(goal="add tests", mode="safe")
    assert config.goal == "add tests"
    assert config.mode == Mode.SAFE


def test_apply_overrides_ignores_none() -> None:
    config = TaskConfig(goal="original")
    config.apply_overrides(goal=None, project=None)
    assert config.goal == "original"


def test_apply_overrides_ignores_unknown_keys() -> None:
    config = TaskConfig()
    config.apply_overrides(nonexistent_key="value")  # should not raise


def test_from_yaml_goal_overrides_preset(tmp_path: pytest.TempdirFactory) -> None:
    f = tmp_path / "task.yaml"  # type: ignore[operator]
    f.write_text("mode: full-auto\ngoal: deploy to prod")  # type: ignore[union-attr]
    config = TaskConfig.from_yaml(f)  # type: ignore[arg-type]
    assert config.goal == "deploy to prod"
    assert config.mode == Mode.FULL_AUTO
