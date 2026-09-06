# Opportunity Strategy & Role Fit Rules (CANONICAL)

**Source Authority:** User directive 2026-08-22 (canonical objective) + HERMES_JOB_HUNT_SYSTEM_RULES.md
**Supersedes:** All prior "DO NOT TARGET post-training" language anywhere in this repository. Such language is retired.

---

## 1. Primary Objective

> Secure a strong AI Research Engineer, Applied Research, Applied Scientist, or equivalent
> research-oriented AI role at a good company as quickly as reasonably possible, while
> simultaneously pursuing higher-upside and more competitive research opportunities.

Relevant domains: agentic AI, reasoning systems, LLM systems, evaluation, RAG, tool use,
memory, multimodal systems, **post-training, RL**, inference, and adjacent areas.

The search must be BROAD but ranked intelligently. Never reduce it to agentic AI only,
cybersecurity only, frontier labs only, or post-training only.

---

## 2. Post-Training Policy (CORRECTED)

Post-training is a **valid target family**. There is no automatic exclusion.

- Search post-training, RL/RLHF/SFT/DPO/GRPO, reasoning, alignment, model-improvement,
  synthetic-data, reward-modeling, and inference-adjacent post-training roles.
- Do NOT pretend the candidate has direct production post-training experience.
- Factuality rules (`PROFILE_RULES.md`) still govern resumes: RLHF/DPO/SFT/LoRA/etc.
  remain UNCLAIMABLE skills. Eligibility ≠ claims.
- Scoring impact: deep-specialization requirements LOWER attainability; roles accepting
  strong transferable ML/research/systems experience RAISE attainability.
- Agentic/applied-AI is currently the more attainable specialization — this influences
  RANKING, never ELIGIBILITY.

---

## 3. Opportunity Levels (replaces target/do-not-target binary)

All four levels stay active simultaneously. Level 1/2 being more attainable never stops
Level 3/4 search.

| Level | Name | Definition | Effort |
|-------|------|-----------|--------|
| L1 | High-Probability / High-Advantage | Strong fit + domain advantage (e.g., security-AI: Fortinet alumni angle, Palo Alto Networks, CrowdStrike, Cisco, Cloudflare, Zscaler, SentinelOne) + realistic requirements | Aggressive apply + network |
| L2 | Strong Realistic Research Targets | Credible qualifications for RE/Applied Scientist/ML Research/agentic/genAI/LLM systems/reasoning/eval/infra/multimodal/post-training/inference at good AI companies | Major pipeline share |
| L3 | Optimistic Targets | Not an obvious candidate but transferable evidence justifies applying | Apply + serious networking |
| L4 | Stretch / High-Upside | Frontier labs, specialization-heavy research; lower probability, exceptional upside | Active; selective deep customization |

---

## 4. Company Priority ≠ Role Priority

Company quality and role quality are scored INDEPENDENTLY, then combined:

**Company quality inputs:** technical reputation, AI investment, research quality,
engineering quality, relevant AI teams, career value, stability.

**Role quality inputs:** research component, technical depth, agentic relevance,
post-training relevance, reasoning/eval relevance, experience match, attainability,
growth opportunity.

A P0 company does not make every role there P0. An exceptional role at an unlisted
company can outrank a mediocre role at a top company.

---

## 5. Asymmetric Advantage

Explicitly modeled, never dominant: prior Fortinet experience, cybersecurity expertise,
backend/systems experience, matching research/projects, university/lab connections,
alumni, former colleagues, referrals, recruiter/HM access.

Advantage boosts priority when it creates a credible hiring narrative; it must not
overwhelm role quality.

---

## 6. Search Work, Not Titles

Search broad role families (Research Engineer/Scientist, Applied Scientist, Applied
Research Engineer/Scientist, ML Research Engineer, AI/ML/LLM/GenAI Engineer, Agent &
Agent Platform Engineer, AI/ML Systems Engineer, Inference Engineer, Evaluation
Engineer, Reasoning Engineer, Post-Training Engineer/RE, RL Engineer, AI Security
Researcher, Multimodal Research Engineer) — then read the JD. Generic titles can hold
excellent research work.

---

## 7. Research Alignment Classification (from JD)

Extract experimentation/new-methods/evaluation/hypothesis-testing/model-behavior/
agents/planning/reasoning/tool-use/memory/long-horizon/RAG/retrieval/context-
engineering/multimodal/synthetic-data/fine-tuning/post-training/SFT/RLHF/DPO/GRPO/
reward-modeling/inference/optimization/benchmarks/publications/prototypes/production-
research signals.

Classify work type:
1. Research
2. Applied Research / R&D
3. Research-heavy Engineering
4. Applied AI Engineering
5. General ML Engineering
6. Unrelated / low-value

Preference order: Applied Research / Research Engineering / Research >
research-heavy AI engineering > general AI engineering. No automatic exclusion.

---

## 8. Canonical Scoring Model (12 dimensions)

Every serious job scores independently on:

| # | Dimension | Weight |
|---|-----------|--------|
| 1 | Role Fit | 15% |
| 2 | Research Alignment | 12% |
| 3 | Technical Alignment | 10% |
| 4 | Agentic/Reasoning Alignment | 8% |
| 5 | Post-Training/Model-Improvement Alignment | 8% |
| 6 | Attainability | 15% |
| 7 | Asymmetric Advantage | 8% |
| 8 | Company Quality | 8% |
| 9 | Strategic Career Value | 6% |
| 10 | Referral/Network Strength | 4% |
| 11 | Location Fit | 3% |
| 12 | Urgency/Freshness | 3% |

Rules:
- Configuration lives in `job_research/config/scoring-config.yaml`; the scorer READS it.
- No single keyword may dominate. Keyword hits are EVIDENCE, weighted and capped;
  the model reasons about actual fit, not token counts.
- Human/judgment overrides are allowed and MUST record a reason
  (`override_reason` field).
- Output per job: dimension scores, opportunity level (L1–L4), final priority (0–100),
  explanation, confidence, missing information, recommended action.

### Recommended Actions (map ranking → behavior)

| Action | Meaning | Behavior |
|--------|---------|----------|
| APPLY_NOW | Strong role + strong fit | Customize resume, apply, find referral, identify HM/team, search hiring posts, outreach |
| APPLY | Good fit | Customize appropriately, apply, network when useful |
| OPTIMISTIC | Lower probability, credible | Apply, strong customization, targeted outreach |
| STRETCH | Very competitive, strategic | Apply selectively, deep customization, researcher/referral outreach |
| LOW_PRIORITY | Searchable, low yield | Keep in index; no significant time |
| SKIP | Irrelevant/closed/impossible/unsuitable | Exclude from queue (recorded, reversible) |

---

## 9. Hard Eligibility Gates (user directive 2026-08-26)

Applied BEFORE scoring. A job failing any gate is non-useful: `recommended_action=SKIP`
with reason in notes, exported to `tracking/jobs/non_useful.csv`, master row retained.

| # | Gate | Rule |
|---|------|------|
| G1 | Experience ceiling | Candidate has ~4.5 yrs production ML. JD stating >4.5 yrs as a hard minimum → non_useful. "5+ or equivalent" flexible phrasing → borderline, keep. Judge from full JD context, not regex alone. |
| G2 | Seniority ceiling | Director / VP / Head / Chief / Principal / people-manager titles → non_useful. Staff/Senior/Lead IC roles stay unless JD confirms 8+ yrs requirement (then G1 applies). |
| G3 | Early-career exclusion | Internships, co-ops, new-grad/university pipelines, early-career programs → non_useful. |
| G4 | Pay floor | Posted pay below **$150k** → non_useful. Only enforceable when pay is posted; unposted = no penalty. |
| G5 | Profile fit | Role unrelated to target families (frontend-only, PM, data-analyst, hardware, bioinformatics, sales) → non_useful. Target: Research/Applied Scientist, MLE, AI Engineer with agentic/reasoning/post-training/inference/eval focus. |
| G6 | Link/JD presence | No working link AND no retrievable JD after fetch attempts → non_useful (`no_jd_unreachable`). |

Verdict vocabulary: `useful` / `borderline` (flexible phrasing, partial fit) / `non_useful`.
Borderlines stay in the pipeline; only `non_useful` is excluded.
Enforcement scripts: `audit_phase1.py` (rule gates) + LLM fit-audit; discovery crons MUST
apply these gates at ingest time — never append a gated-out job as open without SKIP marking.

---

## 10. Guided Search Campaigns

Bounded campaigns per `job_research/config/search-campaigns.yaml`
(Security+AI advantage, big-tech research, enterprise/agentic AI, AI infrastructure,
agentic/reasoning, post-training/model-improvement, frontier labs, strong AI startups,
hiring posts, referral search, open discovery). ~80–90% of effort guided by curated
target companies; ~10–20% open-ended discovery.
