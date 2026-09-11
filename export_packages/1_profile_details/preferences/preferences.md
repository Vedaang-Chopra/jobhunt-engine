# Career Preferences

**Source:** Derived from profile.md, SKILLS.md, and positioning documents
**Last Updated:** 2026-08-21

---

## Target Role Families (Priority Order)

*Realigned 2026-08-22 against resume_fact_bank.yaml + resume_custom/rules/ROLE_FAMILIES.md.
Priority reflects verified evidence weight: agentic research is the deepest vein,
model training/architecture is the primary interest, inference is secondary.*

| Priority | Role Family | Fit Rationale | Evidence Anchors | Base Template |
|----------|------------|---------------|------------------|---------------|
| **1** | **Agentic AI / Applied AI Research Engineer** | Deepest research vein: CAD closed-loop pipeline, SHASTRA workflow reuse, ATHENA multi-agent + production agentic RAG at Fortinet | cad_pipeline, shastra, athena_agents, fort_agentic_rag | base_agentic_ai.tex |
| **2** | **MLE — Model Training & Architectures** | Real training experience: DDP distributed training w/ mixed precision on H100/A100 (CERBERUS), trained neural router (ARTEMIS), PPO/DQN training (RL Soccer, academic), 60+ classifiers trained+deployed (Fortinet); architecture design: Matryoshka 4096→128, Perceiver Resampler, TRM decoder, cross-modal alignment | cerberus_alignment, artemis_router, rl_soccer_methods, fort_sla | base_applied_ml.tex |
| **3** | **ML Engineer / Applied Scientist (Production)** | 4.5 yrs production ML: patent, 40x OpenSearch scaling, edge inference, telemetry pipelines | fort_patent, fort_opensearch, fort_onnx, fort_backend | base_applied_ml.tex |
| **4** | **Research Engineer — Agents/Reasoning** | Inference-time search with verifiable rewards, planning, trace-to-graph, structured generation | cad_pipeline, shastra_trace, athena_eval | base_agent_reasoning.tex |
| **5** | **LLM Evaluation / Inference Engineer** | Secondary strength (not primary): vLLM serving 6+ backends, ONNX ~40% latency, eval harnesses (202 tests). Pursue when JD is eval/serving-heavy AND agentic/training angle exists | artemis_router, fort_onnx, cad_evaluation | base_eval_inference.tex |

### Post-Training Note (honest framing)
Model-training interest maps to **training systems, architectures, and distributed
training** (verified: DDP, mixed precision, router training, RL coursework). Pure
LLM post-training algorithms (RLHF/DPO/SFT implementation) remain a documented GAP —
see `resume_custom/positioning/post_training/POSITIONING.md`: valid target FAMILY,
ranked by attainability; never claim hands-on PT implementation. Inference-time
search on frozen models (CAD) is the honest bridge story.

**Target companies by top families:**
- Agentic AI: Cohere, Databricks, Scale AI, Salesforce Research, Together AI, Fireworks AI, Anyscale, W&B, xAI, AI2, Reka, Character.AI, Runway
- Model Training & Architectures / MLE: NVIDIA, Together AI, Anyscale, Databricks, Google, Meta, Amazon, Mistral, xAI, Mosaic-style training teams, CoreWeave-ecosystem teams
- Production MLE: Google, Amazon, Microsoft, Meta (applied), Salesforce, ServiceNow, Snowflake, Palantir

---

## Location Preferences

1. **US Primary:** SF Bay Area, NYC, Seattle, Boston, Atlanta
2. **Remote-US:** Fully remote roles with US-based companies
3. **India:** Only if exceptional fit (T4 specialist companies)
4. **Canada:** Only for Cohere Toronto, other strong T1/T2
5. **Other:** Not preferred — visa complexity

---

## Visa Requirements

- **Current:** F-1 (OPT eligible Dec 2026)
- **Requirement:** H-1B sponsorship required for long-term roles
- **Strategy:** Target H-1B sponsors; referrals bypass ATS filters

---

## Company Tiering System

### Tier 1 — Quick Wins / Mid-Tier (Apply Week 1-2)
Strong profile fit, known H-1B sponsors, active hiring, GT alumni present, referral accessible
- Salesforce Research, ServiceNow, Snowflake, Palantir, Databricks, Cohere, Together AI, Fireworks AI, Anyscale, Scale AI, W&B, Reka, Character.AI, Runway

### Tier 2 — Target / Strong Fit (Apply Week 2-4)
Excellent profile fit, competitive but reachable, some alumni/connections, H-1B history
- NVIDIA (Applied/Research), Google (Applied/Research), Meta (Applied/FAIR), Microsoft (Research/Applied), Amazon (Applied Science), xAI, AI2, Sierra AI, Cognition, Adept

### Tier 3 — Stretch / Frontier (Apply Week 4+ ONLY with Referral + Preprints)
Top-tier labs, referral mandatory, PhD preference, publication filter
- OpenAI (Agent Team), Anthropic (Eval/Inference), DeepMind, Apple (ML Research)

### Tier 4 — Specialist / Niche (High Differentiation, Anytime)
CAD/geometry AI, Siemens-adjacent, simulation, robotics, edge ML
- Siemens, Autodesk, Ansys, Dassault Systèmes, PTC, Hexagon, Cadence/Synopsys, NVIDIA Omniverse, Intrinsic, Covariant/Dexterity

---

## Role Keywords by Family

### Agentic AI / Applied AI Research (Priority 1)
"Agentic", "multi-agent", "LangGraph", "tool use", "function calling", "autonomous agents", "workflow orchestration", "agentic RAG"

### MLE — Model Training & Architectures (Priority 2)
"distributed training", "DDP/FSDP", "mixed precision", "pre-training", "model architecture", "transformer architecture", "training pipeline at scale", "GPU clusters/H100/A100", "PyTorch training", "Matryoshka/embedding learning", "multimodal model training", "RL training/PPO", "large-scale training infrastructure"
*(Excludes pure RLHF/DPO/SFT algorithm roles — see Post-Training Note above.)*

### ML Engineering / Applied Scientist (Production) (Priority 3)
"Production ML", "scale", "ML platform", "end-to-end", "model deployment", "A/B testing", "feature store"

### Agents/Reasoning (Frontier) (Priority 4)
"Reasoning", "planning", "SWE-bench", "coding agent", "reflection", "supervisor-worker", "workflow reuse", "inference-time search/compute"

### LLM Evaluation / Inference Research (Priority 5 — secondary)
"Evaluation", "benchmarking", "vLLM", "inference optimization", "distributed serving", "SLO/SLA"

---

## Application Sequence

| Phase | Timeline | Target | Goal |
|-------|----------|--------|------|
| Quick Wins | Week 1-2 | T1 companies, fit ≥ 3 | 15-20 applications, 3-5 referral conversations |
| Strong Targets | Week 2-4 | T2 companies, fit ≥ 4 | 10-15 applications, 5+ referrals |
| Stretch | Week 4+ | T3 companies | 3-5 highly targeted (referral + arXiv preprint required) |
| Specialist | Continuous | T4 companies | 3-5 conversations, 1-2 applications |

---

## Quality Gates

### Company Research Complete
- company-intel.md has: LinkedIn ID, 3 email formats, target teams, GT alumni count
- connections.csv has ≥ 20 rows with all 18 columns, P0 separated, deduplicated
- jobs.csv has all open roles classified by role family, fit scored
- _company-registry.md updated

### Role Research Complete
- job-postings.csv deduped across companies, all classified
- job-postings.md has top 10 prioritized with fit scores
- companies-hiring.md shows company tier distribution
- _role-registry.md updated

### Application Ready
- Resume variant selected (matches role family)
- Cover letter drafted (company + role specific)
- Referral contact identified (P0/P1) or noted as "cold"
- Entry in pipeline/applications.csv with all fields
- Notion entry created with same data

---

## Anti-Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| Blind "AI Engineer" keyword search | Company-first + role-family targeted searches |
| Dump all jobs in one CSV | Separate by company AND role family, cross-reference |
| Ignore visa sponsorship signals | Tag every JD with visa_mentioned: yes/no/unclear |
| Apply to T3 without referral + preprint | Gate T3 behind referral + arXiv |
| Mix P0 connections with P1-P3 outreach | Separate activation (P0) from building (P1-P3) |
| Stop at first page of results | Scroll to exhaustion (200+ profiles/jobs) |
| Generic "interested in your work" messages | Specific rationale: mutual, alumni, project, publication |
| Forget to update tracking files | Update CSVs + registries + Notion in same session |
| Apply without classifying role family | Every application tagged with primary role family |