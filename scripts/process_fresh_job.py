#!/usr/bin/env python3
import sys
sys.path.insert(0, 'scripts')
from scripts import discovery_lib, config_lib
import csv
from datetime import date

# The fresh job from the sweep
raw_job = {
    "source_id": "4462948531",
    "title": "Senior Research Scientist, Cloud AI Research",
    "company": "Google",
    "location": "Mountain View, CA",
    "date_posted_raw": "2026-09-07",
    "posted_rel": "17 hours ago",
    "url": "https://www.linkedin.com/jobs/view/4462948531/",
    "dup_of_existing": False
}

# Normalize through discovery_lib
normalized = discovery_lib.normalize_job({
    "title": raw_job["title"],
    "company": raw_job["company"],
    "url": raw_job["url"],
    "location": raw_job["location"],
    "source_id": raw_job["source_id"],
    "date_posted": raw_job["date_posted_raw"],
    "source": "linkedin"
})

print("Normalized row:")
for k, v in normalized.items():
    if v:
        print(f"  {k}: {v}")

# Apply scrutiny gate
# We need a description to check experience requirements - we don't have it yet
# Let's check what the gate would say with minimal info
verdict, flags = discovery_lib.scrutinize({
    "title": normalized["title"],
    "company": normalized["company"],
    "location": normalized["location"],
    "description": "",  # We don't have full JD yet
    "date_posted": normalized["date_posted"],
    "priority_v2": normalized.get("priority_v2", ""),
    "exceptional": normalized.get("exceptional", "")
})

print(f"\nScrutiny verdict: {verdict}")
print(f"Flags: {flags}")

# Check if it would be rejected by any hard gate
if verdict == "reject":
    print("JOB WOULD BE REJECTED - skipping")
else:
    print("JOB PASSES GATES - would be added as open")
    
    # Add to jobs.csv
    JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
    
    # Ensure all columns are present
    row = {col: normalized.get(col, "") for col in discovery_lib._CSV_COLUMNS}
    row["status"] = "open"
    row["recommended_action"] = ""  # Empty since it passes gates
    
    # Write to CSV
    with open(JOBS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=discovery_lib._CSV_COLUMNS)
        writer.writerow(row)
    print(f"Appended to {JOBS_CSV}")