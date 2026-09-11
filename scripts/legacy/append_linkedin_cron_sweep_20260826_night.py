#!/usr/bin/env python3
"""Ingest 2026-08-26 cron LinkedIn sweep #2 (guest API 8 queries + logged-in
fetch 5 queries, past-week US) through discovery_lib; gates G1-G6 per
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
for p in ["_li_loggedin_cron_b1_20260826.json", "_li_loggedin_cron_b2_20260826.json"]:
    for kw, cards in json.loads((REPO / "scripts" / p).read_text()):
        RAW.setdefault(kw, {}).update(cards)
GUEST = json.loads((REPO / "execution_results/linkedin_sweep_2026-08-26.json").read_text())
for j in GUEST["fresh"]:
    RAW.setdefault("_guest", {})[j["source_id"]] = (
        f'{j["title"]} {j["company"]} {j["location"]} posted {j["posted_rel"]}')

LOC_RE = re.compile(r"([A-Za-z][A-Za-z .'-]*,\s*(?:[A-Z]{2}|United States|DC)[^A-Z]*?(?:\(On-site\)|\(Hybrid\)|\(Remote\))?)")
KNOWN = ["Google DeepMind","Toyota Research Institute","Booz Allen Hamilton","Dolby Laboratories",
    "JPMorganChase","Bosch USA","Scout Motors Inc.","Stealth Startup","Bain & Company","Scale AI",
    "OpenAI","Zoom","Cisco","Baseten","Qualcomm","Percepta","Magic","NVIDIA","Cartesia","Console",
    "Peraton Labs","Anthropic","Intuit","webAI","WisdomAI","Lenovo","Liquid AI","Salesforce",
    "TikTok","Microsoft","ByteDance","Fireworks AI","OJ Digital","Xcede","Capgemini","Aisle",
    "Tessera Labs","Cohere","Faire","Fonzi AI","Ema","DoorDash","Innodata Inc.","Nordstrom",
    "EarnIn","Abridge","General Motors","NextGen Federal Systems","Luxoft","IBM",
    "BayOne Solutions","Handshake","Yara AI","Air"]

def parse_card(text):
    body = re.sub(r'^[\\"]*componentkey=[\\"]*job-card-component-ref-\d+[\\"]*>\s*', "", text)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    cut = re.search(r"(?:Posted|Viewed|Saved|Are these results|Be an early applicant|Actively reviewing|· Apply)", body)
    head = body[: cut.start()].strip() if cut else body
    nm = re.search(
        r"(\$[\d.,]+K/yr.*|\$\d+/hr.*|\d+\s+(?:company |school )?(?:alumni|connections?)\s+(?:alumni\s+)?works?\s+here.*"
        r"|(?:(?:Medical, )?Vision,? ?Dental|401\(k\)|Medical\b).*|\d+\s+\d*\+?\s*benefits?\b.*)$", head)
    notes = [nm.group(1).strip()] if nm else []
    core = (head[: nm.start()].strip() if nm else head).strip(" •,-")
    GEO = r"\s+((?:[A-Za-z][A-Za-z .,'-]*?)?(?:[A-Z]{2}\b|United States\b|Bay Area\b|Metropolitan Area\b))(?:\s*\((?:On-site|Hybrid|Remote)\))?\s*$"
    best = None
    geo_body = GEO[len(r"\s+"):]
    for c in KNOWN:
        idx = core.rfind(c)
        if idx < 0:
            continue
        m = re.fullmatch(re.escape(c) + r"\s+" + geo_body, core[idx:])
        if m and (best is None or idx > best[0]):
            best = (idx, c, m.group(1))
    if best is None:
        # also try company immediately followed by paren-tag-only location
        for c in KNOWN:
            m = re.search(re.escape(c) + r"\s+(\((?:On-site|Hybrid|Remote)\))\s*$", core)
            if m:
                best = (m.start(), c, m.group(1)); break
    if best is not None:
        _, co, loc = best
        title = core[: best[0]].strip(" -,–—")
    else:
        words = core.split(" ")
        if len(words) < 3:
            return None
        cand2 = " ".join(words[-2:])
        if re.match(r"^[A-Z][A-Za-z&.]*(?: [A-Z][A-Za-z&.]*)?$", words[-1]) and "(" not in cand2 and "/" not in cand2 and "," not in cand2:
            co, title, loc = cand2, " ".join(words[:-2]), ""
        else:
            co, title, loc = words[-1], " ".join(words[:-1]), ""
    return title, co, loc, notes

jobs = {}
for q, cards in RAW.items():
    for cid, text in cards.items():
        p = parse_card(text) if "_guest" not in cid else None
        if p is None:
            # guest format: "T | C | L | note" or plain text fallback
            if "|" in text:
                parts = [x.strip() for x in text.split("|") if x.strip()]
                if len(parts) >= 3:
                    p = (parts[0], parts[1], parts[2], parts[3:])
            else:
                p = parse_card(f'componentkey="job-card-component-ref-{cid}"> ' + text)
        if not p:
            continue
        prev = jobs.get(cid)
        if prev is None or len(p[3]) > len(prev[3]):
            jobs[cid] = p

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
    (r"\bintern\b|internship|co-op|new grad|new-grad|graduate|campus|university|early career", "G3 early-career"),
    (r"\b(director|vp\b|head of|chief|principal)\b|\blead,|\bmanager\b", "G2 seniority"),
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
    if not gate and hourly:
        gate = "G4 pay<150k(hourly)"
    if not gate and pay:
        lo = float(pay.group(1)) + (float(pay.group(2) or 0) / 10)
        hi = float(pay.group(3) or 0) + (float(pay.group(4) or 0) / 10) if pay.group(3) else lo
        if hi < 150:
            gate = "G4 pay<150k"
    if not gate and re.search(UNRELATED, tl):
        gate = "G5 unrelated"
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{sid}/",
        "location": loc, "source": "linkedin", "source_id": sid,
        "date_posted": "",
        "notes": ("linkedin cron sweep 2026-08-26 past-week US logged-in+guest; "
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
        nurow = {"gate": gate, "date_discovered": now.strftime("%Y-%m-%d"),
                 **{k: row.get(k, "") for k in NU_FIELDS}}
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

run_id = f"li_cron_20260826_{now.strftime('%H%M')}b"
cards_total = sum(len(c) for c in RAW.values()) + sum(v["cards"] for v in GUEST["per_query"].values())
queries_summary = "; ".join(f"{q}:{len(c)}" for q, c in RAW.items() if q != "_guest") + \
    f"; guest-api:{cards_total - sum(len(c) for q, c in RAW.items() if q != '_guest')} cards/{len(GUEST['fresh'])} fresh"
with open(RUNS_CSV, "a", newline="") as f:
    f.write(f'{run_id},{now.strftime("%Y-%m-%dT%H:%M")},linkedin_guest_api+loggedin_browser,'
            f'8 guest queries + 5 logged-in queries (past-week US),{cards_total},'
            f'{len(jobs)},{len(accepted)} new,{len(gated)} gated,{len(dupes)} dup,{len(rejected)} rej;'
            f' queries: {queries_summary}\r\n')

print(json.dumps({
    "unique_ids": len(jobs), "new_open": len(accepted), "gated_skip": len(gated),
    "dupes": len(dupes), "rejected_by_scrutinize": len(rejected),
    "new_jobs": [(r["job_id"], r["title"], r["company"], r["location"]) for r in accepted],
    "gated_detail": gated,
    "rejected_detail": rejected[:20],
}, indent=1))
