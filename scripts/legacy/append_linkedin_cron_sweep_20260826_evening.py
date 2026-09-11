#!/usr/bin/env python3
"""Ingest 2026-08-26 LinkedIn cron sweep (guest API 8 queries + logged-in fetch
4 queries, past-week/24h US) through discovery_lib; gates G1-G6 per
ROLE_FIT_RULES §9; dedupe vs jobs.csv; append new rows (backup first); log run."""
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

RAW = {}
RAW.update(json.loads((REPO / "scripts/_li_loggedin_batch1_20260826.json").read_text()))
for kw, cards in json.loads((REPO / "scripts/_li_loggedin_batch2_20260826.json").read_text()):
    RAW[kw] = cards
GUEST = json.loads((REPO / "execution_results/linkedin_sweep_2026-08-26.json").read_text())
for j in GUEST["fresh"]:
    RAW.setdefault("_guest", []).append([j["source_id"],
        f'{j["title"]} | {j["company"]} | {j["location"]} | posted {j["posted_rel"]}'])

def parse_card(text):
    # logged-in slice format: "<id>\"> Title Company Loc ..."; guest: "T | C | L | note"
    if "|" in text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) < 3:
            return None
        return parts[0], parts[1], parts[2], parts[3:]
    m = re.match(r'^(\d+)\\?"?>\s*(.*)$', text)
    body = m.group(2) if m else text
    return body, None, None, [body]  # parsed structurally below

jobs = {}
for q, cards in RAW.items():
    for cid, text in cards:
        if "|" in text:
            p = parse_card(text)
            t, co, loc, notes = p
        else:
            body = re.sub(r'^\d+\\?"?>\s*', "", text)
            toks = body.split(" ")
            notes_all = body
            # title/company/location extraction: use known patterns — company is the
            # token run right before a location clause "(City, ST..." or "City, ST"
            locm = re.search(r"([A-Z][A-Za-z .'-]+,\s*(?:[A-Z]{2}|United States|New York City Metropolitan Area|San Diego Metropolitan Area)[^A-Z]*(?:\(On-site\)|\(Hybrid\)|\(Remote\))?)", body)
            loc = locm.group(1).strip() if locm else ""
            pre = body[:locm.start()].strip() if locm else body
            # salary/benefit/alumni tails are notes, not title/company
            nm = re.search(r"(\$(?:[\d.,]+K?\/(?:yr|hr)).*|(?:(?:[\d+,]+\s+)?(?:company |school )?(?:alumni|connections?)\s+(?:alumni\s+)?works?\s+here|Actively reviewing.*|Be an early applicant.*)|(?:Medical|401\(k\)|Vision|Dental).*)$", pre)
            notes = [nm.group(1)] if nm else []
            core = pre[:nm.start()].strip() if nm else pre
            words = core.split(" ")
            if len(words) < 3:
                continue
            # heuristics: company = last 1-3 tokens; take last 2 as company fallback
            title = " ".join(words[:-2]) or " ".join(words[:-1])
            company = " ".join(words[-2:])
            known = ["OpenAI","DoorDash","Anthropic","NVIDIA","Datadog","Atlassian","Booz Allen Hamilton",
                     "Google","Microsoft","AMD","Qualcomm","Roku","TSMC","TikTok","Charles River Analytics",
                     "Archetype AI","Fonzi AI","Haystack","The Nuclear Company","AAA Global"]
            matched_co = next((c for c in known if core.endswith(c)), None)
            if matched_co:
                company = matched_co
                title = core[: -len(matched_co)].strip()
            t, co = title, company
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

GATE_TITLES = [
    (r"\bintern\b|internship|co-op|new grad|new-grad|graduate|campus|university|early career|2027 start|all levels", "G3 early-career"),
    (r"\b(director|vp\b|head of|chief|principal)\b", "G2 seniority"),
]
UNRELATED = r"lecturer|professor|ai trainer|red team analyst|forensic|incident responder|threat researcher|vulnerability researcher|splunk|edi edifecs|vision data specialist|technical solutions engineer|construction|nuclear"

accepted, gated, dupes, rejected = [], [], [], []
gated_rows = []
for sid, (title, company, loc, notes) in sorted(jobs.items()):
    tl = (title or "").lower()
    gate = next((g for pat, g in GATE_TITLES if re.search(pat, tl)), None)
    notestr = " ".join(notes)
    pay = re.search(r"\$(\d+)(?:\.(\d+))?K/yr(?:\s*-\s*\$(\d+)(?:\.(\d+))?K/yr)?", notestr)
    hourly = "/hr" in notestr and "/yr" not in notestr
    if not gate and pay:
        lo = float(pay.group(1))
        hi = float(pay.group(3)) if pay.group(3) else lo
        if hi < 150:
            gate = "G4 pay<150k"
    if not gate and re.search(UNRELATED, tl):
        gate = "G5 unrelated"
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": loc, "source": "linkedin", "source_id": sid,
        "date_posted": "", "notes": ("linkedin cron sweep 2026-08-26 past-week/24h US guest-api+logged-in; "
            + "; ".join(notes)[:300] + ((" ; GATE:" + gate) if gate else "")),
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
        gated.append((row["job_id"], gate))
        gated_rows.append(row)
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

if accepted or gated_rows:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted + gated_rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

run_id = f"li_cron_20260826_{now.strftime('%H%M')}"
cards_total = sum(len(c) for c in RAW.values()) + GUEST.get("per_query", {}).get("_", {}).get("cards", 0)
queries_summary = "; ".join(f"{q}:{len(c)}" for q, c in RAW.items()) + \
    f"; guest-api:{sum(v['cards'] for v in GUEST['per_query'].values())} cards/{len(GUEST['fresh'])} fresh"
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f'{run_id},{now.strftime("%Y-%m-%dT%H:%M")},linkedin_guest_api+loggedin_browser,'
            f'8 guest queries x 1 page (past-week US) + 4 logged-in queries (past-24h US),{cards_total},'
            f'{len(jobs)},{len(accepted)} new,{len(gated)} gated,{len(dupes)} dup,{len(rejected)} rej;'
            f' queries: {queries_summary}\r\n')

print(json.dumps({
    "unique_ids": len(jobs), "new_open": len(accepted), "gated_skip": len(gated),
    "dupes": len(dupes), "rejected_by_scrutinize": len(rejected),
    "new_jobs": [(r["job_id"], r["title"], r["company"], r["location"]) for r in accepted],
    "gated_detail": gated,
    "rejected_detail": rejected[:20],
}, indent=1))
