"""CLI entry point for the code agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent.config import Mode, TaskConfig


def main() -> None:
    """Parse CLI args, load config, and run the agent."""
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Autonomous coding agent powered by Claude.",
    )
    parser.add_argument("--project", help="Path to the target project")
    parser.add_argument("--goal", help="Goal to accomplish")
    parser.add_argument(
        "--mode",
        choices=[m.value for m in Mode],
        help="Permission mode: safe | balanced | full-auto",
    )
    parser.add_argument(
        "--config",
        default="task.yaml",
        help="Path to task.yaml config file (default: task.yaml)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    config = TaskConfig.from_yaml(config_path) if config_path.exists() else TaskConfig()
    config.apply_overrides(project=args.project, goal=args.goal, mode=args.mode)

    if not config.goal:
        print("error: no goal specified (use --goal or set goal in task.yaml)", file=sys.stderr)
        sys.exit(1)

    # Agent.run() will be wired up when core.py is implemented.
    print(f"project : {config.project}")
    print(f"goal    : {config.goal}")
    print(f"model   : {config.model}")
    print(f"mode    : {config.mode.value}")
    print("(agent loop not yet implemented)")


if __name__ == "__main__":
    main()
