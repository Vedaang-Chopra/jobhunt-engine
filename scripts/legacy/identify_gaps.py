#!/usr/bin/env python3
"""
Identify skill gaps by comparing market demands against candidate profile.
"""

import json
from collections import Counter
from pathlib import Path

# Legacy paths resolved relative to the parent workspace dir; override with
# JOBHUNT_LEGACY_HERMES_BASE when the legacy layout lives elsewhere.
import os
HERMES_BASE = Path(os.environ.get(
    "JOBHUNT_LEGACY_HERMES_BASE",
    str(Path(__file__).resolve().parents[3]),
))

def load_scored_jobs():
    with open(HERMES_BASE / 'job_research/data/scored_jobs.json', 'r') as f:
        return json.load(f)

def load_market_analysis():
    with open(HERMES_BASE / 'job_research/data/market_analysis.json', 'r') as f:
        return json.load(f)

# Candidate profile skills
CANDIDATE_SKILLS = {
    # Strong evidence
    'Python': 'strong',
    'PyTorch': 'strong',
    'Golang': 'strong',
    'Go': 'strong',
    'Distributed Systems': 'strong',
    'Backend Engineering': 'strong',
    'APIs': 'strong',
    'REST': 'strong',
    'ML Systems': 'strong',
    'RAG': 'strong',
    'Agentic AI Systems': 'strong',
    'Tool Calling': 'strong',
    'LLM Post-Training': 'strong',
    'Reinforcement Learning': 'strong',
    'RLHF': 'strong',
    'DPO': 'strong',
    'Program Synthesis': 'strong',
    'Code Generation': 'strong',
    'Multimodal Models': 'strong',
    'Model Routing': 'strong',
    'Agents': 'strong',
    'Iterative Execution': 'strong',
    'Evaluation': 'strong',
    'Search/Retrieval Infrastructure': 'strong',
    
    # Present but need stronger evidence
    'CUDA': 'moderate',
    'Triton': 'moderate',
    'JAX': 'moderate',
    'TensorFlow': 'moderate',
    'vLLM': 'moderate',
    'TensorRT': 'moderate',
    'DeepSpeed': 'moderate',
    'FSDP': 'moderate',
    'Megatron': 'moderate',
    'Kubernetes': 'moderate',
    'Docker': 'moderate',
    'Ray': 'moderate',
    'MLOps': 'moderate',
    'Model Serving': 'moderate',
    'Inference Optimization': 'moderate',
    'Profiling': 'moderate',
    'Observability': 'moderate',
    'Monitoring': 'moderate',
    'CI/CD': 'moderate',
    'GRPO': 'moderate',
    'PPO': 'moderate',
    'Reward Modeling': 'moderate',
    'Synthetic Data': 'moderate',
    'Distillation': 'moderate',
    'Curriculum Learning': 'moderate',
    'Process Rewards': 'moderate',
    'Verifiers': 'moderate',
    'Reasoning Models': 'moderate',
    'Alignment': 'moderate',
    'Interpretability': 'moderate',
    'Safety': 'moderate',
    'Red Teaming': 'moderate',
    'Multi-Agent Systems': 'moderate',
    'Orchestration': 'moderate',
    'Planning': 'moderate',
    'Memory': 'moderate',
    'Long-Horizon Reasoning': 'moderate',
    'MCP': 'weak',
    'LangGraph': 'weak',
    'LangChain': 'weak',
    'AutoGen': 'weak',
    'Browser/Computer-Use Agents': 'weak',
    
    # Missing/weak
    'Rust': 'weak',
    'C++': 'weak',
    'SQL': 'weak',
    'Linux Kernel': 'weak',
    'Scalable Systems': 'moderate',
    'High Throughput': 'moderate',
    'Low Latency': 'moderate',
    'Microservices': 'moderate',
    'Cloud Systems': 'moderate',
    'GPU Systems': 'moderate',
    'Data Pipelines': 'moderate',
    'Vector Database': 'weak',
    'Search Infrastructure': 'moderate',
    'Large-Scale Compute': 'moderate',
    'Open-Source Contributions': 'weak',
    'First-Author Publications': 'weak',
    'PhD': 'none',
}

# Market demand from analysis (normalized skill names)
MARKET_DEMANDS = {
    # Technical skills (from analysis)
    'Go': 0.95,
    'PPO': 0.85,
    'RL': 0.845,
    'RAG': 0.835,
    'Evaluation': 0.57,
    'REST': 0.56,
    'Python': 0.415,
    'API': 0.375,
    'Distributed Systems': 0.325,
    'Agents': 0.305,
    'Kubernetes': 0.215,
    'Monitoring': 0.195,
    'Backend': 0.17,
    'PyTorch': 0.13,
    'Observability': 0.13,
    'Data Pipelines': 0.125,
    'Docker': 0.105,
    'Profiling': 0.09,
    'CUDA': 0.085,
    'CI/CD': 0.085,
    
    # Engineering skills (from analysis)
    'Rust': 0.415,
    'Inference': 0.175,
    'Optimization': 0.175,
    'SQL': 0.14,
    'C++': 0.11,
    'ML Infrastructure': 0.05,
    'Linux': 0.05,
    'Scalable Systems': 0.04,
    'Model Serving': 0.03,
    'Production Deployment': 0.025,
    'Low Latency': 0.025,
    'Cloud Systems': 0.02,
    
    # Training/Post-training
    'Fine-Tuning': 0.13,
    'Alignment': 0.125,
    'LoRA': 0.105,
    'RLHF': 0.08,
    'Post-Training': 0.06,
    'Pretraining': 0.045,
    'DPO': 0.04,
    'RL Environments': 0.03,
    'GRPO': 0.02,
    'Reward Modeling': 0.01,
    'Synthetic Data': 0.01,
    'Distillation': 0.01,
    'Verifiers': 0.005,
    
    # Agentic skills
    'Orchestration': 0.125,
    'Memory': 0.095,
    'Planning': 0.065,
    'Guardrails': 0.045,
    'MCP': 0.03,
    'Human-in-the-Loop': 0.02,
    'Multi-Agent Systems': 0.015,
    'Prompt Engineering': 0.015,
    'LangChain': 0.01,
    'Tool Calling': 0.01,
    'Agent Evaluation': 0.005,
    'Long-Horizon Reasoning': 0.005,
    
    # Research skills
    'Open-Source Contributions': 0.89,
    'Training Models': 0.74,
    'Evaluating Models': 0.605,
    'Implementing Papers': 0.26,
    'Designing Experiments': 0.24,
    'Developing New Algorithms': 0.17,
    'Publications Required': 0.09,
    'Research Experience': 0.055,
    'PhD Required': 0.055,
    'Large-Scale Compute': 0.05,
    'PhD Preferred': 0.03,
    'Conducting Ablations': 0.02,
}

# Importance weights for target roles
ROLE_IMPORTANCE = {
    # Research Engineer roles - high importance
    'PPO': 0.9, 'RL': 0.9, 'RLHF': 0.9, 'DPO': 0.85, 'GRPO': 0.85,
    'Post-Training': 0.9, 'Pretraining': 0.85, 'Alignment': 0.85,
    'Reasoning Models': 0.9, 'Agents': 0.9, 'Agentic': 0.9,
    'Tool Calling': 0.85, 'Multimodal Models': 0.85,
    'Model Routing': 0.8, 'Evaluation': 0.85, 'Reward Modeling': 0.8,
    'Process Rewards': 0.8, 'Verifiers': 0.8, 'GRPO': 0.85,
    'Synthetic Data': 0.75, 'Distillation': 0.7, 'Curriculum Learning': 0.7,
    'Implementing Papers': 0.8, 'Designing Experiments': 0.85,
    'Developing New Algorithms': 0.8, 'Conducting Ablations': 0.75,
    'Large-Scale Compute': 0.75, 'Open-Source Contributions': 0.7,
    
    # Applied AI / AI Engineer roles
    'RAG': 0.85, 'Agents': 0.9, 'Tool Calling': 0.85,
    'Model Serving': 0.8, 'Inference Optimization': 0.8,
    'vLLM': 0.8, 'TensorRT': 0.75, 'Triton': 0.75,
    'Kubernetes': 0.7, 'Docker': 0.65, 'Python': 0.9,
    'Go': 0.7, 'PyTorch': 0.85, 'APIs': 0.8,
    'Orchestration': 0.8, 'Planning': 0.75, 'Memory': 0.7,
    'MCP': 0.7, 'Guardrails': 0.65, 'Long-Horizon Reasoning': 0.75,
    
    # ML Engineer / ML Systems roles
    'Distributed Systems': 0.9, 'Backend Engineering': 0.85,
    'Model Serving': 0.85, 'Inference': 0.8, 'ML Infrastructure': 0.85,
    'Kubernetes': 0.8, 'GPU Systems': 0.75, 'Profiling': 0.7,
    'Optimization': 0.85, 'Production Deployment': 0.8,
    'CUDA': 0.8, 'Triton': 0.75, 'DeepSpeed': 0.75,
    'FSDP': 0.75, 'Megatron': 0.7, 'Ray': 0.7,
    'Scalable Systems': 0.85, 'High Throughput': 0.8, 'Low Latency': 0.75,
    'Python': 0.9, 'Go': 0.75, 'Rust': 0.6, 'C++': 0.6,
    'Observability': 0.7, 'Monitoring': 0.7, 'CI/CD': 0.65,
}

def calculate_gaps():
    """Calculate gap priorities for each skill."""
    gaps = []
    
    for skill, market_freq in MARKET_DEMANDS.items():
        importance = ROLE_IMPORTANCE.get(skill, 0.5)  # Default medium importance
        relevance = 1.0  # All skills in MARKET_DEMANDS are relevant to target roles
        
        candidate_level = CANDIDATE_SKILLS.get(skill, 'none')
        
        # Convert candidate level to evidence score
        evidence_scores = {
            'strong': 0.9,
            'moderate': 0.5,
            'weak': 0.2,
            'none': 0.0
        }
        evidence = evidence_scores.get(candidate_level, 0.0)
        
        # Gap = market_freq * importance * relevance * (1 - evidence)
        gap_priority = market_freq * importance * relevance * (1 - evidence)
        
        # Determine category
        if evidence >= 0.8:
            category = 'Already Strong'
        elif evidence >= 0.4:
            category = 'Present but Need Stronger Evidence'
        else:
            category = 'Missing / High-Value Gaps'
        
        gaps.append({
            'skill': skill,
            'market_frequency': market_freq,
            'importance': importance,
            'relevance': relevance,
            'candidate_evidence': candidate_level,
            'evidence_score': evidence,
            'gap_priority': gap_priority,
            'category': category
        })
    
    # Sort by gap priority descending
    gaps.sort(key=lambda x: -x['gap_priority'])
    
    return gaps

def main():
    jobs = load_scored_jobs()
    market = load_market_analysis()
    
    print(f"Analyzing gaps across {len(jobs)} jobs...")
    
    gaps = calculate_gaps()
    
    # Categorize
    already_strong = [g for g in gaps if g['category'] == 'Already Strong']
    need_evidence = [g for g in gaps if g['category'] == 'Present but Need Stronger Evidence']
    missing = [g for g in gaps if g['category'] == 'Missing / High-Value Gaps']
    
    print(f"\n=== ALREADY STRONG ({len(already_strong)} skills) ===")
    for g in already_strong[:30]:
        print(f"  {g['skill']}: market={g['market_frequency']:.2f}, importance={g['importance']:.2f}, evidence={g['evidence_score']:.1f}")
    
    print(f"\n=== PRESENT BUT NEED STRONGER EVIDENCE ({len(need_evidence)} skills) ===")
    for g in need_evidence[:30]:
        print(f"  {g['skill']}: market={g['market_frequency']:.2f}, importance={g['importance']:.2f}, evidence={g['evidence_score']:.1f}, gap_priority={g['gap_priority']:.3f}")
    
    print(f"\n=== MISSING / HIGH-VALUE GAPS ({len(missing)} skills) ===")
    for g in missing[:30]:
        print(f"  {g['skill']}: market={g['market_frequency']:.2f}, importance={g['importance']:.2f}, evidence={g['evidence_score']:.1f}, gap_priority={g['gap_priority']:.3f}")
    
    # Save full gap analysis
    with open(HERMES_BASE / 'job_research/data/gap_analysis.json', 'w') as f:
        json.dump({
            'already_strong': already_strong,
            'need_stronger_evidence': need_evidence,
            'missing_high_value': missing,
            'all_gaps': gaps
        }, f, indent=2)
    
    # Top 20 priority gaps to address
    print("\n=== TOP 20 PRIORITY GAPS TO ADDRESS ===")
    top_gaps = [g for g in gaps if g['category'] != 'Already Strong'][:20]
    for i, g in enumerate(top_gaps):
        print(f"  {i+1}. {g['skill']} (priority: {g['gap_priority']:.3f}) - {g['category']}")
        print(f"      Market: {g['market_frequency']:.1%}, Importance: {g['importance']:.1f}, Evidence: {g['candidate_evidence']}")

if __name__ == '__main__':
    main()