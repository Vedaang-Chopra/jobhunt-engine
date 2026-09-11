#!/usr/bin/env python3
import sys
import json
import urllib.request
import time

# Legacy paths resolved relative to the parent workspace dir; override with
# JOBHUNT_LEGACY_HERMES_BASE when the legacy layout lives elsewhere.
import os
HERMES_BASE = Path(os.environ.get(
    "JOBHUNT_LEGACY_HERMES_BASE",
    str(Path(__file__).resolve().parents[3]),
))

# Correct Greenhouse board names (these need to be verified)
COMPANY_BOARDS = {
    'anthropic': 'anthropic',
    'openai': 'openai',  # May not use Greenhouse
    'cohere': 'cohere',
    'mistral': 'mistral-ai',  # or similar
    'databricks': 'databricks',
    'together-ai': 'together-ai',
    'huggingface': 'huggingface',
    'scale-ai': 'scale-ai',
    'perplexity-ai': 'perplexity-ai',
    'character-ai': 'character-ai',
    'runwayml': 'runwayml',
    'elevenlabs': 'elevenlabs',
    'ai2': 'ai2',  # Allen Institute
    'xai': 'xai',
    # Additional companies to try
    'adept': 'adept',
    'inflection': 'inflection',
    'reka': 'reka',
    'you-com': 'you-com',
    'magic-ai': 'magic-ai',
    'reflection-ai': 'reflection-ai',
    'suno': 'suno',
    'stability-ai': 'stability-ai',
    'midjourney': 'midjourney',  # probably not Greenhouse
    'deepmind': 'deepmind',  # Google
    'meta-ai': 'meta',  # Meta
    'nvidia': 'nvidia',
    'microsoft-ai': 'microsoft',
    'google-ai': 'google',
    'aws-ai': 'amazon',
    'amazon-ai': 'amazon',
}

# More accurate board names based on known patterns
VERIFIED_BOARDS = {
    'anthropic': 'anthropic',
    'databricks': 'databricks',
    'xai': 'xai',
    'cohere': 'cohere',
    'mistral': 'mistral',
    'scale-ai': 'scale',
    'perplexity': 'perplexity',
    'character-ai': 'character',
    'runway': 'runway',
    'elevenlabs': 'elevenlabs',
    'adept': 'adept',
    'inflection': 'inflection',
    'reka': 'reka',
    'magic': 'magic',
    'reflection': 'reflection',
    'suno': 'suno',
    'stability': 'stability',
    'you': 'you',
    'modal': 'modal',
    'replicate': 'replicate',
    'baseten': 'baseten',
    'octoai': 'octoai',
    'together': 'together',
    'anything-ai': 'anything',
    'fixie': 'fixie',
    'langchain': 'langchain',
    'llamaindex': 'llamaindex',
    'weaviate': 'weaviate',
    'pinecone': 'pinecone',
    'chromadb': 'chroma',
    'qdrant': 'qdrant',
    'milvus': 'milvus',
    'zilliz': 'zilliz',
    'voyage': 'voyage',
    'cohere-ai': 'cohere',
    'huggingface': 'huggingface',
}


def get_jobs_from_greenhouse(board_name):
    """Fetch jobs from a Greenhouse board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_name}/jobs?content=true"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.load(response)
            return data.get('jobs', [])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # Board doesn't exist
        print(f"HTTP Error for {board_name}: {e.code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error fetching {board_name}: {e}", file=sys.stderr)
        return []


def filter_jobs(jobs, company_name):
    """Filter jobs relevant to our candidate profile."""
    if not jobs:
        return []
    
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
        'pytorch', 'jax', 'tensorflow', 'transformer', 'cuda',
        'kernel', 'compiler', 'runtime', 'verifier', 'reward',
        'process reward', 'outcome reward', 'curriculum',
        'long context', 'context window', 'context length',
        'mixture of experts', 'moe', 'speculative decoding',
        'tensorrt', 'vllm', 'tgi', 'trl', 'peft', 'lora',
        'qlora', 'fsdp', 'deepspeed', 'megatron', 'ray',
        'kubernetes', 'kubeflow', 'mlflow', 'wandb', 'tensorboard'
    ]
    
    # Exclude keywords - roles to avoid
    exclude_keywords = [
        'sales', 'account executive', 'recruiter', 'hr', 'human resources',
        'marketing', 'product manager', 'product marketing', 'operations',
        'finance', 'legal', 'security engineer', 'platform security',
        'it support', 'av engineer', 'data center', 'electrical',
        'mechanical', 'silicon', 'hardware', 'civil engineer',
        'fire protection', 'gas pipeline', 'power generation',
        'power system', 'protection & controls', 'osp engineer',
        'operational technology', 'facilities', 'critical facilities',
        'documentation control', 'energy & infrastructure',
        'safety trainer', 'bsa/aml', 'investigator', 'iam engineer',
        'support agent', 'support engineer', 'it systems',
        'it data', 'office', 'administrative', 'executive',
        'assistant', 'business systems', 'grc', 'corporate',
        'enterprise', 'manager', 'director', 'head of', 'lead',
        'principal', 'staff', 'staff+', 'staff engineer',
        'staff software', 'senior staff', 'architect',
        'evangelist', 'technical program', 'program manager',
        'strategy', 'solutions architect', 'forward deployed',
        'applied ai architect', 'applied ai security',
        'partner engineer', 'partner solutions', 'solutions engineer',
        'developer advocate', 'designated support', 'customer experience',
        'go-to-market', 'gtm', 'revenue', 'growth', 'campaign',
        'specialist', 'designer', 'content engineer', 'technical writer',
        'learning platform', 'education', 'university', 'recruiting',
        'people research', 'recruiter', 'talent',
        'data scientist', 'data analyst', 'analytics engineer',
        'data science', 'economist', 'economic research',
        'biology', 'chemistry', 'life sciences', 'bio',
        'chip design', 'hardware', 'kernel engineer',
        'mobile android', 'mobile ios', 'frontend', 'front-end',
        'web engineer', 'web products', 'android', 'ios',
        'fullstack', 'full-stack', 'backend', 'back-end',
        'database', 'ingestion', 'networking', 'observability',
        'security', 'fraud', 'financial', 'billing', 'money',
        'payments', 'subscriptions', 'ads', 'advertising',
        'consumer', 'subscriptions', 'voice model',
        'search ranking', 'search infrastructure',
        'real-time storage', 'platform infrastructure',
        'linux kernel', 'c++', 'rust', 'kernels/cuda',
        'network engineer', 'civil engineer', 'design engineer',
        'energy', 'transmission', 'distribution', 'pipeline',
        'battery storage', 'fire protection', 'safety'
    ]
    
    # Also exclude intern roles unless very specific
    intern_exclude = ['intern', 'internship', 'co-op', 'coop', 'fellow', 'fellowship']
    
    relevant = []
    for j in jobs:
        title_lower = j['title'].lower()
        
        # Skip internships
        if any(kw in title_lower for kw in intern_exclude):
            # Allow "Research Fellow" type roles but not general interns
            if not any(kw in title_lower for kw in ['research fellow', 'research scientist']):
                continue
        
        # Check if it has relevant keywords
        has_relevant = any(kw in title_lower for kw in keywords)
        # Check if it should be excluded
        is_excluded = any(kw in title_lower for kw in exclude_keywords)
        
        if has_relevant and not is_excluded:
            relevant.append(j)
    
    return relevant


def save_job_file(job, company_name):
    """Save a job to a markdown file."""
    import re
    from datetime import datetime
    from pathlib import Path
    
    def sanitize(text):
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text.strip('_')
    
    company = sanitize(company_name)
    title = sanitize(job.get('title', 'unknown_title'))
    job_id = job.get('id', 'unknown')
    
    filename = f"{company}__{title}__{job_id}.md"
    filepath = Path(HERMES_BASE / "job_research/job_descriptions") / filename
    
    # Parse HTML content to text
    import html
    content = job.get('content', '')
    content = html.unescape(content)
    # Remove HTML tags
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'\s+', ' ', content).strip()
    
    loc = job['location']['name'] if job.get('location') else 'Unknown'
    
    md_content = f"""# {job.get('title', 'Unknown Title')}

**Company:** {company_name}
**Location:** {loc}
**Remote/Hybrid/On-site:** {job.get('metadata', [{}])[0].get('value', 'Unknown') if job.get('metadata') else 'Unknown'}
**Job URL:** {job.get('absolute_url', 'Unknown')}
**Source:** Greenhouse
**Date Discovered:** {datetime.now().isoformat()}
**Date Posted:** {job.get('first_published', 'Unknown')}
**Date Updated:** {job.get('updated_at', 'Unknown')}
**Salary Range:** Not listed in API
**Team:** {', '.join([d['name'] for d in job.get('departments', [])]) if job.get('departments') else 'Not specified'}

---

## Full Job Description Text
{content}

---

*Saved on: {datetime.now().isoformat()}*
"""
    
    with open(filepath, "w") as f:
        f.write(md_content)
    
    return str(filepath)


def main():
    all_relevant = {}
    total_relevant = 0
    
    for board, name in VERIFIED_BOARDS.items():
        print(f"\nFetching {name} ({board})...", file=sys.stderr)
        jobs = get_jobs_from_greenhouse(board)
        
        if jobs is None:
            print(f"  Board not found (404)", file=sys.stderr)
            continue
        elif not jobs:
            print(f"  No jobs or error", file=sys.stderr)
            continue
        
        relevant = filter_jobs(jobs, name)
        print(f"  Total: {len(jobs)}, Relevant: {len(relevant)}", file=sys.stderr)
        
        if relevant:
            all_relevant[name] = relevant
            for j in relevant:
                loc = j['location']['name'] if j.get('location') else 'Unknown'
                print(f"  - {j['title']} | {loc} | {j['absolute_url']}")
                save_job_file(j, name)
            total_relevant += len(relevant)
        
        time.sleep(0.5)  # Rate limiting
    
    # Save summary
    with open(HERMES_BASE / 'job_research/data/greenhouse_summary.json', 'w') as f:
        # Save just summary info
        summary = {}
        for company, jobs in all_relevant.items():
            summary[company] = [
                {
                    'title': j['title'],
                    'location': j['location']['name'] if j.get('location') else 'Unknown',
                    'url': j['absolute_url'],
                    'posted': j.get('first_published'),
                    'updated': j.get('updated_at'),
                    'departments': [d['name'] for d in j.get('departments', [])]
                }
                for j in jobs
            ]
        json.dump(summary, f, indent=2)
    
    print(f"\n\nTotal companies with relevant jobs: {len(all_relevant)}", file=sys.stderr)
    print(f"Total relevant jobs: {total_relevant}", file=sys.stderr)


if __name__ == '__main__':
    main()