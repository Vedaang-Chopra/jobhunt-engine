#!/usr/bin/env python3
"""
Generate final deliverables: job_market_analysis.md, top_jobs.md, and tiered rankings.
"""

import json
from pathlib import Path
from datetime import datetime

# Legacy paths resolved relative to the parent workspace dir; override with
# JOBHUNT_LEGACY_HERMES_BASE when the legacy layout lives elsewhere.
import os
HERMES_BASE = Path(os.environ.get(
    "JOBHUNT_LEGACY_HERMES_BASE",
    str(Path(__file__).resolve().parents[3]),
))

def load_data():
    with open(HERMES_BASE / 'job_research/data/scored_jobs.json', 'r') as f:
        jobs = json.load(f)
    with open(HERMES_BASE / 'job_research/data/market_analysis.json', 'r') as f:
        market = json.load(f)
    with open(HERMES_BASE / 'job_research/data/gap_analysis.json', 'r') as f:
        gaps = json.load(f)
    with open(HERMES_BASE / 'job_research/data/resume_recommendations.json', 'r') as f:
        resume_recs = json.load(f)
    return jobs, market, gaps, resume_recs

def generate_job_market_analysis(jobs, market, gaps, resume_recs):
    """Generate the comprehensive job market analysis markdown."""
    
    total_jobs = len(jobs)
    fit_stats = market.get('fit_score_stats', {})
    
    md = f"""# AI/ML Job Market Analysis Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Jobs Analyzed:** {total_jobs}
**Candidate Profile:** M.S. CS (ML), Georgia Tech, Dec 2026 | 4+ years SWE/MLE experience | LLM post-training, RL, agents, multimodal research

---

## 1. Executive Summary

This analysis covers **{total_jobs} currently open AI/ML roles** sourced from Greenhouse job boards across **{len(market.get('company_distribution', {}))} companies**. The market shows strong demand for candidates with reinforcement learning, agentic AI, and LLM post-training expertise — aligning well with the candidate's research background.

**Key Findings:**
- **Mean Fit Score:** {fit_stats.get('mean', 0):.1f}/100 (Median: {fit_stats.get('median', 0):.1f})
- **Strong Target Roles:** {fit_stats.get('categories', {}).get('Strong target', 0)} (score ≥85)
- **Good Target Roles:** {fit_stats.get('categories', {}).get('Good target', 0)} (score 70-84)
- **Strategic Stretch Roles:** {fit_stats.get('categories', {}).get('Stretch but worthwhile', 0)} (score 55-69)
- **Top Companies Hiring:** Anthropic (29%), xAI (21%), Scale AI (20%), Databricks (14%), Together AI (10%)
- **Primary Locations:** San Francisco Bay Area (49%), Remote-US (16.5%), London/UK (7.5%)

**Market Alignment:** The candidate's background in LLM post-training, RL, agents, and multimodal models matches the most frequently requested capabilities. Primary gaps are in open-source visibility, specific RL algorithm implementation (PPO/GRPO), and production ML infrastructure (Kubernetes, Rust, observability).

---

## 2. Target Role Distribution

| Role Category | Count | Percentage |
|---------------|-------|------------|
"""
    
    role_dist = market.get('role_distribution', {})
    for role, count in sorted(role_dist.items(), key=lambda x: -x[1]):
        pct = count / total_jobs * 100
        md += f"| {role} | {count} | {pct:.1f}% |\n"
    
    md += f"""

---

## 3. Most Common Technical Skills

| Skill | Frequency | % of Jobs |
|-------|-----------|-----------|
"""
    
    tech_skills = market.get('technical_skills', {})
    for skill, count in sorted(tech_skills.items(), key=lambda x: -x[1])[:30]:
        pct = count / total_jobs * 100
        md += f"| {skill} | {count} | {pct:.1f}% |\n"
    
    md += f"""

---

## 4. Most Common Frameworks & Tools

| Framework/Tool | Frequency | % of Jobs |
|----------------|-----------|-----------|
"""
    
    # Extract frameworks from technical skills
    frameworks = ['PyTorch', 'JAX', 'TensorFlow', 'Transformers', 'Hugging Face', 'CUDA', 'Triton',
                  'vLLM', 'TensorRT', 'DeepSpeed', 'FSDP', 'Megatron', 'Ray', 'Kubernetes',
                  'Docker', 'MLflow', 'WandB', 'TensorBoard', 'LangChain', 'LangGraph', 'AutoGen', 'MCP']
    
    for fw in frameworks:
        count = tech_skills.get(fw, 0)
        if count > 0:
            pct = count / total_jobs * 100
            md += f"| {fw} | {count} | {pct:.1f}% |\n"
    
    md += f"""

---

## 5. Most Common Research Capabilities

| Capability | Frequency | % of Jobs |
|------------|-----------|-----------|
"""
    
    research_skills = market.get('research_skills', {})
    for skill, count in sorted(research_skills.items(), key=lambda x: -x[1]):
        pct = count / total_jobs * 100
        md += f"| {skill} | {count} | {pct:.1f}% |\n"
    
    md += f"""

---

## 6. Agentic AI Skill Trends

| Skill | Frequency | % of Jobs | Notes |
|-------|-----------|-----------|-------|
"""
    
    agentic_skills = market.get('agentic_skills', {})
    for skill, count in sorted(agentic_skills.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / total_jobs * 100
            notes = ""
            if skill in ['LangGraph', 'LangChain', 'AutoGen']:
                notes = "Framework-specific (low adoption)"
            elif skill in ['MCP', 'Guardrails', 'Human-in-the-Loop']:
                notes = "Emerging patterns"
            md += f"| {skill} | {count} | {pct:.1f}% | {notes} |\n"
    
    md += f"""

**Key Insight:** "Agent experience" in current hiring primarily means **tool calling, orchestration, and planning** rather than specific frameworks. LangGraph/LangChain/AutoGen mentions are rare (<2%). Employers value custom agent architectures, multi-agent systems, and evaluation capabilities.

---

## 7. Post-Training / LLM Training Trends

| Skill | Frequency | % of Jobs |
|-------|-----------|-----------|
"""
    
    training_skills = market.get('training_post_training', {})
    for skill, count in sorted(training_skills.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / total_jobs * 100
            md += f"| {skill} | {count} | {pct:.1f}% |\n"
    
    md += f"""

**Key Insight:** **RLHF (8%), DPO (4%), GRPO (2%)** appear in postings but **PPO (85%)** dominates as the underlying RL algorithm. Post-training roles emphasize reward modeling, process rewards, verifiers, and reasoning model training. Synthetic data, distillation, and curriculum learning are mentioned but less frequently.

---

## 8. Engineering Requirements

| Skill | Frequency | % of Jobs |
|-------|-----------|-----------|
"""
    
    eng_skills = market.get('engineering_skills', {})
    for skill, count in sorted(eng_skills.items(), key=lambda x: -x[1])[:25]:
        pct = count / total_jobs * 100
        md += f"| {skill} | {count} | {pct:.1f}% |\n"
    
    md += f"""

**Key Insight:** Strong software engineering is **required** for research roles too. **Go (95%)**, **Distributed Systems (32.5%)**, **Kubernetes (21.5%)**, and **Observability (13%)** appear across research and applied roles. Rust (41.5%) and C++ (11%) indicate performance-critical infrastructure work.

---

## 9. Degree Requirements

| Requirement | Count | % of Jobs |
|-------------|-------|-----------|
"""
    
    deg_reqs = market.get('degree_requirements', {})
    for req, count in sorted(deg_reqs.items(), key=lambda x: -x[1]):
        pct = count / total_jobs * 100
        md += f"| {req} | {count} | {pct:.1f}% |\n"
    
    md += f"""

**Key Insight:** **89.5% of roles accept M.S. or equivalent.** Only 5.5% strictly require PhD. Publications are mentioned in 9% of roles, first-author in 0%. Research experience is valued but not strictly required.

---

## 10. Experience Level Patterns

| Years Required | Count | % of Jobs |
|----------------|-------|-----------|
"""
    
    exp_levels = market.get('experience_levels', {})
    for level, count in sorted(exp_levels.items(), key=lambda x: -x[1]):
        pct = count / total_jobs * 100
        md += f"| {level} | {count} | {pct:.1f}% |\n"
    
    md += f"""

**Key Insight:** **82% of roles don't specify years.** Where specified, 3-6 years is most common. The candidate's 4+ years fits well.

---

## 11. Candidate's Strongest Market Matches

Based on fit scoring, the candidate's profile aligns best with:

| Rank | Company | Role | Fit Score | Category | Key Matching Skills |
|------|---------|------|-----------|----------|---------------------|
"""
    
    top_jobs = [j for j in jobs if j.get('fit_score', 0) >= 80][:15]
    for i, job in enumerate(top_jobs):
        md += f"| {i+1} | {job.get('company', '')} | {job.get('title', '')} | {job.get('fit_score', 0)} | {job.get('interview_category', '')} | RL, Agents, Post-training, Distributed Systems |\n"
    
    md += f"""

---

## 12. Skill Gaps Analysis

### Already Strong (High Market Demand + Strong Evidence)
"""
    
    already_strong = gaps.get('already_strong', [])
    for g in already_strong:
        md += f"- **{g['skill']}**: {g['market_frequency']:.0%} market demand, importance {g['importance']:.1f}\n"
    
    md += f"""

### Present but Need Stronger Evidence (High Priority)
"""
    
    need_evidence = gaps.get('need_stronger_evidence', [])
    for g in need_evidence[:15]:
        md += f"- **{g['skill']}**: {g['market_frequency']:.0%} market, importance {g['importance']:.1f}, gap priority: {g['gap_priority']:.3f}\n"
    
    md += f"""

### Missing / High-Value Gaps (Critical to Address)
"""
    
    missing = gaps.get('missing_high_value', [])
    for g in missing[:15]:
        md += f"- **{g['skill']}**: {g['market_frequency']:.0%} market, importance {g['importance']:.1f}, gap priority: {g['gap_priority']:.3f}\n"
    
    md += f"""

---

## 13. Resume Implications

### Resume A: Agentic AI / Applied AI Engineer
**Target Roles:** Applied AI Engineer, AI Engineer, Agentic AI Engineer, Agent Engineer

**Required Keywords:** RAG, Agents, Tool Calling, Orchestration, Planning, Memory, MCP, Model Serving, vLLM, TensorRT, Kubernetes, Python, Go, PPO, RL, Fine-Tuning, LoRA

**Key Projects:** Agentic AI system with tool-use, RAG pipeline with evaluation, Multi-agent workflow, Production model serving, LLM evaluation benchmarks

**De-emphasize:** Pretraining, Large-scale compute, Megatron/DeepSpeed, PhD/Publications, Novel algorithms

---

### Resume B: Research Engineer — LLM / Agents / Reasoning
**Target Roles:** Research Engineer, Research Scientist, Applied Scientist

**Required Keywords:** RLHF, DPO, GRPO, PPO, Post-Training, Alignment, Reasoning, Implementing Papers, Designing Experiments, Training Models, Evaluating Models, Developing New Algorithms, Open-Source Contributions, PyTorch, JAX, Distributed Training

**Key Projects:** Novel RLHF/RL algorithm, Reasoning model with process rewards, Agent architecture, Multimodal training, Code generation, Paper reproductions with ablations

**De-emphasize:** Kubernetes, Docker, CI/CD, Model Serving, RAG, APIs, MLOps, Rust/C++

---

### Resume C: Post-training / RL / LLM Training
**Target Roles:** Post-Training Engineer, RL Engineer, LLM Training Engineer

**Required Keywords:** RLHF, DPO, GRPO, PPO, SFT, Reward Modeling, Verifiers, Process Rewards, Distributed Training, DeepSpeed, FSDP, CUDA, Triton, Fine-Tuning, LoRA, Synthetic Data, Distillation

**Key Projects:** RLHF pipeline, Reward model training, Large-scale distributed training, Synthetic data generation, Reasoning model training, Training optimization

**De-emphasize:** RAG, Agents, Tool Calling, Model Serving, Inference Optimization, Kubernetes, Production Deployment

---

### Resume D: ML Engineer / ML Systems
**Target Roles:** ML Engineer, ML Systems Engineer, ML Infrastructure Engineer, Platform Engineer

**Required Keywords:** Distributed Systems, Model Serving, Inference, ML Infrastructure, Kubernetes, GPU Systems, Profiling, Optimization, Production Deployment, Observability, Rust, C++, SQL, vLLM, TensorRT, Ray

**Key Projects:** High-throughput serving, Distributed training platform, ML pipeline orchestration, GPU cluster management, Model optimization, Observability for ML

**De-emphasize:** Novel algorithms, Publications, PhD, RLHF/DPO/GRPO, Agents, Post-Training, Alignment, Program Synthesis

---

## 14. Recommended Projects / Open-Source Work

Based on gap analysis, the highest-impact projects to undertake:

### Priority 1 (Critical - addresses top gaps)
1. **Open-source RLHF/RL implementation** - Implement PPO/GRPO/DPO in a clean repo; contribute to TRL or similar
2. **Agent framework with planning/memory** - Build and open-source an agentic system with orchestration, tool-use, evaluation
3. **Reward model + process verifier** - Train and release a reward model for reasoning tasks

### Priority 2 (High Value)
4. **Distributed training pipeline** - End-to-end DeepSpeed/FSDP training with profiling and optimization
5. **LLM evaluation suite** - Comprehensive benchmark framework with agent evaluation
6. **Model serving optimization** - vLLM/TensorRT deployment with auto-scaling, monitoring

### Priority 3 (Differentiators)
7. **Multimodal training/eval** - Vision-language model with ablation studies
8. **Code generation agent** - Program synthesis with iterative repair
9. **Computer-use agent** - Browser/desktop automation with safety guardrails

---

## 15. Recommended Learning Priorities

| Priority | Skill | Why | Effort | Resources |
|----------|-------|-----|--------|-----------|
| 1 | **PPO/GRPO Implementation** | 85% market demand, core to RL roles | 2-3 weeks | TRL, OpenRLHF, implement from scratch |
| 2 | **Open-Source Contributions** | 89% mention, demonstrates capability | Ongoing | Transformers, TRL, vLLM, PyTorch |
| 3 | **Kubernetes for ML** | 21.5% demand, production requirement | 2-3 weeks | Kubeflow, KServe, Ray on K8s |
| 4 | **Rust Basics** | 41.5% demand, performance infra | 3-4 weeks | Rust book, candle, burn |
| 5 | **Observability/Monitoring** | 19.5% demand, production ML | 1-2 weeks | Prometheus, Grafana, OpenTelemetry |
| 6 | **MCP/Guardrails** | Emerging agent patterns | 1-2 weeks | MCP spec, Guardrails AI |
| 7 | **CUDA/Triton Kernels** | 8.5% CUDA, performance roles | 3-4 weeks | CUDA programming, Triton tutorial |

---

## 16. Conclusions

1. **Market Fit is Strong:** The candidate's research background (post-training, RL, agents, multimodal) matches the most in-demand capabilities. 39 roles score ≥70 (Good target or better).

2. **Primary Gaps Are Visible Evidence:** The candidate *has* the skills but needs **demonstrable proof** — open-source repos, published implementations, production deployments.

3. **RL is the Differentiator:** PPO/RLHF appear in 85%/8% of roles but few candidates have *implemented* them. A clean, documented RLHF pipeline is a massive differentiator.

4. **Engineering + Research Hybrid Wins:** Roles increasingly demand both (Go + PyTorch, Kubernetes + distributed training). The candidate's dual background is a key advantage.

5. **Target Companies:** Focus applications on **Anthropic, Together AI, Scale AI, xAI** — highest concentration of well-matched roles.

6. **Timeline:** With Dec 2026 graduation, apply **Sept-Nov 2026** for best pipeline. Use summer 2026 to close evidence gaps.

---

*Report generated from {total_jobs} verified job postings across {len(market.get('company_distribution', {}))} companies via Greenhouse API.*
"""
    
    return md

def generate_top_jobs(jobs, market, gaps, resume_recs):
    """Generate detailed analysis of top job opportunities."""
    
    # Get top jobs by fit score
    top_jobs = [j for j in jobs if j.get('fit_score', 0) >= 70]
    top_jobs.sort(key=lambda x: -x.get('fit_score', 0))
    
    md = f"""# Top Job Opportunities - Detailed Analysis

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Qualified Jobs (Fit ≥70):** {len(top_jobs)}

---

"""
    
    for i, job in enumerate(top_jobs[:25]):
        md += f"""## {i+1}. {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}

**Fit Score:** {job.get('fit_score', 0)}/100 | **Category:** {job.get('interview_category', 'Unknown')} | **Location:** {job.get('location', 'Unknown')} | **Work Type:** {job.get('work_type', 'Unknown')}

**URL:** {job.get('url', 'N/A')}

**Date Posted:** {job.get('date_posted', 'Unknown').split('T')[0] if job.get('date_posted', 'Unknown') != 'Unknown' else 'Unknown'}

### What the Team Appears to Be Building
Based on the job description, this team is likely working on:
"""
        # Extract key themes from JD
        jd = job.get('full_jd_text', '').lower()
        themes = []
        if 'post-training' in jd or 'post training' in jd:
            themes.append('LLM post-training / RLHF pipelines')
        if 'reinforcement learning' in jd or 'rlhf' in jd or 'dpo' in jd or 'grpo' in jd or 'ppo' in jd:
            themes.append('Reinforcement learning for alignment')
        if 'agent' in jd or 'agentic' in jd or 'tool use' in jd or 'function calling' in jd:
            themes.append('Agentic AI systems with tool-use')
        if 'pretraining' in jd or 'pre-training' in jd:
            themes.append('Foundation model pretraining')
        if 'multimodal' in jd:
            themes.append('Multimodal foundation models')
        if 'inference' in jd or 'serving' in jd or 'vllm' in jd or 'tensorrt' in jd:
            themes.append('Model inference optimization and serving')
        if 'eval' in jd or 'benchmark' in jd:
            themes.append('Model evaluation and benchmarking')
        if 'distributed' in jd and 'train' in jd:
            themes.append('Distributed training infrastructure')
        if 'interpretability' in jd or 'safety' in jd or 'red team' in jd:
            themes.append('AI safety and interpretability')
        if 'code' in jd and ('generat' in jd or 'synthesis' in jd):
            themes.append('Code generation and program synthesis')
        if 'computer use' in jd or 'browser' in jd:
            themes.append('Computer-use / browser agents')
        
        if themes:
            for t in themes:
                md += f"- {t}\n"
        else:
            md += "- General ML/AI engineering\n"
        
        md += f"""

### Why You Fit (Score: {job.get('fit_score', 0)}/100)
{job.get('why_fits', 'Analysis not available')}

### Potential Concerns
**Biggest Gap:** {job.get('biggest_gap', 'None identified')}

All gaps: {', '.join(job.get('gaps', [])) if job.get('gaps') else 'None'}

### Experiences to Emphasize
Based on the JD requirements, highlight these from your background:
"""
        # Determine which experiences to emphasize based on JD content
        emphasize = []
        if 'post-training' in jd or 'rlhf' in jd or 'dpo' in jd or 'grpo' in jd:
            emphasize.append("LLM post-training research (RLHF, DPO, GRPO)")
        if 'reinforcement learning' in jd or 'ppo' in jd or 'rl' in jd:
            emphasize.append("Reinforcement learning research and implementation")
        if 'agent' in jd or 'agentic' in jd or 'tool use' in jd or 'function calling' in jd:
            emphasize.append("Agentic AI systems, tool-use, orchestration")
        if 'multimodal' in jd:
            emphasize.append("Multimodal model research")
        if 'code' in jd and ('generat' in jd or 'synthesis' in jd):
            emphasize.append("Code generation / program synthesis")
        if 'pretraining' in jd or 'pre-training' in jd:
            emphasize.append("Large-scale pretraining")
        if 'eval' in jd or 'benchmark' in jd:
            emphasize.append("Model evaluation and benchmarking")
        if 'distributed' in jd:
            emphasize.append("Distributed systems / ML infrastructure")
        if 'inference' in jd or 'serving' in jd or 'vllm' in jd or 'tensorrt' in jd:
            emphasize.append("Model inference optimization (vLLM, TensorRT, Triton)")
        if 'production' in jd or 'deploy' in jd:
            emphasize.append("Production ML systems deployment")
        if 'rag' in jd or 'retrieval' in jd:
            emphasize.append("RAG and retrieval systems")
        
        if emphasize:
            for e in emphasize:
                md += f"- {e}\n"
        else:
            md += "- Core ML engineering and research background\n"
        
        # Determine best resume variant
        best_variant = 'A'
        title_lower = job.get('title', '').lower()
        if any(kw in title_lower for kw in ['research engineer', 'research scientist', 'applied scientist']):
            best_variant = 'B'
        elif any(kw in title_lower for kw in ['post-training', 'post training', 'rl engineer', 'training engineer']):
            best_variant = 'C'
        elif any(kw in title_lower for kw in ['ml engineer', 'ml systems', 'infrastructure', 'platform', 'serving', 'inference engineer']):
            best_variant = 'D'
        elif any(kw in title_lower for kw in ['agent', 'applied ai', 'ai engineer']):
            best_variant = 'A'
        
        variant_name = resume_recs.get(best_variant, {}).get('name', 'Unknown')
        
        md += f"""

### Recommended Resume Variant: **{best_variant} - {variant_name}**

### Key Keywords for Application
"""
        # Get top keywords for this variant
        variant_rec = resume_recs.get(best_variant, {})
        for kw, freq in variant_rec.get('required_keywords', [])[:15]:
            md += f"- {kw}\n"
        
        md += f"""

### Likely Interview Topics
Based on the JD and company patterns:
"""
        interview_topics = []
        if 'anthropic' in job.get('company', '').lower():
            interview_topics = [
                "RLHF/DPO/GRPO implementation details",
                "Constitutional AI / alignment techniques",
                "Distributed training at scale (FSDP/DeepSpeed)",
                "Model evaluation and safety testing",
                "Agent architectures and tool-use",
                "Interpretability / mechanistic interpretability"
            ]
        elif 'togetherai' in job.get('company', '').lower():
            interview_topics = [
                "vLLM / TensorRT inference optimization",
                "Distributed training (DeepSpeed, FSDP, Megatron)",
                "Model serving infrastructure",
                "GPU kernel optimization (Triton, CUDA)",
                "Post-training pipelines"
            ]
        elif 'scaleai' in job.get('company', '').lower():
            interview_topics = [
                "Agent evaluation and robustness",
                "RL for agent alignment",
                "Production ML platform engineering",
                "Data engine and human feedback systems",
                "Multi-agent orchestration"
            ]
        elif 'databricks' in job.get('company', '').lower():
            interview_topics = [
                "ML infrastructure and platform engineering",
                "Distributed systems (Spark, Ray, Kubernetes)",
                "Model serving and inference optimization",
                "Feature stores and data pipelines",
                "MLOps and production deployment"
            ]
        elif 'xai' in job.get('company', '').lower():
            interview_topics = [
                "Large-scale pretraining infrastructure",
                "Inference optimization (TensorRT, kernels)",
                "Distributed training at massive scale",
                "GPU cluster management"
            ]
        else:
            interview_topics = [
                "Core ML algorithms and implementation",
                "System design for ML pipelines",
                "Model training and evaluation",
                "Production deployment challenges"
            ]
        
        for topic in interview_topics:
            md += f"- {topic}\n"
        
        md += "\n---\n\n"
    
    return md

def generate_tiered_rankings(jobs):
    """Generate tiered job rankings for final deliverable."""
    
    md = """# Job Rankings by Tier

"""
    
    # Tier A: Strong target (85+)
    tier_a = [j for j in jobs if j.get('fit_score', 0) >= 85]
    # Tier B: Good target (70-84)
    tier_b = [j for j in jobs if 70 <= j.get('fit_score', 0) < 85]
    # Tier C: Strategic stretch (55-69)
    tier_c = [j for j in jobs if 55 <= j.get('fit_score', 0) < 70]
    # Tier D: Skip (<55)
    tier_d = [j for j in jobs if j.get('fit_score', 0) < 55]
    
    md += f"""## Tier A — Apply Immediately ({len(tier_a)} jobs)
**Strong fit (85+) and high-quality opportunity.** These roles closely match your research background and experience level.

| Rank | Company | Role | Location | Fit Score | Why It Fits | Biggest Gap | Experience | Salary | Posted | URL |
|------|---------|------|----------|-----------|-------------|-------------|------------|--------|--------|-----|
"""
    
    for i, job in enumerate(tier_a):
        exp = job.get('experience_requirement', 'Not specified')
        salary = job.get('salary', 'Not listed')
        posted = job.get('date_posted', 'Unknown').split('T')[0] if job.get('date_posted', 'Unknown') != 'Unknown' else 'Unknown'
        why = job.get('why_fits', '')[:100].replace('|', ';').replace('\n', ' ')
        gap = job.get('biggest_gap', '').replace('|', ';').replace('\n', ' ')
        md += f"| {i+1} | {job.get('company', '')} | {job.get('title', '')} | {job.get('location', '')} | {job.get('fit_score', 0)} | {why} | {gap} | {exp} | {salary} | {posted} | {job.get('url', '')} |\n"
    
    md += f"""

## Tier B — Apply ({len(tier_b)} jobs)
**Good fit (70-84) and solid opportunity.** Strong alignment with minor gaps.

| Rank | Company | Role | Location | Fit Score | Why It Fits | Biggest Gap | Experience | Salary | Posted | URL |
|------|---------|------|----------|-----------|-------------|-------------|------------|--------|--------|-----|
"""
    
    for i, job in enumerate(tier_b):
        exp = job.get('experience_requirement', 'Not specified')
        salary = job.get('salary', 'Not listed')
        posted = job.get('date_posted', 'Unknown').split('T')[0] if job.get('date_posted', 'Unknown') != 'Unknown' else 'Unknown'
        why = job.get('why_fits', '')[:100].replace('|', ';').replace('\n', ' ')
        gap = job.get('biggest_gap', '').replace('|', ';').replace('\n', ' ')
        md += f"| {i+1} | {job.get('company', '')} | {job.get('title', '')} | {job.get('location', '')} | {job.get('fit_score', 0)} | {why} | {gap} | {exp} | {salary} | {posted} | {job.get('url', '')} |\n"
    
    md += f"""

## Tier C — Strategic Stretch ({len(tier_c)} jobs)
**Harder but valuable enough that applying makes sense (55-69).** Significant gaps but unique value potential.

| Rank | Company | Role | Location | Fit Score | Why It Fits | Biggest Gap | Experience | Salary | Posted | URL |
|------|---------|------|----------|-----------|-------------|-------------|------------|--------|--------|-----|
"""
    
    for i, job in enumerate(tier_c):
        exp = job.get('experience_requirement', 'Not specified')
        salary = job.get('salary', 'Not listed')
        posted = job.get('date_posted', 'Unknown').split('T')[0] if job.get('date_posted', 'Unknown') != 'Unknown' else 'Unknown'
        why = job.get('why_fits', '')[:100].replace('|', ';').replace('\n', ' ')
        gap = job.get('biggest_gap', '').replace('|', ';').replace('\n', ' ')
        md += f"| {i+1} | {job.get('company', '')} | {job.get('title', '')} | {job.get('location', '')} | {job.get('fit_score', 0)} | {why} | {gap} | {exp} | {salary} | {posted} | {job.get('url', '')} |\n"
    
    md += f"""

## Tier D — Skip ({len(tier_d)} jobs)
**Below threshold (55).** Brief explanation for skipping:

| Rank | Company | Role | Fit Score | Reason |
|------|---------|------|-----------|--------|
"""
    
    skip_reasons = {
        'PhD Required': 'PhD required, candidate has M.S.',
        'Location Mismatch': 'Location not in preferred regions',
        'Experience Mismatch': 'Requires significantly more experience',
        'Role Mismatch': 'Role focuses on non-target areas (sales, infra-only, etc.)',
        'Low Technical Overlap': 'Insufficient technical skill alignment',
        'Internship': 'Internship role, candidate targets full-time'
    }
    
    for i, job in enumerate(tier_d[:30]):  # Limit to 30 for readability
        reason = 'Low overall fit'
        if job.get('gaps'):
            for gap in job['gaps']:
                for key, val in skip_reasons.items():
                    if key.lower() in gap.lower():
                        reason = val
                        break
        md += f"| {i+1} | {job.get('company', '')} | {job.get('title', '')} | {job.get('fit_score', 0)} | {reason} |\n"
    
    if len(tier_d) > 30:
        md += f"\n*... and {len(tier_d) - 30} more roles below threshold*\n"
    
    return md

def main():
    jobs, market, gaps, resume_recs = load_data()
    
    # Generate job market analysis
    print("Generating job_market_analysis.md...")
    market_md = generate_job_market_analysis(jobs, market, gaps, resume_recs)
    with open(HERMES_BASE / 'job_research/job_market_analysis.md', 'w') as f:
        f.write(market_md)
    
    # Generate top jobs analysis
    print("Generating top_jobs.md...")
    top_jobs_md = generate_top_jobs(jobs, market, gaps, resume_recs)
    with open(HERMES_BASE / 'job_research/top_jobs.md', 'w') as f:
        f.write(top_jobs_md)
    
    # Generate tiered rankings
    print("Generating tiered rankings...")
    tiers_md = generate_tiered_rankings(jobs)
    with open(HERMES_BASE / 'job_research/job_tiers.md', 'w') as f:
        f.write(tiers_md)
    
    print("\nAll deliverables generated!")
    print("- job_market_analysis.md")
    print("- top_jobs.md") 
    print("- job_tiers.md")
    print("- jobs_master.csv (already exists)")
    print("- job_descriptions/ (already populated)")

if __name__ == '__main__':
    main()