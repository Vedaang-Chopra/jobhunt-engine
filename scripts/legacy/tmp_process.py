#!/usr/bin/env python3
import sys
import csv
from pathlib import Path

# Add the scripts directory to the path
sys.path.insert(0, './scripts')
try:
    import config_lib
except ImportError as e:
    print(f"Failed to import config_lib: {e}", file=sys.stderr)
    sys.exit(1)

DATA_ROOT = config_lib.data_root()
REQ_PATH = DATA_ROOT / "tracking" / "messages" / "connection_requests.csv"

if not REQ_PATH.exists():
    print(f"ERROR: Request file not found at {REQ_PATH}", file=sys.stderr)
    sys.exit(1)

rows = []
with open(REQ_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

status_col = 'send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)'
approved = [r for r in rows if r.get(status_col) == 'approved']
if not approved:
    print("[SILENT]")
    sys.exit(0)

def get_score(r):
    try:
        return int(r.get('score', 0))
    except ValueError:
        return 0
approved.sort(key=get_score, reverse=True)

for r in approved:
    name = r.get('person_name', '').strip()
    role = r.get('person_type', '').strip()
    company = r.get('company', '').strip()
    why_now = r.get('note_basis(hiring_post|shared_ctx|job_specific|generic)', '').strip()
    priority = r.get('score', '').strip()
    print(f"- [ ] {name}, {role}, {company}, {why_now}, {priority}")