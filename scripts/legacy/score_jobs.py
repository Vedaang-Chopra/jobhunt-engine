#!/usr/bin/env python3
"""
Score and analyze collected jobs against candidate profile.
Updated for new repository structure.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

# Repository root
try:
    from scripts import config_lib
except ImportError:
    import config_lib
DATA = config_lib.data_root()
REPO_ROOT = Path(__file__).parent.parent
JOBS_DIR = DATA / "tracking" / "job_descriptions" / "active"
DATA_DIR = DATA / "job_research" / "data"
CONFIG_DIR = DATA / "job_research" / "config"

CANDIDATE_PROFILE = {
    "education": "M.S. Computer Science, Machine Learning specialization, Georgia Tech (Dec 2026)",
    "experience_years": "4+ years professional software/ML engineering",
    "research_focus": [
        "LLM post-training", "reinforcement learning", "program synthesis / code generation",
        "agentic AI systems", "multimodal models", "model routing",
        "tool-using agents", "iterative execution, evaluation, and repair"
    ],
    "production_experience": [
        "ML systems", "backend/distributed systems", "production AI systems",
        "RAG / agentic workflows", "APIs and tool calling",
        "search/retrieval infrastructure", "Python", "Golang"
    ],
    "target_graduation": "December 2026",
    "target_start": "December 2026 / early 2027",
    "preferred_locations": ["US", "Remote-US", "SF Bay Area", "NYC", "Seattle", "Boston", "Atlanta"],
    "primary_roles": [
        "Research Engineer — LLMs / Agents / Reasoning",
        "Research Engineer — Post-training / RL / RLHF / Alignment",
        "Applied Scientist — LLM / Generative AI",
        "Applied AI Engineer / AI Engineer",
        "Agentic AI Engineer",
        "Machine Learning Engineer — LLM / Generative AI",
        "LLM Training / Post-Training Engineer",
        "Research Software Engineer — AI/ML",
        "ML Systems Engineer (training/inference focused)",
        "Multimodal Research Engineer",
        "Inference / Model Optimization Engineer (ML-heavy)"
    ],
    "avoid_roles": [
        "generic data scientist", "data analyst", "BI / analytics",
        "traditional backend", "frontend", "DevOps/SRE",
        "pure MLOps/platform", "classical ML only",
        "sales engineering", "solutions architect", "AI product management",
        "8-10+ years specialized exp required", "PhD required (no equiv)",
        "internships", "CV apps unrelated to multimodal FMs",
        "external LLM API only roles"
    ]
}

# Scoring weights
WEIGHTS = {
    "technical_skill_overlap": 25,
    "research_domain_overlap": 20,
    "production_engineering_overlap": 15,
    "experience_level_compatibility": 15,
    "education_research_compatibility": 10,
    "project_demonstration_potential": 10,
    "location_start_date_practicality": 5
}

INTERVIEW_CATEGORIES = {
    "Strong target": (85, 100),
    "Good target": (70, 84),
    "Stretch but worthwhile": (55, 69),
    "Very high stretch": (40, 54),
    "Not worth applying": (0, 39)
}


def load_jobs_from_descriptions():
    """Load all job description markdown files and extract structured data."""
    jobs = []
    
    for md_file in JOBS_DIR.glob("*.md"):
        with open(md_file, 'r') as f:
            content = f.read()
        
        # Parse the markdown to extract fields
        job = parse_job_markdown(content, md_file.name)
        jobs.append(job)
    
    return jobs


def parse_job_markdown(content, filename):
    """Parse job markdown file into structured dict."""
    job = {
        "filename": filename,
        "title": "Unknown",
        "company": "Unknown",
        "location": "Unknown",
        "work_type": "Unknown",
        "url": "Unknown",
        "source": "Unknown",
        "date_discovered": "Unknown",
        "date_posted": "Unknown",
        "date_updated": "Unknown",
        "salary": "Not listed",
        "team": "Not specified",
        "full_jd_text": "",
        "scored": False
    }
    
    lines = content.split('\n')
    in_jd = False
    jd_lines = []
    
    for line in lines:
        if line.startswith('# '):
            job['title'] = line[2:].strip()
        elif line.startswith('**Company:**'):
            job['company'] = line.replace('**Company:**', '').strip()
        elif line.startswith('**Location:**'):
            job['location'] = line.replace('**Location:**', '').strip()
        elif line.startswith('**Remote/Hybrid/On-site:**'):
            job['work_type'] = line.replace('**Remote/Hybrid/On-site:**', '').strip()
        elif line.startswith('**Job URL:**'):
            job['url'] = line.replace('**Job URL:**', '').strip()
        elif line.startswith('**Source:**'):
            job['source'] = line.replace('**Source:**', '').strip()
        elif line.startswith('**Date Discovered:**'):
            job['date_discovered'] = line.replace('**Date Discovered:**', '').strip()
        elif line.startswith('**Date Posted:**'):
            job['date_posted'] = line.replace('**Date Posted:**', '').strip()
        elif line.startswith('**Date Updated:**'):
            job['date_updated'] = line.replace('**Date Updated:**', '').strip()
        elif line.startswith('**Salary Range:**'):
            job['salary'] = line.replace('**Salary Range:**', '').strip()
        elif line.startswith('**Team:**'):
            job['team'] = line.replace('**Team:**', '').strip()
        elif line.startswith('## Full Job Description Text'):
            in_jd = True
            continue
        elif line.startswith('---') and in_jd:
            in_jd = False
            continue
        elif in_jd:
            jd_lines.append(line)
    
    job['full_jd_text'] = '\n'.join(jd_lines).strip()
    return job


def score_job(job):
    """Score a job against candidate profile."""
    title = job.get('title', '').lower()
    location = job.get('location', '').lower()
    work_type = job.get('work_type', '').lower()
    full_jd = job.get('full_jd_text', '').lower()
    team = job.get('team', '').lower()
    
    # Combine all text for analysis
    all_text = f"{title} {full_jd} {team}"
    
    scores = {}
    reasons = []
    gaps = []
    
    # 1. Technical Skill Overlap (25 points)
    tech_keywords = {
        'pytorch': 3, 'python': 2, 'golang': 2, 'go': 1, 'cuda': 2,
        'transformers': 3, 'hugging face': 2, 'huggingface': 2,
        'jax': 2, 'tensorflow': 1, 'ray': 2, 'vllm': 3,
        'tensorrt': 2, 'triton': 2, 'deepspeed': 2, 'fsdp': 2,
        'megatron': 2, 'kubernetes': 1, 'docker': 1,
        'distributed training': 3, 'distributed systems': 2,
        'model serving': 2, 'inference': 2, 'optimization': 2,
        'profiling': 1, 'mlops': 1, 'ml infrastructure': 2,
        'data pipelines': 1, 'api': 1, 'rest': 1, 'grpc': 1
    }
    
    tech_score = 0
    tech_found = []
    for kw, weight in tech_keywords.items():
        if kw in all_text:
            tech_score += weight
            tech_found.append(kw)
    
    scores['technical_skill_overlap'] = min(25, tech_score)
    if tech_found:
        reasons.append(f"Technical skills match: {', '.join(tech_found[:10])}")
    
    # 2. Research/Domain Overlap (20 points)
    research_keywords = {
        'post-training': 3, 'post training': 3, 'rlhf': 3, 'dpo': 3,
        'grpo': 3, 'ppo': 2, 'sft': 2, 'reinforcement learning': 3,
        'rl': 2, 'alignment': 2, 'reasoning': 3, 'agents': 3,
        'agentic': 3, 'tool use': 2, 'tool calling': 2, 'function calling': 2,
        'multimodal': 3, 'foundation model': 2, 'foundation models': 2,
        'llm': 2, 'large language model': 2, 'pretraining': 2,
        'fine-tuning': 2, 'fine tuning': 2, 'distillation': 2,
        'synthetic data': 2, 'evaluation': 2, 'benchmark': 2,
        'interpretability': 2, 'safety': 1, 'red team': 1,
        'reward model': 2, 'process reward': 2, 'verifier': 2,
        'code generation': 2, 'program synthesis': 3,
        'computer use': 2, 'browser use': 1, 'long horizon': 2,
        'planning': 2, 'memory': 1, 'orchestration': 2,
        'model routing': 2, 'mixture of experts': 2, 'moe': 2
    }
    
    research_score = 0
    research_found = []
    for kw, weight in research_keywords.items():
        if kw in all_text:
            research_score += weight
            research_found.append(kw)
    
    scores['research_domain_overlap'] = min(20, research_score)
    if research_found:
        reasons.append(f"Research/domain match: {', '.join(research_found[:10])}")
    
    # 3. Production Engineering Overlap (15 points)
    prod_keywords = {
        'production': 2, 'production ai': 2, 'production ml': 2,
        'ml systems': 2, 'backend': 1, 'distributed systems': 2,
        'scalable': 1, 'high throughput': 1, 'low latency': 1,
        'api': 1, 'microservices': 1, 'ci/cd': 1, 'monitoring': 1,
        'observability': 1, 'deployment': 1, 'kubernetes': 1,
        'rag': 2, 'retrieval': 2, 'vector database': 1,
        'search infrastructure': 2, 'data engineering': 1
    }
    
    prod_score = 0
    prod_found = []
    for kw, weight in prod_keywords.items():
        if kw in all_text:
            prod_score += weight
            prod_found.append(kw)
    
    scores['production_engineering_overlap'] = min(15, prod_score)
    if prod_found:
        reasons.append(f"Production engineering match: {', '.join(prod_found[:8])}")
    
    # 4. Experience Level Compatibility (15 points)
    # Check for experience requirements
    exp_score = 15  # Default full score
    exp_text = ""
    
    # Look for experience mentions
    exp_patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
        r'minimum\s*(\d+)\s*years?',
        r'at least\s*(\d+)\s*years?',
        r'required.*?(\d+)\s*years?',
    ]
    
    min_years = 0
    for pattern in exp_patterns:
        matches = re.findall(pattern, all_text)
        for m in matches:
            try:
                years = int(m)
                if years > min_years:
                    min_years = years
            except:
                pass
    
    if min_years > 0:
        exp_text = f"Requires {min_years}+ years experience"
        if min_years <= 4:
            exp_score = 15
        elif min_years <= 6:
            exp_score = 12
        elif min_years <= 8:
            exp_score = 8
        else:
            exp_score = 5
            gaps.append(f"Requires {min_years}+ years experience (candidate has 4+)")
    else:
        exp_text = "No explicit years requirement found"
        exp_score = 12  # Slightly lower if unspecified
    
    scores['experience_level_compatibility'] = exp_score
    if exp_text:
        reasons.append(exp_text)
    
    # 5. Education/Research Compatibility (10 points)
    edu_score = 10  # Default - M.S. from Georgia Tech ML is strong
    edu_text = ""
    
    if 'phd' in all_text or 'ph.d' in all_text or 'doctorate' in all_text:
        if 'required' in all_text or 'must have' in all_text or 'minimum' in all_text:
            edu_score = 5
            gaps.append("PhD required (candidate has M.S.)")
            edu_text = "PhD required"
        else:
            edu_score = 8
            edu_text = "PhD preferred but not required"
    else:
        edu_text = "M.S. or equivalent acceptable"
    
    if 'publication' in all_text or 'published' in all_text:
        if 'first author' in all_text or 'first-author' in all_text:
            edu_score = min(edu_score, 8)
            gaps.append("First-author publications preferred")
        else:
            edu_text += "; publications mentioned"
    
    scores['education_research_compatibility'] = edu_score
    reasons.append(edu_text)
    
    # 6. Project Demonstration Potential (10 points)
    # How well can candidate demonstrate required skills with existing projects
    project_keywords = {
        'post-training': 2, 'rlhf': 2, 'dpo': 2, 'grpo': 2,
        'rl': 2, 'reinforcement learning': 2,
        'agents': 2, 'agentic': 2, 'tool use': 2,
        'multimodal': 2, 'code generation': 2, 'program synthesis': 2,
        'model evaluation': 2, 'synthetic data': 1,
        'distributed training': 1, 'inference optimization': 1,
        'model serving': 1, 'rag': 1
    }
    
    project_score = 5  # Base score
    project_matches = []
    for kw, weight in project_keywords.items():
        if kw in all_text:
            project_score += weight
            project_matches.append(kw)
    
    scores['project_demonstration_potential'] = min(10, project_score)
    if project_matches:
        reasons.append(f"Project demonstration potential for: {', '.join(project_matches[:8])}")
    
    # 7. Location/Start Date Practicality (5 points)
    loc_score = 5
    loc_text = ""
    
    # Check if location matches preferences
    preferred_locs = ['san francisco', 'sf bay', 'bay area', 'new york', 'nyc', 
                      'seattle', 'boston', 'atlanta', 'remote', 'united states', 'us']
    avoid_locs = ['london', 'uk', 'europe', 'asia', 'tokyo', 'zürich', 'zurich', 
                  'singapore', 'india', 'bengaluru', 'belgrade', 'dublin', 'paris',
                  'munich', 'berlin', 'amsterdam', 'australia', 'sydney']
    
    location_match = False
    for pl in preferred_locs:
        if pl in location or pl in work_type:
            location_match = True
            break
    
    if location_match:
        loc_score = 5
        loc_text = "Location matches preference"
    else:
        # Check if it's an avoided location
        for al in avoid_locs:
            if al in location:
                loc_score = 1
                loc_text = f"Location not preferred: {location}"
                gaps.append(f"Location mismatch: {location}")
                break
        if loc_score == 5:
            loc_score = 3
            loc_text = f"Location neutral: {location}"
    
    scores['location_start_date_practicality'] = loc_score
    reasons.append(loc_text)
    
    # Calculate total
    total_score = sum(scores.values())
    
    # Determine interview category
    interview_category = "Not worth applying"
    for cat, (low, high) in INTERVIEW_CATEGORIES.items():
        if low <= total_score <= high:
            interview_category = cat
            break
    
    # Determine biggest gap
    biggest_gap = gaps[0] if gaps else "No major gaps identified"
    
    # Why it fits
    why_fits = "; ".join(reasons[:5])
    
    return {
        "fit_score": total_score,
        "interview_category": interview_category,
        "component_scores": scores,
        "why_fits": why_fits,
        "biggest_gap": biggest_gap,
        "gaps": gaps,
        "reasons": reasons
    }


def main():
    print("Loading jobs from descriptions...")
    jobs = load_jobs_from_descriptions()
    print(f"Loaded {len(jobs)} jobs")
    
    # Score each job
    scored_jobs = []
    for job in jobs:
        if not job.get('scored', False):
            scoring = score_job(job)
            job.update(scoring)
            job['scored'] = True
        scored_jobs.append(job)
    
    # Sort by fit score descending
    scored_jobs.sort(key=lambda x: x.get('fit_score', 0), reverse=True)
    
    # Save scored jobs
    output_file = DATA_DIR / "scored_jobs.json"
    DATA_DIR.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(scored_jobs, f, indent=2)
    
    # Print summary
    print(f"\n=== SCORING SUMMARY ===")
    print(f"Total jobs scored: {len(scored_jobs)}")
    
    # Count by category
    cat_counts = {}
    for job in scored_jobs:
        cat = job.get('interview_category', 'Unknown')
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    for cat in ["Strong target", "Good target", "Stretch but worthwhile", "Very high stretch", "Not worth applying"]:
        if cat in cat_counts:
            print(f"  {cat}: {cat_counts[cat]}")
    
    # Top 20 jobs
    print(f"\n=== TOP 20 JOBS ===")
    for i, job in enumerate(scored_jobs[:20]):
        print(f"{i+1}. [{job['fit_score']}] {job['title']} @ {job['company']} ({job['location']}) - {job['interview_category']}")
        print(f"    Gap: {job['biggest_gap']}")
        print(f"    Why: {job['why_fits'][:150]}...")
        print()
    
    print(f"\nSaved scored jobs to {output_file}")


if __name__ == '__main__':
    main()