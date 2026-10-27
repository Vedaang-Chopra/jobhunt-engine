#!/usr/bin/env python3
"""Process sweep results: filter posts, dedupe, write CSVs, enrich emails."""

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, '/mnt/DATA/job_hunt/jobhunt-engine/scripts')
import config_lib

REPO = Path('/mnt/DATA/job_hunt/jobhunt-engine')
DATA_ROOT = Path(config_lib.data_root())

# Load sweep results
with open(REPO / 'sweep_results.json') as f:
    sweep = json.load(f)

all_posts = sweep['posts']
all_people = sweep['people']

print(f"Raw posts: {len(all_posts)}")
print(f"Raw people: {len(all_people)}")

# ============================================================
# PART A: Process hiring posts
# ============================================================

# Load existing hiring posts for dedupe
hiring_csv = DATA_ROOT / 'tracking' / 'hiring_posts' / 'hiring_posts.csv'
existing_posts = {}
if hiring_csv.exists():
    with open(hiring_csv, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            existing_posts[row['post_url']] = row
            existing_posts[row['post_id']] = row

print(f"Existing hiring posts: {len(existing_posts)}")

# Fit gate: role families we care about
ROLE_FAMILIES = {
    'agentic_ai': ['agentic', 'agent', 'multi-agent', 'langgraph', 'tool use', 'reasoning', 'autonomous'],
    'eval_inference': ['inference', 'evaluation', 'eval', 'vllm', 'serving', 'llm evaluation', 'benchmark'],
    'applied_ml': ['machine learning', 'ml engineer', 'applied scientist', 'applied ml', 'production ml', 'ml platform'],
    'post_training': ['post-training', 'post training', 'rlhf', 'dpo', 'sft', 'alignment', 'fine-tuning'],
    'ml_training_arch': ['distributed training', 'training infra', 'h100', 'a100', 'mixed precision', 'ddp', 'fsdp'],
    'ai_security': ['red team', 'adversarial', 'security', 'safety', 'trust & safety'],
    'agent_reasoning': ['reasoning', 'planning', 'chain of thought', 'cot'],
}

def classify_poster_type(headline: str) -> str:
    hl = (headline or '').lower()
    if any(k in hl for k in ['recruiter', 'talent acquisition', 'talent partner', 'sourcer', 'hiring manager', 'hr']):
        return 'recruiter'
    if any(k in hl for k in ['director', 'vp', 'head of', 'manager', 'lead', 'engineering manager', 'ml manager']):
        return 'hiring_manager'
    if any(k in hl for k in ['founder', 'co-founder', 'ceo', 'cto']):
        return 'founder'
    if any(k in hl for k in ['research scientist', 'research engineer', 'scientist', 'engineer', 'ml engineer', 'software engineer', 'applied scientist']):
        return 'engineer_researcher'
    return 'other'

def classify_role_family(body: str, headline: str) -> str:
    text = (body + ' ' + headline).lower()
    scores = {}
    for fam, keywords in ROLE_FAMILIES.items():
        scores[fam] = sum(1 for k in keywords if k in text)
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
    return 'other'

def fits_role_family(body: str, headline: str) -> bool:
    return classify_role_family(body, headline) != 'other'

def extract_roles(body: str) -> str:
    # Extract role mentions
    roles = []
    role_patterns = [
        r'(?:hiring|looking for|open|role|position)s?\s*:?\s*([^.]+)',
        r'(?:ML|Machine Learning|AI|LLM|Inference|Agentic|Research|Applied|Platform|Infrastructure|Backend|Full Stack|Data|Science)[^.]*Engineer',
        r'(?:Senior|Staff|Principal|Lead|Manager|Director|Head|VP)\s+[^.]*Engineer',
    ]
    for pat in role_patterns:
        matches = re.findall(pat, body, re.IGNORECASE)
        roles.extend(matches)
    return '; '.join(set(r.strip() for r in roles if len(r.strip()) > 3))[:500]

# Process feed posts
new_posts = []
run_id = f"lhp_{datetime.now().strftime('%Y%m%d_%H%M')}"

for p in all_posts:
    if p.get('family') != 'a_hiring_posts':
        continue
    
    body = p.get('body', '')
    headline = p.get('headline', '')
    poster = p.get('poster', '')
    poster_url = p.get('posterUrl', '')
    post_url = p.get('post_url', '')
    link_url = p.get('link_url', '')
    time_str = p.get('time', '')
    degree = p.get('degree', '')
    
    # Fit gate
    if not fits_role_family(body, headline):
        print(f"  FILTERED (no role match): {poster} - {headline[:60]}")
        continue
    
    # Check if real hiring lead (not commentary)
    if not re.search(r'(hiring|we.?re hiring|join|apply|dm me|reach out|open role|position)', body, re.IGNORECASE):
        print(f"  FILTERED (no hiring signal): {poster}")
        continue
    
    # Build post_id
    company_guess = 'unknown'
    # Try to extract company from headline
    company_match = re.search(r'@\s*([A-Za-z0-9\.\-]+)|at\s+([A-Za-z0-9\.\-]+)', headline, re.IGNORECASE)
    if company_match:
        company_guess = (company_match.group(1) or company_match.group(2)).strip('.')
    
    post_id = f"{company_guess}_{datetime.now().strftime('%Y-%m-%d')}_{hashlib.md5((post_url or poster_url).encode()).hexdigest()[:8]}"
    
    # Dedupe
    if post_url in existing_posts or post_id in existing_posts:
        print(f"  DUPLICATE: {poster} - {post_url[:60]}")
        continue
    
    poster_type = classify_poster_type(headline)
    role_family = classify_role_family(body, headline)
    roles_mentioned = extract_roles(body)
    priority = 'high' if poster_type in ('hiring_manager', 'recruiter', 'founder') else 'normal'
    
    # Parse posted_date from time_str (e.g., "1d", "2h")
    posted_date = datetime.now().date().isoformat()
    if time_str:
        try:
            if 'h' in time_str:
                posted_date = datetime.now().date().isoformat()
            elif 'd' in time_str:
                days = int(re.search(r'(\d+)', time_str).group(1))
                from datetime import timedelta
                posted_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        except:
            pass
    
    new_posts.append({
        'post_id': post_id,
        'poster_name': poster,
        'poster_headline': headline[:200],
        'poster_type': poster_type,
        'company': company_guess,
        'team_or_org': '',
        'post_url': post_url,
        'posted_date': posted_date,
        'discovered_date': datetime.now().date().isoformat(),
        'roles_mentioned': roles_mentioned,
        'application_url': link_url,
        'connection_degree': degree,
        'shared_context': '',
        'priority': priority,
        'role_family': role_family,
        'status': 'new',
        'notes': f"Feed pass {run_id}; source={p.get('query_keywords', '')}"
    })
    print(f"  NEW: {poster} ({poster_type}) - {company_guess} - {roles_mentioned[:80]}")

print(f"\nNew hiring posts to add: {len(new_posts)}")

# Append to hiring_posts.csv
if new_posts:
    hiring_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'post_id', 'poster_name', 'poster_headline', 'poster_type', 'company', 'team_or_org',
        'post_url', 'posted_date', 'discovered_date', 'roles_mentioned', 'application_url',
        'connection_degree', 'shared_context', 'priority', 'role_family', 'status', 'notes'
    ]
    write_header = not hiring_csv.exists()
    with open(hiring_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in new_posts:
            writer.writerow(row)
    print(f"Appended to {hiring_csv}")

# ============================================================
# PART B: Process people sweep
# ============================================================

people_csv = DATA_ROOT / 'tracking' / 'people_sweeps' / 'people_sweep.csv'

# Load existing people for dedupe
existing_people = set()  # (normalized_name, company) tuples
existing_slugs = set()
contacts_csv = DATA_ROOT / 'tracking' / 'contacts' / 'contacts.csv'

def normalize_name(name: str) -> str:
    return re.sub(r'[^a-z]', '', (name or '').lower())

def linkedin_slug(url: str) -> str:
    m = re.search(r'linkedin\.com/in/([a-z0-9\-]{3,60})', url or '')
    return m.group(1) if m else ''

# Load contacts.csv for blocked statuses
blocked_statuses = {'requested', 'connected', 'contacted', 'responded'}
contact_status = {}
if contacts_csv.exists():
    with open(contacts_csv, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row.get('name', '')
            slug = linkedin_slug(row.get('linkedin_url', ''))
            status = (row.get('outreach_status') or '').strip().lower()
            if name:
                contact_status[normalize_name(name)] = status
            if slug:
                existing_slugs.add(slug)
            if name:
                existing_people.add((normalize_name(name), row.get('company', '').lower()))

# Load prior sweep rows
if people_csv.exists():
    with open(people_csv, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row.get('name', '')
            slug = linkedin_slug(row.get('linkedin_url', ''))
            status = (row.get('status') or '').strip().lower()
            if slug:
                existing_slugs.add(slug)
            if name:
                existing_people.add((normalize_name(name), row.get('company', '').lower()))

print(f"Existing people (slugs): {len(existing_slugs)}")
print(f"Existing people (fuzzy): {len(existing_people)}")

# Process extracted people
new_people = []
people_run_id = f"psweep_{datetime.now().strftime('%Y%m%d_%H%M')}"

for p in all_people:
    if p.get('family') == 'a_hiring_posts':
        continue  # These are posts, not people
    
    name = p.get('name', '').strip()
    headline = p.get('headline', '').strip()
    company = p.get('company', '').strip()
    linkedin_url = p.get('linkedinUrl', '').strip() or p.get('linkedin_url', '').strip()
    family = p.get('family', '')
    query_keywords = p.get('query_keywords', '')
    
    if not name or not linkedin_url:
        continue
    
    slug = linkedin_slug(linkedin_url)
    norm_name = normalize_name(name)
    norm_company = company.lower()
    
    # Check dedupe
    is_duplicate = False
    if slug and slug in existing_slugs:
        is_duplicate = True
    if (norm_name, norm_company) in existing_people:
        is_duplicate = True
    # Fuzzy check
    if not is_duplicate:
        for ename, eco in existing_people:
            if ename and norm_name:
                ratio = len(set(ename) & set(norm_name)) / max(len(ename), len(norm_name))
                if ratio >= 0.85 and (not eco or not norm_company or eco == norm_company):
                    is_duplicate = True
                    break
    
    # Check blocked
    is_blocked = contact_status.get(norm_name, '') in blocked_statuses
    
    if is_blocked:
        print(f"  BLOCKED: {name} ({company}) - status={contact_status.get(norm_name)}")
        continue
    if is_duplicate:
        print(f"  DUPLICATE: {name} ({company})")
        continue
    
    # Determine person_type from family and headline
    if family == 'b_recruiters':
        person_type = 'recruiter'
    elif family == 'c_company_people':
        person_type = 'engineer_researcher'  # default
        # Try to infer from headline
        hl = headline.lower()
        if any(k in hl for k in ['manager', 'director', 'head', 'lead', 'vp']):
            person_type = 'hiring_manager'
        elif 'recruiter' in hl or 'talent' in hl:
            person_type = 'recruiter'
    else:
        person_type = 'engineer_researcher'
    
    # Build why_relevant
    why = f"Found via {family} query: {query_keywords}"
    if family == 'b_recruiters':
        why = f"Recruiter at {company} ({query_keywords})"
    elif family == 'c_company_people':
        why = f"Engineer/Researcher at {company} ({query_keywords}) - referral path"
    
    new_people.append({
        'sweep_run_id': people_run_id,
        'date': datetime.now().date().isoformat(),
        'name': name,
        'title': headline[:200],
        'company': company,
        'person_type': person_type,
        'linkedin_url': linkedin_url,
        'post_url': '',
        'why_relevant': why,
        'status': 'pending_review',
        'notes': f"family={family}; email_enrich=pending"
    })
    
    # Update dedupe sets
    if slug:
        existing_slugs.add(slug)
    existing_people.add((norm_name, norm_company))
    print(f"  NEW: {name} | {headline[:60]} | {company} | {person_type}")

print(f"\nNew people to add: {len(new_people)}")

# Append to people_sweep.csv
if new_people:
    people_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'sweep_run_id', 'date', 'name', 'title', 'company', 'person_type',
        'linkedin_url', 'post_url', 'why_relevant', 'status', 'notes'
    ]
    write_header = not people_csv.exists()
    with open(people_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in new_people:
            writer.writerow(row)
    print(f"Appended to {people_csv}")

# ============================================================
# PART C: Email enrichment for new contacts
# ============================================================

print("\n=== PART C: Email Enrichment ===")

# For each new person without email, run email_pattern_finder
# First, collect unique companies
companies_to_check = set()
for p in new_people:
    companies_to_check.add(p['company'])

# Map company names to slugs (from target-companies.yaml)
import yaml
comp_path = DATA_ROOT / 'job_research' / 'config' / 'target-companies.yaml'
company_slugs = {}
if comp_path.exists():
    data = yaml.safe_load(comp_path.read_text()) or {}
    for item in data.get('companies', []):
        if isinstance(item, dict):
            name = item.get('company') or item.get('name') or ''
            # Create slug
            slug = name.lower().replace(' ', '_').replace('.', '').replace('/', '_')
            company_slugs[name.lower()] = slug

email_results = {}

for p in new_people:
    company = p['company']
    slug = company_slugs.get(company.lower())
    
    if not slug:
        # Try fuzzy match
        for cn, cs in company_slugs.items():
            if cn in company.lower() or company.lower() in cn:
                slug = cs
                break
    
    if not slug:
        p['notes'] += f"; email_enrich: no slug for '{company}'"
        email_results[f"{p['name']} ({company})"] = "no slug"
        continue
    
    # Run email_pattern_finder.py --company <slug> (dry-run)
    import subprocess
    try:
        result = subprocess.run([
            '/mnt/DATA/job_hunt/jobhunt-engine/.venv/bin/python',
            '/mnt/DATA/job_hunt/jobhunt-engine/scripts/email_pattern_finder.py',
            '--company', slug
        ], capture_output=True, text=True, timeout=30, cwd='/mnt/DATA/job_hunt/jobhunt-engine')
        
        output = result.stdout.strip()
        email_results[f"{p['name']} ({company})"] = output.split('\n')[0] if output else "no output"
        
        # Update notes
        if 'confirmed' in output.lower():
            p['notes'] += f"; email_enrich: CONFIRMED pattern for {slug}"
        elif 'unverified' in output.lower():
            p['notes'] += f"; email_enrich: UNVERIFIED pattern for {slug} (do not send)"
        elif 'unknown' in output.lower():
            p['notes'] += f"; email_enrich: UNKNOWN pattern for {slug}"
        else:
            p['notes'] += f"; email_enrich: {output[:80]}"
            
    except Exception as e:
        p['notes'] += f"; email_enrich: error={e}"
        email_results[f"{p['name']} ({company})"] = f"error: {e}"

print("\nEmail enrichment results:")
for k, v in email_results.items():
    print(f"  {k}: {v}")

# Rewrite people CSV with updated notes
if new_people:
    with open(people_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # Re-read existing + new
        all_rows = []
        if people_csv.exists():
            with open(people_csv, newline='', encoding='utf-8') as fr:
                for row in csv.DictReader(fr):
                    all_rows.append(row)
        # Update new rows
        for np in new_people:
            all_rows.append(np)
        for row in all_rows:
            writer.writerow(row)

# ============================================================
# Log search run
# ============================================================

search_runs_csv = DATA_ROOT / 'tracking' / 'search_runs' / 'search_runs.csv'
search_runs_csv.parent.mkdir(parents=True, exist_ok=True)
run_fields = ['run_id', 'date', 'sources', 'queries', 'total_scanned', 'new_jobs_found', 'duplicates_skipped', 'strong_fits', 'notes']
write_header = not search_runs_csv.exists()
with open(search_runs_csv, 'a', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=run_fields)
    if write_header:
        writer.writeheader()
    writer.writerow({
        'run_id': run_id,
        'date': datetime.now().date().isoformat(),
        'sources': 'linkedin_posts+linkedin_people',
        'queries': '8 (4 content + 4 people)',
        'total_scanned': len(all_posts) + len(all_people),
        'new_jobs_found': len(new_posts),
        'duplicates_skipped': len(all_posts) - len(new_posts) + len(all_people) - len(new_people),
        'strong_fits': sum(1 for p in new_posts if p['priority'] == 'high'),
        'notes': f"Feed pass: {len(new_posts)} new posts; People sweep: {len(new_people)} new contacts; Email enrich: {sum(1 for v in email_results.values() if 'confirmed' in v.lower())} confirmed"
    })

print("\n=== SUMMARY ===")
print(f"PART A - New hiring posts: {len(new_posts)}")
for p in new_posts:
    print(f"  {p['poster_name']} ({p['poster_type']}) @ {p['company']} - {p['roles_mentioned'][:80]} - {p['post_url']}")

print(f"\nPART B - New people queued: {len(new_people)}")
for p in new_people:
    print(f"  {p['name']} @ {p['company']} - {p['person_type']} - {p['why_relevant'][:80]}")

print(f"\nPART C - Emails resolved:")
confirmed = sum(1 for v in email_results.values() if 'confirmed' in v.lower())
unverified = sum(1 for v in email_results.values() if 'unverified' in v.lower())
unknown = sum(1 for v in email_results.values() if 'unknown' in v.lower())
print(f"  Confirmed: {confirmed}, Unverified: {unverified}, Unknown/None: {unknown}")