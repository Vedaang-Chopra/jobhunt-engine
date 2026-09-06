# Job Market Patterns Intelligence

**Source Authority:** This document accumulates cumulative qualitative conclusions from JD analysis per HERMES_JOB_HUNT_SYSTEM_RULES.md §9.3

## Purpose

Maintain market intelligence from collected job descriptions. Do not create a new Markdown report for every JD. Use structured CSV for counts/per-job features, this document for accumulated qualitative conclusions.

Update after each significant batch of JD analysis (weekly or after company deep-dives).

---

## Role Family Patterns

### Agentic AI / Applied AI Research

**Frequent Requirements:**
- LangGraph/LangChain (90%+ of postings)
- Multi-agent orchestration, supervisor-worker patterns
- Tool/function calling, structured generation (Pydantic)
- Agentic RAG, planning, reasoning, long-horizon tasks
- Production agentic systems (not just prototypes)

**Recurring Keywords:**
- "agentic", "multi-agent", "tool use", "function calling"
- "LangGraph", "LangChain", "AutoGen", "crewAI"
- "orchestration", "planning", "reflection", "critique"
- "workflow", "supervisor", "worker", "handoff"

**Screening-Critical vs Boilerplate:**
- CRITICAL: LangGraph production experience, multi-agent system design
- BOILERPLATE: "familiar with LangChain" (often listed but not screened heavily)

**Emerging Trends:**
- Agent evaluation frameworks (SWE-bench, WebArena, GAIA)
- Trace-to-graph workflow reuse
- Cost-aware agent routing
- Computer-use / browser-use agents

---

### LLM Evaluation / Inference Research

**Frequent Requirements:**
- vLLM, TensorRT, Triton (80%+)
- Model serving, distributed inference, SLO/SLA
- Evaluation frameworks, benchmarking (HumanEval, SWE-bench, MMLU)
- Latency/throughput optimization, quantization
- GPU optimization (CUDA, Triton kernels - sometimes)

**Recurring Keywords:**
- "evaluation", "benchmarking", "model quality"
- "vLLM", "TensorRT", "Triton", "inference optimization"
- "distributed serving", "SLO", "latency", "throughput"
- "model serving", "LLM serving", "deployment"

**Screening-Critical vs Boilerplate:**
- CRITICAL: vLLM production experience, distributed inference systems
- BOILERPLATE: "familiar with ML metrics" (generic)

**Emerging Trends:**
- Speculative decoding, prefix caching
- Matryoshka embeddings, embedding compression
- Edge deployment, ONNX Runtime
- Geometric/functional correctness evaluation (execution-grounded)

---

### ML Engineering / Applied Scientist (Production)

**Frequent Requirements:**
- ML infrastructure, feature platforms, training pipelines
- Model serving, Kubernetes, MLOps
- Model registry, feature store, ML platform
- Airflow/Kubeflow/MLflow, pipeline orchestration
- A/B testing, experimentation platforms

**Recurring Keywords:**
- "ML infrastructure", "feature platform", "training pipeline"
- "model serving", "Kubernetes", "MLOps", "model registry"
- "feature store", "ML platform", "pipeline orchestration"
- "Airflow", "Kubeflow", "MLflow", "model deployment"
- "A/B testing", "experimentation platform", "data pipeline"

**Screening-Critical vs Boilerplate:**
- CRITICAL: Production ML systems at scale, Kubernetes, pipeline orchestration
- BOILERPLATE: "MLflow experience" (often just logging)

**Emerging Trends:**
- GitOps for ML, automated retraining, drift detection
- Feature stores (Feast, Tecton)
- Real-time inference, streaming features

---

### Applied AI / Applied Scientist

**Frequent Requirements:**
- Production ML, end-to-end model deployment
- Business impact, product ML
- Recommendation, ranking, personalization
- Forecasting, anomaly detection, fraud detection
- Computer vision, NLP, time series

**Recurring Keywords:**
- "production ML", "applied scientist", "applied ML"
- "end-to-end", "model deployment", "A/B testing"
- "feature store", "ML platform", "business impact"
- "recommendation", "ranking", "personalization"
- "forecasting", "anomaly detection", "fraud detection"

**Screening-Critical vs Boilerplate:**
- CRITICAL: End-to-end production ML, measurable business impact
- BOILERPLATE: "passion for AI", "interest in ML"

---

### Research Engineer / Scientist (Frontier)

**Frequent Requirements:**
- Publications at top venues (NeurIPS, ICML, ICLR)
- Research experience: reasoning, planning, agents
- SWE-bench, coding agents, program synthesis
- Reflection, supervisor-worker, workflow reuse
- Long-horizon task decomposition

**Recurring Keywords:**
- "research engineer", "research scientist"
- "reasoning", "planning", "SWE-bench", "coding agent"
- "reflection", "supervisor-worker", "workflow reuse"
- "compositional generalization", "long-horizon"
- "task decomposition", "LLM-as-judge", "structured generation"

**Screening-Critical vs Boilerplate:**
- CRITICAL: Top-venue publications, novel research contributions
- BOILERPLATE: "research mindset", "curiosity"

**Emerging Trends:**
- Inference-time compute scaling
- Verifiable reward signals (execution-grounded)
- Agent evaluation beyond token-level metrics

---

## Cross-Cutting Patterns

### ATS-Sensitive Terminology (Must Mirror)

| Category | Terms to Include |
|----------|------------------|
| Agentic AI | "LangGraph", "multi-agent", "tool calling", "function calling", "agentic RAG" |
| Evaluation | "vLLM", "benchmarking", "HumanEval", "SWE-bench", "model evaluation" |
| Inference | "TensorRT", "Triton", "distributed serving", "SLO", "latency optimization" |
| ML Engineering | "Kubernetes", "MLOps", "feature store", "model registry", "pipeline" |
| RL/Post-Training | "RLHF", "DPO", "PPO", "GRPO", "reward model", "SFT", "LoRA" (DO NOT CLAIM) |

### Degree Requirements Trends

- **PhD Required**: ~15% of Research Engineer/Scientist roles (mostly frontier labs)
- **PhD Preferred**: ~35% of Research roles
- **M.S. Acceptable**: ~70% of Applied/Engineering roles
- **No Degree Specified**: ~20% (skills-based hiring increasing)

### Experience Level Trends

- **0-2 years**: Rare for target roles
- **3-4 years**: Sweet spot for Applied/Engineering roles (matches candidate)
- **5-6 years**: Senior/Staff roles
- **8+ years**: Principal/Architect (avoid)
- **Not Specified**: ~25% of postings

### Location Trends

- **San Francisco Bay Area**: 35% of target roles
- **New York City**: 20%
- **Seattle**: 15%
- **Remote-US**: 15%
- **Other US**: 10%
- **International (London, Toronto, etc.)**: 5% (often separate reqs)

### Visa Sponsorship

- **Explicitly Sponsors**: Most T1/T2 companies (Databricks, Cohere, Together, Scale, etc.)
- **Case-by-Case**: Some startups
- **Does Not Sponsor**: Rare for AI/ML roles at funded companies
- **Strategy**: Target H-1B sponsors; referrals bypass ATS filters

---

## Company-Specific Patterns

### Cohere
- Heavy Agentic AI, Applied Research, Platform hiring
- NYC office expanding (target location)
- GT alumni network strong (8 identified)
- Email: `first@cohere.com` (94%)

### Anthropic
- Evaluation/Inference, Safety, Alignment, Post-Training
- PhD preferred for Research roles
- Referral mandatory for frontier roles
- US remote-friendly for many roles

### Together AI / Fireworks AI
- Inference optimization, vLLM, serving
- Strong alignment with ARTEMIS/CERBERUS work
- H-1B sponsors, SF-based

### Databricks
- Mosaic AI, ML Platform, Inference, Agentic AI
- Strong GT alumni, H-1B sponsor
- Forward Deployed Engineer roles (customer-facing)

### Salesforce Research
- Agentic AI, Einstein GPT, Applied Research
- Strong GT pipeline, enterprise ML scale
- T1 Quick Win tier

### Scale AI
- Frontier Agents, Evaluation, Data Engine
- Agentic Tooling & Productivity roles
- H-1B sponsor, SF/NYC

### NVIDIA / Google / Meta / Microsoft / Amazon
- T2 Target tier
- Massive scale, strong H-1B
- PhD preferred for Research, M.S. OK for Applied/Engineering
- Need referral for best odds

### Frontier Labs (OpenAI, Anthropic, DeepMind, xAI)
- T3 Stretch tier
- Referral + preprints MANDATORY
- PhD strong preference
- Publication filter applied

---

## Skill Gap Analysis (Candidate vs Market)

### Candidate Strengths (Well-Represented in Market)
- Agentic AI / Multi-agent (LangGraph) — HIGH demand
- Production ML systems — HIGH demand
- LLM Evaluation / Inference (vLLM) — HIGH demand
- VLM Routing / Multimodal — GROWING demand
- Geometric/Execution-grounded verification — UNIQUE differentiator

### Candidate Gaps (Market Demands, Candidate Lacks)
- RLHF/RLAIF/DPO/SFT/LoRA — HIGH demand in post-training roles (valid targets; attainability lowered where deep specialization is required — see ROLE_FIT_RULES.md §2)
- Distributed LLM Training (FSDP, DeepSpeed, Megatron) — MEDIUM demand
- JAX/TPU — GOOGLE/DEEPMIND specific
- CUDA Kernel / Triton — HIGH demand in inference optimization
- Kubernetes — MEDIUM demand (MLOps roles)
- SWE-bench/WebArena results — GROWING demand for agent eval

### Strategic Recommendations
1. **Double down on Agentic AI + Evaluation** — strongest market fit
2. **Submit arXiv preprints (CAD, ARTEMIS, CERBERUS)** — critical for T3 applications
3. **Build distributed training demo** — even small multi-GPU LoRA fills gap
4. **Activate referral network** — 30%+ of applications should have referrals
5. **Target T1 companies first** — Cohere, Databricks, Together, Fireworks, Salesforce, Scale
---

# Data-Derived Market Patterns (auto-generated 2026-08-22)
**Basis:** 146 active JDs with extracted features (`job_research/data/jd_features.csv`).
Regenerate via `python3 scripts/backfill_jd_features.py`. The prose sections above
are historical LLM-written patterns retained for context; this section is the
data-driven source of truth.

## Work-Type Distribution (active JDs)
- 5_general_engineering: 108 (73%)
- 3_research_heavy_engineering: 11 (7%)
- 2_applied_research_rd: 10 (6%)
- 4_applied_ai_engineering: 10 (6%)
- 1_research: 7 (4%)

## Most-Required Skills (frequency across JDs)
- go: 134 (91% of JDs)
- ppo: 127 (86% of JDs)
- rag: 115 (78% of JDs)
- evaluation: 87 (59% of JDs)
- python: 58 (39% of JDs)
- safety: 46 (31% of JDs)
- agents: 41 (28% of JDs)
- multimodal: 37 (25% of JDs)
- interpretability: 32 (21% of JDs)
- distributed systems: 31 (21% of JDs)
- agentic: 29 (19% of JDs)
- kubernetes: 21 (14% of JDs)
- inference: 20 (13% of JDs)
- reasoning: 18 (12% of JDs)
- alignment: 17 (11% of JDs)
- benchmark: 16 (10% of JDs)
- reinforcement learning: 14 (9% of JDs)
- fine-tuning: 14 (9% of JDs)
- docker: 12 (8% of JDs)
- retrieval: 12 (8% of JDs)

## Education Requirements
- unspecified: 85 (58%)
- ms_acceptable: 45 (30%)
- phd_preferred: 16 (10%)

## Caveats
- Frequency ≠ importance: 'ppo'/'go' hit rates are inflated by boilerplate keyword
  dumps in auto-generated requirement summaries, not true screening bars.
- Post-training skills (rlhf/dpo/grpo) appear in a meaningful minority — valid targets
  per corrected policy, scored on attainability.