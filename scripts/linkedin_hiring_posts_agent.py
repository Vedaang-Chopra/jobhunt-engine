#!/usr/bin/env python3
"""LinkedIn hiring-post discovery driven by the web_nav_agent loop.

Read-only: the goal contract prohibits apply/message/connect/post/comment/
settings actions. Extracted posts are appended to
<data_root>/tracking/hiring_posts/hiring_posts.csv using the canonical 17-col
schema from scripts/linkedin_posts_sweep.py (append_rows + to_post_row).
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:
    import config_lib  # noqa: E402

from browser_session_lib import open_logged_in_session  # noqa: E402
from web_nav_agent.agent import run as run_agent  # noqa: E402
from web_nav_agent.goal import GoalContract  # noqa: E402

GOAL_YAML = """\
description: >
  Find LinkedIn posts that signal HIRING (poster is a founder/eng manager/recruiter
  or post announces open roles). Scroll the feed, identify hiring-signal posts,
  and extract company, role(s), poster, and post url for each.
success_conditions:
  - At least one post extracted with company + role + hiring signal.
stop_conditions:
  - 5 consecutive observations with no new content.
  - Auth required / challenge page detected.
  - Action or time budget exhausted.
allowed_actions: [navigate, click, type, scroll, press_key, wait, extract, done]
prohibited_actions:
  - submit application
  - send message
  - connect
  - post
  - comment
  - modify settings
max_actions: 40
max_seconds: 600
allowed_domains: [linkedin.com]
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="linkedin_hiring_posts_agent",
        description="LLM-agent sweep of LinkedIn feed for hiring posts.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print extracted posts; do not write CSV")
    parser.add_argument("--max-actions", type=int, default=None,
                        help="Override goal max_actions")
    parser.add_argument("--task-hint", default="",
                        help="Extra hint for the LLM")
    parser.add_argument("--source", default="linkedin_hiring_posts_agent")
    args = parser.parse_args(argv)
    result: dict = {"status": "ERROR", "stop_reason": "not run", "extracted": []}

    if args.max_actions is not None:
        if args.max_actions < 0:
            parser.error("--max-actions must be >= 0")
        if args.max_actions == 0:
            # Arg-validation path only: nothing to run.
            print("max_actions=0 -> no-op run (arg validation path)")
            return 0

    import yaml
    goal_dict = yaml.safe_load(GOAL_YAML)
    if args.max_actions is not None:
        goal_dict["max_actions"] = args.max_actions
    goal = GoalContract.from_dict(goal_dict)

    with open_logged_in_session(source=args.source) as session:
        result = run_agent(session, goal, task_hint=args.task_hint)

    posts = []
    for entity in result.get("extracted", []):
        if isinstance(entity, dict) and (entity.get("company") or
                                         entity.get("poster") or
                                         entity.get("roles_mentioned")):
            posts.append(entity)

    print(f"status={result['status']} stop={result['stop_reason']} "
          f"posts={len(posts)}")
    if not posts:
        return _exit_code(result)

    discovered_date = datetime.now().strftime("%Y-%m-%d")
    run_tag = f"wna_{uuid.uuid4().hex[:6]}"
    try:
        from linkedin_posts_sweep import append_rows, to_post_row
        rows = [to_post_row(p, discovered_date,
                            f"web_nav_agent:{run_tag}") for p in posts]
    except ImportError:
        rows = [_fallback_row(p, discovered_date) for p in posts]

    if args.dry_run:
        for r in rows:
            print(r.get("post_id"), "|", r.get("company"),
                  "|", r.get("roles_mentioned"))
        print(f"DRY-RUN: would append {len(rows)} rows")
    else:
        out_csv = (config_lib.data_root() / "tracking" / "hiring_posts"
                   / "hiring_posts.csv")
        n = _append(rows, out_csv)
        print(f"appended {n} rows to {out_csv}")
    return _exit_code(result)


def _append(rows, out_csv) -> int:
    """Append via linkedin_posts_sweep.append_rows when importable."""
    from linkedin_posts_sweep import POSTS_HEADER, append_rows
    return append_rows(rows, out_csv)


def _fallback_row(post: dict, discovered_date: str) -> dict:
    header = [
        "post_id", "poster_name", "poster_headline", "poster_type", "company",
        "team_or_org", "post_url", "posted_date", "discovered_date",
        "roles_mentioned", "application_url", "connection_degree",
        "shared_context", "priority", "role_family", "status", "notes",
    ]
    row = {k: "" for k in header}
    slug_src = (post.get("company") or post.get("poster") or "post")
    slug = "".join(c if c.isalnum() else "_" for c in str(slug_src).lower())[:40].strip("_")
    tail = "".join(c for c in str(post.get("post_url") or post.get("urn") or "x")
                   if c.isalnum())[-8:] or "x"
    row.update({
        "post_id": f"lpk_{slug}_{discovered_date}_{tail}",
        "poster_name": post.get("poster", ""),
        "company": post.get("company", ""),
        "post_url": post.get("post_url", ""),
        "posted_date": post.get("posted_date", ""),
        "discovered_date": discovered_date,
        "roles_mentioned": post.get("roles_mentioned", ""),
        "status": "new",
        "notes": "web_nav_agent",
    })
    return row


def _exit_code(result: dict) -> int:
    return 3 if result.get("status") == "AUTH_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
