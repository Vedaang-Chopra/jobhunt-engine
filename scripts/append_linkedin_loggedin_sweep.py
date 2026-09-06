#!/usr/bin/env python3
"""Normalize logged-in LinkedIn sweep JSON through discovery_lib, dedupe, append, log run."""
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl
except ImportError:
    import discovery_lib as dl
try:
    from scripts import config_lib
except ImportError:
    import config_lib  # noqa: E402

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
SRC = Path.home() / ".hermes/profiles/job-hunt/cache/browser-use/workspace/dfb06043-49f2-4c15-8bf6-0a70886a5258/li_loggedin_sweep.json"

results = json.loads(SRC.read_text())
all_jobs = {}
for r in results:
    for j in r["jobs"]:
        if j.get("source_id") and j.get("title"):
            all_jobs.setdefault(j["source_id"], j)

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
for j in all_jobs.values():
    raw = {
        "title": j["title"], "company": j.get("company", ""), "url": f"https://www.linkedin.com/jobs/view/{j['source_id']}/",
        "location": j.get("location", ""), "source": "linkedin", "source_id": j["source_id"],
        "date_posted": "", "notes": "linkedin logged-in sweep 2026-08-23 past-week US",
    }
    row = dl.normalize_job(raw)
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{j['source_id']}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((j, matched.get("job_id", "?")))
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

run_id = f"li_loggedin_{datetime.now().strftime('%Y%m%d_%H%M')}"
with open(RUNS_CSV, "a", newline="") as f:
    csv.writer(f).writerow([
        run_id, datetime.now().strftime("%Y-%m-%dT%H:%M"), "linkedin_loggedin_browser",
        "8 queries x 1 page (past-week US filter)", len(all_jobs),
        len(accepted), len(rejected), len(dupes),
        "browser_exec_logged_in_tab",
    ])

print(json.dumps({
    "run_id": run_id, "backup": bak.name,
    "unique_cards": len(all_jobs), "appended": len(accepted),
    "rejected": [{"job": j["company"] + "|" + j["title"], "flags": fl} for j, fl in rejected],
    "dupes": len(dupes),
}, indent=2))
