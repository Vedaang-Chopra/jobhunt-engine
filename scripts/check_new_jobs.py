#!/usr/bin/env python3
"""Check fresh jobs from LinkedIn sweep against dedup and scrutiny gates."""

import sys
sys.path.insert(0, 'scripts')

from scripts import discovery_lib, config_lib
import csv

# Load existing jobs for dedup
JOBS_CSV = config_lib.data_root() / 'tracking' / 'jobs' / 'jobs.csv'
existing_jobs = []
with open(JOBS_CSV, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        existing_jobs.append(row)

# Build dedup index
dedup = discovery_lib.DedupIndex()
for job in existing_jobs:
    dedup.add(job)

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

gated_out = 0
new_accepted = 0

for job in fresh_jobs:
    normalized = discovery_lib.normalize_job(job)
    normalized['description'] = ''  # No description available from guest API
    is_dup, matched = dedup.seen_before(normalized)
    verdict, flags = discovery_lib.scrutinize(normalized)
    print(f'Job: {normalized["title"]} at {normalized["company"]}')
    print(f'  Location: {normalized["location"]}')
    print(f'  Dup check: {"DUPLICATE" if is_dup else "NEW"}')
    print(f'  Scrutiny: {verdict}, flags: {flags}')
    if is_dup:
        print(f'  -> SKIP (duplicate)')
    elif verdict == 'reject':
        print(f'  -> GATED OUT ({flags})')
        gated_out += 1
    else:
        print(f'  -> ACCEPTED (new)')
        new_accepted += 1
    print()

print(f'Summary: {new_accepted} new jobs accepted, {gated_out} gated out')