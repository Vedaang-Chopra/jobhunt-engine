import sys
sys.path.insert(0, 'scripts')
from discovery_lib import DedupIndex
import csv
from pathlib import Path

# Build dedup index from existing jobs.csv
JOBS_CSV = Path('jobhunt-data/tracking/jobs/jobs.csv')
idx = DedupIndex()
with open(JOBS_CSV, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        idx.add(row)

# Check the new job
new_row = {
    'job_id': '',
    'company': 'MeeBoss',
    'title': 'Applied AI Engineer',
    'location': 'Seattle, WA',
    'job_url': 'https://www.linkedin.com/jobs/view/4465328361/',
    'canonical_application_url': 'https://www.linkedin.com/jobs/view/4465328361/',
    'source': 'linkedin',
    'source_id': '4465328361',
    'date_discovered': '2026-09-10',
    'date_posted': '2026-09-09',
    'status': 'open',
    'company_slug': 'meeboss'
}

is_dup, matched = idx.seen_before(new_row)
print(f'Is duplicate: {is_dup}')
if matched:
    print(f'Matched: {matched.get("job_id")} - {matched.get("company")} - {matched.get("title")}')