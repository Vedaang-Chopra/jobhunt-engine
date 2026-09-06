#!/usr/bin/env python3
"""Normalize fresh LinkedIn guest-sweep results through discovery_lib,
dedupe against jobs.csv, append accepted rows + log the search run."""
import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl
except ImportError:
    import discovery_lib as dl  # noqa: E402
try:
    from scripts import config_lib
except ImportError:
    import config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
SWEEP_JSON = config_lib.path("execution_results_dir") / "linkedin_sweep_2026-08-23.json"

data = json.loads(SWEEP_JSON.read_text())
fresh = data["fresh"]

# backup first
bak = JOBS_CSV.with_suffix(".csv.bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
shutil.copy2(JOBS_CSV, bak)

with open(JOBS_CSV, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)

idx = dl.DedupIndex()
for r in existing:
    idx.add(r)

accepted, rejected, dupes = [], [], []
seen_run = set()
for j in fresh:
    raw = {
        "title": j["title"],
        "company": j["company"],
        "url": j["url"],
        "location": j.get("location", ""),
        "source": "linkedin",
        "source_id": j["source_id"],
        "date_posted": j.get("date_posted_raw", ""),
        "notes": f"linkedin guest sweep 2026-08-23; posted_rel={j.get('posted_rel','')}",
    }
    row = dl.normalize_job(raw)
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{j['source_id']}"
    if j["source_id"] in seen_run:
        dupes.append((j, "cross-run dupe"))
        continue
    seen_run.add(j["source_id"])
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((j, f"matches {matched.get('job_id','?')}"))
        continue
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((j, flags))
        continue
    idx.add(row)
    accepted.append(row)

with open(JOBS_CSV, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    for row in accepted:
        w.writerow(row)

run_id = f"li_guest_{datetime.now().strftime('%Y%m%d_%H%M')}"
with open(RUNS_CSV, "a", newline="") as f:
    csv.writer(f).writerow([
        run_id, datetime.now().strftime("%Y-%m-%dT%H:%M"), "linkedin_guest_api",
        "8 queries x 1 page (past-week US filter)", len(fresh) + len(data["duplicates"]),
        len(accepted), len(rejected), len(dupes),
        f"playwright_mcp_unavailable_logged_in_leg_skipped",
    ])

print(json.dumps({
    "run_id": run_id, "backup": bak.name,
    "fresh_scanned": len(fresh),
    "appended": len(accepted),
    "rejected": [{"job": j["company"] + "|" + j["title"], "flags": fl} for j, fl in rejected],
    "dupes": len(dupes),
}, indent=2))
