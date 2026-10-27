import csv,re
from pathlib import Path
p=Path('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/jobs/jobs.csv')
with p.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f)); header=list(rows[0])
ids={
'linkedin_capital_one_applied_researcher_ii_ai_foundations_llm_core_and_agentic_ai_4458112360':None,
'linkedin_protective_life_jr_and_sr_ai_developer_4465248858':None,
'linkedin_thomson_reuters_generative_ai_machine_learning_engineer_4349250403':None,
'linkedin_truveta_machine_learning_engineer_llms_generative_ai_4341825663':'G1_experience_ceiling_6yrs',
'linkedin_tiktok_usds_joint_venture_machine_learning_engineer_e_commerce_usds_4466786288':None}
for r in rows:
 if r.get('job_id') not in ids: continue
 r['status']='open'
 r['notes']=re.sub(r';? GATED OUT after JD fetch: [^;]+','',r.get('notes','')).strip('; ')
 if ids[r['job_id']]:
  r['recommended_action']='SKIP'; r['notes']=(r['notes']+'; GATED OUT after JD fetch: '+ids[r['job_id']]).strip('; ')
with p.open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=header); w.writeheader(); w.writerows(rows)
print('restored_non_false_positive_gates; gated_g1=1')
