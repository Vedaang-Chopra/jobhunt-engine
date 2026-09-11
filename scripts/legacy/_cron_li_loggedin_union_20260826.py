#!/usr/bin/env python3
"""2026-08-26 cron sweep: logged-in union IDs -> find new vs jobs.csv,
fetch details via guest jobPosting endpoint, save incrementally."""
import csv, html as H, json, re, sys, time, urllib.request
from pathlib import Path

REPO = Path("/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting")
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import config_lib
except ImportError:
    import config_lib
JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
OUT = REPO / "execution_results" / "linkedin_loggedin_new_2026-08-26.json"

# id -> [title, connections-signal]
UNION = {
 "4456298713": ["Research Engineer", ""],
 "4456253930": ["Research Engineer, Winslow, DeepMind", "10 connections work here"],
 "4436894755": ["Research Engineer / Research Scientist - Personal AGI, Personality and Model Behavior", ""],
 "4456297705": ["Research Engineer", ""],
 "4456214401": ["Research Engineer, Gemini Code Post-training, DeepMind", "10 connections work here"],
 "4437046937": ["AI Researcher, On-Device LLM Efficiency", "12 connections work here"],
 "4438603830": ["Applied AI Scientist", ""],
 "4438613253": ["Applied AI Scientist", ""],
 "4448246875": ["Research Engineer / Research Scientist - Personal AGI, Memory", ""],
 "4443668490": ["ML Systems Research Engineer, RL / Inference / Agent Systems", ""],
 "4322290299": ["Research Engineer/Research Scientist, Pre-training", "2 connections work here"],
 "4387756113": ["Research Engineer", "13 connections work here"],
 "4438206154": ["AI Scientist 2", "2 connections work here"],
 "4447720275": ["Frontier Agents Engineer (Applied AI)", ""],
 "4409981292": ["Research Engineer, Knowledge Team", "2 connections work here"],
 "4429652864": ["Machine Learning Researcher", "12 connections work here"],
 "4435916615": ["Research Engineer/ Applied Scientist", ""],
 "4437084478": ["Advisory AI Prototyping Engineer", ""],
 "4430405218": ["Research Engineer", ""],
 "4389311565": ["AI/ML Research Scientist - Agentic Systems", ""],
 "4410781418": ["Machine Learning Research Engineer", "3 connections work here"],
 "4355681487": ["Research Engineer, Monetization AI", ""],
 "4322223560": ["Member of Technical Staff (AI Researcher)", ""],
 "4399734283": ["Research Scientist - LLM", ""],
 "4440777564": ["AI Modeling Specialist Engineer", ""],
 "4455905006": ["Applied Scientist, Conversational Assistant Modeling and Learning", ""],
 "4457337487": ["Applied Researcher II (AI Foundations)", "18 connections work here"],
 "4446546683": ["Applied Scientist, Reinforcement Learning (Mid, Senior, Staff)", "4 connections work here"],
 "4458112360": ["Applied Researcher II (AI Foundations, LLM Core and Agentic AI)", "18 connections work here"],
 "4456256807": ["Research Scientist, Generative AI - Seattle", ""],
 "4322400090": ["Research Engineer/Research Scientist, Pre-training", "2 connections work here"],
 "4434583387": ["Forward Deployed AI Research Scientist", ""],
 "4430762460": ["Senior AI Research Scientist", ""],
 "4454677239": ["Applied AI Scientist - Hybrid", ""],
 "4453804455": ["Research Scientist- Vision-Language-Action (VLA) Models", ""],
 "4455911793": ["Applied scientist, Agentic AI, AWS Agentic AI", "35 connections work here"],
 "4455972884": ["Member of Technical Staff - Post Training", ""],
 "4456414109": ["Member of Technical Staff, Evals & Post-Training Product", ""],
 "4441205777": ["Lead, AI Engineering", ""],
 "4441218161": ["Lead, AI Engineering", ""],
 "4444193196": ["Senior Language Engineer", ""],
 "4437412135": ["Member of Technical Staff - RL Inference", ""],
 "4420164179": ["AI Systems, Language & Reasoning Models", ""],
 "4410871057": ["Research Engineer, Training & Inference", ""],
 "4457390974": ["AWS Agentic AI Platform Engineer", ""],
 "4436253202": ["Research Engineer, Post-Training Inference", ""],
 "4457517821": ["Research Scientist", ""],
 "4420681241": ["Agentic AI Machine Learning Engineer", ""],
 "4418852774": ["Applied AI Engineer, Codex Core Agent", ""],
 "4317542784": ["Researcher, Post Training", ""],
 "4437900104": ["LLM Platform Engineer", ""],
 "4399721103": ["Research Engineer, Mid-Training", ""],
 "4437900105": ["LLM Platform Engineer", ""],
 "4430001901": ["Research Engineer, Domain Scaling", "2 connections work here"],
 "4446845111": ["Software Engineer, AI Research & Prototyping", ""],
 "4430022049": ["Research Engineer, Domain Scaling", "2 connections work here"],
 "4453856072": ["Senior LLM Engineer", ""],
 "4447581691": ["Engineer 2: AI Agentic Solutions (Hybrid - Seattle, WA)", ""],
 "4445150639": ["GenAI / Agentic AI Developer", "2 connections work here"],
 "4447719279": ["Frontier Agents Engineer (Applied AI)", ""],
 "3813454490": ["Research Engineer, Post-Training (All Industry Levels)", ""],
 "4455796592": ["Machine Learning Engineer II , AGI Customization", ""],
 "4455023096": ["AI Systems Builder (Impact-Driven) [33169]", ""],
 "4441215194": ["Lead, AI Engineering", ""],
 "4456111728": ["AI Software Engineer II", ""],
 "4454133418": ["Senior AI Engineer - Agentic Systems", ""],
 "4429937252": ["Integration Engineer II - AI and Python Developer", "5 connections work here"],
 "4401181867": ["Solutions Architect - AI Model Specialist", ""],
 "4447233543": ["Applied AI Engineer II", "5 connections work here"],
 "4447617231": ["Forward Deployed Engineer, Agentic Platform", ""],
 "4403252857": ["AI Engineer", ""],
 "4420665760": ["Agentic AI Machine Learning Engineer", ""],
 "4452862947": ["AI Research Engineer – Agentic AI", ""],
 "4436878764": ["GenAI / Agentic AI Developer", ""],
 "4430703007": ["AI Builder", ""],
 "4399791760": ["AI Agent Engineer", ""],
 "4454134392": ["Senior AI Engineer - Agentic Systems", ""],
 "4456316716": ["AI Agent Engineer", ""],
 "4446557716": ["Software Engineer, Generative AI", ""],
 "4428886430": ["Application/Agentic AI Engineer", ""],
 "4455826017": ["AI & LLM Applications Scientist", ""],
 "4418514625": ["Senior Applied Scientist", "13 connections work here"],
 "4455901482": ["Applied Scientist, Ring AI", ""],
 "4455796387": ["Applied Scientist, SPX AI Lab", ""],
 "4411293048": ["Senior Applied Scientist", ""],
 "4411609385": ["Senior Applied Scientist", "38 connections work here"],
 "4437911859": ["Applied Scientist", "13 connections work here"],
 "4455914308": ["Applied Scientist, AGI Customization Services", ""],
 "4446586470": ["Senior Applied Scientist", "38 connections work here"],
 "4441205776": ["Lead, AI Engineering", ""],
 "4441217184": ["Lead, AI Engineering", ""],
 "4414911374": ["Software Engineer, AI - Dunkirk / Buffalo NY", ""],
 "4317544242": ["Researcher, Evals", ""],
 "4317703639": ["Senior Research Scientist, Model Evaluation", ""],
 "4456266162": ["Senior Research Engineer, Agentic Data and Tooling, DeepMind", "10 connections work here"],
 "4437905316": ["Research Engineer, Model Evaluations", "2 connections work here"],
 "4317709468": ["Senior Research Scientist, Model Evaluation", ""],
 "4438368908": ["Senior Research Engineer - Enterprise Products", "58 connections work here"],
 "4409674119": ["Research Engineer, Pre-training Data - MSL FAIR", ""],
 "4447214228": ["Senior Applied Scientist", ""],
 "4456054475": ["Senior Software Engineer, Agent Simulation and Evaluation", "58 connections work here"],
}

existing = set()
with open(JOBS_CSV, newline="") as f:
    for row in csv.DictReader(f):
        existing.add(str(row.get("source_id", "")).strip())
new_ids = [i for i in UNION if i not in existing]
print(f"union={len(UNION)} already_tracked={len(UNION)-len(new_ids)} new_candidates={len(new_ids)}")

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

def clean(s):
    return H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or ""))).strip()

def detail(jid):
    url = f"https://www.linkedin.com/jobs/guest/jobs/api/jobPosting/{jid}"
    req = urllib.request.Request(url, headers=HEADERS)
    body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    comp = re.search(r'<h4[^>]*>\s*(.*?)\s*</h4>', body, re.S) or \
           re.search(r'companyName":"(.*?)"', body)
    loc = re.search(r'job-search-card__location[^>]*>\s*(.*?)\s*<', body, re.S) or \
          re.search(r'"location":"(.*?)"', body)
    t = re.search(r'<time[^>]*datetime="([^"]+)"', body)
    title = re.search(r'<h2[^>]*>\s*(.*?)\s*</h2>', body, S := re.S) or \
            re.search(r'<title>\s*(.*?)\s*</title>', body, S)
    desc = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', body, re.S)
    return {
        "source_id": jid, "title": clean(title.group(1)) if title else "",
        "company": clean(comp.group(1)) if comp else "",
        "location": clean(loc.group(1)) if loc else "",
        "date_posted_raw": t.group(1)[:10] if t else "",
        "url": f"https://www.linkedin.com/jobs/view/{jid}/",
        "desc_chars": len(clean(desc.group(1))) if desc else 0,
    }

out, fails = [], []
for i, jid in enumerate(new_ids):
    try:
        d = detail(jid)
        d["connections_signal"] = UNION[jid][1]
        if not d["company"]:
            d["company_fallback_title"] = UNION[jid][0]
        out.append(d)
    except Exception as e:
        fails.append((jid, str(e)))
    if (i + 1) % 10 == 0:
        OUT.write_text(json.dumps({"new_details": out, "fails": fails}, indent=1))
        print(f"  saved {len(out)} after {i+1}")
    time.sleep(1.0)

OUT.write_text(json.dumps({"new_details": out, "fails": fails}, indent=1))
print(f"DONE details_ok={len(out)} fails={len(fails)}")
for j in out:
    print(f"{j['source_id']} | {j['company'][:30]} | {j['title'][:60]} | {j['location'][:40]}")
for fid, err in fails:
    print(f"FAIL {fid}: {err}")
