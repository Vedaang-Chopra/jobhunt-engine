#!/usr/bin/env python3
"""Ingest linkedin_sweep_2026-08-26.json: normalize via discovery_lib, dedupe,
append to jobs.csv, log search run."""
import csv, json, shutil, sys
from datetime import datetime
from pathlib import Path

REPO = Path("/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting")
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl, config_lib
except ImportError:
    import discovery_lib as dl
    import config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
SRC = REPO / "execution_results" / "linkedin_sweep_2026-08-26.json"

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
        "notes": "linkedin guest-api sweep 2026-08-26 past-week US",
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
run_id = f"li_guest_20260826_{datetime.now().strftime('%H%M')}"
queries_summary = "; ".join(f"{q}:{v['cards']}" for q, v in results["per_query"].items())
total_cards = len(results["fresh"]) + len(results["duplicates"])
with open(RUNS_CSV, "a", newline="") as f:
    w = csv.writer(f)
    if f.tell() == 0:
        w.writerow(["run_id", "date", "sources", "queries", "total_scanned",
                    "new_jobs_found", "duplicates_skipped", "strong_fits", "notes"])
    w.writerow([run_id, now, "linkedin_guest_api",
                queries_summary or "8 queries x up to 2 pages (past-week US filter)",
                total_cards, len(accepted), len(dupes), "",
                f"{len(rejected)} rejected; logged-in Playwright attempt found session not signed in (login wall) - guest API used"])

print(json.dumps({
    "cards_scanned": total_cards, "new_accepted": len(accepted), "dupes": len(dupes),
    "rejected": len(rejected),
    "new_jobs_detail": [{"job_id": r["job_id"], "title": r.get("title"), "company": r.get("company"),
                         "location": r.get("location"), "url": r.get("url")} for r in accepted],
    "rejected_detail": rejected,
}, indent=1))
