#!/usr/bin/env python3
"""Expired/stale-job cleanup pass over tracking/jobs/jobs.csv.

Reuses the policy primitives in scripts/freshness_check.py (reference_date,
days_since, parse_date, EXPIRE_AFTER_DAYS, check_url, is_ats_url, load_rows,
write_rows, compute_row_updates) so there is exactly one expiry policy.

Behavior:
  - Rows are NEVER deleted (append-only history rule). Status transitions
    only: open -> expired (>90d past posted/updated reference date, or an
    HTTP 404/410 when --http is given).
  - Transitioned rows get last_checked stamped with the run date.
  - Rows already expired/archived/rejected are skipped entirely (nothing
    stamped, nothing written for them).
  - DRY-RUN BY DEFAULT: nothing touches the jobs CSV unless --apply is
    passed. --dry-run and --apply are mutually exclusive.

CLI:
  --jobs-csv PATH   override the master jobs CSV
  --dry-run         plan only, print summary (default when no flag given)
  --apply           write status transitions back to the CSV
  --http            live HEAD/GET checks on open weekly/biweekly-tier ATS
                    URLs exactly like freshness_check --live

A run report is written to
  <data_root>/execution_results/cleanup_reports/cleanup_expired_<date>.json
with {date, mode, totals_by_action, by_source, changed_job_ids}.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib

try:
    from scripts.freshness_check import (
        BIWEEKLY_INTERVAL_DAYS,
        EXPIRE_AFTER_DAYS,
        WEEKLY_INTERVAL_DAYS,
        assign_tier,
        check_url,
        compute_row_updates,
        days_since,
        http_url_expired,
        is_ats_url,
        load_rows,
        parse_date,
        reference_date,
        today_utc,
        write_rows,
    )
except ImportError:
    from freshness_check import (
        BIWEEKLY_INTERVAL_DAYS,
        EXPIRE_AFTER_DAYS,
        WEEKLY_INTERVAL_DAYS,
        assign_tier,
        check_url,
        compute_row_updates,
        days_since,
        http_url_expired,
        is_ats_url,
        load_rows,
        parse_date,
        reference_date,
        today_utc,
        write_rows,
    )

DEFAULT_JOBS = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"

# Only these statuses are eligible for a transition; everything else
# (expired/archived/rejected/anything else) is left completely untouched.
ELIGIBLE_STATUSES = {"open"}
TERMINAL_STATUSES = {"expired", "archived", "rejected"}


def report_path(today: date) -> Path:
    return (config_lib.data_root() / "execution_results" / "cleanup_reports"
            / f"cleanup_expired_{today.isoformat()}.json")


def live_http_expired(row: dict, today: date, actions: Counter[str],
                      linkedin_deferred: list[str]) -> bool | None:
    """Mirror freshness_check --live: HEAD/GET the ATS URLs of open rows in
    the weekly/biweekly tiers whose re-check interval has elapsed. Returns
    True/False when a check ran, None otherwise."""
    tier = assign_tier(row.get("priority_v2"))
    if tier not in ("weekly", "biweekly"):
        return None
    url = row.get("canonical_application_url") or row.get("job_url") or ""
    source = (row.get("source") or "").lower()
    lc = days_since(row.get("last_checked") or row.get("last_verified"), today)
    interval = (WEEKLY_INTERVAL_DAYS if tier == "weekly"
                else BIWEEKLY_INTERVAL_DAYS)
    if lc is not None and lc < interval:
        return None
    if "linkedin" in source or "linkedin" in url.lower():
        # LinkedIn: browser spot-check only — deferred, never HTTP-checked.
        if tier == "weekly":
            linkedin_deferred.append(f"{row.get('job_id')} {url} ({tier})")
            actions["linkedin_deferred"] += 1
        return None
    if not is_ats_url(url):
        return None
    code = check_url(url)
    expired = http_url_expired(code)
    actions[f"http_{('ok' if not expired else 'expired')}"] += 1
    print(f"[http] {code} {row.get('job_id')} {url}")
    return expired


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs-csv", type=Path, default=DEFAULT_JOBS)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="plan only, no writes (default)")
    mode.add_argument("--apply", action="store_true",
                      help="write status transitions back to the CSV")
    ap.add_argument("--http", action="store_true",
                    help="live HTTP expiry checks on open weekly/biweekly "
                         "ATS URLs (like freshness_check --live)")
    args = ap.parse_args(argv)
    apply_mode = bool(args.apply)

    rows = load_rows(args.jobs_csv)
    today = today_utc()
    actions: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    changed_job_ids: list[str] = []
    linkedin_deferred: list[str] = []

    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status in TERMINAL_STATUSES:
            actions["skipped_terminal"] += 1
            continue
        if status not in ELIGIBLE_STATUSES:
            actions["skipped_other_status"] += 1
            continue

        http_expired = None
        if args.http:
            http_expired = live_http_expired(row, today, actions,
                                             linkedin_deferred)

        updates = compute_row_updates(row, http_expired=http_expired,
                                      today=today)
        if updates.get("status") != "expired":
            # No transition warranted: this cleanup pass makes status
            # transitions ONLY — no staleness bookkeeping is stamped here.
            actions["no_change"] += 1
            continue

        reason = "expired_by_http" if http_expired else "expired_by_age"
        changes = {"status": "expired", "last_checked": today.isoformat()}
        field_changes = {k: v for k, v in changes.items()
                         if v != (row.get(k) or "")}
        if not field_changes:
            actions["no_change"] += 1
            continue

        actions[reason] += 1
        by_source[(row.get("source") or "").strip().lower()] += 1
        changed_job_ids.append(row.get("job_id") or "")
        if apply_mode:
            row.update(field_changes)

    print("\n=== cleanup_expired summary ===")
    print(f"jobs csv: {args.jobs_csv}")
    print(f"rows total: {len(rows)}")
    print(f"mode: {'APPLY' if apply_mode else 'DRY-RUN'}"
          f"{' +http' if args.http else ''}")
    print(f"totals by action: {dict(actions)}")
    print(f"changes by source: {dict(by_source)}")
    print(f"rows to transition (open -> expired): {len(changed_job_ids)}")
    if linkedin_deferred:
        print(f"\nLinkedIn browser spot-check deferred ({len(linkedin_deferred)}):")
        for entry in linkedin_deferred[:25]:
            print(f"  - {entry}")
        if len(linkedin_deferred) > 25:
            print(f"  ... and {len(linkedin_deferred) - 25} more")

    report = {
        "date": today.isoformat(),
        "mode": "apply" if apply_mode else "dry-run",
        "totals_by_action": dict(actions),
        "by_source": dict(by_source),
        "changed_job_ids": changed_job_ids,
    }
    rpath = report_path(today)
    rpath.parent.mkdir(parents=True, exist_ok=True)
    rpath.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report: {rpath}")

    if apply_mode:
        write_rows(args.jobs_csv, rows)
        print(f"wrote {args.jobs_csv}")
    else:
        print("dry-run: no writes performed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
