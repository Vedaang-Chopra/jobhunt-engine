# Canonical Jobs Schema

**Location:** `tracking/jobs/jobs.csv`
**Version:** 1.0
**Last Updated:** 2026-08-21

---

## Schema Definition

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| job_id | string | YES | Stable identifier: `{company_slug}_{title_slug}_{source_id_or_hash}` |
| company | string | YES | Company name |
| title | string | YES | Exact job title from posting |
| location | string | YES | Location(s) as listed |
| job_url | string | YES | Original job posting URL |
| canonical_application_url | string | NO | Direct application URL if different from job_url |
| source | string | YES | Discovery source (greenhouse, lever, workday, company_page, linkedin, indeed, referral, other) |
| date_discovered | date | YES | ISO 8601 date when first discovered |
| date_posted | date | NO | Original posting date from job board |
| date_updated | date | NO | Last update date from job board |
| status | enum | YES | open, expired, filled, withdrawn, archived |
| fit_score | int | YES | 0-100 score from qualification |
| fit_tier | enum | YES | A (85-100), B (70-84), C (55-69), D (40-54), E (0-39) |
| role_family | enum | YES | agentic_ai, agent_reasoning, applied_ml, eval_inference, post_training, other |
| seniority | enum | NO | entry, mid, senior, staff, principal, director, vp, unknown |
| key_requirements | string | NO | Comma-separated key requirements from JD |
| matching_strengths | string | NO | Comma-separated candidate strengths matching JD |
| main_gaps | string | NO | Comma-separated main gaps |
| resume_variant | enum | NO | agentic, applied_ml, eval_inference, agent_reasoning, RL_Post_Training |
| networking_priority | enum | NO | high, medium, low |
| application_priority | enum | NO | high, medium, low |
| last_checked | date | YES | ISO 8601 date of last status check |
| notes | string | NO | Free-form notes |
| full_description_hash | string | YES | SHA256 hash of full job description text for integrity |
| description_file | string | NO | Path to archived job description file (monthly archive) |
| is_medical_false_positive | boolean | NO | true if medical/anesthesia role (false positive from discovery) |

---

## Controlled Values

### status
- `open` — Actively accepting applications
- `expired` — Posting expired/closed
- `filled` — Position filled
- `withdrawn` — Company withdrew posting
- `archived` — Archived for historical tracking (medical false positives go here)

### fit_tier
- `A` — Strong target (85-100)
- `B` — Good target (70-84)
- `C` — Stretch but worthwhile (55-69)
- `D` — Very high stretch (40-54)
- `E` — Not worth applying (0-39)

### role_family
- `agentic_ai` — Agentic AI / Applied AI Research
- `agent_reasoning` — Agents/Reasoning (Frontier)
- `applied_ml` — Applied AI / Applied Scientist / ML Engineering (Production)
- `eval_inference` — LLM Evaluation / Inference Research
- `post_training` — Post-Training / RL (NOT targeted — gap documented)
- `other` — Doesn't fit primary families

### seniority
- `entry` — New grad / 0-2 years
- `mid` — 2-5 years
- `senior` — 5-8 years
- `staff` — 8-12 years
- `principal` — 12+ years
- `director` — Management track
- `vp` — VP level
- `unknown` — Not specified

### source
- `greenhouse` — Greenhouse job board
- `lever` — Lever job board
- `workday` — Workday job board
- `company_page` — Direct company career page
- `linkedin` — LinkedIn job search
- `indeed` — Indeed
- `referral` — Referral from contact
- `other` — Other source

### resume_variant
- `agentic` — base_agentic_ai.tex
- `applied_ml` — base_applied_ml.tex
- `eval_inference` — base_eval_inference.tex
- `agent_reasoning` — base_agent_reasoning.tex
- `RL_Post_Training` — Specialized for post-training roles

---

## Stable Identifier Format

`{company_slug}_{title_slug}_{source_id_or_hash}`

Examples:
- `togetherai_research_engineer_core_ml_4384627007`
- `anthropic_research_engineer_rl_5254364008`
- `databricks_ai_engineer_fde_8546367002`
- `scaleai_senior_frontier_agents_engineer_4720478005`

If no source ID exists, use first 8 chars of SHA256(company + title + location).

## Hash Scheme Change (Migration 003, 2026-08-22)
`full_description_hash` = first 16 hex chars of SHA256 of the JD body text (content between `## Full Job Description Text` and the following `---`, whitespace-collapsed). Previous unverifiable hashes replaced; old values in `archive/migration_003/jobs_pre_migration.csv`.

## Summary Backfill (2026-08-22)
`scripts/backfill_job_summaries.py` populates `key_requirements` / `matching_strengths` / `main_gaps` for every open row from its archived JD file (deterministic extraction, no fabrication). Every open row must carry non-empty `key_requirements`; discovery scripts should leave these to the backfill rather than writing empty rows into the queue. Legacy Wellfound JD files were normalized to the canonical `## Full Job Description Text` format (hashes recomputed).
