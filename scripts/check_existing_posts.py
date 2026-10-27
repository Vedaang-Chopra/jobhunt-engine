#!/usr/bin/env python3
import csv

# Read existing hiring posts
existing_urls = set()
existing_ids = set()
with open('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/hiring_posts/hiring_posts.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        existing_urls.add(row.get('post_url', ''))
        existing_ids.add(row.get('post_id', ''))

print(f'Existing posts: {len(existing_urls)}')
print(f'Existing IDs: {len(existing_ids)}')
print()
print('Sample post URLs:')
for url in list(existing_urls)[:5]:
    print(f'  {url}')