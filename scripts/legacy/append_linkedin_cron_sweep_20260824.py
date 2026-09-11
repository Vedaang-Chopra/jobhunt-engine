#!/usr/bin/env python3
"""Normalize 2026-08-24 cron LinkedIn logged-in + guest sweeps through discovery_lib,
dedupe against jobs.csv, append new rows (with backup), log search run."""
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
    import config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
LI_JSON = REPO / "execution_results" / "linkedin_loggedin_sweep_2026-08-24_cron.json"
GUEST_JSON = REPO / "execution_results" / "linkedin_sweep_2026-08-24.json"

results = json.loads(LI_JSON.read_text())

all_jobs = {}  # sid -> {title, company, loc, query}
for query, jobs in results.items():
    for j in jobs:
        parts = [p.strip() for p in j["meta"].split("|")]
        if len(parts) < 3:
            continue
        title, company, loc = parts[0], parts[1], parts[2]
        prev = all_jobs.get(j["id"])
        if prev is None or (len(title) > len(prev["title"]) and title.lower() != company.lower()):
            cand = {"title": title, "company": company, "loc": loc,
                    "query": query, "extra": "; ".join(parts[3:5])}
            if prev and not cand["title"]:
                cand["title"] = prev["title"]
            all_jobs[j["id"]] = cand

guest_fresh = []
if GUEST_JSON.exists():
    g = json.loads(GUEST_JSON.read_text())
    guest_fresh = g.get("fresh", [])

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

def try_add(sid, title, company, loc, notes):
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": loc, "source": "linkedin", "source_id": sid,
        "notes": notes,
    }
    row = dl.normalize_job(raw)
    if not row.get("company") or not row.get("title"):
        rejected.append((sid, title, "missing company/title"))
        return
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{sid}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((sid, title, matched.get("job_id", "?")))
        return
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((sid, title, flags))
        return
    idx.add(row)
    accepted.append(row)

for sid, j in sorted(all_jobs.items()):
    notes = ("linkedin logged-in sweep 2026-08-24 past-week US; query=" + j["query"]
             + ("; " + j["extra"] if j["extra"] else ""))
    try_add(sid, j["title"], j["company"], j["loc"], notes)

for gj in guest_fresh:
    notes = ("linkedin guest sweep 2026-08-24 past-week US; "
             + (gj.get("posted_rel") or ""))
    try_add(gj["source_id"], gj["title"], gj["company"], gj["location"], notes)

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

now = datetime.now().strftime("%Y-%m-%dT%H:%M")
run_id = f"li_cron_20260824_{datetime.now().strftime('%H%M')}"
cards = sum(len(v) for v in results.values())
queries_summary = "; ".join(f"{q}:{len(v)}" for q, v in results.items())
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f'{run_id},{now},linkedin_loggedin_browser+guest_api,"6 queries x 1 page (past-week US filter)",'
            f'{cards},{len(all_jobs)+len(guest_fresh)},{len(accepted)},'
            f'{len(dupes)},{len(rejected)} rejected,{queries_summary}\r\n')

print(json.dumps({
    "logged_in_cards": cards,
    "unique_loggedin_ids": len(all_jobs),
    "guest_fresh_considered": len(guest_fresh),
    "new_accepted": len(accepted),
    "dupes": len(dupes),
    "rejected": len(rejected),
    "new_job_ids": [(r["job_id"], r.get("location", "")) for r in accepted],
    "rejected_detail": rejected[:25],
}, indent=1))
