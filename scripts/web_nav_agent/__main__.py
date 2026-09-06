"""CLI: python -m web_nav_agent --goal-yaml goal.yaml [--task-hint ...].

Exit code 3 when status == AUTH_REQUIRED so cron wrappers can surface it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from browser_session_lib import open_logged_in_session  # noqa: E402
from web_nav_agent.agent import run as run_agent  # noqa: E402
from web_nav_agent.goal import GoalContract  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="web_nav_agent",
        description="Hybrid deterministic+LLM web navigation agent.")
    parser.add_argument("--goal-yaml", required=True,
                        help="Path to a goal YAML file")
    parser.add_argument("--task-hint", default="",
                        help="Extra hint text passed to the LLM")
    parser.add_argument("--source", default="web_nav_agent",
                        help="Session source label for logging")
    args = parser.parse_args(argv)

    goal = GoalContract.from_yaml(args.goal_yaml)
    result: dict = {"run_id": "", "status": "ERROR", "extracted": [],
                    "actions": [], "stop_reason": "session not opened"}
    with open_logged_in_session(source=args.source) as session:
        result = run_agent(session, goal, task_hint=args.task_hint)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 3 if result.get("status") == "AUTH_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
