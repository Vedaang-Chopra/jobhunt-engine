#!/usr/bin/env python3
"""
Generate resume implications for 4 resume variants based on market analysis.
"""

import json
from pathlib import Path

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
    return jobs, market, gaps

# Resume variants with their target role focuses
RESUME_VARIANTS = {
    'A': {
        'name': 'Agentic AI / Applied AI Engineer',
        'focus': 'Agent frameworks, tool calling, orchestration, production deployment, RAG, evaluation',
        'target_roles': ['Applied AI Engineer', 'AI Engineer', 'Agentic AI Engineer', 'Agent Engineer'],
        'priority_skills': [
            'RAG', 'Agents', 'Tool Calling', 'Function Calling', 'Orchestration',
            'Planning', 'Memory', 'MCP', 'LangGraph', 'LangChain', 'AutoGen',
            'Multi-Agent Systems', 'Agent Evaluation', 'Guardrails',
            'Human-in-the-Loop', 'Long-Horizon Reasoning', 'Browser/Computer-Use Agents',
            'Code Agents', 'Prompt Engineering', 'Model Serving', 'Inference Optimization',
            'vLLM', 'TensorRT', 'Triton', 'Kubernetes', 'Docker', 'Python', 'Go',
            'APIs', 'REST', 'Production Deployment', 'Observability', 'Monitoring',
            'RL', 'PPO', 'Reinforcement Learning', 'Fine-Tuning', 'LoRA',
            'Distributed Systems', 'Scalable Systems', 'High Throughput', 'Low Latency'
        ],
        'deemphasize': [
            'Pretraining', 'Large-Scale Compute', 'Distributed Training', 'Megatron',
            'FSDP', 'DeepSpeed', 'CUDA Kernels', 'Triton Kernels',
            'PhD', 'Publications', 'First-Author Publications', 'Research Experience',
            'Conducting Ablations', 'Developing New Algorithms'
        ],
        'key_projects': [
            'Agentic AI system with tool-use and orchestration',
            'RAG pipeline with evaluation framework',
            'Multi-agent workflow system',
            'Production model serving with vLLM/TensorRT',
            'LLM evaluation benchmark suite',
            'Computer-use/browser agent implementation'
        ]
    },
    'B': {
        'name': 'Research Engineer — LLM / Agents / Reasoning',
        'focus': 'Research publications, novel algorithms, reasoning, agent architectures, experiments',
        'target_roles': ['Research Engineer', 'Research Scientist', 'Applied Scientist'],
        'priority_skills': [
            'Reinforcement Learning', 'PPO', 'RLHF', 'DPO', 'GRPO', 'Post-Training',
            'Alignment', 'Reasoning Models', 'Agents', 'Agentic', 'Tool Calling',
            'Multimodal Models', 'Model Routing', 'Implementing Papers',
            'Designing Experiments', 'Training Models', 'Evaluating Models',
            'Developing New Algorithms', 'Conducting Ablations', 'Large-Scale Compute',
            'Open-Source Contributions', 'PyTorch', 'JAX', 'Transformers',
            'Distributed Training', 'Reward Modeling', 'Process Rewards', 'Verifiers',
            'Synthetic Data', 'Distillation', 'Curriculum Learning',
            'Program Synthesis', 'Code Generation', 'Computer Use', 'Interpretability',
            'Safety', 'Red Teaming', 'Publications', 'Research Experience'
        ],
        'deemphasize': [
            'Kubernetes', 'Docker', 'CI/CD', 'Observability', 'Monitoring',
            'Production Deployment', 'Model Serving', 'RAG', 'APIs',
            'Microservices', 'Cloud Systems', 'DevOps', 'MLOps',
            'Rust', 'C++', 'SQL', 'Linux Kernel'
        ],
        'key_projects': [
            'Novel RLHF/RL algorithm for LLM alignment',
            'Reasoning model with process rewards',
            'Agent architecture with planning and memory',
            'Multimodal model training/evaluation',
            'Code generation with program synthesis',
            'Reproduction of key papers with ablations',
            'Open-source contribution to transformers/trl/vllm'
        ]
    },
    'C': {
        'name': 'Post-training / RL / LLM Training',
        'focus': 'RLHF, DPO, GRPO, SFT, reward modeling, training pipelines, distributed training',
        'target_roles': ['Post-Training Engineer', 'RL Engineer', 'LLM Training Engineer', 'Training Engineer'],
        'priority_skills': [
            'RLHF', 'DPO', 'GRPO', 'PPO', 'SFT', 'Post-Training', 'Pretraining',
            'Reward Modeling', 'Verifiers', 'Process Rewards', 'Outcome Rewards',
            'Alignment', 'Fine-Tuning', 'LoRA', 'QLoRA', 'PEFT',
            'Distributed Training', 'DeepSpeed', 'FSDP', 'Megatron', 'Ray',
            'CUDA', 'Triton', 'JAX', 'PyTorch', 'Transformers',
            'Training Models', 'Evaluating Models', 'Large-Scale Compute',
            'Synthetic Data', 'Distillation', 'Curriculum Learning',
            'Reasoning Models', 'Model Evaluation', 'Benchmark',
            'Open-Source Contributions', 'Implementing Papers',
            'Designing Experiments', 'Conducting Ablations'
        ],
        'deemphasize': [
            'RAG', 'Agents', 'Tool Calling', 'MCP', 'LangGraph', 'LangChain',
            'Model Serving', 'Inference Optimization', 'vLLM', 'TensorRT',
            'Kubernetes', 'Docker', 'CI/CD', 'Observability', 'Monitoring',
            'Production Deployment', 'APIs', 'Microservices', 'Cloud Systems',
            'Rust', 'C++', 'SQL', 'Frontend', 'Web Development'
        ],
        'key_projects': [
            'RLHF pipeline with PPO/DPO/GRPO implementation',
            'Reward model training and evaluation',
            'Large-scale distributed training (DeepSpeed/FSDP)',
            'Synthetic data generation for post-training',
            'Reasoning model training with process rewards',
            'Training pipeline optimization and profiling',
            'Open-source training framework contribution'
        ]
    },
    'D': {
        'name': 'ML Engineer / ML Systems',
        'focus': 'ML infrastructure, serving, optimization, distributed systems, Kubernetes, production',
        'target_roles': ['ML Engineer', 'ML Systems Engineer', 'ML Infrastructure Engineer', 'Platform Engineer'],
        'priority_skills': [
            'Distributed Systems', 'Backend Engineering', 'Model Serving',
            'Inference', 'ML Infrastructure', 'Data Pipelines', 'Kubernetes',
            'Cloud Systems', 'GPU Systems', 'Profiling', 'Optimization',
            'Production Deployment', 'APIs', 'Observability', 'Monitoring',
            'CI/CD', 'Microservices', 'Scalable Systems', 'High Throughput',
            'Low Latency', 'Python', 'Go', 'Rust', 'C++', 'SQL', 'Linux',
            'DeepSpeed', 'FSDP', 'Megatron', 'Ray', 'vLLM', 'TensorRT',
            'Triton', 'CUDA', 'Docker', 'MLOps', 'Model Serving',
            'Vector Database', 'Search Infrastructure', 'Retrieval',
            'Training Models', 'Evaluating Models', 'Inference Optimization'
        ],
        'deemphasize': [
            'Novel Algorithm Development', 'Publications', 'PhD',
            'First-Author Publications', 'Research Experience',
            'Conducting Ablations', 'Designing Experiments',
            'Developing New Algorithms', 'RLHF', 'DPO', 'GRPO',
            'Post-Training', 'Alignment', 'Reasoning Models',
            'Agents', 'Agentic', 'Tool Calling', 'MCP', 'Planning',
            'Memory', 'Orchestration', 'Multi-Agent Systems',
            'Program Synthesis', 'Code Generation', 'Computer Use'
        ],
        'key_projects': [
            'High-throughput model serving infrastructure',
            'Distributed training platform (DeepSpeed/FSDP/Ray)',
            'ML pipeline orchestration with Kubernetes',
            'GPU cluster management and scheduling',
            'Model optimization (quantization, compilation, TensorRT)',
            'Observability and monitoring for ML systems',
            'Feature store / data pipeline for ML',
            'Auto-scaling inference deployment'
        ]
    }
}

def generate_resume_recommendations():
    jobs, market, gaps = load_data()
    
    # Get top keywords from market analysis
    tech_skills = market.get('technical_skills', {})
    research_skills = market.get('research_skills', {})
    agentic_skills = market.get('agentic_skills', {})
    training_skills = market.get('training_post_training', {})
    engineering_skills = market.get('engineering_skills', {})
    
    # Combine all market skills with frequencies
    all_market_skills = {}
    for d in [tech_skills, research_skills, agentic_skills, training_skills, engineering_skills]:
        for k, v in d.items():
            all_market_skills[k.lower()] = v
    
    recommendations = {}
    
    for variant_key, variant in RESUME_VARIANTS.items():
        print(f"\nGenerating recommendations for Resume {variant_key}: {variant['name']}")
        
        # Required keywords - high frequency in market + in priority skills
        required_keywords = []
        for skill in variant['priority_skills']:
            freq = all_market_skills.get(skill.lower(), 0)
            if freq > 0:
                required_keywords.append((skill, freq))
        
        required_keywords.sort(key=lambda x: -x[1])
        
        # Technologies - from priority skills that are technical
        tech_keywords = [s for s in variant['priority_skills'] 
                        if s.lower() in [k.lower() for k in tech_skills.keys()]]
        
        # Research concepts
        research_concepts = [s for s in variant['priority_skills']
                           if s.lower() in [k.lower() for k in research_skills.keys()]]
        
        # Engineering concepts
        eng_concepts = [s for s in variant['priority_skills']
                       if s.lower() in [k.lower() for k in engineering_skills.keys()]]
        
        # Accomplishments recruiters expect
        accomplishments = []
        for job in jobs[:50]:  # Top 50 jobs
            if job.get('fit_score', 0) >= 70:
                # Extract accomplishment patterns from JD
                text = job.get('full_jd_text', '').lower()
                if 'ship' in text or 'deliver' in text or 'build' in text or 'launch' in text:
                    accomplishments.append('Shipped/produced production ML systems')
                if 'optimize' in text or 'performance' in text or 'latency' in text or 'throughput' in text:
                    accomplishments.append('Optimized model inference/training performance')
                if 'scale' in text or 'distributed' in text or 'large.scale' in text:
                    accomplishments.append('Scaled ML systems to large compute/data')
                if 'research' in text and ('novel' in text or 'new' in text or 'algorithm' in text):
                    accomplishments.append('Developed novel ML algorithms/approaches')
                if 'evaluat' in text and 'benchmark' in text:
                    accomplishments.append('Built evaluation frameworks and benchmarks')
                if 'open source' in text or 'oss' in text:
                    accomplishments.append('Open-source contributions to ML ecosystem')
        
        # Deduplicate
        accomplishments = list(set(accomplishments))
        
        # Skills NOT to emphasize
        skills_not_emphasize = variant['deemphasize']
        
        # Projects that deserve most space
        key_projects = variant['key_projects']
        
        recommendations[variant_key] = {
            'name': variant['name'],
            'target_roles': variant['target_roles'],
            'required_keywords': required_keywords[:30],
            'technologies': tech_keywords,
            'research_concepts': research_concepts,
            'engineering_concepts': eng_concepts,
            'accomplishments': accomplishments,
            'skills_not_emphasize': skills_not_emphasize,
            'key_projects': key_projects
        }
    
    # Save recommendations
    with open(HERMES_BASE / 'job_research/data/resume_recommendations.json', 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    # Print summary
    for variant_key, rec in recommendations.items():
        print(f"\n=== RESUME {variant_key}: {rec['name']} ===")
        print(f"Target Roles: {', '.join(rec['target_roles'])}")
        print(f"\nTop Keywords (with market frequency):")
        for kw, freq in rec['required_keywords'][:15]:
            print(f"  {kw}: {freq:.1%}")
        print(f"\nKey Projects to Highlight:")
        for proj in rec['key_projects']:
            print(f"  - {proj}")
        print(f"\nSkills to De-emphasize: {len(rec['skills_not_emphasize'])} items")
    
    print("\n\nRecommendations saved to resume_recommendations.json")

if __name__ == '__main__':
    generate_resume_recommendations()