#!/usr/bin/env python3
"""Normalize 2026-08-26 LinkedIn cron sweep (7 logged-in searches, past-week US,
Associate/Mid-Senior filters) through discovery_lib; apply hard gates G1-G6;
dedupe vs jobs.csv; append new rows (backup first); log search run."""
import csv, json, re, shutil, sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl, config_lib
except ImportError:
    import discovery_lib as dl, config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = DATA / "tracking" / "search_runs" / "search_runs.csv"
NON_USEFUL = DATA / "tracking" / "jobs" / "non_useful.csv"

RAW = json.loads(Path(__file__).with_name("_li_cron_raw_20260826.json").read_text())

def parse_card(text):
    parts = [p.strip() for p in text.split("|") if p.strip()]
    if len(parts) < 3:
        return None
    title, company, loc = parts[0], parts[1], parts[2]
    rest = parts[3:]
    notes = [p for p in rest if re.search(
        r"connections? work|alumni? work|alum works|\$.*(/yr|/hr)|early applicant"
        r"|Actively reviewing|Posted |\d+ (hours?|days?) ago|Viewed", p)]
    return title, company, loc, notes

GATE_TITLES = [
    (r"\bintern\b|internship|co-op|new grad|new-grad|graduate|campus|university|early career|2027 start|phd, early", "G3 early-career"),
    (r"\b(director|vp|head of|chief|principal)\b", "G2 seniority"),
]
UNRELATED = r"lecturer|professor|analyst - ai trainer|red team analyst|forensic|incident responder|threat researcher|vulnerability researcher|splunk|edi edifecs|vision data specialist|technical solutions engineer|construction"

jobs = {}
for q, cards in RAW.items():
    for cid, text in cards:
        p = parse_card(text)
        if not p:
            continue
        t, co, loc, notes = p
        prev = jobs.get(cid)
        if prev is None or len(notes) > len(prev[3]):
            jobs[cid] = [t, co, loc, notes]

now = datetime.now()
bak = JOBS_CSV.with_suffix(".csv.bak_" + now.strftime("%Y%m%d_%H%M%S"))
shutil.copy2(JOBS_CSV, bak)

with open(JOBS_CSV, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)
idx = dl.DedupIndex()
for row in existing:
    idx.add(row)

accepted, gated, dupes, rejected = [], [], [], []
for sid, (title, company, loc, notes) in sorted(jobs.items()):
    tl = title.lower()
    gate = next((g for pat, g in GATE_TITLES if re.search(pat, tl)), None)
    pay = re.search(r"\$(\d+)K/yr(?:\s*-\s*\$(\d+)K/yr)?", " ".join(notes))
    hourly = any("/hr" in n for n in notes)
    if not gate and pay:
        lo = int(pay.group(1))
        hi = int(pay.group(2)) if pay.group(2) else lo
        if hi < 150 or (hourly and hi == lo):
            gate = f"G4 pay<{150}k" if hi < 150 else None
        elif lo < 150 and hi >= 150:
            pass  # band crosses floor — keep
    if not gate and re.search(UNRELATED, tl):
        gate = "G5 unrelated"
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": loc, "source": "linkedin", "source_id": sid,
        "date_posted": "", "notes": ("linkedin logged-in cron sweep 2026-08-26 past-week US assoc/mid-senior; "
            + "; ".join(notes) + (("; GATE:" + gate) if gate else "")),
    }
    row = dl.normalize_job(raw)
    if not row.get("company") or not row.get("title"):
        rejected.append((sid, title, "missing fields")); continue
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{sid}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((sid, title)); continue
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((sid, title, flags)); continue
    idx.add(row)
    if gate:
        row["recommended_action"] = "SKIP"
        row["notes"] = raw["notes"]
        gated.append((row["job_id"], gate))
        # non_useful ledger
        NU_FIELDS = ["job_id", "company", "title", "location", "job_url", "source",
                     "date_discovered", "gate", "notes"]
        nurow = {"gate": gate, "date_discovered": now.strftime("%Y-%m-%d"), **{k: row.get(k, "") for k in NU_FIELDS}}
        write_header = not NON_USEFUL.exists()
        with open(NON_USEFUL, "a", newline="") as nf:
            w = csv.DictWriter(nf, fieldnames=NU_FIELDS, extrasaction="ignore")
            if write_header:
                w.writeheader()
            w.writerow({k: nurow.get(k, "") for k in NU_FIELDS})
    else:
        accepted.append(row)

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

run_id = f"li_loggedin_20260826_{now.strftime('%H%M')}"
cards_total = sum(len(v) for v in RAW.values())
queries_summary = "; ".join(f"{q}:{len(c)}" for q, c in RAW.items())
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f'{run_id},{now.strftime("%Y-%m-%dT%H:%M")},linkedin_loggedin_browser,'
            f'7 queries x 1 page (past-week US + Associate/Mid-Senior chips verified),{cards_total},'
            f'{len(jobs)},{len(accepted)} new,{len(gated)} gated,{len(dupes)} dup,{len(rejected)} rej;'
            f' queries: {queries_summary}\r\n')

print(json.dumps({
    "unique_ids": len(jobs), "new_open": len(accepted), "gated_skip": len(gated),
    "dupes": len(dupes), "rejected_by_scrutinize": len(rejected),
    "new_jobs": [(r["job_id"], r["location"]) for r in accepted],
    "gated_detail": gated,
    "rejected_detail": rejected[:15],
}, indent=1))
