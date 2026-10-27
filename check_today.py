import csv
from datetime import date

# Check for new hiring posts discovered today
today = date.today().isoformat()
new_posts = []
with open('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/hiring_posts/hiring_posts.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('discovered_date') == today and row.get('status') == 'new':
            new_posts.append(row)

print(f"New hiring posts today ({today}): {len(new_posts)}")
for p in new_posts:
    print(f"  - {p['poster_name']} ({p['poster_type']}) @ {p['company']}: {p['roles_mentioned'][:80]}... URL: {p['post_url'][:80]}")
    print(f"    Why: {p.get('notes', '')[:120]}")

# Check for new people sweep entries today
new_people = []
with open('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/people_sweeps/people_sweep.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('date') == today:
            new_people.append(row)

print(f"\nNew people queued today ({today}): {len(new_people)}")
for p in new_people:
    print(f"  - {p['name']} @ {p['company']} ({p['person_type']}): {p['why_relevant'][:80]}...")