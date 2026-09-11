#!/usr/bin/env python3
"""
Migration script: Consolidate job_research/jobs_master.csv and job_search/state/jobs.csv
into tracking/jobs/jobs.csv with canonical schema.
"""

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path

# Legacy paths resolved relative to the parent workspace dir; override with
# JOBHUNT_LEGACY_HERMES_BASE when the legacy layout lives elsewhere.
import os
HERMES_BASE = Path(os.environ.get(
    "JOBHUNT_LEGACY_HERMES_BASE",
    str(Path(__file__).resolve().parents[3]),
))

# Paths
MASTER_CSV = Path(HERMES_BASE / "application_hunting/job_research/jobs_master.csv")
SECONDARY_CSV = Path(HERMES_BASE / "application_hunting/job_research/job_search/state/jobs.csv")
OUTPUT_CSV = Path(HERMES_BASE / "application_hunting/tracking/jobs/jobs.csv")

# Medical company patterns to flag as false positives
MEDICAL_PATTERNS = [
    r'essential',  # Essential Healthcare - CRNA/Anesthesiologist roles
]

# Role family mapping from fit_tier and title keywords
def determine_role_family(title, company, existing_role_family=None):
    """Determine role family from title and company."""
    # If secondary CSV already has a curated role_family, use it
    if existing_role_family and existing_role_family in ['agentic_ai', 'agent_reasoning', 'applied_ml', 'eval_inference', 'post_training', 'other']:
        return existing_role_family
    
    title_lower = title.lower()
    
    # Post-training / RL roles (NOT targeted)
    if any(kw in title_lower for kw in ['post-training', 'post training', 'rlhf', 'dpo', 'grpo', 'rl post', 'reinforcement learning', 'rl engineering', 'rl velocity', 'rl scaling', 'code rl', 'pretraining', 'pre-training']):
        return 'post_training'
    
    # Agentic AI / Applied AI Research
    if any(kw in title_lower for kw in ['agentic', 'multi-agent', 'tool use', 'function calling', 'workflow orchestration', 'applied ai engineer', 'applied ai architect', 'forward deployed', 'fde']):
        return 'agentic_ai'
    
    # Agents/Reasoning (Frontier)
    if any(kw in title_lower for kw in ['reasoning', 'planning', 'swe-bench', 'coding agent', 'reflection', 'supervisor-worker', 'workflow reuse', 'agent engineer', 'frontier agents']):
        return 'agent_reasoning'
    
    # Evaluation / Inference
    if any(kw in title_lower for kw in ['evaluation', 'benchmark', 'inference optim', 'model serving', 'inference engineer', 'model optimization', 'llm inference', 'inference framework', 'model eval']):
        return 'eval_inference'
    
    # Applied ML / Production
    if any(kw in title_lower for kw in ['ml engineer', 'machine learning engineer', 'ml infrastructure', 'ml platform', 'mlops', 'feature platform', 'training pipeline', 'serving engineer', 'ai infrastructure', 'applied scientist', 'applied ml', 'platform engineer', 'software engineer', 'data engineer', 'data platform', 'distributed systems', 'backend engineer', 'infrastructure engineer', 'systems engineer', 'site reliability', 'production engineer', 'capacity planner', 'arc team', 'identity', 'gen ai', 'generative ai', 'arc team', 'field engineer', 'senior data engineer', 'research advisor', 'vp research', 'business development', 'it engineer', 'product engineer', 'customer success', 'systems research', 'senior product', 'it engineer']):
        return 'applied_ml'
    
    # Research Engineer generic
    if 'research engineer' in title_lower or 'research scientist' in title_lower:
        if 'inference' in title_lower or 'evaluation' in title_lower or 'serving' in title_lower:
            return 'eval_inference'
        if 'post' in title_lower or 'rl' in title_lower or 'reinforcement' in title_lower or 'pretraining' in title_lower or 'pre-training' in title_lower:
            return 'post_training'
        if 'agent' in title_lower or 'agentic' in title_lower:
            return 'agentic_ai'
        return 'applied_ml'
    
    # AI Tutor roles (xAI) - not relevant
    if 'ai tutor' in title_lower:
        return 'other'
    
    # Safeguards/Trust & Safety - not relevant
    if 'safeguards' in title_lower or 'trust & safety' in title_lower or 'red team' in title_lower:
        return 'other'
    
    # Product/Management - not relevant
    if 'product management' in title_lower or 'product engineer' in title_lower:
        return 'other'
    
    # External Affairs - not relevant
    if 'external affairs' in title_lower:
        return 'other'
    
    # Default
    return 'other'

def determine_resume_variant(role_family):
    """Map role family to resume variant."""
    mapping = {
        'agentic_ai': 'agentic',
        'agent_reasoning': 'agent_reasoning',
        'applied_ml': 'applied_ml',
        'eval_inference': 'eval_inference',
        'post_training': 'RL_Post_Training',
        'other': 'agentic',  # default
    }
    return mapping.get(role_family, 'agentic')

def slugify(text):
    """Create slug from text."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

def generate_job_id(company, title, location, source_id=None):
    """Generate stable job ID."""
    company_slug = slugify(company)
    title_slug = slugify(title)
    
    if source_id:
        # Extract numeric ID from Greenhouse URL
        match = re.search(r'(\d{10})', source_id)
        if match:
            return f"{company_slug}_{title_slug}_{match.group(1)}"
    
    # Fallback: hash of company + title + location
    hash_input = f"{company}|{title}|{location}".encode()
    hash_suffix = hashlib.sha256(hash_input).hexdigest()[:8]
    return f"{company_slug}_{title_slug}_{hash_suffix}"

def is_medical_false_positive(company, title):
    """Check if job is a medical/anesthesia false positive."""
    company_lower = company.lower()
    title_lower = title.lower()
    
    for pattern in MEDICAL_PATTERNS:
        if pattern in company_lower:
            return True
    
    # Check for CRNA, Anesthesiologist, medical terms
    medical_terms = ['crna', 'anesthesiologist', 'anesthesia', 'medical center', 'hospital', 'rn ', 'nurse']
    for term in medical_terms:
        if term in title_lower:
            return True
    
    return False

def parse_master_csv():
    """Parse jobs_master.csv."""
    jobs = []
    with open(MASTER_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Extract source_id from URL
            url = row.get('URL', '')
            source_id = None
            match = re.search(r'(\d{10})', url)
            if match:
                source_id = match.group(1)
            
            job = {
                'company': row.get('Company', '').strip(),
                'title': row.get('Role', '').strip(),
                'location': row.get('Location', '').strip(),
                'job_url': url,
                'fit_score': int(row.get('Fit Score', 0)),
                'fit_tier': row.get('Target Category', '').strip(),
                'why_fits': row.get('Why It Fits', '').strip(),
                'biggest_gap': row.get('Biggest Gap', '').strip(),
                'experience_req': row.get('Experience Requirement', '').strip(),
                'salary': row.get('Salary', '').strip(),
                'date_posted': row.get('Posted', '').strip(),
                'source_id': source_id,
                'source': 'greenhouse',
                'existing_role_family': None,
            }
            
            # Determine role family and other derived fields
            job['role_family'] = determine_role_family(job['title'], job['company'])
            job['resume_variant'] = determine_resume_variant(job['role_family'])
            job['is_medical'] = is_medical_false_positive(job['company'], job['title'])
            
            # Parse fit_tier to standard values
            fit_tier_map = {
                'Strong target': 'A',
                'Good target': 'B',
                'Stretch but worthwhile': 'C',
                'Very high stretch': 'D',
                'Not worth applying': 'E',
            }
            job['fit_tier_std'] = fit_tier_map.get(job['fit_tier'], 'E')
            
            # Generate job_id
            job['job_id'] = generate_job_id(job['company'], job['title'], job['location'], source_id)
            
            jobs.append(job)
    return jobs

def parse_secondary_csv():
    """Parse job_search/state/jobs.csv."""
    jobs = []
    with open(SECONDARY_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            job = {
                'job_id': row.get('job_id', '').strip(),
                'company': row.get('company', '').strip(),
                'title': row.get('title', '').strip(),
                'location': row.get('location', '').strip(),
                'job_url': row.get('job_url', '').strip(),
                'canonical_application_url': row.get('canonical_application_url', '').strip(),
                'source': row.get('source', '').strip(),
                'date_discovered': row.get('date_discovered', '').strip(),
                'date_posted': row.get('date_posted', '').strip(),
                'status': row.get('status', '').strip(),
                'fit_score': int(row.get('fit_score', 0)) if row.get('fit_score') else 0,
                'fit_tier': row.get('fit_tier', '').strip(),
                'role_family': row.get('role_family', '').strip(),
                'seniority': row.get('seniority', '').strip(),
                'key_requirements': row.get('key_requirements', '').strip(),
                'matching_strengths': row.get('matching_strengths', '').strip(),
                'main_gaps': row.get('main_gaps', '').strip(),
                'resume_variant': row.get('resume_variant', '').strip(),
                'networking_priority': row.get('networking_priority', '').strip(),
                'application_priority': row.get('application_priority', '').strip(),
                'last_checked': row.get('last_checked', '').strip(),
                'notes': row.get('notes', '').strip(),
                'is_medical': False,  # These are curated, not medical
                'existing_role_family': row.get('role_family', '').strip(),
            }
            jobs.append(job)
    return jobs

def merge_jobs(master_jobs, secondary_jobs):
    """Merge jobs, preferring secondary for enriched fields, master for completeness."""
    merged = {}
    
    # First pass: add all master jobs
    for job in master_jobs:
        key = job['job_id']
        merged[key] = job
    
    # Second pass: merge secondary jobs
    for job in secondary_jobs:
        key = job['job_id']
        if key in merged:
            # Merge: prefer secondary for enriched fields
            existing = merged[key]
            # Update with secondary's enriched fields
            for field in ['canonical_application_url', 'date_discovered', 'status', 
                         'key_requirements', 'matching_strengths', 'main_gaps',
                         'seniority', 'networking_priority', 'application_priority',
                         'last_checked', 'notes']:
                if job.get(field):
                    existing[field] = job[field]
            # If secondary has role_family, use it (more curated)
            if job.get('existing_role_family'):
                existing['role_family'] = job['existing_role_family']
                existing['resume_variant'] = determine_resume_variant(job['existing_role_family'])
            # Ensure is_medical is False for curated jobs
            existing['is_medical'] = False
        else:
            # New job from secondary - use its role_family
            job['role_family'] = determine_role_family(job['title'], job['company'], job.get('existing_role_family'))
            job['resume_variant'] = determine_resume_variant(job['role_family'])
            merged[key] = job
    
    return list(merged.values())

def write_canonical_csv(jobs):
    """Write canonical jobs.csv with proper schema."""
    # Sort by fit_score descending, then company, then title
    jobs.sort(key=lambda x: (-x.get('fit_score', 0), x.get('company', ''), x.get('title', '')))
    
    fieldnames = [
        'job_id', 'company', 'title', 'location', 'job_url', 'canonical_application_url',
        'source', 'date_discovered', 'date_posted', 'date_updated', 'status',
        'fit_score', 'fit_tier', 'role_family', 'seniority',
        'key_requirements', 'matching_strengths', 'main_gaps',
        'resume_variant', 'networking_priority', 'application_priority',
        'last_checked', 'notes', 'full_description_hash', 'description_file',
        'is_medical_false_positive'
    ]
    
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for job in jobs:
            # Compute description hash (placeholder - would need full JD text)
            desc_text = job.get('why_fits', '') + job.get('biggest_gap', '') + job.get('key_requirements', '') + job.get('matching_strengths', '')
            desc_hash = hashlib.sha256(desc_text.encode()).hexdigest()[:16] if desc_text else ''
            
            # Determine date_discovered
            date_discovered = job.get('date_discovered', '')
            if not date_discovered:
                date_discovered = datetime.now().strftime('%Y-%m-%d')
            
            # Determine status
            status = job.get('status', 'open')
            if job.get('is_medical'):
                status = 'archived'
            
            # Determine fit_tier
            fit_tier = job.get('fit_tier_std', job.get('fit_tier', 'E'))
            if fit_tier not in ['A', 'B', 'C', 'D', 'E']:
                fit_tier = 'E'
            
            # Determine seniority
            seniority = job.get('seniority', 'unknown')
            if not seniority or seniority == 'unknown':
                # Infer from title
                title_lower = job.get('title', '').lower()
                if any(kw in title_lower for kw in ['senior', 'sr.', 'lead', 'principal', 'staff']):
                    seniority = 'senior'
                elif any(kw in title_lower for kw in ['junior', 'jr.', 'entry', 'new grad', 'fellow', 'intern']):
                    seniority = 'entry'
                else:
                    seniority = 'mid'
            
            row = {
                'job_id': job.get('job_id', ''),
                'company': job.get('company', ''),
                'title': job.get('title', ''),
                'location': job.get('location', ''),
                'job_url': job.get('job_url', ''),
                'canonical_application_url': job.get('canonical_application_url', job.get('job_url', '')),
                'source': job.get('source', 'greenhouse'),
                'date_discovered': date_discovered,
                'date_posted': job.get('date_posted', ''),
                'date_updated': '',
                'status': status,
                'fit_score': job.get('fit_score', 0),
                'fit_tier': fit_tier,
                'role_family': job.get('role_family', 'other'),
                'seniority': seniority,
                'key_requirements': job.get('key_requirements', job.get('why_fits', '')),
                'matching_strengths': job.get('matching_strengths', job.get('why_fits', '')),
                'main_gaps': job.get('main_gaps', job.get('biggest_gap', '')),
                'resume_variant': job.get('resume_variant', 'agentic'),
                'networking_priority': job.get('networking_priority', 'medium'),
                'application_priority': job.get('application_priority', 'medium'),
                'last_checked': job.get('last_checked', date_discovered),
                'notes': job.get('notes', ''),
                'full_description_hash': desc_hash,
                'description_file': '',
                'is_medical_false_positive': 'true' if job.get('is_medical') else 'false',
            }
            writer.writerow(row)

def main():
    print("Loading master jobs...")
    master_jobs = parse_master_csv()
    print(f"  Loaded {len(master_jobs)} jobs from master CSV")
    
    print("Loading secondary jobs...")
    secondary_jobs = parse_secondary_csv()
    print(f"  Loaded {len(secondary_jobs)} jobs from secondary CSV")
    
    print("Merging...")
    merged = merge_jobs(master_jobs, secondary_jobs)
    print(f"  Merged to {len(merged)} unique jobs")
    
    # Count medical false positives
    medical_count = sum(1 for j in merged if j.get('is_medical'))
    print(f"  Medical false positives: {medical_count}")
    
    # Count by role family
    role_counts = {}
    for j in merged:
        rf = j.get('role_family', 'other')
        role_counts[rf] = role_counts.get(rf, 0) + 1
    print(f"  Role family distribution: {role_counts}")
    
    print("Writing canonical CSV...")
    write_canonical_csv(merged)
    print(f"  Written to {OUTPUT_CSV}")

if __name__ == '__main__':
    main()