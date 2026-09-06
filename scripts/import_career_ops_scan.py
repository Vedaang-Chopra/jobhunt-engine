#!/usr/bin/env python3
"""Import career-ops portal-scan results into the canonical jobs table.

Reads the career-ops scanner output (data/scan-history.tsv, TSV with columns:
url, first_seen, portal, title, company, status, location, fingerprint,
posted_at, trust_score, trust_flags, normalized_company) and upserts new
postings into tracking/jobs/jobs.csv using this repository's canonical
schema and job_id scheme.

Design rules:
  - career-ops is a DISCOVERY SOURCE, same standing as LinkedIn/Greenhouse
    sweeps (docs/rules/JOB_DISCOVERY_RULES.md). It never overwrites scores,
    statuses, or notes already assigned by this repo.
  - Dedup: skip when job_url already present, or when
    (company_slug, source_id) matches an existing row (migrate_jobs_v2 key).
  - job_id follows the canonical scheme
    {company_slug}_{title_slug}_{source_id_or_hash} (tracking/jobs/SCHEMA.md).
    Ashby ids use the leading 8 hex chars of the posting UUID, matching
    existing ashby rows.
  - SimHash fingerprint from career-ops goes to notes provenance, NOT into
    full_description_hash (that column means SHA256 of the fetched JD text;
    backfill_jd_features.py owns filling it properly).
  - Default is a DRY RUN. Pass --apply to write.

Usage:
  python3 scripts/import_career_ops_scan.py            # dry run, prints plan
  python3 scripts/import_career_ops_scan.py --apply    # write new rows
"""
import argparse
import csv
import hashlib
import os
import re
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from scripts import config_lib
except ImportError:
    import config_lib
from discovery_lib import normalize_source  # noqa: E402

DEFAULT_SCAN_TSV = os.path.join(
    REPO, "..", "career-ops", "data", "scan-history.tsv")
JOBS_CSV = str(config_lib.data_root() / "tracking" / "jobs" / "jobs.csv")


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:80]


def extract_source(url):
    """Return (source, source_id) parsed from an ATS posting URL.

    Source comes from discovery_lib.normalize_source(); only direct
    greenhouse/ashby/lever postings are accepted (career-ops gate).
    """
    source = normalize_source(url)
    if source not in ("greenhouse", "ashby", "lever"):
        return None, ""
    m = (
        re.search(r"/jobs/(\d+)", url)
        or re.search(r"gh_jid=(\d+)", url)
    )
    if m:
        return source, f"gh_{m.group(1)}"
    m = re.search(r"jobs\.ashbyhq\.com/[A-Za-z0-9._-]+/([0-9a-f]{8})[0-9a-f-]*", url)
    if m:
        return source, m.group(1)
    m = re.search(r"jobs\.lever\.co/[A-Za-z0-9._-]+/([A-Za-z0-9._-]+)", url)
    if m:
        return source, m.group(1)
    return source, ""


def load_existing():
    with open(JOBS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames: list[str] = list(reader.fieldnames or [])
        rows = list(reader)
    urls = {r.get("job_url", "").strip().rstrip("/") for r in rows}
    keys = {
        (r.get("company_slug") or "", r.get("source_id") or "")
        for r in rows
        if r.get("company_slug") and r.get("source_id")
    }
    return fieldnames, rows, urls, keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-tsv", default=DEFAULT_SCAN_TSV)
    ap.add_argument("--apply", action="store_true",
                    help="write new rows (default: dry run)")
    args = ap.parse_args()

    scan_path = os.path.normpath(args.scan_tsv)
    if not os.path.exists(scan_path):
        sys.exit(f"scan-history not found: {scan_path}")

    fieldnames, existing_rows, seen_urls, seen_keys = load_existing()
    today = date.today().isoformat()
    new_rows, skipped_dup, skipped_nonats = [], [], []

    with open(scan_path, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("url\t"):
                continue
            cols = line.split("\t")
            if len(cols) < 6:
                continue
            (url, first_seen, _portal, title, company, status,
             *rest) = [c.strip() for c in cols]
            url_clean = url.rstrip("/")
            source, source_id = extract_source(url_clean)
            if not source:
                skipped_nonats.append((url_clean, title))
                continue
            if url_clean in seen_urls:
                skipped_dup.append(url_clean)
                continue
            company_slug = slugify(company)
            if source_id and (company_slug, source_id) in seen_keys:
                skipped_dup.append(url_clean)
                continue

            posted_at = rest[1] if len(rest) > 2 else ""
            trust_flags = rest[3] if len(rest) > 4 else ""
            fingerprint = rest[0] if rest else ""

            title_slug = slugify(title)
            tail = source_id or hashlib.sha256(url_clean.encode()).hexdigest()[:10]
            job_id = f"{company_slug}_{title_slug}_{tail}"[:160]

            notes_parts = [f"career-ops scan import {today}"]
            if trust_flags:
                notes_parts.append(f"trust_flags={trust_flags}")
            if fingerprint:
                notes_parts.append(f"simhash={fingerprint}")
            row = {k: "" for k in fieldnames}
            loc_candidate = next(
                (c for c in ([rest[2]] if len(rest) > 3 else []) if c), "")
            # Guard: upstream scan-history sometimes leaks a date into the
            # location column. A bare ISO date is NOT a location — move it to
            # date_posted when that is missing and leave location empty
            # (scrutiny treats unknown/empty locations as pass-through).
            if re.fullmatch(r"\s*20\d\d-\d\d-\d\d\s*", loc_candidate or ""):
                posted_at = posted_at or loc_candidate.strip()
                loc_candidate = ""
            row.update({
                "job_id": job_id,
                "company": company,
                "company_slug": company_slug,
                "title": title,
                "location": loc_candidate,
                "job_url": url_clean,
                "canonical_application_url": url_clean,
                "source": source,
                "source_id": source_id,
                "date_discovered": first_seen or today,
                "date_posted": posted_at,
                "status": "open",
                "last_checked": first_seen or today,
                "notes": "; ".join(notes_parts)[:900],
            })
            new_rows.append(row)
            seen_urls.add(url_clean)
            if source_id:
                seen_keys.add((company_slug, source_id))

    print(f"scan file : {scan_path}")
    print(f"existing  : {len(existing_rows)} canonical rows")
    print(f"new       : {len(new_rows)}")
    print(f"duplicate : {len(skipped_dup)} (already tracked)")
    print(f"non-ATS   : {len(skipped_nonats)} (no greenhouse/ashby/lever URL)")
    if new_rows:
        print("\nSample of what would be added:")
        for r in new_rows[:15]:
            print(f"  + [{r['source']:9s}] {r['company']}: {r['title']}")
        if len(new_rows) > 15:
            print(f"  ... and {len(new_rows) - 15} more")

    if not args.apply:
        print("\nDRY RUN — no changes written. Re-run with --apply to write.")
        return

    with open(JOBS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for r in new_rows:
            writer.writerow(r)
    print(f"\nAPPLIED — appended {len(new_rows)} rows to tracking/jobs/jobs.csv")
    print("Next: run score_jobs_v2.py to score the new discoveries.")


if __name__ == "__main__":
    main()
