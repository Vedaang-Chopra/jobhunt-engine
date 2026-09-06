#!/usr/bin/env python3
"""
jd_integrity.py — JD pointer population + hash validation (2026-08-22).

1. For each jobs.csv row with empty description_file, find matching JD file in
   tracking/job_descriptions/active/ by (company, source_id) pattern and populate pointer.
2. Validate full_description_hash: recompute SHA256 of JD body vs stored hash;
   report mismatches (do NOT overwrite stored hashes silently — report only).
3. Report JD files with no matching job row (orphans).

Usage: python3 scripts/jd_integrity.py [--dry-run]
"""

import csv
import hashlib
import re
import sys
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
JOBS_CSV = config_lib.path("jobs_csv")
ACTIVE = config_lib.path("jd_active_dir")


def main():
    dry = "--dry-run" in sys.argv
    with open(JOBS_CSV, newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)

    jd_files = {p.name: p for p in ACTIVE.glob("*.md")}

    # index JD files by (company_prefix, source_id)
    jd_index = {}
    for name, path in jd_files.items():
        m = re.match(r"([a-zA-Z0-9]+)__.*?__(\d+)\.md", name)
        if m:
            jd_index[(m.group(1).lower(), m.group(2))] = name

    populated, hash_ok, hash_bad, orphans = 0, 0, [], set(jd_files.keys())
    matched_keys = set()

    for r in rows:
        src_id = (r.get("source_id") or "").replace("gh_", "")
        company = (r.get("company_slug") or r.get("company") or "").lower()
        if not src_id:
            continue

        # find matching JD file (company alias tolerance)
        match = None
        for (co, sid), fname in jd_index.items():
            if sid == src_id:
                match = fname
                break

        if match:
            matched_keys.add((company, src_id))
            if not (r.get("description_file") or "").strip():
                r["description_file"] = f"tracking/job_descriptions/active/{match}"
                populated += 1

            # hash validation per SCHEMA.md: whitespace-collapse body, then SHA256
            body = jd_files[match].read_text(errors="replace")
            mm = re.search(r"## Full Job Description Text\n(.*?)\n---", body, re.S)
            content = (mm.group(1) if mm else body).strip()
            content = re.sub(r"\s+", " ", content).strip()
            computed = hashlib.sha256(content.encode()).hexdigest()[:16]
            stored = (r.get("full_description_hash") or "").strip()
            if stored and stored != computed:
                hash_bad.append((r["job_id"], stored, computed))
            elif stored == computed:
                hash_ok += 1

    orphan_files = [n for n in jd_files if n not in
                    {v for (_, _), v in jd_index.items() if _} ]
    # simpler orphan calc: files never matched to any row's source_id
    matched_names = set()
    for r in rows:
        src_id = (r.get("source_id") or "").replace("gh_", "")
        for (co, sid), fname in jd_index.items():
            if sid == src_id:
                matched_names.add(fname)
    orphans = sorted(set(jd_files) - matched_names)

    print(f"Rows: {len(rows)} | description_file populated: {populated}")
    print(f"Hash OK: {hash_ok} | Hash MISMATCH: {len(hash_bad)}")
    print(f"JD files with no matching job row (orphans): {len(orphans)}")
    if hash_bad[:5]:
        print("Sample mismatches:")
        for jid, s, c in hash_bad[:5]:
            print(f"  {jid}: stored={s} computed={c}")
    if orphans[:5]:
        print("Sample orphans:", orphans[:5])

    if dry:
        print("\nDry run — nothing written.")
        return

    with open(JOBS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {JOBS_CSV}")


if __name__ == "__main__":
    main()
