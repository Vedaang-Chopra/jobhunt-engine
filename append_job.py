import sys, csv
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
row['job_id'] = 'meeboss_applied_ai_engineer_4465328361'
row['company_slug'] = 'meeboss'
row['source'] = 'linkedin'
row['source_id'] = '4465328361'
with open('jobhunt-data/tracking/jobs/jobs.csv', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
out_row = [row.get(field, '') for field in header]
with open('jobhunt-data/tracking/jobs/jobs.csv', 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(out_row)
print('Appended job: MeeBoss - Applied AI Engineer')