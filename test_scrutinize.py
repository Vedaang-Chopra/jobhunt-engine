import sys
sys.path.insert(0, 'scripts')
from discovery_lib import normalize_job, scrutinize

raw = {
    'title': 'Applied AI Engineer',
    'company': 'MeeBoss',
    'url': 'https://www.linkedin.com/jobs/view/4465328361/',
    'location': 'Seattle, WA',
    'date_posted_raw': '2026-09-09',
    'source_id': '4465328361'
}

row = normalize_job(raw)
print('Normalized row:')
for k, v in row.items():
    if v:
        print(f'  {k}: {v}')

verdict, flags = scrutinize(row)
print(f'\nScrutiny verdict: {verdict}')
print(f'Flags: {flags}')