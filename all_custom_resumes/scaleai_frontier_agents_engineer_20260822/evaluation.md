# Fit Analysis — Scale AI: Frontier Agents Engineer (Applied AI)

**Job ID:** `scaleai_frontier_agents_engineer_applied_ai_4720573005`
**URL:** https://job-boards.greenhouse.io/scaleai/jobs/4720573005
**Applied:** 2026-08-22
**Canonical fit:** fit_score=81 (Tier B), priority_v2=62.1 (top active greenhouse listing)
**Resume variant:** agentic_ai (Priority-1 role family per preferences.md)

## Requirement → Evidence Mapping

| JD Requirement | Evidence Used | Source |
|---|---|---|
| Production AI agents, multi-agent systems | ATHENA supervisor-worker orchestration (5 agents); CAD closed-loop agent pipeline | athena_agents, cad_pipeline |
| Tool use / function calling / planning | Fortinet agentic RAG: LLM plans multi-step tool calls, structured function calling; SHASTRA workflow reuse | fort_agentic_rag, shastra |
| RAG, retrieval pipelines, vector DBs | Agentic RAG production system; FAISS, cross-modal retrieval in skills | fort_agentic_rag |
| Evaluation frameworks (golden datasets, regression suites, LLM-as-a-Judge) | 202-test harness with VLM-based visual judgment; ablation design | cad_evaluation |
| LLM fundamentals, modern tooling | vLLM serving of 6+ VLM backends; LangChain/LangGraph | artemis_router |
| Production reliability, distributed systems | OpenSearch 50→2,000 events/sec; patent deployment; 4.5 yrs production ML | fort_opensearch, fort_patent |
| Fine-tuning/RL (preferred) | PPO/DQN RL Soccer, neural router training — framed as academic only | rl_soccer_methods |

## Deliberate Framing Choices

1. **CAD bullet reframed**: "inference-time search" framing kept but emphasized
   *autonomous agent workflow with verifiable execution reward* — matches JD's
   "autonomous workflow" + "confidence estimation, reflection" language without
   implying RL post-training (factual guardrail).
2. **Evaluation elevated to its own bullet**: JD has an entire "Experimentation &
   Evaluation" section; base template buried this inside the verification bullet.
3. **Skills reordered**: added explicit RAG/Knowledge and Evaluation categories;
   moved Agentic AI first; added "Reflection & Self-Critique", "A/B Experimentation",
   "Confidence Estimation", "Semantic Search", "Vector Databases" — all backed by
   existing evidence (ATHENA reflection critique, cad_evaluation, FAISS work).
4. **Header tagline**: changed from CAD-specific to "Production agentic AI systems --
   Multi-agent orchestration, planning & tool use -- LLM evaluation -- RAG".
5. **No banned claims**: no RLHF/DPO/SFT/LoRA/fine-tuning claims; RL stays
   "(academic projects)".

## Gaps (honest)

- No enterprise-customer-facing experience (JD prefers it) — mitigated by
  hackathon-to-production and cross-team deployment stories.
- Kubernetes marked UNVERIFIED in profile — omitted from resume.
- Cloud depth is Azure-focused; JD mentions AWS/Azure/GCP. Azure only is claimed.

## Post-Audit Keyword Coverage (2026-08-22)

- Required qualifications: 11/11 keywords present.
- Preferred qualifications: 25/30 present (plurals stemmed).
- Round 2 additions — **candidate-supplied, pending documentation** (user stated in
  session; not yet backed by profile_info artifacts):
  - Small Language Model fine-tuning on edge assistant project → skills line
  - Prompt-level guardrails on agentic RAG output → Fortinet bullet
  - CI/CD experience at Fortinet → systems skills
- Azure is the claimed cloud platform; "(no AWS/GCP)" noted explicitly.
- Deliberately NOT added: AWS, GCP, Kubernetes (UNVERIFIED), tracing, knowledge
  graph, distillation — no evidence supplied for any of these.
- Cover letter corrected: no cloud platform implied except "(Azure-deployed)".
  Earlier "AWS" hit was a substring false positive ("drAWS" in "draws") — no
  hallucination existed in the document itself.

## Factuality Verification

- [x] All metrics trace to profile_info/accomplishments (~70%, ~75%, 50→2000 eps,
      202 tests, 5 agents, 6+ backends, BLEU/CLIPScore, 27% ablation, n=5 raters)
- [x] CAD described as frozen-model execution loop, no RL post-training implied
- [x] RL tagged "(academic projects)"
- [x] No invented experience; every keyword traced to either profile_info
      VERIFIED/SAFE rows or explicit candidate confirmation this session
