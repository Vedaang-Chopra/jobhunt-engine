#!/usr/bin/env python3
import csv, json, re, hashlib
from datetime import date, datetime
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO/'scripts'))
from scripts import config_lib, discovery_lib
raw_path=REPO/'execution_results/linkedin_browser_raw_2026-09-15.json'
raw=json.loads(raw_path.read_text()); raw=json.loads(raw) if isinstance(raw,str) else raw
data_root=config_lib.data_root(); jobs_csv=data_root/'tracking/jobs/jobs.csv'; runs_csv=config_lib.path('search_runs_csv')
with jobs_csv.open(newline='',encoding='utf-8') as f:
    rows=list(csv.DictReader(f)); header=list(rows[0].keys()) if rows else discovery_lib._CSV_COLUMNS
seen_sid=set(); seen_pair=set()
for r in rows:
    for s in (r.get('source_id',''), r.get('job_id','')):
        if s: seen_sid.add(s.lower())
    if r.get('company') and r.get('title'):
        seen_pair.add((r['company'].lower().strip(),r['title'].lower().strip()))

def gates(j):
    t=j.get('title',''); low=t.lower(); flags=[]
    if re.search(r'\b(director|vice president|vp|head|chief|principal)\b',t,re.I): flags.append('G2_seniority_title')
    if re.search(r'\b(intern|internship|co[- ]?op|new grad|new graduate|early career|university program|campus)\b',t,re.I): flags.append('G3_early_career')
    if re.search(r'\b(frontend|front-end|product manager|data analyst|hardware|bioinformatics|sales|marketing|devops|sre|qa|support|recruiter|account executive)\b',t,re.I): flags.append('G5_profile_fit')
    return flags
new=[]; gated=[]; dup=0; rejected=0
for j in raw.get('jobs',{}).values():
    sid=str(j.get('source_id','')).strip(); pair=(j.get('company','').strip().lower(),j.get('title','').strip().lower())
    if not sid or sid.lower() in seen_sid or pair in seen_pair:
        dup+=1; continue
    flags=gates(j)
    if flags:
        gated.append({'source_id':sid,'company':j.get('company',''),'title':j.get('title',''),'flags':flags}); seen_sid.add(sid.lower()); seen_pair.add(pair); continue
    row=discovery_lib.normalize_job({'title':j['title'],'company':j['company'],'url':j['url'],'location':j.get('location',''),'source':'linkedin','source_id':sid,'date_posted':'','notes':f"LinkedIn browser sweep query={j.get('query','')}; JD not fetched in bounded sweep"})
    row['job_id']=f"linkedin_{discovery_lib.slugify(j['company'])}_{discovery_lib.slugify(j['title'])}_{sid}"
    row['status']='open'; row['recommended_action']=''; row['date_discovered']=date.today().isoformat(); row['last_checked']=date.today().isoformat(); row['last_verified']=date.today().isoformat(); row['missing_info']='JD not fetched; salary/experience gates not observable from search card'
    new.append(row); seen_sid.add(sid.lower()); seen_pair.add(pair)
if new:
    with jobs_csv.open('a',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=header); [w.writerow({k:r.get(k,'') for k in header}) for r in new]
queries=raw.get('queries',{}); scanned=sum(ep.get('count',0) for vals in queries.values() for ep in vals)
run_id=f"linkedin_browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
notes=f"Playwright MCP one-tab sweep; guest+logged_in attempted; 8 queries; gated_out={len(gated)}; gate_details="+'; '.join(f"{x['company']}|{x['title']}:{','.join(x['flags'])}" for x in gated[:50])
with runs_csv.open('a',newline='',encoding='utf-8') as f:
    csv.writer(f).writerow([run_id,date.today().isoformat(),'linkedin_browser_guest+logged_in','; '.join(f"{q}:{sum(e.get('count',0) for e in v)}" for q,v in queries.items()),scanned,len(new),dup,'',notes])
out=REPO/'execution_results'/f"linkedin_browser_sweep_{date.today().isoformat()}.json"
out.write_text(json.dumps({'scanned':scanned,'new':len(new),'duplicates_skipped':dup,'gated_out':len(gated),'gated':gated,'new_jobs':[{'job_id':r['job_id'],'company':r['company'],'title':r['title']} for r in new],'blocked':raw.get('blocked',False),'query_stats':queries},indent=2))
print(f"SCANNED={scanned} NEW={len(new)} DUPS={dup} GATED_OUT={len(gated)} BLOCKED={raw.get('blocked',False)}")
print(f"RUN_ID={run_id}")
print(f"OUTPUT={out}")
for r in new: print(f"NEW {r['company']} | {r['title']} | {r['location']}")
for r in gated: print(f"GATED {r['company']} | {r['title']} | {','.join(r['flags'])}")
