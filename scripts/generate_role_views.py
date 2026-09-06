#!/usr/bin/env python3
"""Regenerate job_research/roles/<family>/job-postings.csv from tracking/jobs/jobs.csv.

Single source of truth: tracking/jobs/jobs.csv (open rows only, scored rows first).
Role views are derived artifacts — never edit them by hand; rerun this script
after every sweep or re-score.

Usage:
    python3 scripts/generate_role_views.py            # rebuild all views
    python3 scripts/generate_role_views.py --dry-run  # show counts only

Family mapping (jobs.csv role_family -> view directory) is defined in
job_research/roles/_role-registry.md and mirrored in ROLE_VIEWS below.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
JOBS_CSV = config_lib.path("jobs_csv")
ROLES_DIR = config_lib.path("role_views_dir")

# jobs.csv role_family (SCHEMA.md) -> view directory name (_role-registry.md)
ROLE_VIEWS = {
    "agentic_ai": "agentic-ai",
    "applied_ml": "applied-ai",
    "eval_inference": "evaluation-inference",
    "post_training": "post-training",
    "agent_reasoning": "research-engineer",
}

# ml-engineering view is a BACKLOG slice of applied_ml (see _role-registry.md).
# It is not derivable from role_family alone, so it is not regenerated here;
# its rows keep role_family=other in jobs.csv and are excluded from all views.

VIEW_COLUMNS = [
    "job_id", "company", "title", "location", "priority_v2",
    "recommended_action", "opportunity_level", "role_family", "seniority",
    "date_posted", "date_discovered", "key_requirements", "main_gaps",
    "job_url", "canonical_application_url", "source", "description_file",
    "notes",
]

ACTION_ORDER = {"APPLY_NOW": 0, "APPLY": 1, "OPTIMISTIC": 2, "STRETCH": 3,
                "LOW_PRIORITY": 4, "SKIP": 5}


def _priority(row: dict) -> float:
    try:
        return float(row.get("priority_v2") or 0)
    except ValueError:
        return 0.0


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with open(JOBS_CSV, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("status") == "open"]

    buckets: dict[str, list[dict]] = {}
    unmapped = []
    for row in rows:
        fam = row.get("role_family", "")
        view = ROLE_VIEWS.get(fam)
        if view is None:
            unmapped.append(row["job_id"])
            continue
        buckets.setdefault(view, []).append(row)

    for view_rows in buckets.values():
        view_rows.sort(key=lambda r: (-_priority(r),
                                      ACTION_ORDER.get(r.get("recommended_action", ""), 9)))

    if dry_run:
        for view in sorted(buckets):
            print(f"{view}: {len(buckets[view])} open rows")
        print(f"excluded (no view mapping): {len(unmapped)}")
        return

    for view, view_rows in sorted(buckets.items()):
        out_dir = ROLES_DIR / view
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "job-postings.csv"
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=VIEW_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(view_rows)
        top = view_rows[0] if view_rows else None
        top_desc = (f"top: {top['priority_v2']} {top['title'][:45]} @ {top['company']}"
                    if top else "empty")
        print(f"wrote {out_path.relative_to(REPO)}: {len(view_rows)} rows | {top_desc}")
    print(f"excluded (no view mapping, e.g. role_family=other/ml-engineering backlog): {len(unmapped)}")


if __name__ == "__main__":
    main()
