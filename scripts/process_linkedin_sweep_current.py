#!/usr/bin/env python3
import csv, json, re
from pathlib import Path
from datetime import date
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from discovery_lib import normalize_job, scrutinize
import config_lib
root=Path(config_lib.data_root())
out=root/'execution_results'/f'linkedin_sweep_{date.today().isoformat()}.json'
jobs=root/'tracking/jobs/jobs.csv'
runs=root/'tracking/search_runs/search_runs.csv'
data=json.loads(out.read_text())
with jobs.open(newline='') as f:
    reader=csv.DictReader(f); fields=reader.fieldnames; existing=list(reader)
source_ids={r.get('source_id','').strip().lower() for r in existing if r.get('source_id')}
namekeys={(r.get('company','').strip().lower(), re.sub(r'\s+',' ',r.get('title','').strip().lower())) for r in existing}
new=[]; gated=0; gate_counts={}; dup=0
for j in data.get('fresh',[]):
    raw={'title':j['title'],'company':j['company'],'url':j['url'],'location':j.get('location',''),'date_posted':j.get('date_posted_raw',''),'source_id':j.get('source_id',''),'source':'linkedin'}
    row=normalize_job(raw); row['date_discovered']=date.today().isoformat(); row['status']='open'; row['source']='linkedin'; row['source_id']=j.get('source_id','')
    flags=[]
    # Explicit hard gates required by ROLE_FIT_RULES G2/G3; G1/G4 need JD/pay evidence unavailable in guest cards.
    if re.search(r'\b(director|vp|vice president|head|chief|principal|manager)\b', row['title'], re.I): flags.append('G2')
    if re.search(r'\b(intern(ship)?|new grad|new graduate|early career)\b', row['title'], re.I): flags.append('G3')
    verdict, libflags=scrutinize(row)
    if verdict=='reject':
        if 'location_not_supported' in libflags: flags.append('G5')
        if 'seniority_bar' in libflags: flags.append('G2')
        if 'internship_no_conversion' in libflags: flags.append('G3')
    flags=list(dict.fromkeys(flags))
    if flags:
        row['recommended_action']='SKIP'; row['notes']='gated:'+','.join(flags); row['status']='open'; gated+=1
        for f in flags: gate_counts[f]=gate_counts.get(f,0)+1
    sid=str(row.get('source_id','')).lower(); key=(row['company'].lower(), re.sub(r'\s+',' ',row['title'].lower()))
    if sid in source_ids or key in namekeys:
        dup+=1; continue
    source_ids.add(sid); namekeys.add(key); new.append({k:row.get(k,'') for k in fields})
if new:
    with jobs.open('a',newline='') as f:
        csv.DictWriter(f,fieldnames=fields).writerows(new)
with runs.open('a',newline='') as f:
    csv.writer(f).writerow([date.today().isoformat(),'linkedin_guest_sweep',len(data.get('fresh',[])),len(new),gated,'completed_guest_only_mcp_unavailable'])
print(json.dumps({'fresh':len(data.get('fresh',[])),'new_rows':len(new),'gated_out':gated,'gate_counts':gate_counts,'duplicates':dup,'output':str(out),'jobs_csv':str(jobs)},sort_keys=True))
for r in new: print(f"+ {r['title']} @ {r['company']} [{r['location']}] action={r.get('recommended_action','') or 'OPEN_UNSCORED'}")
