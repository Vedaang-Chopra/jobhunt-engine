import csv
from datetime import date

# Check ALL entries with today's date
today = date.today().isoformat()
all_today_posts = []
with open('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/hiring_posts/hiring_posts.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('discovered_date') == today:
            all_today_posts.append(row)

print(f"All hiring posts with discovered_date={today}: {len(all_today_posts)}")
for p in all_today_posts:
    print(f"  - {p['poster_name']} ({p['poster_type']}) @ {p['company']}: {p['roles_mentioned'][:80]}... Status: {p['status']}")

# Also check for recently added (last few rows with new status)
print("\n--- All 'new' status posts ---")
new_posts_all = []
with open('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/hiring_posts/hiring_posts.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('status') == 'new':
            new_posts_all.append(row)

print(f"Total 'new' status posts: {len(new_posts_all)}")
# Show last 10
for p in new_posts_all[-10:]:
    print(f"  - {p['poster_name']} ({p['poster_type']}) @ {p['company']}: {p['discovered_date']} {p['roles_mentioned'][:60]}...")