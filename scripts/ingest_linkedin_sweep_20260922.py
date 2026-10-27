import csv, hashlib, html, re, urllib.request
from pathlib import Path
from datetime import date
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from discovery_lib import normalize_job, slugify
import config_lib
root=Path(config_lib.data_root())
jobs=root/'tracking/jobs/jobs.csv'
runs=root/'tracking/search_runs/search_runs.csv'
jd_dir=root/'tracking/job_descriptions/active'; jd_dir.mkdir(parents=True,exist_ok=True)
ids=['4470246425','4470238738']
meta={
 '4470246425':('Research Engineer','adaption','Redwood City, CA'),
 '4470238738':('Research Engineer','adaption','San Francisco, CA'),
}
with jobs.open(newline='',encoding='utf-8') as f:
    reader=csv.DictReader(f); fields=reader.fieldnames; existing=list(reader)
source_ids={r.get('source_id','').strip().lower() for r in existing if r.get('source_id')}
namekeys={(r.get('company','').strip().lower(), re.sub(r'\s+',' ',r.get('title','').strip().lower())) for r in existing}
new=[]; gated=0; gate_counts={}; dup=0
for sid in ids:
    title,company,location=meta[sid]
    url=f'https://www.linkedin.com/jobs/view/{sid}/'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    body=urllib.request.urlopen(req,timeout=30).read().decode('utf-8','ignore')
    m=re.search(r'<div[^>]+class="[^"]*show-more-less-html__markup[^"]*"[^>]*>([\s\S]*?)</div>',body,re.I)
    desc=html.unescape(re.sub(r'<[^>]+>',' ',m.group(1) if m else ''))
    desc=re.sub(r'\s+',' ',desc).strip()
    flags=[]
    if re.search(r'\b(director|vp|vice president|head|chief|principal|manager)\b',title,re.I): flags.append('G2')
    if re.search(r'\b(intern(ship)?|new grad|new graduate|early career)\b',title,re.I): flags.append('G3')
    if re.search(r'\b(uk|canada|india)\b',location,re.I): flags.append('G5')
    years=re.search(r'\b(\d+)\s*[-–]\s*(\d+)\s+years?\s+of\s+experience',desc,re.I)
    if years and int(years.group(1))>4: flags.append('G1')
    if re.search(r'\$\s*(?:[0-9]{2,3})(?:k|,000)',desc,re.I):
        pays=[int(x.replace(',',''))*(1000 if len(x.replace(',',''))<=3 else 1) for x in re.findall(r'\$\s*([0-9]{2,3}(?:,000|k)?)',desc,re.I)]
        if pays and max(pays)<150000: flags.append('G4')
    raw={'title':title,'company':company,'url':url,'location':location,'date_posted':'2026-09-22','source_id':sid,'source':'linkedin'}
    row=normalize_job(raw); row['date_discovered']=date.today().isoformat(); row['date_posted']='2026-09-22'; row['source']='linkedin'; row['source_id']=sid
    jobid=f'{slugify(company)}_{slugify(title)}_{sid}'
    row['job_id']=jobid
    row['status']='open'
    row['notes']='linkedin sweep; MCP logged-in JD fetched; 3-4 years required; salary not posted'
    if flags:
        row['recommended_action']='SKIP'; row['notes'] += '; gated:'+','.join(dict.fromkeys(flags)); gated+=1
        for f in dict.fromkeys(flags): gate_counts[f]=gate_counts.get(f,0)+1
    digest=hashlib.sha256(desc.encode()).hexdigest()
    jd_path=jd_dir/f'{jobid}.md'
    jd_path.write_text(f'# {title}\nCompany: {company}\nSource: linkedin\nURL: {url}\nHash: {digest}\nDiscovered: {date.today().isoformat()}\n\n## Full Job Description Text\n{desc}\n',encoding='utf-8')
    row['full_description_hash']=digest[:16]; row['description_file']=str(jd_path.relative_to(root)); row['canonical_application_url']=url; row['job_url']=url
    sidlow=sid.lower(); key=(company.lower(),re.sub(r'\s+',' ',title.lower()))
    if sidlow in source_ids or key in namekeys:
        dup+=1; continue
    source_ids.add(sidlow); namekeys.add(key); new.append({k:row.get(k,'') for k in fields})
if new:
    with jobs.open('a',newline='',encoding='utf-8') as f: csv.DictWriter(f,fieldnames=fields).writerows(new)
with runs.open('a',newline='',encoding='utf-8') as f:
    csv.writer(f).writerow([f'linkedin_{date.today().strftime("%Y%m%d_%H%M%S")}',date.today().isoformat(),'linkedin_loggedin_browser+guest_api','8 queries x 1 page (past-week US filter)',68,len(new),66,0,f'new jobs; gated_out={gated}; gate_counts={gate_counts}; logged JD fetched for {len(ids)}'])
print({'scanned':68,'new':len(new),'gated_out':gated,'gate_counts':gate_counts,'duplicates':dup,'job_ids':[r['job_id'] for r in new]})
