#!/usr/bin/env python3
import csv
import datetime
from pathlib import Path

# Import the discovery_lib for normalization
import sys
sys.path.insert(0, str(Path.cwd() / "scripts"))
from scripts import discovery_lib

JOBS_CSV = Path("jobhunt-data/tracking/jobs/jobs.csv")
SEARCH_RUNS_CSV = Path("jobhunt-data/tracking/search_runs/search_runs.csv")

today = datetime.date.today().isoformat()

# Jobs to add (4 passing)
new_jobs = [
    {
        "title": "Research Engineer, Post-Training",
        "company": "Vizcom",
        "url": "https://www.linkedin.com/jobs/view/4455714605/",
        "location": "San Francisco, CA",
        "source_id": "4455714605",
        "date_posted": "2026-09-09",
        "source": "linkedin",
        "notes": "Post-training research role at Series B AI design tool company. Pay $164K-$215K. 28 applicants.",
    },
    {
        "title": "Machine Learning Engineer",
        "company": "NVIDIA",
        "url": "https://www.linkedin.com/jobs/view/4464154311/",
        "location": "Santa Clara, CA",
        "source_id": "4464154311",
        "date_posted": "2026-09-09",
        "source": "linkedin",
        "notes": "ML Engineer with AI agents, distributed systems (K8s/Ray/Slurm). Pay $152K-$241K. 3+ years req (candidate ~4.5).",
    },
    {
        "title": "Research Scientist",
        "company": "Alexander Chapman",
        "url": "https://www.linkedin.com/jobs/view/4465307204/",
        "location": "New York, NY",
        "source_id": "4465307204",
        "date_posted": "2026-09-09",
        "source": "linkedin",
        "notes": "Recruiter posting for Series E AI startup ($2.2B+ valuation). Multiple levels. LLMs, agents, RL. 68 applicants.",
    },
    {
        "title": "Researcher, Training",
        "company": "OpenAI",
        "url": "https://www.linkedin.com/jobs/view/4417171127/",
        "location": "San Francisco, CA",
        "source_id": "4417171127",
        "date_posted": "2026-09-07",
        "source": "linkedin",
        "notes": "Architecture team, LLM training runs. Pay $300K-$600K. 200+ applicants. Stretch but credible.",
    },
]

# Normalize and append
with open(JOBS_CSV, "a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=discovery_lib._CSV_COLUMNS)
    for job in new_jobs:
        row = discovery_lib.normalize_job(job)
        row["date_discovered"] = today
        row["last_checked"] = today
        row["status"] = "open"
        row["recommended_action"] = "OPTIMISTIC"
        row["notes"] = job["notes"] + f" [discovery-linkedin {today}]"
        # Ensure job_id is set
        if not row["job_id"]:
            row["job_id"] = f"{row['company_slug']}_{discovery_lib.slugify(row['title'])}_{row['source_id']}"
        writer.writerow(row)
        print(f"Appended: {row['job_id']}")

# Log search run
search_runs_header = [
    "run_id", "run_date", "source", "queries", "total_found", "total_new", "total_gated", "notes"
]
run_id = f"discovery_linkedin_{today}_{datetime.datetime.now().strftime('%H%M%S')}"
run_row = {
    "run_id": run_id,
    "run_date": today,
    "source": "linkedin",
    "queries": "Research Engineer Machine Learning; AI Research Scientist; Post-Training LLM; LLM Fine-Tuning Engineer; AI Agent Engineer; Applied Scientist AI; Machine Learning Engineer LLM; LLM Evaluation Research",
    "total_found": 62,
    "total_new": 6,
    "total_gated": 2,
    "notes": f"Guest API sweep. 6 fresh, 56 dupes. Gated: Notion Early Career (G3+G4), MeeBoss 5+yrs (G1). Added: Vizcom, NVIDIA, Alexander Chapman, OpenAI."
}

file_exists = SEARCH_RUNS_CSV.exists()
with open(SEARCH_RUNS_CSV, "a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=search_runs_header)
    if not file_exists:
        writer.writeheader()
    writer.writerow(run_row)

print(f"\nLogged search run: {run_id}")
print("Done.")