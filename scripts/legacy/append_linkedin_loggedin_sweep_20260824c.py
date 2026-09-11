#!/usr/bin/env python3
"""Normalize 2026-08-24 logged-in + guest LinkedIn sweeps through discovery_lib,
dedupe against jobs.csv, append new rows (with backup), log search run."""
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
    import config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
LI_JSON = Path.home() / "li_sweep_0824c.json"
GUEST_JSON = REPO / "execution_results" / "linkedin_sweep_2026-08-24.json"

results = json.loads(LI_JSON.read_text())
if isinstance(results, str):
    results = json.loads(results)
all_jobs = {}
for r in results:
    for j in r["jobs"]:
        parts = j.get("parts", [])
        sid = j["source_id"]
        if len(parts) < 3:
            continue
        # heuristics: parts[0] may be title when card starts with long title text
        title, company = None, None
        if len(parts) >= 2 and not re.match(r"^\$", parts[0]):
            # typical order: [title?, company, location, ...] — detect title by
            # presence of a following location-like part
            if re.search(r", (CA|NY|WA|TX|GA|MA|VA|CT|MI|MD|NC|NJ|PA|CO)\b|\(Remote\)|\(On-site\)|\(Hybrid\)|Metropolitan Area|Bay Area|United States", parts[1]):
                company, loc = parts[0], parts[1]
                rest = parts[2:]
            else:
                title, company, loc = parts[0], parts[1], parts[2]
                rest = parts[3:]
        else:
            company, loc, rest = parts[0], parts[1], parts[2:]
        notes_bits = [p for p in rest if re.search(r"connections work here|alumni work|company alumni works|school alumni|Posted |\$.*K/yr|early applicant|Actively reviewing", p)]
        prev = all_jobs.get(sid)
        cand = {
            "_title": title or "", "_company": company, "_loc": loc,
            "_notes": notes_bits, "_query": r["query"],
        }
        if prev is None or len(notes_bits) > len(prev["_notes"]):
            if prev is not None and not cand["_title"]:
                cand["_title"] = prev["_title"]
            all_jobs[sid] = cand

# fold in title guesses across query variants
for sid, j in list(all_jobs.items()):
    pass

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

def try_add(sid, title, company, loc, notes, source_tag):
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": loc, "source": "linkedin", "source_id": sid,
        "date_posted": "", "posted_rel": "", "notes": notes,
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
    notes = ("linkedin logged-in sweep 2026-08-24 past-week US; query=" + j["_query"]
             + ("; " + "; ".join(j["_notes"]) if j["_notes"] else ""))
    try_add(sid, j["_title"], j["_company"], j["_loc"], notes, "loggedin")

for gj in guest_fresh:
    notes = ("linkedin guest sweep 2026-08-24 past-week US; "
             + (gj.get("posted_rel") or ""))
    try_add(gj["source_id"], gj["title"], gj["company"], gj["location"], notes, "guest")

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

now = datetime.now().strftime("%Y-%m-%dT%H:%M")
queries_summary = "; ".join(f"{r['query']}:{len(r['jobs'])}" for r in results)
run_id = f"li_loggedin_20260824_{datetime.now().strftime('%H%M')}"
cards = sum(len(r["jobs"]) for r in results)
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f"{run_id},{now},linkedin_loggedin_browser+guest_api,8 queries x 1 page (past-week US filter),"
            f"{cards},{len(all_jobs)+len(guest_fresh)},{len(accepted)},"
            f"{len(dupes)},{len(rejected)} rejected\r\n")

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
