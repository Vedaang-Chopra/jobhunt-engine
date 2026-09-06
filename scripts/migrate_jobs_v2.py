#!/usr/bin/env python3
"""
migrate_jobs_v2.py — One-time deterministic migration (2026-08-22).

1. Backs up jobs.csv to archive/migration_003/jobs_pre_migration.csv
2. Canonicalizes company names via alias map (togetherai/Together AI -> together_ai, etc.)
3. Extracts ATS source ID from job_url (Greenhouse jid, etc.) into source_id column
4. Deduplicates on (company_slug, source_id) — keeps the row with the most
   complete data / earliest discovery, merges source provenance into notes
5. Staleness pass: postings with date_posted > 180 days old get status=open
   retained but flagged stale (stale_flag=true) — NOT deleted (verification pending)
6. Adds verification timestamp column (last_verified)
7. Writes before/after migration report to archive/migration_003/MANIFEST.md

Usage: python3 scripts/migrate_jobs_v2.py            # apply
       python3 scripts/migrate_jobs_v2.py --dry-run  # report only
"""

import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
JOBS_CSV = config_lib.path("jobs_csv")
ARCHIVE_DIR = REPO / "archive/migration_003"
TODAY = date.today().isoformat()

COMPANY_ALIASES = {
    "togetherai": "together_ai", "together ai": "together_ai",
    "anthropic": "anthropic",
    "scaleai": "scale_ai", "scale ai": "scale_ai",
    "databricks": "databricks",
    "xai": "xai",
    "youcom": "you_com", "you.com": "you_com",
    "comet": "comet", "stabilityai": "stability_ai",
    "essential": "essential_healthcare",
}

NEW_COLS = ["company_slug", "source_id", "stale_flag", "last_verified", "merged_from"]


def extract_source_id(url):
    m = re.search(r"/jobs/(\d+)", url or "")
    if m:
        return f"gh_{m.group(1)}"
    m = re.search(r"gh_jid=(\d+)", url or "")
    if m:
        return f"gh_{m.group(1)}"
    return ""


def days_old(posted):
    try:
        y, mo, d = map(int, posted.split("-"))
        return (date.today() - date(y, mo, d)).days
    except Exception:
        return None


def row_quality(row):
    """Higher = more complete record."""
    q = 0
    for f in ["key_requirements", "matching_strengths", "main_gaps", "notes",
              "date_posted", "seniority", "resume_variant"]:
        v = (row.get(f) or "").strip()
        if v and v not in ("No major gaps identified", "medium"):
            q += 1
    if (row.get("full_description_hash") or "").strip():
        q += 2
    return q


def main():
    dry = "--dry-run" in sys.argv
    with open(JOBS_CSV, newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)

    before_count = len(rows)
    for c in NEW_COLS:
        if c not in fields:
            fields.append(c)

    # 1) canonicalize company + slug + source_id
    for r in rows:
        raw = (r.get("company") or "").strip()
        canon = COMPANY_ALIASES.get(raw.lower(), raw.lower().replace(" ", "_"))
        r["company_slug"] = canon
        r["company"] = canon  # canonical display name = slug (aliases resolved)
        r["source_id"] = extract_source_id(r.get("job_url", ""))

    # 2) dedupe on (company_slug, source_id) when source_id present
    groups = {}
    no_src = []
    for r in rows:
        key = (r["company_slug"], r["source_id"]) if r["source_id"] else None
        if key:
            groups.setdefault(key, []).append(r)
        else:
            no_src.append(r)

    kept, merges = [], []
    for key, grp in groups.items():
        if len(grp) == 1:
            kept.append(grp[0])
            continue
        grp.sort(key=row_quality, reverse=True)
        winner = grp[0]
        losers = grp[1:]
        dup_note = "; ".join(sorted({r.get("job_id", "") for r in losers}))
        winner["merged_from"] = dup_note
        winner.setdefault("notes", "")
        if "dedup:" not in winner["notes"]:
            winner["notes"] = (f"[dedup:{TODAY}: merged {len(losers)} duplicate row(s) "
                               f"by source_id {key[1]}] " + winner["notes"])[:900]
        merges.append({"kept": winner["job_id"], "removed": [r["job_id"] for r in losers],
                       "source_id": key[1]})
        kept.append(winner)

    kept.extend(no_src)

    # 3) staleness flag (>180 days since posting, still open)
    stale = 0
    for r in kept:
        r["last_verified"] = ""
        age = days_old(r.get("date_posted", ""))
        if age is not None and age > 180 and r.get("status") == "open":
            r["stale_flag"] = "true"
            stale += 1
        else:
            r["stale_flag"] = "false"

    after_count = len(kept)

    print(f"BEFORE: {before_count} rows")
    print(f"AFTER:  {after_count} rows ({before_count - after_count} duplicates removed)")
    print(f"Stale flagged (>180d, open): {stale}")
    print(f"Rows without source_id (kept as-is): {len(no_src)}")

    if merges:
        print("\nMerges:")
        for m in merges:
            print(f"  kept {m['kept']}  <-  removed {m['removed']}  (src {m['source_id']})")

    if dry:
        print("\nDry run — nothing written.")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    backup = ARCHIVE_DIR / "jobs_pre_migration.csv"
    backup.write_bytes(JOBS_CSV.read_bytes())

    with open(JOBS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(kept)

    manifest = ARCHIVE_DIR / "MANIFEST.md"
    lines = [
        "# Migration 003 — Job Identity Canonicalization, Dedup, Staleness",
        f"**Date:** {TODAY}",
        f"**Before:** {before_count} rows | **After:** {after_count} rows | "
        f"**Removed duplicates:** {before_count - after_count} | **Stale flagged:** {stale}",
        "",
        "## Company alias canonicalization",
        "togetherai/Together AI→together_ai, scaleai/Scale AI→scale_ai, youcom→you_com, "
        "stabilityai→stability_ai, essential→essential_healthcare (all lowercase slugs)",
        "",
        "## Job identity",
        "New `source_id` column = ATS posting id (gh_<jid>). Dedup key = (company_slug, source_id).",
        "",
        "## Merges",
    ]
    for m in merges:
        lines.append(f"- kept `{m['kept']}`; removed {', '.join('`'+r+'`' for r in m['removed'])} (src {m['source_id']})")
    lines += [
        "",
        "## Staleness policy",
        "Rows with date_posted >180 days and status=open get stale_flag=true (verification pending).",
        "Nothing deleted; verification pass (fetch live status) will close or confirm.",
        "",
        f"## Backup",
        f"Pre-migration table: `archive/migration_003/jobs_pre_migration.csv`",
    ]
    manifest.write_text("\n".join(lines))
    print(f"\nBackup: {backup}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
