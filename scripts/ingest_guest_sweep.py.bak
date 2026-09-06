#!/usr/bin/env python3
"""Ingest fresh guest-sweep results into tracking/jobs/jobs.csv via discovery_lib."""
import csv
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import config_lib
except ImportError:
    import config_lib
from discovery_lib import DedupIndex, normalize_job, scrutinize  # noqa: E402
import config_lib

JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = config_lib.path("search_runs_csv")
SRC = REPO / "execution_results/linkedin_sweep_2026-08-23.json"

data = json.loads(SRC.read_text())
fresh = data["fresh"]

store = DedupIndex()
with open(JOBS_CSV, newline="") as f:
    for row in csv.DictReader(f):
        store.add(row)

new_rows, dupes, rejected = [], 0, []
for j in fresh:
    sid = j["source_id"]
    raw = {
        "title": j["title"],
        "company": j["company"],
        "url": j["url"],
        "job_id": f"li_{sid}",
        "source": "linkedin",
        "source_id": f"li_{sid}",
        "location": j.get("location", ""),
        "date_posted": j.get("date_posted_raw", ""),
        "notes": f"posted_rel={j.get('posted_rel','')}",
    }
    row = normalize_job(raw)
    is_dup, _ = store.seen_before(row)
    if is_dup:
        dupes += 1
        continue
    verdict, flags = scrutinize(row)
    if verdict == "reject":
        rejected.append((row["company"], row["title"], flags))
        continue
    store.add(row)
    new_rows.append(row)

if new_rows:
    cols = list(new_rows[0].keys())
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        for r in new_rows:
            r.pop("_ats_id", None)
            w.writerow(r)

run_id = f"li_guest_{date.today().strftime('%Y%m%d_%H%M')}"
with open(RUNS_CSV, "a", newline="") as f:
    w = csv.writer(f)
    w.writerow([run_id, date.today().isoformat(), "linkedin_guest_api",
                len(data["per_query"]), sum(q["cards"] for q in data["per_query"].values()),
                len(new_rows), dupes, 0,
                f"rejected={len(rejected)}; playwright_mcp_unavailable"])
