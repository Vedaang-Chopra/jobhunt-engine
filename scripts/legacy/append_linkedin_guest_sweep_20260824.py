#!/usr/bin/env python3
"""Normalize guest sweep JSON (2026-08-24) through discovery_lib, dedupe,
append to jobs.csv, and log the search run."""
import csv
import json
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
SRC = REPO / "execution_results" / "linkedin_sweep_2026-08-24.json"

results = json.loads(SRC.read_text())
fresh = results["fresh"]
print(f"input fresh candidates: {len(fresh)}")

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
for j in fresh:
    sid = str(j["source_id"])
    raw = {
        "title": j["title"], "company": j["company"],
        "url": j.get("url") or f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": j.get("location", ""),
        "source": "linkedin", "source_id": sid,
        "date_posted": j.get("date_posted_raw", ""),
        "posted_rel": j.get("posted_rel", ""),
        "notes": "linkedin guest-api sweep 2026-08-24 past-week US",
    }
    row = dl.normalize_job(raw)
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{sid}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((sid, raw["title"], matched.get("job_id", "?")))
        continue
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((sid, raw["title"], flags))
        continue
    idx.add(row)
    accepted.append(row)

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

now = datetime.now().strftime("%Y-%m-%dT%H:%M")
run_id = f"li_guest_20260824_{datetime.now().strftime('%H%M')}"
queries_summary = "; ".join(f"{q}:{v['cards']}" for q, v in results["per_query"].items())
total_cards = len(results["fresh"]) + len(results["duplicates"])
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f'"{run_id}",{now},linkedin_guest_api,"8 queries x up to 2 pages (past-week US filter)",'
            f'{total_cards},{len(results["fresh"])},{len(dupes)},'
            f'{len(rejected)} rejected; browser logged-in tab hung on LinkedIn pages (renderer timeouts), guest API used instead\r\n')

print(json.dumps({
    "cards_scanned": total_cards,
    "new_accepted": len(accepted),
    "dupes": len(dupes),
    "rejected": len(rejected),
    "new_job_ids": [r["job_id"] for r in accepted],
    "new_jobs_detail": [{"job_id": r["job_id"], "title": r.get("title"), "company": r.get("company"),
                          "location": r.get("location"), "url": r.get("url"),
                          "priority_v2": r.get("priority_v2")} for r in accepted],
    "rejected_detail": rejected,
}, indent=1))
