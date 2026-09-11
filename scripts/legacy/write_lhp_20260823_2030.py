"""One-off: write hiring_posts rows + search_runs log for run lhp_20260823_2030."""
import csv, hashlib, os

HDR = ("post_id,poster_name,poster_headline,poster_type,company,team_or_org,post_url,"
       "posted_date,discovered_date,roles_mentioned,application_url,connection_degree,"
       "shared_context,priority,role_family,status,notes").split(',')
TODAY = '2026-08-23'


def pid(comp, date, url):
    return f"{comp.lower().replace(' ', '_')}_{date}_{hashlib.sha256(url.encode()).hexdigest()[:8]}"


def row(**kw):
    base = {k: '' for k in HDR}
    base.update(kw)
    return base


rows = [
    row(post_id=pid('capital_one', '2026-08-23', 'https://www.linkedin.com/in/harshs27/'),
        poster_name='Harsh Shrivastava',
        poster_headline='Director, AI Engineering at Capital One || Causal Foundation Models',
        poster_type='hiring_manager', company='Capital One', team_or_org='AI Engineering',
        posted_date='2026-08-22', discovered_date=TODAY,
        roles_mentioned='Lead ML Engineer; Manager Data Science; Principal Associate Data Scientist; upcoming AI Engineer/Applied Researcher roles',
        application_url='https://lnkd.in/gdPsqnaG', connection_degree='2nd',
        priority='high', role_family='applied_ml', status='new',
        notes='Real lead: explicit openings list + offers recruiter intros. Feed pass.'),
    row(post_id=pid('cohere', '2026-08-21', 'https://www.linkedin.com/feed/update/urn:li:share:7496345985082744832/'),
        poster_name='Natalie W. (via Irem Ergun repost)',
        poster_headline='Talent Partner @ Cohere', poster_type='recruiter',
        company='Cohere', team_or_org='GPU Clusters / Infrastructure',
        post_url='https://www.linkedin.com/feed/update/urn:li:share:7496345985082744832/',
        posted_date='2026-08-21', discovered_date=TODAY,
        roles_mentioned='Engineering Manager, GPU Infrastructure',
        application_url='https://jobs.ashbyhq.com/cohere (via post apply link)',
        connection_degree='Following', priority='low', role_family='eval_inference',
        status='not_fit',
        notes='EM-level role (K8s fleet ops, US/Canada) - above user level; context/referral only. Feed pass.'),
    row(post_id=pid('apple', '2026-08-20', 'https://lnkd.in/ghif9wsw'),
        poster_name='Javier M.', poster_headline='Technical Recruiting @ Apple SWE | AI/ML',
        poster_type='recruiter', company='Apple', team_or_org='Safari Continuity',
        post_url='https://lnkd.in/ghif9wsw', posted_date='2026-08-20', discovered_date=TODAY,
        roles_mentioned='Software Engineer, Safari Continuity (Cupertino)',
        application_url='https://jobs.apple.com/en-us/details/200669039',
        connection_degree='Following', priority='low', role_family='applied_ml',
        status='new',
        notes='Real lead but Swift/Objective-C systems role, outside ML role families; onsite Cupertino. Feed pass.'),
    row(post_id=pid('databricks', '2026-05-28', 'https://www.linkedin.com/posts/qi-zheng-43249930_reliable-llm-inference-at-scale-activity-7465835944365985792-mNaC'),
        poster_name='Qi Zheng', poster_headline='LLM Inference @ Databricks',
        poster_type='engineer_researcher', company='Databricks', team_or_org='LLM Inference',
        post_url='https://www.linkedin.com/posts/qi-zheng-43249930_reliable-llm-inference-at-scale-activity-7465835944365985792-mNaC',
        posted_date='2026-05-28', discovered_date=TODAY,
        roles_mentioned='Inference infrastructure engineers (DM or careers link)',
        application_url='https://lnkd.in/gyeaY4Bx', priority='medium',
        role_family='eval_inference', status='new',
        notes='"Actively hiring for the team - DM me" - inference infra, strong role-family match. Web search pass.'),
    row(post_id=pid('nvidia', '2025-08-04', 'https://www.linkedin.com/posts/kyle-kranen_nvidia-newgrad-nvidiadynamo-activity-7358194302969131008-Zpk_'),
        poster_name='Kyle Kranen',
        poster_headline='Senior Manager - Deep Learning Algorithms - Dynamo @ NVIDIA',
        poster_type='hiring_manager', company='NVIDIA', team_or_org='Dynamo (LLM inference)',
        post_url='https://www.linkedin.com/posts/kyle-kranen_nvidia-newgrad-nvidiadynamo-activity-7358194302969131008-Zpk_',
        posted_date='2025-08-04', discovered_date=TODAY,
        roles_mentioned='New college grad inference engineers (vLLM/SGLang)',
        connection_degree='2nd', priority='medium', role_family='eval_inference',
        status='new',
        notes='New-grad inference role, strong fit BUT post ~1yr old - verify req still open. Web search pass.'),
    row(post_id=pid('together_ai', '2026-07-27', 'https://www.linkedin.com/posts/martijn-bartelds_were-hiring-phd-research-interns-at-together-activity-7487522283461210112-STuj'),
        poster_name='Martijn Bartelds', poster_headline='ML Researcher @ Together AI',
        poster_type='engineer_researcher', company='Together AI',
        team_or_org='Frontier AI Agents research',
        post_url='https://www.linkedin.com/posts/martijn-bartelds_were-hiring-phd-research-interns-at-together-activity-7487522283461210112-STuj',
        posted_date='2026-07-27', discovered_date=TODAY,
        roles_mentioned='PhD research interns (Fall 2026, SF in-person)',
        application_url='https://lnkd.in/giEEZZHn', priority='low',
        role_family='agentic_ai', status='not_fit',
        notes='PhD-only requirement - not a fit; recorded for network context. Web search pass.'),
]

os.makedirs('tracking/hiring_posts', exist_ok=True)
newfile = not os.path.exists('tracking/hiring_posts/hiring_posts.csv')
with open('tracking/hiring_posts/hiring_posts.csv', 'a', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=HDR)
    if newfile:
        w.writeheader()
    w.writerows(rows)

with open('tracking/search_runs/search_runs.csv', 'a', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames="run_id,date,sources,queries,total_scanned,new_jobs_found,duplicates_skipped,strong_fits,notes".split(','))
    if fh.tell() == 0:
        w.writeheader()
    w.writerow(dict(run_id='lhp_20260823_2030', date=TODAY,
                    sources='linkedin_posts,web_search', queries=12, total_scanned=60,
                    new_jobs_found=6, duplicates_skipped=0, strong_fits=2,
                    notes='feed pass 8 cards (3 leads) + web pass (3 leads; 3 of 5 web searches rate-limited/failed); people sweep 31 queued'))
print('hiring posts written:', len(rows))
