"""CLI wrapper for one adaptive discovery cycle (Task 10).

Usage:
    python scripts/discovery_cycle.py --modes jobs,posts,feed --budget 15 [--dry-run]

Exit codes: 0 completed/dry-run, 2 stopped on authwall/CAPTCHA,
3 when the production planner or executor modules are not available yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from search_strategy import cycle as cycle_mod
except ImportError:  # pragma: no cover - direct-script fallback
    import cycle as cycle_mod  # type: ignore


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run one adaptive discovery cycle.")
    parser.add_argument("--modes", default="jobs,posts,feed",
                        help="Comma-separated search modes (default: jobs,posts,feed)")
    parser.add_argument("--budget", type=int, default=15,
                        help="Total query budget across modes (default: 15)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Plan only; do not execute any queries")
    parser.add_argument("--data-root", default=None,
                        help="Override data root for policy/memory resolution")
    args = parser.parse_args(argv)

    if args.data_root:
        import os
        os.environ["JOBHUNT_HOME"] = args.data_root

    planner_fn = cycle_mod._default_planner
    executor_factory = cycle_mod._default_executor_factory

    if planner_fn is None or executor_factory is None:
        print("planner/executor not available yet")
        return 3
    executor_fn = executor_factory()
    if executor_fn is None:
        print("planner/executor not available yet")
        return 3

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    summary = cycle_mod.run_cycle(modes=modes, total_budget=args.budget,
                                  planner_fn=planner_fn, executor_fn=executor_fn,
                                  dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, default=str))
    if summary.get("status") == "stopped_authwall":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
