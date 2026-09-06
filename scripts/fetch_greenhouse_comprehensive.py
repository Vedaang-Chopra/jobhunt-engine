#!/usr/bin/env python3
"""
Comprehensive Greenhouse job fetching with full content.
Updated for new repository structure.
"""

import sys
import json
import re
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib
_DATA = config_lib.data_root()
DATA_DIR = _DATA / "job_research" / "data"
JOBS_DIR = _DATA / "tracking" / "job_descriptions" / "active"

def filter_jobs(jobs, company_name):
    """Filter jobs relevant to our candidate profile."""
    keywords = [
        'research', 'engineer', 'ml', 'ai', 'llm', 'machine learning',
        'training', 'post-training', 'rl', 'agent', 'reasoning',
        'multimodal', 'applied scientist', 'inference', 'optimization',
        'post training', 'rlhf', 'dpo', 'grpo', 'sft', 'reinforcement',
        'foundation', 'generative', 'agentic', 'coding', 'synthesis',
        'evaluation', 'synthetic', 'routing', 'tool', 'memory',
        'orchestration', 'planning', 'distributed', 'serving',
        'pretraining', 'fine-tuning', 'fine tuning', 'alignment',
        'safety', 'interpretability', 'red team', 'safeguards',
        'code', 'computer use', 'tool use', 'model eval', 'benchmark',
        'data', 'platform', 'infrastructure', 'kernel', 'cuda',
        'pytorch', 'jax', 'tensorflow', 'transformer'
    ]
    
    exclude_keywords = [
        'sales', 'account executive', 'recruiter', 'hr', 'human resources',
        'marketing', 'product manager', 'product marketing', 'operations',
        'finance', 'legal', 'security engineer', 'platform security',
        'it support', 'av engineer', 'data center', 'electrical',
        'mechanical', 'silicon', 'hardware', 'tpv', 'kernel engineer',
        'office', 'administrative', 'executive', 'assistant',
        'business systems', 'grc', 'corporate', 'enterprise',
        'manager', 'director', 'head of', 'lead', 'principal',
        'staff', 'staff+', 'staff engineer', 'staff software',
        'senior staff', 'principal', 'architect', 'evangelist',
        'technical program', 'program manager', 'strategy',
        'solutions architect', 'forward deployed', 'applied ai architect',
        'applied ai security', 'applied ai engineer'
    ]
    
    relevant = []
    for j in jobs:
        title_lower = j['title'].lower()
        has_relevant = any(kw in title_lower for kw in keywords)
        is_excluded = any(kw in title_lower for kw in exclude_keywords)
        
        if has_relevant and not is_excluded:
            relevant.append(j)
    
    return relevant


def get_jobs_from_greenhouse(board_name):
    """Fetch jobs from a Greenhouse board."""
    import urllib.request
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_name}/jobs?content=true"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.load(response)
            return data.get('jobs', [])
    except Exception as e:
        print(f"Error fetching {board_name}: {e}", file=sys.stderr)
        return []


def save_job_description(job, company_name):
    """Save full job description to markdown file."""
    import re
    from datetime import datetime
    
    def sanitize_filename(text):
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text.strip('_')
    
    company = sanitize_filename(company_name)
    title = sanitize_filename(job.get('title', 'unknown_title'))
    
    url = job.get('absolute_url', '')
    job_id = url.rstrip('/').split('/')[-1] if url else 'unknown'
    
    filename = f"{company}__{title}__{job_id}.md"
    filepath = JOBS_DIR / filename
    
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    
    md_content = f"""# {job.get('title', 'Unknown Title')}

**Company:** {company_name}
**Location:** {job.get('location', {}).get('name', 'Unknown') if job.get('location') else 'Unknown'}
**Remote/Hybrid/On-site:** {job.get('metadata', [{}])[0].get('value', 'Unknown') if job.get('metadata') else 'Unknown'}
**Job URL:** {job.get('absolute_url', 'Unknown')}
**Source:** greenhouse
**Date Discovered:** {datetime.now().isoformat()}
**Date Posted:** {job.get('updated_at', 'Unknown')}
**Salary Range:** {job.get('salary', 'Not listed')}
**Team:** {job.get('department', 'Not specified')}

---

## Role Description
{job.get('content', 'Not provided')}

---

## Responsibilities
{job.get('responsibilities', 'Not provided')}

---

## Minimum Qualifications
{job.get('requirements', 'Not provided')}

---

## Preferred Qualifications
{job.get('preferred_qualifications', 'Not provided')}

---

## Required Technologies
{', '.join(job.get('skills', [])) if job.get('skills') else 'Not provided'}

---

## Experience Requirement
{job.get('experience', 'Not specified')}

---

## Education Requirement
{job.get('education', 'Not specified')}

---

## Full Job Description Text
{job.get('content', 'Not captured')}

---

*Saved on: {datetime.now().isoformat()}*
"""
    
    with open(filepath, "w") as f:
        f.write(md_content)
    
    return str(filepath)


def main():
    companies = {
        'anthropic': 'Anthropic',
        'openai': 'OpenAI', 
        'cohere': 'Cohere',
        'mistral': 'Mistral',
        'databricks': 'Databricks',
        'together-ai': 'Together AI',
        'huggingface': 'Hugging Face',
        'scale-ai': 'Scale AI',
        'perplexity-ai': 'Perplexity',
        'character-ai': 'Character AI',
        'runwayml': 'Runway',
        'elevenlabs': 'ElevenLabs',
        'ai2': 'AI2',
        'xai': 'xAI',
    }
    
    all_relevant = {}
    
    for board, name in companies.items():
        print(f"\nFetching {name} ({board})...", file=sys.stderr)
        jobs = get_jobs_from_greenhouse(board)
        if jobs:
            relevant = filter_jobs(jobs, name)
            print(f"  Total: {len(jobs)}, Relevant: {len(relevant)}", file=sys.stderr)
            if relevant:
                all_relevant[name] = relevant
                for j in relevant:
                    loc = j['location']['name'] if j.get('location') else 'Unknown'
                    print(f"  - {j['title']} | {loc} | {j['absolute_url']}")
                    save_job_description(j, name)
        else:
            print(f"  No jobs or error", file=sys.stderr)
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / 'greenhouse_jobs.json', 'w') as f:
        json.dump(all_relevant, f, indent=2)
    
    # Also save a summary
    with open(DATA_DIR / 'greenhouse_summary.json', 'w') as f:
        summary = {k: len(v) for k, v in all_relevant.items()}
        json.dump(summary, f, indent=2)
    
    print(f"\n\nTotal companies with relevant jobs: {len(all_relevant)}", file=sys.stderr)
    total_relevant = sum(len(v) for v in all_relevant.values())
    print(f"Total relevant jobs: {total_relevant}", file=sys.stderr)


if __name__ == '__main__':
    main()