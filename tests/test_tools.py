"""Functional tests for the six standalone tools."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent.tools import all_tools, execute
from agent.tools.files import list_dir, read_file, write_file
from agent.tools.git import git_checkpoint, git_diff
from agent.tools.shell import run_command

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Return a path containing a freshly initialised git repo with one commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "ci@test.local"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "CI"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("# test repo")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


def test_read_file_returns_content(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    assert read_file(str(f)) == "hello world"


def test_read_file_preserves_newlines(tmp_path: Path) -> None:
    f = tmp_path / "multi.txt"
    f.write_text("line1\nline2\nline3")
    assert read_file(str(f)) == "line1\nline2\nline3"


def test_read_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_file(str(tmp_path / "nope.txt"))


def test_read_file_roundtrips_with_write(tmp_path: Path) -> None:
    path = str(tmp_path / "rt.txt")
    write_file(path, "roundtrip")
    assert read_file(path) == "roundtrip"


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------


def test_write_file_creates_file(tmp_path: Path) -> None:
    path = str(tmp_path / "out.txt")
    write_file(path, "content")
    assert Path(path).read_text() == "content"


def test_write_file_creates_parent_dirs(tmp_path: Path) -> None:
    path = str(tmp_path / "a" / "b" / "c.txt")
    write_file(path, "nested")
    assert Path(path).read_text() == "nested"


def test_write_file_overwrites_existing(tmp_path: Path) -> None:
    path = str(tmp_path / "file.txt")
    write_file(path, "first")
    write_file(path, "second")
    assert Path(path).read_text() == "second"


def test_write_file_returns_byte_count(tmp_path: Path) -> None:
    result = write_file(str(tmp_path / "f.txt"), "hello")
    assert "5" in result  # 5 bytes


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------


def test_list_dir_returns_all_entries(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "sub").mkdir()
    entries = list_dir(str(tmp_path))
    names = {Path(e).name for e in entries}
    assert names == {"a.txt", "b.txt", "sub"}


def test_list_dir_is_sorted(tmp_path: Path) -> None:
    for name in ("z.py", "a.py", "m.py"):
        (tmp_path / name).write_text("")
    entries = list_dir(str(tmp_path))
    assert entries == sorted(entries)


def test_list_dir_empty_dir(tmp_path: Path) -> None:
    sub = tmp_path / "empty"
    sub.mkdir()
    assert list_dir(str(sub)) == []


def test_list_dir_nonexistent_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        list_dir(str(tmp_path / "ghost"))


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------


def test_run_command_returns_stdout() -> None:
    out = run_command("echo hello")
    assert "hello" in out


def test_run_command_respects_cwd(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("")
    out = run_command("ls", cwd=str(tmp_path))
    assert "marker.txt" in out


def test_run_command_raises_on_nonzero_exit() -> None:
    with pytest.raises(RuntimeError, match="command failed"):
        run_command("false")


def test_run_command_includes_stderr_in_error() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        run_command("ls /no_such_dir_xyz_abc 2>&1; exit 1")
    assert "command failed" in str(exc_info.value)


def test_run_command_timeout_raises() -> None:
    with pytest.raises(Exception):  # subprocess.TimeoutExpired
        run_command("sleep 10", timeout=1)


def test_run_command_multiline_output() -> None:
    out = run_command("printf 'a\\nb\\nc\\n'")
    assert out.count("\n") >= 3


# ---------------------------------------------------------------------------
# git_diff
# ---------------------------------------------------------------------------


def test_git_diff_empty_on_clean_repo(git_repo: Path) -> None:
    diff = git_diff(cwd=str(git_repo))
    assert diff.strip() == ""


def test_git_diff_shows_modification(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("# modified")
    diff = git_diff(cwd=str(git_repo))
    assert "modified" in diff


def test_git_diff_no_diff_for_untracked_file(git_repo: Path) -> None:
    # Untracked files don't appear in `git diff` (unstaged)
    (git_repo / "new.py").write_text("x = 1")
    diff = git_diff(cwd=str(git_repo))
    assert diff.strip() == ""


def test_git_diff_returns_string(git_repo: Path) -> None:
    result = git_diff(cwd=str(git_repo))
    assert isinstance(result, str)


def test_git_diff_outside_repo_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="git diff failed"):
        git_diff(cwd=str(tmp_path))


# ---------------------------------------------------------------------------
# git_checkpoint
# ---------------------------------------------------------------------------


def _log(repo: Path, n: int = 1) -> str:
    return subprocess.check_output(["git", "log", "--oneline", f"-{n}"], cwd=repo, text=True)


def test_git_checkpoint_creates_commit(git_repo: Path) -> None:
    (git_repo / "feature.py").write_text("x = 1")
    git_checkpoint(cwd=str(git_repo))
    assert "chkpt:" in _log(git_repo)


def test_git_checkpoint_uses_custom_prefix(git_repo: Path) -> None:
    (git_repo / "f.py").write_text("y = 2")
    git_checkpoint(prefix="snap", cwd=str(git_repo))
    assert "snap:" in _log(git_repo)


def test_git_checkpoint_includes_timestamp(git_repo: Path) -> None:
    (git_repo / "g.py").write_text("z = 3")
    git_checkpoint(cwd=str(git_repo))
    log = _log(git_repo)
    # Timestamp format: YYYYMMDD-HHMMSS
    import re

    assert re.search(r"chkpt: \d{8}-\d{6}", log)


def test_git_checkpoint_on_clean_repo_succeeds(git_repo: Path) -> None:
    # --allow-empty: checkpoint works even with no changes
    result = git_checkpoint(cwd=str(git_repo))
    assert isinstance(result, str)


def test_git_checkpoint_stages_all_changes(git_repo: Path) -> None:
    (git_repo / "staged.py").write_text("a = 1")
    (git_repo / "unstaged.py").write_text("b = 2")
    git_checkpoint(cwd=str(git_repo))
    # After checkpoint, working tree should be clean
    status = subprocess.check_output(["git", "status", "--short"], cwd=git_repo, text=True)
    assert status.strip() == ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_six_tools_are_registered() -> None:
    names = {td.name for td in all_tools()}
    for expected in (
        "read_file",
        "write_file",
        "list_dir",
        "run_command",
        "git_diff",
        "git_checkpoint",
    ):
        assert expected in names, f"{expected} not registered"


def test_all_tools_have_valid_schemas() -> None:
    for td in all_tools():
        assert td.input_schema["type"] == "object"
        assert "properties" in td.input_schema
        assert "guard" not in td.input_schema["properties"], (
            f"{td.name}: guard must not appear in schema"
        )


def test_all_tools_have_descriptions() -> None:
    for td in all_tools():
        assert td.description, f"{td.name}: description is empty"


def test_execute_read_file(tmp_path: Path) -> None:
    path = str(tmp_path / "exec.txt")
    write_file(path, "via execute")
    result = execute("read_file", {"path": path})
    assert result == "via execute"


def test_execute_write_file(tmp_path: Path) -> None:
    path = str(tmp_path / "written.txt")
    execute("write_file", {"path": path, "content": "hello"})
    assert Path(path).read_text() == "hello"


def test_execute_run_command() -> None:
    result = execute("run_command", {"cmd": "echo registry"})
    assert "registry" in result


def test_execute_unknown_tool_raises() -> None:
    with pytest.raises(KeyError):
        execute("no_such_tool", {})


def test_execute_injects_guard(tmp_path: Path) -> None:
    from agent.config import Mode, _preset
    from agent.policy import BlockedPathError, PolicyGuard

    env = tmp_path / ".env"
    env.write_text("SECRET=x")
    guard = PolicyGuard(_preset(Mode.BALANCED))

    with pytest.raises(BlockedPathError):
        execute("read_file", {"path": str(env)}, guard=guard)
