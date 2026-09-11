#!/usr/bin/env python3
"""2026-08-26 cron ingest: logged-in LinkedIn sweep union -> normalize via
discovery_lib, dedupe against jobs.csv, append new rows, log search run.
Locations were not exposed by /jobs/view server HTML; recorded from the
search-level geoId=103644278 (United States) filter."""
import csv, json, shutil, sys
from datetime import datetime
from pathlib import Path

REPO = Path("/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting")
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib as dl, config_lib
except ImportError:
    import discovery_lib as dl
    import config_lib

DATA = config_lib.data_root()
JOBS_CSV = DATA / "tracking/jobs/jobs.csv"
RUNS_CSV = DATA / "tracking/search_runs/search_runs.csv"

# id -> (title_from_page, company_name, conn_signal)
JOBS = {
 "4436894755": ("Research Engineer / Research Scientist - Personal AGI, Personality and Model Behavior", "OpenAI", ""),
 "4448246875": ("Research Engineer / Research Scientist - Personal AGI, Memory", "OpenAI", ""),
 "4322290299": ("Research Engineer/Research Scientist, Pre-training", "Anthropic", "2 connections work here"),
 "4447720275": ("Frontier Agents Engineer (Applied AI)", "Scale AI", ""),
 "4409981292": ("Research Engineer, Knowledge Team", "Anthropic", "2 connections work here"),
 "4429652864": ("Machine Learning Researcher", "Qualcomm", "12 connections work here"),
 "4430405218": ("Research Engineer", "Sesame", ""),
 "4440777564": ("AI Modeling Specialist Engineer", "Lenovo", ""),
 "4457337487": ("Applied Researcher II (AI Foundations)", "Capital One", "18 connections work here"),
 "4446546683": ("Applied Scientist, Reinforcement Learning (Mid, Senior, Staff)", "Hippocratic AI", "4 connections work here"),
 "4458112360": ("Applied Researcher II (AI Foundations, LLM Core and Agentic AI)", "Capital One", "18 connections work here"),
 "4434583387": ("Forward Deployed AI Research Scientist", "AMD", ""),
 "4454677239": ("Applied AI Scientist - Hybrid", "XPO", ""),
 "4453804455": ("Research Scientist- Vision-Language-Action (VLA) Models", "Bosch USA", ""),
 "4455911793": ("Applied scientist, Agentic AI, AWS Agentic AI", "Amazon Web Services (AWS)", "35 connections work here"),
 "4455972884": ("Member of Technical Staff - Post Training", "Microsoft AI", ""),
 "4456414109": ("Member of Technical Staff, Evals & Post-Training Product", "Fireworks AI", ""),
 "4441205777": ("Lead, AI Engineering", "Bain & Company", ""),
 "4444193196": ("Senior Language Engineer", "Microsoft AI", ""),
 "4437412135": ("Member of Technical Staff - RL Inference", "SpaceXAI", ""),
 "4420164179": ("AI Systems, Language & Reasoning Models", "Unconventional AI", ""),
 "4457390974": ("AWS Agentic AI Platform Engineer", "Booz Allen Hamilton", ""),
 "4457517821": ("Research Scientist", "Zoom", ""),
 "4420681241": ("Agentic AI Machine Learning Engineer", "Booz Allen Hamilton", ""),
 "4317542784": ("Researcher, Post Training", "Cartesia", ""),
 "4399721103": ("Research Engineer, Mid-Training", "Cognition", ""),
 "4437900105": ("LLM Platform Engineer", "Whatnot", ""),
 "4430001901": ("Research Engineer, Domain Scaling", "Anthropic", "2 connections work here"),
 "4446845111": ("Software Engineer, AI Research & Prototyping", "Sage Care", ""),
 "4430022049": ("Research Engineer, Domain Scaling", "Anthropic", "2 connections work here"),
 "4453856072": ("Senior LLM Engineer", "Molex", ""),
 "4447581691": ("Engineer 2: AI Agentic Solutions (Hybrid - Seattle, WA)", "Nordstrom", ""),
 "4447719279": ("Frontier Agents Engineer (Applied AI)", "Scale AI", ""),
 "4455796592": ("Machine Learning Engineer II , AGI Customization", "Amazon", ""),
 "4455023096": ("AI Systems Builder (Impact-Driven) [33169]", "Stealth Startup", ""),
 "4441215194": ("Lead, AI Engineering", "Bain & Company", ""),
 "4456111728": ("AI Software Engineer II", "Relativity Space", ""),
 "4454133418": ("Senior AI Engineer - Agentic Systems", "IBM", ""),
 "4429937252": ("Integration Engineer II - AI and Python Developer", "Deloitte", "5 connections work here"),
 "4401181867": ("Solutions Architect - AI Model Specialist", "FriendliAI", ""),
 "4447233543": ("Applied AI Engineer II", "Deloitte", "5 connections work here"),
 "4447617231": ("Forward Deployed Engineer, Agentic Platform", "Cohere", ""),
 "4403252857": ("AI Engineer", "Gamma", ""),
 "4420665760": ("Agentic AI Machine Learning Engineer", "Booz Allen Hamilton", ""),
 "4452862947": ("AI Research Engineer – Agentic AI", "Bosch USA", ""),
 "4436878764": ("GenAI / Agentic AI Developer", "Capgemini", ""),
 "4430703007": ("AI Builder", "EarnIn", ""),
 "4399791760": ("AI Agent Engineer", "General Motors", ""),
 "4454134392": ("Senior AI Engineer - Agentic Systems", "IBM", ""),
 "4456316716": ("AI Agent Engineer", "NTT DATA North America", ""),
 "4446557716": ("Software Engineer, Generative AI", "Abridge", ""),
 "4428886430": ("Application/Agentic AI Engineer", "NextGen Federal Systems", ""),
 "4455826017": ("AI & LLM Applications Scientist", "InVitro Cell Research, LLC", ""),
 "4418514625": ("Senior Applied Scientist", "Adobe", "13 connections work here"),
 "4455901482": ("Applied Scientist, Ring AI", "Ring", ""),
 "4455796387": ("Applied Scientist, SPX AI Lab", "Amazon", ""),
 "4411293048": ("Senior Applied Scientist", "Microsoft AI", ""),
 "4411609385": ("Senior Applied Scientist", "Microsoft", "38 connections work here"),
 "4437911859": ("Applied Scientist", "Adobe", "13 connections work here"),
 "4455914308": ("Applied Scientist, AGI Customization Services", "Amazon", ""),
 "4446586470": ("Senior Applied Scientist", "Microsoft", "38 connections work here"),
 "4441205776": ("Lead, AI Engineering", "Bain & Company", ""),
 "4441217184": ("Lead, AI Engineering", "Bain & Company", ""),
 "4414911374": ("Software Engineer, AI - Dunkirk / Buffalo NY", "ImmunityBio, Inc.", ""),
 "4317544242": ("Researcher, Evals", "Cartesia", ""),
 "4317703639": ("Senior Research Scientist, Model Evaluation", "Cohere", ""),
 "4456266162": ("Senior Research Engineer, Agentic Data and Tooling, DeepMind", "Google DeepMind", "10 connections work here"),
 "4437905316": ("Research Engineer, Model Evaluations", "Anthropic", "2 connections work here"),
 "4317709468": ("Senior Research Scientist, Model Evaluation", "Cohere", ""),
 "4438368908": ("Senior Research Engineer - Enterprise Products", "NVIDIA", "58 connections work here"),
 "4409674119": ("Research Engineer, Pre-training Data - MSL FAIR", "Meta", ""),
 "4447214228": ("Senior Applied Scientist", "Oracle", ""),
}

with open(JOBS_CSV, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)

tracked = {str(r.get("source_id", "")).strip() for r in existing}
new_ids = [i for i in JOBS if i not in tracked]
print(f"sweep_union={len(JOBS)} already_tracked={len(JOBS)-len(new_ids)} candidates={len(new_ids)}")

bak = JOBS_CSV.with_suffix(".csv.bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
shutil.copy2(JOBS_CSV, bak)

idx = dl.DedupIndex()
for row in existing:
    idx.add(row)

accepted, dupes, rejected = [], [], []
for jid in new_ids:
    title, company, conn = JOBS[jid]
    raw = {
        "title": title, "company": company,
        "url": f"https://www.linkedin.com/jobs/view/{jid}/",
        "location": "United States",
        "source": "linkedin", "source_id": jid,
        "date_posted": "",
        "notes": f"linkedin logged-in sweep 2026-08-26 past-week US (geoId=103644278); location from search geo-filter"
                 + (f"; {conn}" if conn else ""),
    }
    if conn:
        raw["matching_strengths"] = conn
    row = dl.normalize_job(raw)
    row["job_id"] = f"{row['company_slug']}_{dl.slugify(row['title'])}_{jid}"
    is_dup, matched = idx.seen_before(row)
    if is_dup:
        dupes.append((jid, title[:50], matched.get("job_id", "?")))
        continue
    verdict, flags = dl.scrutinize(row)
    if verdict != "accept":
        rejected.append((jid, title[:50], flags))
        continue
    idx.add(row)
    accepted.append(row)

if accepted:
    with open(JOBS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in accepted:
            w.writerow({k: row.get(k, "") for k in fieldnames})

now = datetime.now().strftime("%Y-%m-%dT%H:%M")
run_id = f"li_loggedin_20260826_{datetime.now().strftime('%H%M')}"
with open(RUNS_CSV, "a", newline="") as f:
    w = csv.writer(f)
    if f.tell() == 0:
        w.writerow(["run_id", "date", "sources", "queries", "total_scanned",
                    "new_jobs_found", "duplicates_skipped", "strong_fits", "notes"])
    w.writerow([run_id, now, "linkedin_loggedin+guest_api",
                "8 profile-guided queries x both endpoints (past-week US)",
                len(JOBS), len(accepted), len(dupes),
                sum(1 for r in accepted if r.get("matching_strengths")),
                f"{len(rejected)} rejected (seniority/location); guest detail API 404 -> logged-in /jobs/view fetch used"])

print(json.dumps({
    "new_accepted": len(accepted), "dupes": len(dupes), "rejected": len(rejected),
    "jobs": [{"job_id": r["job_id"], "title": r.get("title"), "company": r.get("company"),
              "conn": r.get("matching_strengths", ""), "url": r.get("url")} for r in accepted],
}, indent=1))
