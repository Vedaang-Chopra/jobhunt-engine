#!/usr/bin/env python3
"""qualify_sweep.py — Bulk profile-fit cleanup for the jobs backlog.

Applies the profile_fit_rules gates + a priority floor to all OPEN rows in
tracking/jobs/jobs.csv and transitions non-fitting rows to ``archived``.
Rows are NEVER deleted (lifecycle transition only, per repo rules).

Categories:
  hard-disqualified  — title matches a hard rule (internship, new-grad,
                       exec/leadership, tutor/annotation, consulting/sales)
  low_priority       — priority_v2 below the --min-priority floor (default 40)
  expired_stale      — open rows already marked expired by freshness sweep
                       (only with --include-expired)

Posts cleanup (--posts): dismisses hiring_posts rows older than N days
(default 14) that are still status 'new'.

Dry-run by default; writes require --apply. JSON report goes to
execution_results/cleanup_reports/.

Usage:
  python3 scripts/qualify_sweep.py                 # dry-run report
  python3 scripts/qualify_sweep.py --apply         # archive + dismiss
  python3 scripts/qualify_sweep.py --min-priority 55 --apply
  python3 scripts/qualify_sweep.py --posts --post-age-days 14
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib  # type: ignore[no-redef]

try:
    from scripts import profile_fit_rules as _fit
except ImportError:
    import profile_fit_rules as _fit  # type: ignore[no-redef]

DATA_ROOT = Path(config_lib.data_root())
JOBS_CSV = DATA_ROOT / "tracking/jobs/jobs.csv"
POSTS_CSV = DATA_ROOT / "tracking/hiring_posts/hiring_posts.csv"
REPORT_DIR = DATA_ROOT / "execution_results/cleanup_reports"


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Profile-fit backlog cleanup")
    ap.add_argument("--apply", action="store_true",
                    help="write changes (default: dry-run)")
    ap.add_argument("--min-priority", type=float, default=40.0,
                    help="archive open jobs with priority_v2 below this "
                         "(default 40 = below STRETCH)")
    ap.add_argument("--include-expired", action="store_true",
                    help="also archive open rows the freshness sweep marked "
                         "expired")
    ap.add_argument("--posts", action="store_true",
                    help="also clean hiring_posts.csv (dismiss stale 'new')")
    ap.add_argument("--post-age-days", type=int, default=14,
                    help="dismiss 'new' posts older than this (default 14)")
    ap.add_argument("--jobs-only", action="store_true",
                    help="skip posts even without --posts (default: posts "
                         "included when flag given; jobs always run)")
    return ap.parse_args(argv)


def load_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames, rows):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def clean_jobs(rules, min_priority: float, include_expired: bool):
    fieldnames, rows = load_csv(JOBS_CSV)
    for col in (_fit.FIT_COL, _fit.REASON_COL):
        if col not in fieldnames:
            fieldnames.append(col)

    companies_by_slug = {}
    companies_csv = DATA_ROOT / "tracking/companies/companies.csv"
    if companies_csv.is_file():
        with open(companies_csv, newline="", encoding="utf-8") as fh:
            companies_by_slug = {
                r.get("company_slug", ""): r for r in csv.DictReader(fh)}

    today = date.today().isoformat()
    changed = []
    counts = Counter()

    for row in rows:
        if row.get("status") != "open":
            continue
        fit = _fit.evaluate_row(row, rules, companies_by_slug)
        row[_fit.FIT_COL] = fit["fit_class"]
        row[_fit.REASON_COL] = fit["reason"]
        reason = None
        if fit["fit_class"] == "disqualified":
            reason = f"disqualified:{fit['matched_rules'][0]}"
        elif include_expired and (row.get("last_scored") or "") == "" \
                and row.get("recommended_action") in ("SKIP",):
            reason = "skip_action"
        else:
            try:
                pr = float(row.get("priority_v2") or -1)
            except ValueError:
                pr = -1
            if 0 <= pr < min_priority:
                reason = f"low_priority(<{min_priority:g})"
        if not reason:
            continue
        counts[reason.split(":")[0].split("(")[0]] += 1
        row["status"] = "archived"
        row["date_updated"] = today
        changed.append({"job_id": row["job_id"], "company": row.get("company"),
                        "title": row.get("title"), "reason": reason,
                        "priority_v2": row.get("priority_v2")})
    return fieldnames, rows, changed, counts


def clean_posts(max_age_days: int):
    """Return the canonical post rows with stale `new` rows dismissed."""
    if not POSTS_CSV.is_file():
        return [], [], [], Counter()
    fieldnames, rows = load_csv(POSTS_CSV)
    today = datetime.now()
    changed, counts = [], Counter()
    for row in rows:
        if row.get("status") != "new":
            continue
        # Canonical hiring_posts.csv stores discovered_date / posted_date.
        # Legacy imports may still provide first_seen / date_posted, so retain
        # those only as trailing compatibility fallbacks.
        seen = (row.get("discovered_date") or row.get("posted_date")
                or row.get("first_seen") or row.get("date_posted") or "")
        try:
            age = (today - datetime.strptime(seen[:10], "%Y-%m-%d")).days
        except ValueError:
            continue
        if age > max_age_days:
            row["status"] = "dismissed"
            counts["stale_posts"] += 1
            changed.append({"post_id": row.get("post_id"),
                            "author": row.get("author") or row.get("author_name"),
                            "age_days": age})
    return fieldnames, rows, changed, counts


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rules = _fit.load_fit_rules()

    fieldnames, rows, changed, counts = clean_jobs(
        rules, args.min_priority, args.include_expired)

    post_fieldnames, post_rows, post_changed, post_counts = [], [], [], Counter()
    if args.posts:
        post_fieldnames, post_rows, post_changed, post_counts = clean_posts(
            args.post_age_days)

    print(f"Jobs: {len(rows)} scanned, {len(changed)} to archive "
          f"(min_priority={args.min_priority:g}, dry_run={not args.apply})")
    print(f"  by reason: {dict(counts)}")
    if args.posts:
        print(f"Posts: {len(post_changed)} stale 'new' posts to dismiss "
              f"(age>{args.post_age_days}d)")
    for c in changed[:25]:
        print(f"  [{c['reason']}] {str(c['title'])[:58]} @ {c['company']} "
              f"(p={c['priority_v2']})")

    report = {
        "date": date.today().isoformat(),
        "applied": bool(args.apply),
        "min_priority": args.min_priority,
        "jobs_scanned": len(rows),
        "jobs_archived": len(changed),
        "archive_reasons": dict(counts),
        "posts_dismissed": len(post_changed),
        "changed_jobs": changed,
        "changed_posts": post_changed,
    }

    if args.apply:
        write_csv(JOBS_CSV, fieldnames, rows)
        if post_changed:
            # clean_posts has already updated these canonical in-memory rows;
            # reloading would discard the selected dismissals.
            write_csv(POSTS_CSV, post_fieldnames, post_rows)
        print(f"\nWrote {JOBS_CSV}" + (f" and {POSTS_CSV}" if post_changed else ""))
    else:
        print("\nDry run — no files written.")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"qualify_sweep_{date.today().isoformat()}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
