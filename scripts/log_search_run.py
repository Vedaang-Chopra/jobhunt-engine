#!/usr/bin/env python3
"""Log the LinkedIn discovery sweep to search_runs.csv."""

import csv
from datetime import datetime
from pathlib import Path

sys_path = Path(__file__).resolve().parent.parent / "scripts"
import sys
sys.path.insert(0, str(sys_path))

from scripts import config_lib

SEARCH_RUNS_CSV = config_lib.data_root() / "tracking" / "search_runs" / "search_runs.csv"

# Log this run
run_id = f"discovery_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
row = {
    "run_id": run_id,
    "date": datetime.now().strftime("%Y-%m-%d"),
    "sources": "linkedin_guest_sweep",
    "queries": "8 queries (Research Engineer ML, AI Research Scientist, Post-Training LLM, LLM Fine-Tuning Engineer, AI Agent Engineer, Applied Scientist AI, ML Engineer LLM, LLM Evaluation Research) x 2 pages each",
    "total_scanned": "68",
    "new_jobs_found": "2",
    "duplicates_skipped": "66",
    "strong_fits": "",
    "notes": "guest API sweep; 1 accepted (OpenAI Researcher Alignment), 1 gated out (Cleveland Clinic - seniority_bar, thin_jd)"
}

# Append to CSV
file_exists = SEARCH_RUNS_CSV.exists()
with open(SEARCH_RUNS_CSV, 'a', newline='') as f:
    fieldnames = ["run_id", "date", "sources", "queries", "total_scanned", "new_jobs_found", "duplicates_skipped", "strong_fits", "notes"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if not file_exists:
        writer.writeheader()
    writer.writerow(row)

print(f"Logged search run: {run_id}")