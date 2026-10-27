import csv
import sys

# Path to jobs.csv
jobs_csv = 'jobhunt-data/tracking/jobs/jobs.csv'
job_id_to_update = 'meeboss_applied_ai_engineer_4465328361'

# Read the CSV
rows = []
with open(jobs_csv, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

# Find the row to update
updated = False
for row in rows:
    if row['job_id'] == job_id_to_update:
        # Update the row
        row['recommended_action'] = 'SKIP'
        # Append gate note to existing notes
        existing_notes = row.get('notes', '')
        gate_note = 'G1: Experience ceiling (JD states 5+ years, candidate has ~4.5 yrs)'
        if existing_notes:
            row['notes'] = existing_notes + '; ' + gate_note
        else:
            row['notes'] = gate_note
        updated = True
        break

if not updated:
    print(f"ERROR: Job with job_id {job_id_to_update} not found.")
    sys.exit(1)

# Write back
with open(jobs_csv, 'w', newline='') as f:
    fieldnames = rows[0].keys()
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Updated job {job_id_to_update} to SKIP due to G1.")