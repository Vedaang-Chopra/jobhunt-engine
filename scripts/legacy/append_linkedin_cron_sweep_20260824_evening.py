#!/usr/bin/env python3
"""Normalize 2026-08-24 evening LinkedIn sweeps (logged-in browser + guest API)
through discovery_lib, dedupe against jobs.csv, append new rows, log search run."""
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
LI_JSONS = [REPO / "execution_results" / f"li_loggedin_sweep_b{b}.json" for b in (1, 2)]
GUEST_JSON = REPO / "execution_results" / "linkedin_sweep_2026-08-24.json"

all_jobs = {}
results = []
for path in LI_JSONS:
    d = json.loads(path.read_text())
    if isinstance(d, str):
        d = json.loads(d)
    results.extend(d)

for r in results:
    for j in r.get("jobs", []):
        sid = j["id"]
        parts = [p for p in j.get("parts", []) if not re.search(r"[<>=]|class=|role=|componentkey", p)]
        title, company, loc = None, None, ""
        # typical order after cleanup: [title?, company, location, ...signals]
        rest = parts
        if len(parts) >= 3 and re.search(r", |\(|United States|Bay Area|Area\b", parts[1]):
            company, loc, rest = parts[0], parts[1], parts[2:]
        elif len(parts) >= 3:
            title, company, loc, rest = parts[0], parts[1], parts[2], parts[3:]
        elif len(parts) == 2:
            company, rest = parts[0], parts[1:]
        else:
            continue
        notes_bits = [p for p in rest if re.search(
            r"connections? works? here|alumni work|\$\d+K/yr|Posted \d|early applicant|Actively reviewing|Viewed", p)]
        prev = all_jobs.get(sid)
        cand = {"_title": title or "", "_company": company, "_loc": loc,
                "_notes": notes_bits, "_query": r["query"]}
        if prev is None or len(notes_bits) > len(prev["_notes"]):
            if prev is not None and not cand["_title"]:
                cand["_title"] = prev["_title"]
            all_jobs[sid] = cand

# fill missing titles from other query variants
for sid, j in list(all_jobs.items()):
    if not j["_title"]:
        for r2 in results:
            for jj in r2.get("jobs", []):
                if jj["id"] == sid:
                    ps = [p for p in jj.get("parts", []) if not re.search(r"[<>=]|class=|role=|componentkey", p)]
                    if len(ps) >= 3:
                        j["_title"] = ps[0]
                        break

guest_fresh = []
if GUEST_JSON.exists():
    guest_fresh = json.loads(GUEST_JSON.read_text()).get("fresh", [])

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
    if not title:
        rejected.append((sid, "", ["no title parsed"]))
        return
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": loc, "source": "linkedin", "source_id": sid,
        "date_posted": "", "notes": notes,
    }
    row = dl.normalize_job(raw)
    if not row.get("company") or not row.get("title"):
        rejected.append((sid, title, ["missing company/title"]))
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
    try_add(sid, j["_title"], j["_company"], j["_loc"], notes)

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
run_id = f"li_sweep_20260824_{datetime.now().strftime('%H%M')}"
cards = sum(len(r.get("jobs", [])) for r in results) + sum(1 for _ in guest_fresh)
notes = (f"{len(all_jobs)} unique logged-in ids + {len(guest_fresh)} guest fresh; "
         f"{len(rejected)} rejected by fit gate")
with open(RUNS_CSV, "a", newline="") as f:
    w = csv.writer(f)
    w.writerow([run_id, now.split("T")[0], "linkedin_loggedin_browser+guest_api",
                "8 profile-guided queries x 1 page (past-week US filter)",
                cards, len(accepted), len(dupes), "", notes])

print(json.dumps({
    "unique_loggedin_ids": len(all_jobs),
    "guest_fresh_considered": len(guest_fresh),
    "new_accepted": len(accepted),
    "dupes": len(dupes),
    "rejected": len(rejected),
    "new_job_ids": [(r["job_id"], r.get("location", "")) for r in accepted],
    "rejected_detail": rejected[:25],
}, indent=1))
