#!/usr/bin/env python3
import csv, json, re, html, hashlib, sys, shutil, time
from pathlib import Path
from datetime import date, datetime
from urllib.request import Request, urlopen
REPO=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO/'scripts'))
from scripts import config_lib
from scripts.discovery_lib import normalize_job, DedupIndex, _CSV_COLUMNS
from scripts.linkedin_sweep_runner import fetch_jd, make_job_id, save_jd_file
JOBS=config_lib.path('jobs_csv'); RUNS=config_lib.path('search_runs_csv'); DATA=config_lib.data_root()
spill=Path('/home/vchopra/.hermes/profiles/job-hunt-fresh/cache/spillover/call_PNRwPtdpE4G2j24o26RW8Bc0.txt')
s=json.loads(spill.read_text()); result=s['result']; x=result.split('### Result\n',1)[1]; val,_=json.JSONDecoder().raw_decode(x); browser_data=json.loads(val)
# Merge guest and authenticated results, with guest metadata preferred.
merged={}
for q,v in browser_data.items():
    for j in v.get('guest',[])+v.get('logged',[]):
        sid=str(j.get('source_id','')).strip()
        title=html.unescape(str(j.get('title',''))).strip(); company=html.unescape(str(j.get('company',''))).strip()
        if not sid or not title or not company or len(title)<3 or len(company)<2: continue
        k=sid
        if k not in merged or (not merged[k].get('date_posted_raw') and j.get('date_posted_raw')): merged[k]={**j,'query':q}
# Existing dedup
existing=[]
if JOBS.exists():
    with JOBS.open(newline='') as f: existing=list(csv.DictReader(f))
idx=DedupIndex()
seen_sid=set(); seen_ct=set()
for r in existing:
    idx.add(r); seen_sid.add((r.get('source_id') or '').lower()); seen_ct.add(((r.get('company') or '').lower().strip(),(r.get('title') or '').lower().strip()))
accepted=[]; gated=[]; skipped_dupes=0; gate_counts={}
for j in merged.values():
    sid=j['source_id']; ct=(j['company'].lower().strip(),j['title'].lower().strip())
    if sid.lower() in seen_sid or ct in seen_ct: skipped_dupes+=1; continue
    jd=fetch_jd(j['url'],sid); time.sleep(.85)
    title=j['title']; desc=jd or ''
    gate=None
    # G2: only explicitly disallowed senior/management titles.
    if re.search(r'\b(director|vp|vice president|head of|chief|principal)\b',title,re.I) or re.search(r'\b(manager|people manager|engineering manager|research manager)\b',title,re.I): gate='G2'
    # G3 early-career signals, with conversion exception.
    elif re.search(r'\b(intern(ship)?|co[- ]?op|new[- ]?grad|early[- ]?career|junior|new graduate)\b',title+' '+desc,re.I) and not re.search(r'full[- ]time conversion|return offer|conversion to full[- ]time',desc,re.I): gate='G3'
    # G4 posted compensation below $150k; only reject if a lower bound is explicit.
    else:
        pays=[]
        for m in re.finditer(r'\$\s*([0-9]{2,3}(?:,[0-9]{3})?)\s*(?:-|to)\s*\$?\s*([0-9]{2,3}(?:,[0-9]{3})?)?\s*(k|K)?',desc):
            a=int(m.group(1).replace(',','')); b=int(m.group(2).replace(',','')) if m.group(2) else a
            if m.group(3): a*=1000; b*=1000
            pays.append((a,b))
        if pays and max(b for a,b in pays)<150000: gate='G4'
    # G5 clearly unrelated titles.
    if not gate and re.search(r'\b(frontend|front-end|sales|account executive|product manager|data analyst|hardware engineer|bioinformatics)\b',title,re.I): gate='G5'
    # G1 hard experience minimum, flexible equivalent language stays borderline.
    if not gate:
        for m in re.finditer(r'\b([5-9]|[1-9][0-9])\+?\s*(?:-|to\s+)?years?\b',desc,re.I):
            if not re.search(r'or equivalent|equivalent experience',desc[max(0,m.start()-80):m.end()+100],re.I): gate='G1'; break
    if not gate and not jd: gate='G6'
    if gate:
        gated.append((j,gate)); gate_counts[gate]=gate_counts.get(gate,0)+1; continue
    raw={'title':title,'company':j['company'],'url':j['url'],'location':j.get('location',''),'source':'linkedin','source_id':sid,'date_posted':j.get('date_posted_raw',''),'description':jd,'notes':f"sweep=linkedin_guest+logged_in_{date.today().isoformat()}; query={j.get('query','')}; alumni={j.get('alumni','')}"}
    try: row=normalize_job(raw)
    except Exception: continue
    dup,match=idx.seen_before(row)
    if dup: skipped_dupes+=1; continue
    row['job_id']=make_job_id('linkedin',j['company'],title,sid); row['source_id']=sid; row['source']='linkedin'
    if jd:
        row['full_description_hash']=hashlib.sha256(jd.encode()).hexdigest()[:16]; row['description_file']=save_jd_file(row['job_id'],jd)
    row['status']='open'; idx.add(row); seen_sid.add(sid.lower()); seen_ct.add(ct); accepted.append(row)
# Atomic-ish append with backup.
if accepted:
    backup=JOBS.with_suffix('.bak.'+datetime.now().strftime('%Y%m%d_%H%M%S')); shutil.copy2(JOBS,backup)
    fields=[]
    with JOBS.open(newline='') as f: fields=list(csv.DictReader(f).fieldnames or [])
    for c in _CSV_COLUMNS:
        if c not in fields: fields.append(c)
    with JOBS.open('a',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writerows([{c:r.get(c,'') for c in fields} for r in accepted])
RUNS.parent.mkdir(parents=True,exist_ok=True); exists=RUNS.exists()
with RUNS.open('a',newline='') as f:
    w=csv.writer(f)
    if not exists: w.writerow(['run_id','sources','notes','new_count'])
    rid='linkedin_'+date.today().isoformat()+'_'+datetime.now().strftime('%H%M%S')
    w.writerow([rid,'linkedin_guest_api+linkedin_logged_in_fetch',f'queries=8; unique_cards={len(merged)}; duplicates={skipped_dupes}; gated_out={len(gated)}; gates={gate_counts}; accepted={len(accepted)}',len(accepted)])
OUT=config_lib.path('execution_results_dir')/('linkedin_sweep_'+date.today().isoformat()+'.json'); OUT.write_text(json.dumps({'queries':list(browser_data),'summary':{'unique_cards':len(merged),'duplicates':skipped_dupes,'accepted':len(accepted),'gated_out':len(gated),'gate_counts':gate_counts,'run_id':rid}},indent=2))
print(json.dumps({'unique_cards':len(merged),'duplicates':skipped_dupes,'accepted':len(accepted),'gated_out':len(gated),'gate_counts':gate_counts,'run_id':rid,'jobs_csv':str(JOBS),'runs_csv':str(RUNS)}))
