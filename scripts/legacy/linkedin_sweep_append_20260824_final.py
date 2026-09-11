#!/usr/bin/env python3
"""Fixup: build source_id->title map from guest sweep JSON + per-ID /jobs/view fetches,
then run the same normalize/dedupe/append pipeline."""
import csv
import html
import json
import re
import shutil
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl, config_lib
except ImportError:
    import discovery_lib as dl  # type: ignore
    import config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
LI_JSON = Path.home() / "li_sweep_0824c.json"
GUEST_JSON = REPO / "execution_results" / "linkedin_sweep_2026-08-24.json"

results = json.loads(LI_JSON.read_text())
if isinstance(results, str):
    results = json.loads(results)

all_jobs = {}
for r in results:
    for j in r["jobs"]:
        parts = j.get("parts", [])
        sid = j["source_id"]
        if len(parts) < 3:
            continue
        notes_bits = [p for p in parts[3:] if re.search(
            r"connections work here|alumni work|alumni works|Posted |\$.*K/yr|early applicant|Actively reviewing", p)]
        cand = {"_title": "", "_company": parts[0], "_loc": parts[1],
                "_notes": notes_bits, "_query": r["query"]}
        prev = all_jobs.get(sid)
        if prev is None or len(notes_bits) > len(prev["_notes"]):
            if prev is not None and prev["_title"]:
                cand["_title"] = prev["_title"]
            all_jobs[sid] = cand

# titles known from guest API (fresh + duplicates lists)
g = json.loads(GUEST_JSON.read_text()) if GUEST_JSON.exists() else {}
guest_titles = {}
for gj in g.get("fresh", []) + g.get("duplicates", []):
    guest_titles[gj["source_id"]] = (gj.get("title", ""), gj)
for sid, j in all_jobs.items():
    if sid in guest_titles and guest_titles[sid][0]:
        j["_title"] = guest_titles[sid][0]

missing = [sid for sid, j in all_jobs.items() if not j["_title"]]
print(f"{len(all_jobs)} logged-in ids, {len(missing)} missing titles")

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
for n, sid in enumerate(missing):
    try:
        body = urllib.request.urlopen(urllib.request.Request(
            f"https://www.linkedin.com/jobs/view/{sid}/", headers=HEADERS),
            timeout=30).read().decode("utf-8", "ignore")
        m = (re.search(r'<h1[^>]*>\s*(?:<[^>]+>\s*)*([^<]{3,150}?)\s*<', body) or
             re.search(r'property="og:title" content="([^"]+)"', body))
        if m:
            t = html.unescape(m.group(1)).strip()
            t = re.sub(r"\s*\|\s*LinkedIn$", "", t)
            all_jobs[sid]["_title"] = t
        else:
            print(f"  no title found for {sid}")
    except Exception as e:
        print(f"  fetch failed {sid}: {e}")
    time.sleep(0.9)

still_missing = [s for s, j in all_jobs.items() if not j["_title"]]

bak = JOBS_CSV.with_suffix(".csv.bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
shutil.copy2(JOBS_CSV, bak)

with open(JOBS_CSV, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)

idx = dl.DedupIndex()
for row in existing:
    idx.add(row)

accepted, rejected, dupes = [], [], []

def try_add(sid, title, company, loc, notes):
    raw = {"title": title, "company": company,
           "url": f"https://www.linkedin.com/jobs/view/{sid}/",
           "location": loc, "source": "linkedin", "source_id": sid,
           "date_posted": "", "posted_rel": "", "notes": notes}
    row = dl.normalize_job(raw)
    if not row.get("company") or not row.get("title"):
        rejected.append((sid, title, "missing company/title"))
        return
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{sid}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((sid, title, matched.get("job_id", "?")))
        return
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((sid, title, flags))
        return
    idx.add(row)
    accepted.append(row)

for sid, j in sorted(all_jobs.items()):
    notes = ("linkedin logged-in sweep 2026-08-24 past-week US; query=" + j["_query"]
             + ("; " + "; ".join(j["_notes"]) if j["_notes"] else ""))
    try_add(sid, j["_title"], j["_company"], j["_loc"], notes)

# also fold in guest-only fresh rows (not present in logged-in set)
logged_ids = set(all_jobs)
for gj in g.get("fresh", []):
    if gj["source_id"] in logged_ids:
        continue
    notes = "linkedin guest sweep 2026-08-24 past-week US; " + (gj.get("posted_rel") or "")
    try_add(gj["source_id"], gj.get("title", ""), gj.get("company", ""),
            gj.get("location", ""), notes)

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

now = datetime.now().strftime("%Y-%m-%dT%H:%M")
run_id = f"li_loggedin_20260824_{datetime.now().strftime('%H%M')}"
cards = sum(len(r["jobs"]) for r in results)
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f"{run_id},{now},linkedin_loggedin_browser+guest_api,"
            f"8 queries x 1 page (past-week US filter),{cards},{len(all_jobs)},"
            f"{len(accepted)},{len(dupes)},{len(rejected)} rejected\r\n")

print(json.dumps({
    "logged_in_cards": cards,
    "unique_loggedin_ids": len(all_jobs),
    "titles_from_guest": sum(1 for j in all_jobs.values() if j["_title"]) - (len(missing) - len(still_missing)),
    "still_missing_title": still_missing,
    "new_accepted": len(accepted),
    "dupes": len(dupes),
    "rejected": len(rejected),
    "new_jobs": [(r["job_id"], r.get("location", "")) for r in accepted],
    "rejected_detail": rejected[:30],
}, indent=1))
