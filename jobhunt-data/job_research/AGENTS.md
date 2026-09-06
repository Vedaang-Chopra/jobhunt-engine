# Job Research Subsystem — Agent Rules

**Parent:** Root `AGENTS.md` → This file contains only local additions.

## Scope

This subsystem owns job discovery, qualification, scoring, and market intelligence. It consumes facts from `profile_info/` and writes to `tracking/jobs/`, `job_research/companies/`, `job_research/roles/`, and `job_research/data/`.

## Canonical Assets

- **Configuration:** `config/target-companies.yaml`, `config/role-keywords.yaml`, `config/location-preferences.yaml`, `config/search-schedule.yaml`
- **Company Research:** `companies/<slug>/` (company-intel.md, jobs.md, connections.md, hiring_posts.csv, outreach-log.md)
- **Role Analysis:** `roles/<slug>/` (job-postings.csv)
- **Registries:** `companies/_company-registry.md`, `roles/_role-registry.md`
- **Market Intelligence:** `data/jd_features.csv`, `data/market_analysis.json`
- **Workflows:** `docs/workflows/JOB_SEARCH_WORKFLOW.md`, `docs/workflows/COMPANY_RESEARCH_WORKFLOW.md`
- **Rules:** `docs/rules/JOB_DISCOVERY_RULES.md`, `docs/rules/LINKEDIN_REFERRAL_RULES.md`
- **Sources:** `docs/sources/JOB_SOURCES.md`

## Operational Rules

1. **Canonical profile is source of truth** — All job-fit analysis reads from `profile_info/` (profile.md, skills.md, accomplishments.md, resume_fact_bank.yaml)
2. **Multi-source discovery is mandatory** — Never rely on LinkedIn alone. Use `docs/sources/JOB_SOURCES.md` registry.
3. **Official career page is authoritative** — Verify roles on company career pages; prefer official application URLs.
4. **Single master job table** — `tracking/jobs/jobs.csv` is the only authoritative job list (schema: `tracking/jobs/SCHEMA.md`).
5. **Stable job identifiers** — `job_id` format: `{company_slug}_{title_slug}_{source_id_or_hash}`. Never change after creation.
6. **Description integrity** — `full_description_hash` (SHA256) must match archived job description file.
7. **Role family classification** — Every job classified using `role-keywords.yaml` into: agentic_ai, eval_inference, applied_ml, agent_reasoning, post_training, other.
8. **Fit scoring uses canonical weights** — Role fit (30%), attainability (25%), strategic value (15%), location (10%), referral strength (10%), urgency (10%).
9. **Distinguish company-selectivity from profile-mismatch difficulty** — Different decisions required.
10. **Search coverage tracking** — Every run logs to `tracking/search_runs/search_runs.csv`.
11. **Deduplicate before adding** — Search existing records by `job_id`; update in place; retain multiple source URLs.
> **POST-TRAINING POLICY (CORRECTED 2026-08-22):** Post-training / RL /
RLHF / SFT / DPO / GRPO / reasoning / alignment roles are VALID TARGETS.
They are scored like any other role: deep-specialization requirements lower
attainability; transferable ML/research/systems strength raises it. The candidate's
stronger agentic/applied-AI evidence affects RANKING, never ELIGIBILITY. Resumes must
still obey PROFILE_RULES factuality rules (no unverified skill claims).

## Workflows

### Job Search Workflow (`docs/workflows/JOB_SEARCH_WORKFLOW.md`)
1. Read canonical profile, preferences, source registry
2. Run multi-source discovery (LinkedIn Jobs, Hiring Posts, Career Pages, Greenhouse, etc.)
3. Deduplicate by `job_id`
4. Extract JD intelligence → `job_research/data/jd_features.csv`
5. Score fit, attainability, gaps, strategy, location, connections, urgency
6. Rank application priority
7. Save/update canonical records
8. Update market-pattern intelligence
9. Identify high-priority companies for referral research
10. Report source coverage and failures

### Company Research Workflow (`docs/workflows/COMPANY_RESEARCH_WORKFLOW.md`)
Given a company:
1. Inspect official careers
2. Search configured boards
3. Search LinkedIn Jobs
4. Search recent hiring posts
5. Identify relevant teams
6. Collect and analyze roles
7. Find connections (1st/2nd/3rd, alumni, mutuals, team, HM, recruiters)
8. Inspect strong profiles individually
9. Discover public professional contact info
10. Rank referral/outreach candidates
11. Prepare recommended asks/messages
12. Save/update company directory and aggregate indexes

## Data Outputs

| Output | Location | Format |
|--------|----------|--------|
| Master job table | `tracking/jobs/jobs.csv` | CSV (schema) |
| Per-company jobs | `job_research/companies/<slug>/jobs.csv` | CSV |
| Per-company narrative | `job_research/companies/<slug>/jobs.md` | Markdown |
| Per-company intel | `job_research/companies/<slug>/company-intel.md` | Markdown |
| Per-company connections | `job_research/companies/<slug>/connections.csv` | CSV |
| Per-company hiring posts | `job_research/companies/<slug>/hiring_posts.csv` | CSV |
| Per-role postings | `job_research/roles/<slug>/job-postings.csv` | CSV |
| Company registry | `job_research/companies/_company-registry.md` | Markdown |
| Role registry | `job_research/roles/_role-registry.md` | Markdown |
| JD features | `job_research/data/jd_features.csv` | CSV |
| Market analysis | `job_research/data/market_analysis.json` | JSON |
| Search runs | `tracking/search_runs/search_runs.csv` | CSV |

## Scripts

- `scripts/fetch_greenhouse.py` — Greenhouse job discovery
- `scripts/fetch_greenhouse_comprehensive.py` — Comprehensive Greenhouse fetching
- `scripts/score_jobs_v2.py` — Canonical scorer v2 (12 dimensions; config-driven)
- `scripts/analyze_market.py` — Market pattern analysis
- `scripts/agent_helpers.py` — Browser automation helpers

## Entry Points

- **General search**: Execute `JOB_SEARCH_WORKFLOW.md`
- **Company deep-dive**: Execute `COMPANY_RESEARCH_WORKFLOW.md`
- **Referral research**: Execute `REFERRAL_RESEARCH_WORKFLOW.md` (in linkedin/)
- **On-demand**: `company-deep-dive`, `interview-prep-generator` (from search-schedule.yaml)