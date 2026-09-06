#!/usr/bin/env python3
"""
Analyze job market patterns from scored jobs.
Updated for new repository structure.
"""

import json
import re
from collections import Counter
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib
DATA_DIR = config_lib.data_root() / "job_research" / "data"
SCORED_JOBS_FILE = DATA_DIR / "scored_jobs.json"


def load_scored_jobs():
    with open(SCORED_JOBS_FILE, 'r') as f:
        return json.load(f)


def analyze_technical_skills(jobs):
    """Analyze frequency of technical skills in job descriptions."""
    skills = {
        'Python': 0, 'PyTorch': 0, 'JAX': 0, 'TensorFlow': 0,
        'Transformers': 0, 'Hugging Face': 0, 'CUDA': 0, 'Triton': 0,
        'Distributed Training': 0, 'Kubernetes': 0, 'Ray': 0, 'vLLM': 0,
        'TensorRT': 0, 'Inference Optimization': 0, 'RL': 0, 'PPO': 0,
        'GRPO': 0, 'DPO': 0, 'RLHF': 0, 'SFT': 0, 'Preference Optimization': 0,
        'RAG': 0, 'Agents': 0, 'Tool Calling': 0, 'Evaluation': 0,
        'Synthetic Data': 0, 'Multimodal Models': 0, 'Golang': 0, 'Go': 0,
        'DeepSpeed': 0, 'FSDP': 0, 'Megatron': 0, 'MLflow': 0,
        'WandB': 0, 'TensorBoard': 0, 'MLOps': 0, 'Docker': 0,
        'API': 0, 'REST': 0, 'gRPC': 0, 'Microservices': 0,
        'Observability': 0, 'Monitoring': 0, 'CI/CD': 0,
        'Model Serving': 0, 'Backend': 0, 'Distributed Systems': 0,
        'Data Pipelines': 0, 'GPU Systems': 0, 'Profiling': 0,
        'Production Deployment': 0, 'Search Infrastructure': 0,
        'Vector Database': 0, 'Retrieval': 0
    }
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower in text:
                skills[skill] += 1
    
    return skills


def analyze_research_skills(jobs):
    """Analyze research skill requirements."""
    skills = {
        'Publications Required': 0, 'First-Author Publications': 0,
        'Research Experience': 0, 'Implementing Papers': 0,
        'Designing Experiments': 0, 'Training Models': 0,
        'Evaluating Models': 0, 'Developing New Algorithms': 0,
        'Conducting Ablations': 0, 'Reproducing Papers': 0,
        'Large-Scale Compute': 0, 'Open-Source Contributions': 0,
        'PhD Required': 0, 'PhD Preferred': 0
    }
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        
        if 'phd' in text or 'ph.d' in text or 'doctorate' in text:
            if 'required' in text or 'must have' in text or 'minimum' in text:
                skills['PhD Required'] += 1
            else:
                skills['PhD Preferred'] += 1
        
        if 'publication' in text or 'published' in text:
            skills['Publications Required'] += 1
            if 'first author' in text or 'first-author' in text:
                skills['First-Author Publications'] += 1
        
        if 'research experience' in text:
            skills['Research Experience'] += 1
        if 'implement' in text and ('paper' in text or 'research' in text):
            skills['Implementing Papers'] += 1
        if 'design' in text and 'experiment' in text:
            skills['Designing Experiments'] += 1
        if 'train' in text and ('model' in text or 'llm' in text):
            skills['Training Models'] += 1
        if 'evaluat' in text and 'model' in text:
            skills['Evaluating Models'] += 1
        if 'new algorithm' in text or 'novel algorithm' in text or 'develop' in text and 'algorithm' in text:
            skills['Developing New Algorithms'] += 1
        if 'ablation' in text:
            skills['Conducting Ablations'] += 1
        if 'reproduc' in text and 'paper' in text:
            skills['Reproducing Papers'] += 1
        if 'large.scale' in text or 'large scale' in text or 'massive compute' in text or '10k' in text or '100k' in text:
            skills['Large-Scale Compute'] += 1
        if 'open source' in text or 'open-source' in text or 'oss' in text:
            skills['Open-Source Contributions'] += 1
    
    return skills


def analyze_agentic_skills(jobs):
    """Analyze agentic AI skill requirements."""
    skills = {
        'LangGraph': 0, 'LangChain': 0, 'AutoGen': 0, 'Custom Framework': 0,
        'Tool Calling': 0, 'Planning': 0, 'Memory': 0, 'Orchestration': 0,
        'Multi-Agent Systems': 0, 'Workflow Execution': 0,
        'Browser/Computer-Use Agents': 0, 'Code Agents': 0,
        'Agent Evaluation': 0, 'Long-Horizon Reasoning': 0,
        'RL for Agents': 0, 'Function Calling': 0, 'MCP': 0,
        'Prompt Engineering': 0, 'Guardrails': 0, 'Human-in-the-Loop': 0
    }
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower in text:
                skills[skill] += 1
    
    return skills


def analyze_training_post_training(jobs):
    """Analyze LLM training/post-training requirements."""
    skills = {
        'Pretraining': 0, 'SFT': 0, 'RLHF': 0, 'DPO': 0, 'GRPO': 0,
        'Reward Modeling': 0, 'Verifiers': 0, 'Process Rewards': 0,
        'Reasoning Models': 0, 'Synthetic Data': 0, 'Distillation': 0,
        'Curriculum Learning': 0, 'Evaluation': 0, 'Inference-Time Compute': 0,
        'RL Environments': 0, 'Alignment': 0, 'Post-Training': 0,
        'Fine-Tuning': 0, 'PEFT': 0, 'LoRA': 0, 'QLoRA': 0
    }
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower in text:
                skills[skill] += 1
    
    return skills


def analyze_engineering_skills(jobs):
    """Analyze engineering skill requirements."""
    skills = {
        'Distributed Systems': 0, 'Backend Engineering': 0,
        'Model Serving': 0, 'Inference': 0, 'ML Infrastructure': 0,
        'Data Pipelines': 0, 'Kubernetes': 0, 'Cloud Systems': 0,
        'GPU Systems': 0, 'Profiling': 0, 'Optimization': 0,
        'Production Deployment': 0, 'APIs': 0, 'Observability': 0,
        'Monitoring': 0, 'CI/CD': 0, 'Microservices': 0,
        'Scalable Systems': 0, 'High Throughput': 0, 'Low Latency': 0,
        'Rust': 0, 'C++': 0, 'SQL': 0, 'Linux': 0
    }
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower in text:
                skills[skill] += 1
    
    return skills


def analyze_degree_requirements(jobs):
    """Analyze degree requirements."""
    deg = {'PhD Required': 0, 'PhD Preferred': 0, 'M.S. Acceptable': 0, 
           'B.S. Acceptable': 0, 'No Degree Specified': 0}
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        
        if 'phd' in text or 'ph.d' in text or 'doctorate' in text:
            if 'required' in text or 'must have' in text or 'minimum' in text:
                deg['PhD Required'] += 1
            else:
                deg['PhD Preferred'] += 1
        elif 'master' in text or 'm.s.' in text or 'ms' in text or 'm.sc' in text:
            deg['M.S. Acceptable'] += 1
        elif 'bachelor' in text or 'b.s.' in text or 'bs' in text or 'b.sc' in text:
            deg['B.S. Acceptable'] += 1
        else:
            deg['No Degree Specified'] += 1
    
    return deg


def analyze_experience_levels(jobs):
    """Analyze experience level requirements."""
    exp_counts = Counter()
    
    for job in jobs:
        text = (job.get('title', '') + ' ' + job.get('full_jd_text', '')).lower()
        
        # Find experience requirements
        patterns = [
            r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
            r'minimum\s*(\d+)\s*years?',
            r'at least\s*(\d+)\s*years?',
            r'required.*?(\d+)\s*years?',
        ]
        
        found = False
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                try:
                    years = int(m)
                    if years <= 2:
                        exp_counts['0-2 years'] += 1
                    elif years <= 4:
                        exp_counts['3-4 years'] += 1
                    elif years <= 6:
                        exp_counts['5-6 years'] += 1
                    elif years <= 8:
                        exp_counts['7-8 years'] += 1
                    else:
                        exp_counts['8+ years'] += 1
                    found = True
                except:
                    pass
        
        if not found:
            exp_counts['Not Specified'] += 1
    
    return dict(exp_counts)


def analyze_role_distribution(jobs):
    """Analyze distribution of role types."""
    roles = Counter()
    
    role_keywords = {
        'Research Engineer': ['research engineer'],
        'Research Scientist': ['research scientist'],
        'Applied Scientist': ['applied scientist'],
        'ML Engineer': ['machine learning engineer', 'ml engineer'],
        'AI Engineer': ['ai engineer', 'applied ai engineer'],
        'Software Engineer': ['software engineer', 'backend engineer', 'fullstack', 'full-stack'],
        'Performance Engineer': ['performance engineer'],
        'Inference Engineer': ['inference engineer', 'model serving'],
        'Training Engineer': ['training engineer', 'pretraining'],
        'Post-Training Engineer': ['post-training', 'post training'],
        'RL Engineer': ['reinforcement learning', 'rl engineer'],
        'Agent Engineer': ['agent engineer', 'agentic'],
        'Data Engineer': ['data engineer'],
        'Infrastructure Engineer': ['infrastructure engineer', 'platform engineer'],
        'Other': []
    }
    
    for job in jobs:
        title = job.get('title', '').lower()
        matched = False
        for role, keywords in role_keywords.items():
            for kw in keywords:
                if kw in title:
                    roles[role] += 1
                    matched = True
                    break
            if matched:
                break
        if not matched:
            roles['Other'] += 1
    
    return dict(roles)


def analyze_company_distribution(jobs):
    """Analyze distribution by company."""
    return Counter(job.get('company', 'Unknown') for job in jobs)


def analyze_location_distribution(jobs):
    """Analyze distribution by location."""
    locs = Counter()
    for job in jobs:
        loc = job.get('location', 'Unknown')
        # Simplify location
        if 'san francisco' in loc.lower() or 'sf bay' in loc.lower() or 'bay area' in loc.lower():
            locs['San Francisco Bay Area'] += 1
        elif 'new york' in loc.lower() or 'nyc' in loc.lower():
            locs['New York City'] += 1
        elif 'seattle' in loc.lower():
            locs['Seattle'] += 1
        elif 'boston' in loc.lower():
            locs['Boston'] += 1
        elif 'atlanta' in loc.lower():
            locs['Atlanta'] += 1
        elif 'remote' in loc.lower() and 'united states' in loc.lower():
            locs['Remote-US'] += 1
        elif 'remote' in loc.lower():
            locs['Remote'] += 1
        elif 'london' in loc.lower() or 'uk' in loc.lower():
            locs['London/UK'] += 1
        elif 'zurich' in loc.lower() or 'zürich' in loc.lower():
            locs['Zürich'] += 1
        elif 'tokyo' in loc.lower():
            locs['Tokyo'] += 1
        elif 'singapore' in loc.lower():
            locs['Singapore'] += 1
        elif 'bengaluru' in loc.lower() or 'bangalore' in loc.lower():
            locs['Bengaluru'] += 1
        elif 'belgrade' in loc.lower():
            locs['Belgrade'] += 1
        elif 'mountain view' in loc.lower():
            locs['Mountain View'] += 1
        elif 'palo alto' in loc.lower():
            locs['Palo Alto'] += 1
        elif 'washington' in loc.lower() or 'dc' in loc.lower():
            locs['Washington DC'] += 1
        else:
            locs[loc] += 1
    return dict(locs)


def analyze_fit_scores(jobs):
    """Analyze fit score distribution."""
    scores = [job.get('fit_score', 0) for job in jobs]
    categories = Counter(job.get('interview_category', 'Unknown') for job in jobs)
    
    return {
        'mean': sum(scores) / len(scores) if scores else 0,
        'median': sorted(scores)[len(scores)//2] if scores else 0,
        'min': min(scores) if scores else 0,
        'max': max(scores) if scores else 0,
        'categories': dict(categories)
    }


def main():
    jobs = load_scored_jobs()
    print(f"Analyzing {len(jobs)} jobs...")
    
    # Run all analyses
    tech_skills = analyze_technical_skills(jobs)
    research_skills = analyze_research_skills(jobs)
    agentic_skills = analyze_agentic_skills(jobs)
    training_skills = analyze_training_post_training(jobs)
    engineering_skills = analyze_engineering_skills(jobs)
    degree_reqs = analyze_degree_requirements(jobs)
    exp_levels = analyze_experience_levels(jobs)
    role_dist = analyze_role_distribution(jobs)
    company_dist = analyze_company_distribution(jobs)
    location_dist = analyze_location_distribution(jobs)
    fit_stats = analyze_fit_scores(jobs)
    
    # Save all analyses
    analysis = {
        'total_jobs': len(jobs),
        'technical_skills': dict(sorted(tech_skills.items(), key=lambda x: -x[1])),
        'research_skills': dict(sorted(research_skills.items(), key=lambda x: -x[1])),
        'agentic_skills': dict(sorted(agentic_skills.items(), key=lambda x: -x[1])),
        'training_post_training': dict(sorted(training_skills.items(), key=lambda x: -x[1])),
        'engineering_skills': dict(sorted(engineering_skills.items(), key=lambda x: -x[1])),
        'degree_requirements': degree_reqs,
        'experience_levels': exp_levels,
        'role_distribution': role_dist,
        'company_distribution': dict(company_dist),
        'location_distribution': location_dist,
        'fit_score_stats': fit_stats
    }
    
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / 'market_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    # Print key findings
    print("\n=== TECHNICAL SKILLS (Top 20) ===")
    for skill, count in sorted(tech_skills.items(), key=lambda x: -x[1])[:20]:
        pct = count / len(jobs) * 100
        print(f"  {skill}: {count} ({pct:.1f}%)")
    
    print("\n=== RESEARCH SKILLS ===")
    for skill, count in sorted(research_skills.items(), key=lambda x: -x[1]):
        pct = count / len(jobs) * 100
        print(f"  {skill}: {count} ({pct:.1f}%)")
    
    print("\n=== AGENTIC AI SKILLS ===")
    for skill, count in sorted(agentic_skills.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / len(jobs) * 100
            print(f"  {skill}: {count} ({pct:.1f}%)")
    
    print("\n=== TRAINING/POST-TRAINING SKILLS ===")
    for skill, count in sorted(training_skills.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / len(jobs) * 100
            print(f"  {skill}: {count} ({pct:.1f}%)")
    
    print("\n=== ENGINEERING SKILLS (Top 20) ===")
    for skill, count in sorted(engineering_skills.items(), key=lambda x: -x[1])[:20]:
        pct = count / len(jobs) * 100
        print(f"  {skill}: {count} ({pct:.1f}%)")
    
    print("\n=== DEGREE REQUIREMENTS ===")
    for deg, count in degree_reqs.items():
        pct = count / len(jobs) * 100
        print(f"  {deg}: {count} ({pct:.1f}%)")
    
    print("\n=== EXPERIENCE LEVELS ===")
    for exp, count in sorted(exp_levels.items(), key=lambda x: -x[1]):
        pct = count / len(jobs) * 100
        print(f"  {exp}: {count} ({pct:.1f}%)")
    
    print("\n=== ROLE DISTRIBUTION ===")
    for role, count in sorted(role_dist.items(), key=lambda x: -x[1]):
        pct = count / len(jobs) * 100
        print(f"  {role}: {count} ({pct:.1f}%)")
    
    print("\n=== COMPANY DISTRIBUTION ===")
    for company, count in sorted(company_dist.items(), key=lambda x: -x[1]):
        pct = count / len(jobs) * 100
        print(f"  {company}: {count} ({pct:.1f}%)")
    
    print("\n=== LOCATION DISTRIBUTION ===")
    for loc, count in sorted(location_dist.items(), key=lambda x: -x[1]):
        pct = count / len(jobs) * 100
        print(f"  {loc}: {count} ({pct:.1f}%)")
    
    print(f"\n=== FIT SCORE STATS ===")
    print(f"  Mean: {fit_stats['mean']:.1f}")
    print(f"  Median: {fit_stats['median']:.1f}")
    print(f"  Min: {fit_stats['min']}")
    print(f"  Max: {fit_stats['max']}")
    print(f"  Categories: {fit_stats['categories']}")
    
    print("\nAnalysis saved to market_analysis.json")


if __name__ == '__main__':
    main()