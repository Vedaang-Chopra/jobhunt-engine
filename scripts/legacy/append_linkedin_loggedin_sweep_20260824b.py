#!/usr/bin/env python3
"""Normalize logged-in LinkedIn sweep JSON (2026-08-24 run) through discovery_lib,
dedupe, append to jobs.csv (with backup), and log the search run."""
import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl, config_lib
except ImportError:
    import discovery_lib as dl  # type: ignore
    import config_lib  # type: ignore

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
SRC = Path.home() / ".hermes/profiles/job-hunt/cache/browser-use/workspace/3ea25948-4518-4504-afb2-d1a185503759/li_sweep_0824.json"

results = json.loads(SRC.read_text())
all_jobs = {}
for r in results:
    for j in r["jobs"]:
        parts = j.get("parts", [])
        if len(parts) < 4:
            continue
        sid = j["source_id"]
        if sid in all_jobs:
            # keep richer variant
            if len(all_jobs[sid]["_notes"]) >= len(parts):
                continue
        notes_bits = []
        for p in parts[4:]:
            if re.search(r"connections work here|company alumni|Posted|\$.*K/yr", p):
                notes_bits.append(p)
        all_jobs[sid] = {
            "_title": parts[1], "_company": parts[2], "_loc": parts[3],
            "_notes": notes_bits, "_query": r["query"],
        }

bak = JOBS_CSV.with_suffix(".csv.bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
shutil.copy2(JOBS_CSV, bak)

with open(JOBS_CSV, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)

idx = dl.DedupIndex()
for row in existing:
    idx.add(row)

accepted, rejected, dupes = [], [], []
for sid, j in sorted(all_jobs.items()):
    raw = {
        "title": j["_title"], "company": j["_company"],
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": j["_loc"], "source": "linkedin", "source_id": sid,
        "date_posted": "", "posted_rel": "",
        "notes": ("linkedin logged-in sweep 2026-08-24 past-week US; query=" + j["_query"]
                  + ("; " + "; ".join(j["_notes"]) if j["_notes"] else "")),
    }
    row = dl.normalize_job(raw)
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{sid}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((sid, j["_title"], matched.get("job_id", "?")))
        continue
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((sid, j["_title"], flags))
        continue
    idx.add(row)
    accepted.append(row)

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

# log search run
now = datetime.now().strftime("%Y-%m-%dT%H:%M")
queries_summary = "; ".join(f"{r['query']}:{len(r['jobs'])}" for r in results)
run_id = f"li_loggedin_20260824_{datetime.now().strftime('%H%M')}"
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f"{run_id},{now},linkedin_loggedin_browser,{len(results)} queries x 1 page (past-week US filter),"
            f"{sum(len(r['jobs']) for r in results)},{len(all_jobs)},{len(accepted)},"
            f"{len(dupes)},{len(rejected)} rejected; guest sweep already ran earlier today\r\n")

print(json.dumps({
    "cards_scanned": sum(len(r["jobs"]) for r in results),
    "unique_ids": len(all_jobs),
    "new_accepted": len(accepted),
    "dupes": len(dupes),
    "rejected": len(rejected),
    "new_job_ids": [r["job_id"] for r in accepted],
    "rejected_detail": rejected[:20],
}, indent=1))
