#!/usr/bin/env python3
"""Ingest fresh guest-sweep results into tracking/jobs/jobs.csv via discovery_lib."""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import config_lib
except ImportError:
    import config_lib
import discovery_lib as d  # noqa: E402

JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
SRC_FILE = sorted((config_lib.path("execution_results_dir")).glob("linkedin_sweep_*.json"))[-1]
SOURCE = "linkedin_guest_api"

data = json.loads(SRC_FILE.read_text())
with open(JOBS_CSV, newline="") as f:
    existing = list(csv.DictReader(f))
seen = set()
for row in existing:
    seen.add(row["source_id"].lower())
    if row.get("company") and row.get("title"):
        seen.add(row["company"].lower().replace(" ", "_") + "|" +
                 row["title"].lower().replace(" ", "_"))

new_rows = []
for job in data["fresh"]:
    if job["source_id"].lower() in seen:
        continue
    raw = {
        "title": job["title"],
        "company": job["company"],
        "url": job["url"],
        "location": job.get("location", ""),
        "source": SOURCE,
        "source_id": f"li_{job['source_id']}",
        "date_posted": job.get("date_posted_raw", ""),
        "notes": f"posted_rel={job.get('posted_rel','')}; sweep={SRC_FILE.name}",
    }
    try:
        row = d.normalize_job(raw)
    except ValueError:
        continue
    verdict, flags = d.scrutinize(row)
    row["status"] = "rejected" if verdict == "reject" else "open"
    row["missing_info"] = ";".join(flags)
    new_rows.append(row)
    seen.add(job["source_id"].lower())

if new_rows:
    cols = list(existing[0].keys()) if existing else None
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        for row in new_rows:
            w.writerow(row)

accepted = sum(1 for r in new_rows if r["status"] == "open")
print(f"appended={len(new_rows)} accepted={accepted} rejected={len(new_rows)-accepted}")
for r in new_rows:
    print(f"  {r['status']:8s} {r['source_id']:20s} {r['company']} | {r['title']} | {r['location']} | flags={r['missing_info']}")
