import csv,json,re,sys
from pathlib import Path
REPO=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(REPO/'scripts'))
from scripts import config_lib
from scripts.linkedin_browser_sweep import apply_eligibility_gates
raw=json.load(open(REPO/'execution_results/linkedin_new_jds_2026-09-15.json')); raw=json.loads(raw) if isinstance(raw,str) else raw
ids_to_job={str(sid):j for sid,j in raw.get('jds',{}).items()}
# Save fetched JDs, preserving canonical relative description_file paths.
jd_dir=config_lib.data_root()/'tracking/job_descriptions/active'; jd_dir.mkdir(parents=True,exist_ok=True)
with open(config_lib.data_root()/'tracking/jobs/jobs.csv',newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f)); header=list(rows[0])
changed=[]; gated=[]
for r in rows:
    sid=str(r.get('source_id',''))
    if sid not in ids_to_job: continue
    text=ids_to_job[sid]['text']; slug=r['job_id']
    p=jd_dir/(slug+'.md'); p.write_text('# LinkedIn job description\n\n'+text+'\n',encoding='utf-8')
    r['description_file']=str(p.relative_to(config_lib.data_root()))
    r['full_description_hash']=__import__('hashlib').sha256(text.encode()).hexdigest()[:16]
    verdict,flags=apply_eligibility_gates({**r,'description':text,'job_url':r.get('job_url','')})
    if verdict=='non_useful':
        r['status']='open'; r['recommended_action']='SKIP'; r['notes']=(r.get('notes','')+'; GATED OUT after JD fetch: '+','.join(flags)).strip('; '); gated.append((r['company'],r['title'],flags))
    changed.append(r['job_id'])
with open(config_lib.data_root()/'tracking/jobs/jobs.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=header); w.writeheader(); w.writerows(rows)
print('jd_saved',len(changed),'gated_after_jd',len(gated)); [print('GATED',*x) for x in gated]
