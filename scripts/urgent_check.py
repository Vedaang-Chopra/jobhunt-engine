#!/usr/bin/env python3
"""Urgent-job alert fast path (daily-rhythm Task 3).

Scans the master jobs CSV for rows with age <= 24h AND priority_v2 >= 68
(APPLY tier) and prints up to 3 alert lines to stdout so cron delivery
forwards them immediately instead of waiting for the morning digest.

Print-only: writes nothing, always exits 0.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parents[1]
DEFAULT_JOBS = config_lib.path("jobs_csv")
DEFAULT_CONTACTS = config_lib.path("contacts_csv")

MAX_AGE_HOURS = 24.0
APPLY_THRESHOLD = 68
MAX_ALERTS = 3


def parse_dt(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def job_age_hours(row, now):
    posted = parse_dt(row.get("date_posted")) or parse_dt(row.get("date_discovered"))
    if posted is None:
        return None
    return (now - posted).total_seconds() / 3600.0


def qualifies(row, now):
    """True when age <= 24h AND priority_v2 >= APPLY_THRESHOLD."""
    if str(row.get("status", "")).strip().lower() not in ("open", "", "queued"):
        return False
    if str(row.get("is_medical_false_positive", "")).strip().lower() == "true":
        return False
    try:
        priority = float(row.get("priority_v2") or 0)
    except ValueError:
        return False
    if priority < APPLY_THRESHOLD:
        return False
    age = job_age_hours(row, now)
    return age is not None and age <= MAX_AGE_HOURS


def top_contact(company, contact_rows):
    """First contact matching company (case-insensitive), else None."""
    target = (company or "").strip().lower()
    for c in contact_rows:
        if (c.get("company") or "").strip().lower() == target and target:
            name = (c.get("name") or "").strip()
            url = (c.get("linkedin_url") or "").strip()
            if name or url:
                return {"name": name, "url": url}
    return None


def format_alert(row, age_hours, contact):
    url = (row.get("canonical_application_url") or row.get("job_url") or "").strip()
    who = (
        f"{contact['name']} ({contact['url']})" if contact and contact["name"]
        else (contact["url"] if contact else None)
    )
    tail = f"top referral contact: {who}" if who else "no referral contact on file"
    return (
        f"\U0001F525 HOT JOB: {row.get('title', '').strip()} @ "
        f"{row.get('company', '').strip()} \u2014 {max(age_hours, 0):.0f}h old, APPLY tier "
        f"\u2014 {url} \u2014 {tail}"
    )


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Urgent-job alert fast path.")
    parser.add_argument("--date", default=None,
                        help="Target day (YYYY-MM-DD). Defaults to the --now day, "
                             "not the wall clock, so --now overrides stay coherent.")
    parser.add_argument("--now", default=None, help="Override current time (testing).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print-only anyway; documents that nothing is written.")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--contacts", type=Path, default=DEFAULT_CONTACTS)
    args = parser.parse_args(argv)

    now = parse_dt(args.now) or datetime.now()
    try:
        job_rows = load_rows(args.jobs)
        contact_rows = load_rows(args.contacts)
    except OSError as exc:
        print(f"urgent_check: could not read inputs ({exc}); no alerts.", file=sys.stderr)
        return 0

    alerts = []
    for row in job_rows:
        if len(alerts) >= MAX_ALERTS:
            break
        if not qualifies(row, now):
            continue
        # --date filter: keep only rows discovered/posted on the target day
        # (when both dates are parseable); undated rows fall back to age gate.
        day = (parse_dt(args.date) or now).date()
        dates = [parse_dt(row.get(k)) for k in ("date_discovered", "date_posted")]
        dated = [d.date() for d in dates if d is not None]
        if dated and day not in dated:
            continue
        alerts.append(format_alert(row, job_age_hours(row, now),
                                   top_contact(row.get("company"), contact_rows)))

    if args.dry_run:
        print("[dry-run] would print the alerts below; nothing is ever written:")
    for line in alerts[:MAX_ALERTS]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
