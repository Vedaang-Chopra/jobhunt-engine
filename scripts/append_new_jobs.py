#!/usr/bin/env python3
"""Append accepted new jobs from LinkedIn sweep to jobs.csv."""

import sys
sys.path.insert(0, 'scripts')

from scripts import discovery_lib, config_lib
import csv
from datetime import date

# Load existing jobs for dedup
JOBS_CSV = config_lib.data_root() / 'tracking' / 'jobs' / 'jobs.csv'

# Fresh jobs from the sweep
fresh_jobs = [
    {
        'source_id': '4464104900',
        'title': 'Staff/Senior Machine Learning Scientist',
        'company': 'Cleveland Clinic',
        'location': 'Cleveland, OH',
        'date_posted_raw': '2026-09-09',
        'posted_rel': '23 minutes ago',
        'url': 'https://www.linkedin.com/jobs/view/4464104900/',
    },
    {
        'source_id': '4417173100',
        'title': 'Researcher, Alignment',
        'company': 'OpenAI',
        'location': 'San Francisco, CA',
        'date_posted_raw': '2026-09-07',
        'posted_rel': '2 days ago',
        'url': 'https://www.linkedin.com/jobs/view/4417173100/',
    }
]

# Build dedup index from existing
existing_jobs = []
with open(JOBS_CSV, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        existing_jobs.append(row)

dedup = discovery_lib.DedupIndex()
for job in existing_jobs:
    dedup.add(job)

# Process fresh jobs
new_rows = []
gated_out = 0

for job in fresh_jobs:
    normalized = discovery_lib.normalize_job(job)
    normalized['description'] = ''  # No description available from guest API
    is_dup, matched = dedup.seen_before(normalized)
    verdict, flags = discovery_lib.scrutinize(normalized)
    
    if is_dup:
        print(f'SKIP (duplicate): {normalized["title"]} at {normalized["company"]}')
        continue
    elif verdict == 'reject':
        # Append with recommended_action=SKIP and gate in notes
        normalized['status'] = 'open'  # Keep as open but mark for skip
        normalized['recommended_action'] = 'SKIP'
        normalized['notes'] = f'GATED OUT at ingest: {", ".join(flags)}'
        new_rows.append(normalized)
        print(f'GATED OUT: {normalized["title"]} at {normalized["company"]} ({flags})')
        gated_out += 1
    else:
        # Accepted - add as new open job
        normalized['status'] = 'open'
        normalized['recommended_action'] = ''
        normalized['notes'] = 'Discovered via LinkedIn guest API sweep'
        new_rows.append(normalized)
        print(f'ACCEPTED: {normalized["title"]} at {normalized["company"]}')

# Append new rows to jobs.csv
if new_rows:
    with open(JOBS_CSV, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=discovery_lib._CSV_COLUMNS)
        for row in new_rows:
            # Ensure all columns are present
            full_row = {k: row.get(k, '') for k in discovery_lib._CSV_COLUMNS}
            writer.writerow(full_row)
    print(f'\nAppended {len(new_rows)} rows to jobs.csv')
else:
    print('\nNo new rows to append')

print(f'Summary: {len(new_rows) - gated_out} new jobs accepted, {gated_out} gated out')