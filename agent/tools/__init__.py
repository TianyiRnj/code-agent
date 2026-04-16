"""ALL_TOOLS: registry of all available tool functions."""

from agent.tools.files import list_dir, patch_file, read_file, write_file
from agent.tools.git import git_checkpoint, git_commit, git_diff, git_rollback
from agent.tools.shell import run_command

ALL_TOOLS = [
    read_file,
    write_file,
    patch_file,
    list_dir,
    run_command,
    git_checkpoint,
    git_rollback,
    git_diff,
    git_commit,
]
