"""CLI entry point for the code agent."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from agent.config import Mode, TaskConfig, load_env_file


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
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: WARNING)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s  %(name)s  %(message)s",
    )

    load_env_file()

    config_path = Path(args.config)
    config = TaskConfig.from_yaml(config_path) if config_path.exists() else TaskConfig()
    config.apply_overrides(project=args.project, goal=args.goal, mode=args.mode)

    if not config.goal:
        print("error: no goal specified (use --goal or set goal in task.yaml)", file=sys.stderr)
        sys.exit(1)

    # Import here so the CLI starts up without requiring ANTHROPIC_API_KEY
    # when --help is used.
    from agent.core import Agent  # noqa: PLC0415

    agent = Agent(config)
    sys.exit(agent.run())


if __name__ == "__main__":
    main()
