#!/usr/bin/env python3
"""Freshness / staleness loop for tracking/jobs/jobs.csv.

Tiered re-verification policy:
  weekly   : priority_v2 >= 68  -> re-verify every 7 days
  biweekly : 55 <= priority_v2 < 68 -> re-verify every 14 days
  stale    : priority_v2 < 55   -> stale_flag after 30 days unchecked
Auto-archive: status=expired after 90 days past posted/updated date.
Rows are NEVER deleted — expired rows are kept with status=expired.

CLI:
  --dry-run  print tier assignment + planned actions, no writes
  --live     perform HTTP checks (ATS URLs) + write updates in place
LinkedIn URLs are never HTTP-checked here; they are always deferred and
printed as candidates for a browser spot-check (weekly tier only).
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from scripts import config_lib
except ImportError:
    import config_lib
DEFAULT_JOBS = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"

WEEKLY_MIN = 68.0
BIWEEKLY_MIN = 55.0
WEEKLY_INTERVAL_DAYS = 7
BIWEEKLY_INTERVAL_DAYS = 14
STALE_AFTER_DAYS = 30
EXPIRE_AFTER_DAYS = 90
HTTP_TIMEOUT = 15
EXPIRED_HTTP_CODES = {404, 410}
ATS_HOSTS = ("greenhouse.io", "ashbyhq.com", "lever.co", "jobvite.com",
             "myworkdayjobs.com", "oraclecloud.com")


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def days_since(iso_value: str | None, today: date) -> int | None:
    d = parse_date(iso_value)
    if d is None:
        return None
    return (today - d).days


def assign_tier(score) -> str:
    """Weekly for score>=68, biweekly for 55-67.99, stale below / missing."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "stale"
    if s >= WEEKLY_MIN:
        return "weekly"
    if s >= BIWEEKLY_MIN:
        return "biweekly"
    return "stale"


def is_ats_url(url: str) -> bool:
    u = (url or "").lower()
    return any(host in u for host in ATS_HOSTS)


def http_url_expired(status_code: int | None) -> bool:
    return status_code in EXPIRED_HTTP_CODES


def check_url(url: str) -> int | None:
    """Cheap HEAD then GET fallback. Returns final status code or None."""
    for method in ("HEAD", "GET"):
        try:
            req = Request(url, method=method,
                          headers={"User-Agent": "freshness-check/1.0"})
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                code = resp.getcode()
                resp.read(64) if method == "GET" else None
                return code
        except Exception:
            continue
    return None


def reference_date(row: dict) -> str | None:
    """Newest of date_updated / date_posted — the freshness clock.

    Falls back to date_discovered when both are missing/unparseable, so rows
    ingested without a board posting date still start their freshness clock
    (otherwise they would never age out of status=open).
    """
    updated = parse_date(row.get("date_updated"))
    posted = parse_date(row.get("date_posted"))
    candidates = [d for d in (updated, posted) if d is not None]
    if not candidates:
        discovered = parse_date(row.get("date_discovered"))
        if discovered is not None:
            return discovered.isoformat()
        return None
    return max(candidates).isoformat()


def compute_row_updates(row: dict, http_expired: bool | None = None,
                        today: date | None = None) -> dict:
    """Return the field updates this row needs under the tiered policy.

    http_expired: True/False when an HTTP check ran; None otherwise.
    """
    today = today or today_utc()
    tier = assign_tier(row.get("priority_v2"))
    updates: dict = {}

    # --- auto-archive: expired after 90d past posted/updated (rows kept) ---
    ref = reference_date(row)
    age_days = days_since(ref, today)
    already_expired = (row.get("status") or "").strip().lower() == "expired"
    if http_expired or (age_days is not None and age_days > EXPIRE_AFTER_DAYS):
        updates["status"] = "expired"
    elif already_expired:
        updates["status"] = "expired"

    if updates.get("status") == "expired":
        # expiry supersedes staleness bookkeeping but still stamp last_checked
        updates.setdefault("last_checked", today.isoformat())
        return {"tier": tier, **updates}

    # --- staleness ---
    interval = WEEKLY_INTERVAL_DAYS if tier == "weekly" else \
        BIWEEKLY_INTERVAL_DAYS if tier == "biweekly" else STALE_AFTER_DAYS
    last_checked = row.get("last_checked") or row.get("last_verified") or ""
    unchecked_days = days_since(last_checked, today)
    if unchecked_days is None:
        unchecked_days = age_days  # never checked: use posting clock
    due = unchecked_days is not None and unchecked_days >= interval

    if tier == "stale":
        if due:
            updates["stale_flag"] = "true"
            updates["last_checked"] = today.isoformat()
        elif row.get("stale_flag") in ("true", "True", "1") and not due:
            pass  # leave existing flag alone until re-checked
    elif due:
        # weekly/biweekly: re-verified now (live check stamps the date)
        updates["last_checked"] = today.isoformat()
        if http_expired:
            updates["status"] = "expired"
        if row.get("stale_flag"):
            updates["stale_flag"] = ""  # verified live again
    return {"tier": tier, **updates}


def load_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []  # fresh install: no jobs yet is a valid empty state
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict]) -> None:
    """Rewrite CSV preserving all rows (never delete) and column order."""
    fieldnames: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    tmp = path.with_suffix(".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs-csv", type=Path, default=DEFAULT_JOBS)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    args = ap.parse_args(argv)

    rows = load_rows(args.jobs_csv)
    today = today_utc()
    tiers: Counter[str] = Counter()
    linkedin_spotcheck: list[str] = []
    actions: Counter[str] = Counter()
    changed = 0

    for row in rows:
        tier = assign_tier(row.get("priority_v2"))
        tiers[tier] += 1
        url = row.get("canonical_application_url") or row.get("job_url") or ""
        source = (row.get("source") or "").lower()

        http_expired = None
        needs_check = False
        if args.live and tier in ("weekly", "biweekly") and \
                (row.get("status") or "").lower() != "expired":
            lc = days_since(row.get("last_checked") or row.get("last_verified"), today)
            interval = WEEKLY_INTERVAL_DAYS if tier == "weekly" else BIWEEKLY_INTERVAL_DAYS
            if lc is None or lc >= interval:
                needs_check = True

        if needs_check and "linkedin" in source or "linkedin" in url.lower():
            # LinkedIn: browser spot-check only — deferred, printed, top tier
            if tier == "weekly":
                linkedin_spotcheck.append(
                    f"{row.get('job_id')} {url} ({tier})")
                actions["linkedin_deferred"] += 1
            needs_check = False
        elif needs_check and is_ats_url(url):
            code = check_url(url)
            http_expired = http_url_expired(code)
            actions[f"http_{http_expired and 'expired' or 'ok'}"] += 1
            print(f"[http] {code} {row.get('job_id')} {url}")

        updates = compute_row_updates(row, http_expired=http_expired, today=today)
        tier = updates.pop("tier", tier)
        field_changes = {k: v for k, v in updates.items()
                         if v != (row.get(k) or "")}
        if field_changes:
            changed += 1
            for k in field_changes:
                actions[k] += 1
            if args.live:
                row.update(field_changes)

        if args.dry_run:
            print(f"[{tier}] id={row.get('job_id')} "
                  f"score={row.get('priority_v2')} status={row.get('status')} "
                  f"actions={field_changes}")

    print("\n=== summary ===")
    print(f"rows total: {len(rows)}")
    print(f"tiers: {dict(tiers)}")
    print(f"actions: {dict(actions)}")
    print(f"rows to change: {changed}")
    if linkedin_spotcheck:
        print(f"\nLinkedIn browser spot-check deferred ({len(linkedin_spotcheck)}):")
        for entry in linkedin_spotcheck[:25]:
            print(f"  - {entry}")
        if len(linkedin_spotcheck) > 25:
            print(f"  ... and {len(linkedin_spotcheck) - 25} more")

    if args.live:
        write_rows(args.jobs_csv, rows)
        print(f"wrote {args.jobs_csv}")
    else:
        print("dry-run: no writes performed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
