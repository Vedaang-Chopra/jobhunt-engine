# Profile Rules

**Source Authority:** `profile_info/` (canonical verified career facts)

## 1. Canonical Profile Source

All job-fit, referral analysis, resume customization, and outreach workflows must read from the canonical profile in `profile_info/` rather than copying or duplicating facts.

### Required Profile Domains

| Domain | Source File | Purpose |
|--------|-------------|---------|
| Identity & Summary | `profile_info/profile.md` | Executive summary, visa status, contact info |
| Education | `profile_info/education/education.md` | Degrees, GPA, advisors, coursework |
| Experience | `profile_info/experience/fortinet.md`, `profile_info/experience/georgia_tech.md` | Work history, projects, achievements |
| Research | `profile_info/research/research_projects.md` | Graduate research projects with evidence |
| Projects | `profile_info/projects/projects.md` | Project portfolio with evidence mapping |
| Skills | `profile_info/skills/skills.md` | Verified skills + DO NOT CLAIM list |
| Publications & Patents | `profile_info/publications_patents/publications_patents.md` | Papers, patents, targets |
| Accomplishments | `profile_info/accomplishments/accomplishments.md` | Metrics with SAFE/CAUTION/UNSAFE classification |
| Preferences | `profile_info/preferences/preferences.md` | Role families, locations, tiering, visa strategy |
| Machine-Readable Facts | `profile_info/resume_fact_bank.yaml` | Structured facts for automated resume generation |

## 2. Factuality Enforcement

### Verification Rules
- Every metric must trace to `accomplishments/accomplishments.md` with status SAFE, CAUTION, or UNSAFE
- CAUTION metrics must use "~" qualifier (e.g., "~70%", "~40%")
- No technology claimed unless in `skills/skills.md` with status VERIFIED
- No banned claims (see DO NOT CLAIM list in `skills/skills.md`)

### Banned Claims (Non-Negotiable — resume/LinkedIn claims only, NOT target eligibility)
- RLHF, RLAIF, DPO, SFT, LoRA/QLoRA implementation experience; Reward Modeling (RL sense)
- Pre-training / LLM Training, Distributed LLM Training (FSDP, DeepSpeed, Megatron)
- JAX, TPU, CUDA Kernel Programming
- Kubernetes, DeepSpeed, FSDP, Megatron-LM, TensorRT, Triton Inference Server, Airflow/Prefect, MLflow
- "14-agent", "Blackboard controller", "Keyframe synthesis" for ATHENA
- "BLEU +18%", "CLIPScore +22%" — use "+0.18 absolute BLEU-4"
- "100K+ query profiles", "~30% lower cost", "KL-divergence" for ARTEMIS

> **NOTE (2026-08-22):** These are CLAIM restrictions only. Post-training / RL roles are
> valid TARGETS (see ROLE_FIT_RULES.md §2). The candidate may apply to and honestly discuss
> transferable RL-adjacent work (academic PPO/DQN, inference-time search with verifiable
> reward) — but may never claim the banned skills as experience.

### Mandatory Qualifiers
- RL skills (PPO, DQN, Reward Shaping, Curriculum, Self-Play): always qualify as "(academic project)" or "(coursework)"
- CAD project: always state "frozen model, no RL post-training, no fine-tuning"
- Self-reported metrics: always use "~" qualifier

## 3. Role Family Mapping

| Role Family | Resume Template | Primary Positioning |
|-------------|-----------------|---------------------|
| Agentic AI / Applied AI Research | `base_agentic_ai.tex` | Production agentic RAG + multi-agent research (CAD, ATHENA, SHASTRA) |
| LLM Evaluation / Inference Research | `base_eval_inference.tex` | CAD eval harness (202 tests), ARTEMIS routing, CERBERUS edge, ONNX |
| ML Engineering / Applied Scientist (Production) | `base_applied_ml.tex` | 4+ yrs production ML, patent, scaling, edge inference, SLA forecasting |
| Applied AI / Applied Scientist | `base_applied_ml.tex` | Fortinet production ML at scale, patent, automated pipelines |
| Research Engineer / Scientist (Frontier) | `base_agent_reasoning.tex` | Multi-agent orchestration, tool-use, planning, structured generation |
| Post-Training / RL / Model-Improvement | `base_agent_reasoning.tex` | VALID TARGET. Inference-adjacent PT + eval/data angles lead; deep-specialization gaps honestly scored (see ROLE_FIT_RULES.md §2) |

> **POST-TRAINING POLICY (CORRECTED 2026-08-22):** Post-training / RL /
RLHF / SFT / DPO / GRPO / reasoning / alignment roles are VALID TARGETS.
They are scored like any other role: deep-specialization requirements lower
attainability; transferable ML/research/systems strength raises it. The candidate's
stronger agentic/applied-AI evidence affects RANKING, never ELIGIBILITY. Resumes must
still obey PROFILE_RULES factuality rules (no unverified skill claims).

## 4. Geography Rules

**Primary Market:** United States

**Default Preference Order:**
1. San Francisco Bay Area / California
2. Seattle and other major U.S. AI hubs
3. Other strong U.S. opportunities
4. Remote U.S.
5. Very strong India roles
6. Exceptional roles elsewhere

Location is a ranking factor, not a hard exclusion **within the US**. The
hard eligibility rule (enforced by `discovery_lib.scrutinize`):

- ✅ **Anywhere in the United States** — all states/cities + Remote-US.
- ⚠️ **India** — only *very good* roles: priority_v2 ≥ 68 (APPLY tier) or
  explicitly marked exceptional. Accepted rows carry the
  `india_exceptional` flag; lower-priority India rows are rejected
  (`india_below_exceptional`).
- ❌ **All other countries** — UK, Canada, EU, etc. are hard-rejected
  (`location_not_supported`). No exceptions.

## 5. Comparative Advantages

When evaluating roles/companies, explicitly consider:
- Prior employer/competitor adjacency (Fortinet → Cisco, security AI)
- Georgia Tech/alumni links
- Lab relationships (CORE Robotics Lab @ Siemens)
- CAD/design research overlap
- Security/AI background
- Agentic/reasoning work
- Relevant projects
- Former colleagues
- Domain overlap

## 6. Never Invent

Work authorization, years of experience, publications, degrees, skills, relocation preference, compensation, or other eligibility facts. Ask when material information is missing.

## 7. Update Rules

1. Update canonical facts only when supported by evidence
2. Record provenance with the fact (source, date, verification method)
3. Do not infer accomplishments from job-search material
4. When profile changes, update `profile_info/resume_fact_bank.yaml` simultaneously
5. All downstream artifacts (resumes, LinkedIn, applications) derive from canonical source