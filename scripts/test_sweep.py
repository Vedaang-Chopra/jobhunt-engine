#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/DATA/job_hunt/jobhunt-engine/scripts')
import config_lib
import people_sweep

# Load preferences and build queries
prefs = people_sweep.load_preferences()
queries = people_sweep.build_queries(prefs)
capped = people_sweep.cap_queries(queries, 8)

print(f"Total companies: {len(prefs.get('companies', []))}")
print(f"Total queries before cap: {len(queries)}")
print(f"Capped to {len(capped)} queries:")
for q in capped:
    print(f"  [{q['family']}] {q['keywords']}")
    print(f"    {q['url']}")

# Now load the dedup index
index = people_sweep.PeopleDedupIndex()
contacts_path = config_lib.path("contacts_csv")
if contacts_path.exists():
    index.load_contacts(contacts_path)
    print(f"\nLoaded {len(index._slugs)} contact slugs from contacts.csv")

people_sweep_path = config_lib.path("people_sweep_csv")
if people_sweep_path.exists():
    index.load_prior_rows(people_sweep_path)
    print(f"Loaded prior sweep rows from people_sweep.csv")

print(f"\nTotal names in index: {len(index._names)}")
print(f"Total slugs in index: {len(index._slugs)}")

# Print sample of existing contacts
print("\nSample contacts in index:")
for i, (norm_name, company, status) in enumerate(index._names[:10]):
    print(f"  {norm_name} @ {company} [{status}]")