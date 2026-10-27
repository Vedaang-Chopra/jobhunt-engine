#!/usr/bin/env python3
"""Process LinkedIn sweep results: normalize, gate, dedupe, append to jobs.csv"""

import json
import csv
import sys
from datetime import date

sys.path.insert(0, 'scripts')
from discovery_lib import normalize_job, DedupIndex, scrutinize

def main():
    # Load existing jobs to build dedup index
    JOBS_CSV = 'jobhunt-data/tracking/jobs/jobs.csv'
    idx = DedupIndex()
    with open(JOBS_CSV, newline='') as f:
        for row in csv.DictReader(f):
            idx.add(row)

    # Load fresh jobs from sweep
    with open('jobhunt-data/execution_results/linkedin_sweep_2026-09-07.json') as f:
        data = json.load(f)

    fresh = data['fresh']
    today = date.today().isoformat()

    new_rows = []
    gated_out = 0

    for j in fresh:
        raw = {
            'title': j['title'],
            'company': j['company'],
            'url': j['url'],
            'location': j['location'],
            'date_posted': j['date_posted_raw'],
            'source_id': j['source_id'],
            'source': 'linkedin',
        }
        row = normalize_job(raw)
        row['date_discovered'] = today
        row['status'] = 'open'
        
        # Apply scrutiny gate
        verdict, flags = scrutinize(row)
        print(f'SCRUTINY: {row["title"]} @ {row["company"]} -> {verdict} flags={flags}')
        
        if verdict == 'reject':
            row['recommended_action'] = 'SKIP'
            row['notes'] = f'gated:{flags[0]}' + (' ' + row.get('notes', '') if row.get('notes') else '')
            gated_out += 1
        
        # Check dedup
        is_dup, matched = idx.seen_before(row)
        if is_dup:
            print(f'  DUPLICATE of {matched.get("job_id")}')
            continue
        
        # Add to index for subsequent checks
        idx.add(row)
        new_rows.append(row)

    print(f'\nTotal fresh: {len(fresh)}')
    print(f'Gated out: {gated_out}')
    print(f'New rows to append: {len(new_rows)}')

    # Print new rows
    for r in new_rows:
        print(f'  + {r["title"]} @ {r["company"]} ({r["location"]}) source_id={r["source_id"]}')

    # Append to jobs.csv
    if new_rows:
        import discovery_lib
        columns = discovery_lib._CSV_COLUMNS
        with open(JOBS_CSV, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            for row in new_rows:
                # Ensure all columns present
                out_row = {col: row.get(col, '') for col in columns}
                writer.writerow(out_row)
        print(f'Appended {len(new_rows)} rows to {JOBS_CSV}')
    else:
        print('No new rows to append')

    # Log search run
    SEARCH_RUNS_CSV = 'jobhunt-data/tracking/search_runs/search_runs.csv'
    with open(SEARCH_RUNS_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([today, 'linkedin_guest_sweep', len(fresh), len(new_rows), gated_out, 'completed'])
    print(f'Logged search run to {SEARCH_RUNS_CSV}')

if __name__ == '__main__':
    main()