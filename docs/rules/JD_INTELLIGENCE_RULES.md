# Job Description Intelligence Rules

**Source Authority:** This document consolidates JD intelligence rules from HERMES_JOB_HUNT_SYSTEM_RULES.md, docs/intelligence/JOB_MARKET_PATTERNS.md, and the modular rule files in `docs/hermes_job_hunt_rules_modular/`

## 1. Goal

Every collected JD should improve future job search and resume positioning. Do not merely store/read job descriptions.

## 2. Extract from Every JD

- Required skills
- Preferred skills
- Recurring technical keywords
- Responsibilities
- Frameworks/tools
- Research expectations
- Production/system expectations
- Seniority signals
- Education requirements
- Years-of-experience requirements
- Domain classification
- ATS-sensitive terminology
- Must-have vs nice-to-have requirements
- Gaps relative to the profile

## 3. Aggregate Market Intelligence

Maintain cumulative patterns across categories such as Research Engineer, Agentic AI, post-training, inference/ML systems, MLE, multimodal, AI security, CAD/design AI, etc.

Track frequent requirements, important repeated terminology, emerging tooling, common screening signals, candidate gaps, and resume terminology worth using when truthful.

## 4. Frequency is Not Importance

Distinguish boilerplate, useful ATS terminology, real screening requirements, and strategically important capabilities. Do not reduce JD intelligence to word counts.

## 5. Storage

Use structured CSV/JSON for per-JD features/counts and one canonical Markdown intelligence file for qualitative market conclusions. Do not create one Markdown report per JD.

### Canonical Locations

- Per-JD features: `job_research/data/jd_features.csv`
- Market intelligence: `docs/intelligence/JOB_MARKET_PATTERNS.md`
- Active JDs: `tracking/job_descriptions/active/`
- Archived JDs: `tracking/job_descriptions/archive/YYYY-MM/`

## 6. Role Family Patterns (from JOB_MARKET_PATTERNS.md)

### Agentic AI / Applied AI Research
**Frequent Requirements:** LangGraph/LangChain (90%+), multi-agent orchestration, tool/function calling, agentic RAG, planning/reasoning
**Screening-Critical:** LangGraph production experience, multi-agent system design
**Boilerplate:** "familiar with LangChain"

### LLM Evaluation / Inference Research
**Frequent Requirements:** vLLM, TensorRT, Triton (80%+), model serving, evaluation frameworks
**Screening-Critical:** vLLM production experience, distributed inference systems
**Boilerplate:** "familiar with ML metrics"

### ML Engineering / Applied Scientist (Production)
**Frequent Requirements:** ML infrastructure, feature platforms, training pipelines, MLOps
**Screening-Critical:** Production ML systems at scale, Kubernetes, pipeline orchestration
**Boilerplate:** "MLflow experience"

### Research Engineer / Scientist (Frontier)
**Frequent Requirements:** Top-venue publications, reasoning/planning/agents research
**Screening-Critical:** Top-venue publications, novel research contributions
**Boilerplate:** "research mindset"

## 7. Cross-Cutting Patterns

### ATS-Sensitive Terminology (Must Mirror)
| Category | Terms to Include |
|----------|------------------|
| Agentic AI | "LangGraph", "multi-agent", "tool calling", "function calling", "agentic RAG" |
| Evaluation | "vLLM", "benchmarking", "HumanEval", "SWE-bench", "model evaluation" |
| Inference | "TensorRT", "Triton", "distributed serving", "SLO", "latency optimization" |
| ML Engineering | "Kubernetes", "MLOps", "feature store", "model registry", "pipeline" |
| RL/Post-Training | "RLHF", "DPO", "PPO", "GRPO", "reward model", "SFT", "LoRA" (DO NOT CLAIM) |

### Degree/Experience Trends
- PhD Required: ~15% of Research Engineer roles (mostly frontier labs)
- PhD Preferred: ~35% of Research roles
- M.S. Acceptable: ~70% of Applied/Engineering roles
- 3-4 years: Sweet spot for Applied/Engineering roles (matches candidate)

### Visa Sponsorship
- Explicitly Sponsors: Most T1/T2 companies
- Strategy: Target H-1B sponsors; referrals bypass ATS filters