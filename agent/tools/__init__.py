"""Tool registry — import all tool modules to trigger @tool registration."""

from agent.tools.files import list_dir, patch_file, read_file, write_file
from agent.tools.git import git_checkpoint, git_commit, git_diff, git_rollback
from agent.tools.registry import ToolDef, all_tools, execute
from agent.tools.shell import run_command

__all__ = [
    # registry API
    "ToolDef",
    "all_tools",
    "execute",
    # individual tools
    "read_file",
    "write_file",
    "patch_file",
    "list_dir",
    "run_command",
    "git_checkpoint",
    "git_rollback",
    "git_diff",
    "git_commit",
]
