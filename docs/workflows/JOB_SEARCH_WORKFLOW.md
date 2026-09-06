# Job Search Workflow

**Source Authority:** This document defines the canonical end-to-end job search workflow per HERMES_JOB_HUNT_SYSTEM_RULES.md §18.1

## Overview

This workflow orchestrates multi-source job discovery, qualification, and prioritization. It is the primary entry point for finding new opportunities.

---

## Phase 1: Preparation

### Inputs
- Canonical profile (`profile_info/`)
- Role/location preferences (`profile_info/preferences/preferences.md`)
- Configured job-source registry (`docs/sources/JOB_SOURCES.md`)
- Target company list (`job_research/config/target-companies.yaml`)
- Role keywords (`job_research/config/role-keywords.yaml`)

### Read
1. `profile_info/profile.md` — candidate summary, visa status, target roles
2. `profile_info/preferences/preferences.md` — tiering, location preferences, role families
3. `job_research/config/target-companies.yaml` — companies by tier with career URLs
4. `job_research/config/role-keywords.yaml` — keywords per role family
5. `docs/sources/JOB_SOURCES.md` — active source registry

---

## Phase 2: Multi-Source Discovery

### 2.0 Unified Entrypoint (preferred)

Run `python3 scripts/discovery_run.py [--sources l1,l2,career_ops,freshness|all-due]`
as the single entrypoint for a discovery session. It orchestrates L1
(`linkedin_portal_sweep.py`), L2 (`linkedin_recommended_sweep.py`), career_ops
(`career_ops_sweep.py`), and freshness (`freshness_check.py`), logs one summary
row to `tracking/search_runs/search_runs.csv`, self-pauses failing sources
(streak ≥ 2 in `execution_results/ops/health.json`), and locks via
`.hermes/ops.lock`. L1/L2 need an interactive logged-in browser and are skipped
with a clear log line when run unattended.

The full pipeline after discovery is:

```
discovery_run.py            multi-source job discovery + freshness sweep
   ↓
today_queue.py              review views: fresh_jobs_<date>.csv,
                            top_queue.csv, needing_attention.csv
   ↓                          (human review of the daily queue)
contact_discovery.py        ranked people per company (hiring-post posters,
                            existing contacts, optional live LinkedIn,
                            web-search fallback; never-contacted-only)
   ↓
connection_queue.py         approve/send ledger over
                            tracking/messages/connection_requests.csv
                            (draft → approve → record-sent → record-connected;
                             poster_connect_sweep.py drives live sends)
```

Execute searches across all configured sources (sequential or parallel workers):

### 2.1 LinkedIn Jobs Search
For each target company and role family:
- Search LinkedIn Jobs with role keywords, then apply the **native filter UI**:
  Date posted (past week), Experience level (Associate/Mid-Senior),
  Location/Remote, Company filter for company sweeps
- Verify filters registered via active chips + result count before extracting
- Capture: job title, company, location, URL, date posted, team
- Save to `tracking/job_descriptions/active/`

### 2.2 LinkedIn Hiring-Post Search
For each target company:
- Search recent LinkedIn posts through the search UI with native filters:
  Content type = Posts, Date posted = Past Week, Sort = Latest; company facet
  where offered. Confirm chips before extracting
- Signals: "we're hiring", "join my team", "hiring research engineers", "new role on my team", "looking for ML engineers"
- For each relevant post, capture:
  - Poster, poster's role, company, team
  - Role(s) mentioned, date/recency, post URL
  - Application/job URL if present
  - Hiring manager/team member/recruiter/founder classification
  - Connection degree, mutual/alumni signals
  - Why this is a useful lead
- Save to `job_research/companies/<slug>/hiring_posts.csv` and `.md`

### 2.3 Company Career Page Search
For each target company (especially T1/T2):
- Navigate to official career page (`career_url` from config)
- Search/filter for relevant roles using role keywords
- Verify roles found on third-party platforms
- Prefer official application URL
- Save to `tracking/job_descriptions/active/`

### 2.4 External Job Board Search
For configured boards (Greenhouse, Lever, Indeed, Jobride):
- Query via API (Greenhouse) or browser (others)
- Filter using role keywords and exclude keywords
- Save to `tracking/job_descriptions/active/`

### 2.4a career-ops Portal Scanner Sweep (automated multi-ATS)
Run `python3 scripts/career_ops_sweep.py` — this is the preferred first step of
any discovery session because it is fast, zero-token, and covers ~119 tracked
companies across Greenhouse, Ashby, Lever, Workday, and SmartRecruiters APIs:
1. Scanner (`career-ops/scan.mjs`) hits each tracked company's public ATS API
   (config: `career-ops/portals.yml`; company list synced from
   `job_research/config/target-companies.yaml` — add new companies there AND to
   portals.yml after verifying their ATS endpoint).
   To discover new boards at scale, run `python3 scripts/probe_boards.py`
   with a candidate list (`scripts/board_candidates.json`) — it probes
   Greenhouse/Ashby/Lever token endpoints and reports live non-empty boards;
   merge verified results into portals.yml.
2. Importer (`scripts/import_career_ops_scan.py`) dedups against canonical rows
   (job_url + company_slug/source_id), appends unscored rows with provenance in
   notes, never overwrites existing scores/statuses.
3. Sweep logs coverage to `tracking/search_runs/search_runs.csv`.
4. Follow with `score_jobs_v2.py` for any newly imported unscored rows.
Scanner-reachable companies are scanned automatically; companies NOT reachable
via public ATS APIs (Google, Meta, Microsoft, Apple, NVIDIA, Snowflake, W&B,
AI2, Fortinet, etc.) still require browser sweeps under 2.1–2.3.

### 2.5 Company Discovery
- Discover new companies via:
  - Job boards (companies posting relevant roles)
  - LinkedIn hiring posts (companies announcing hiring)
  - Startup databases (YC, a16z, Sequoia, etc.)
  - Research labs and publication affiliations
  - Competitor/adjacent companies
  - Companies employing relevant alumni/former colleagues
- Add new companies to `job_research/config/target-companies.yaml` with tier assignment
- Create company directory in `job_research/companies/<slug>/`

---

## Phase 3: Deduplication

For each discovered job:
1. Generate stable `job_id`: `{company_slug}_{title_slug}_{source_id_or_hash}`
2. Check `tracking/jobs/jobs.csv` for existing record
3. If exists:
   - Update `source_urls` to include new source
   - Update `last_checked` date
   - Update `status` if changed (open/expired/filled)
4. If new:
   - Create new record with all provenance fields
   - Set `status=open`
   - Save full JD to `tracking/job_descriptions/active/`

---

## Phase 4: JD Analysis & Intelligence Extraction

For each new/updated job:
1. Extract structured intelligence:
   - Required skills, preferred skills
   - Recurring technical keywords
   - Responsibilities, frameworks/tools
   - Research expectations, production/system expectations
   - Seniority signals, education requirements
   - Years-of-experience requirements
   - Domain classification (role family)
   - ATS-sensitive terminology
   - Must-have vs nice-to-have distinctions
   - Gaps relative to candidate profile
2. Save extracted features to `job_research/data/jd_features.csv`
4. Update cumulative market intelligence in `docs/intelligence/JOB_MARKET_PATTERNS.md`

---

## Phase 5: Fit, Attainability, and Priority Scoring

For every serious role, estimate (using `scripts/score_jobs.py` or equivalent):

### Component Scores (0-100)
| Component | Weight | Description |
|-----------|--------|-------------|
| Role/Technical Fit | 30% | How closely actual work matches experience, skills, research, projects |
| Attainability/Interview Probability | 25% | How realistic profile passes recruiter/hiring-team screening |
| Strategic Value | 15% | Career upside, learning, company/team quality, research relevance |
| Location Fit | 10% | Matches geographic priorities |
| Referral/Connection Strength | 10% | Realistic referral, intro, alumni, mutual, hiring-manager path |
| Urgency/Freshness | 10% | Posting freshness, closing risk, hiring-post recency |

### Distinguish Two Types of "Hard"
1. **Company-selectivity difficulty** — company/team has very high hiring bar
2. **Profile-mismatch difficulty** — candidate lacks important requirements for this role

These require different decisions.

### Difficulty Categories
- **Strong / Higher-Probability** — Strong fit, attainable, good connections
- **Realistic** — Good fit, competitive but achievable
- **Competitive** — Strong company/team, fit is good but bar is high
- **Stretch** — Frontier lab, PhD preference, referral mandatory
- **Poor Current Fit** — Significant gaps, not worth applying now

### Overall Application Priority
Synthesized from above. Record mechanical score AND judgment override reason if different.

---

## Phase 6: Application Portfolio Strategy

Maintain a balanced portfolio:
- Strong-fit / higher-probability opportunities (T1, some T2)
- Realistic but competitive opportunities (T2, some T1)
- Strategically valuable stretch roles (T3 with referral)
- Selected elite/frontier opportunities (T3, referral + preprints mandatory)

Do not consume all early applications on only the hardest frontier labs.

---

## Phase 7: Save/Update Canonical Records

1. Update `tracking/jobs/jobs.csv` with scored jobs
2. Update `job_research/companies/<slug>/jobs.csv` and `.md` per company
3. Update `job_research/roles/<slug>/job-postings.csv` per role family
4. Update `_company-registry.md` and `_role-registry.md` status fields
5. Identify high-priority companies for referral research (fit ≥ 4, T1/T2)
6. Queue Tier A/B jobs for application in `tracking/applications/applications.csv`

---

## Phase 8: Search Coverage Reporting

Record in `tracking/search_runs/search_runs.csv`:
- Run ID, date
- Sources attempted
- Sources successfully searched
- Sources requiring authentication
- Failures/errors
- Skipped sources and reason
- Total scanned, new jobs found, duplicates skipped, strong fits
- Notes

Never claim a search was comprehensive if significant configured sources were not checked.

---

## Automation

### Scheduled Runs (from `job_research/config/search-schedule.yaml`)
- **Daily (Mon-Fri 9 AM)**: T1 company scan (`daily-t1-job-scan`)
- **Daily (Mon-Fri 10 AM)**: T2 company scan (`daily-t2-job-scan`)
- **Weekly (Mon 9 AM)**: Role-family searches across all companies (`weekly-role-scan`)
- **Weekly (Mon 10 AM)**: Referral search for companies with active apps (`weekly-referral-search`)
- **Weekly (Mon 9 AM)**: Pipeline review (`weekly-pipeline-review`)
- **Daily (8 AM)**: Company news monitor (`company-news-monitor`)

### On-Demand
- `company-deep-dive` — Full company research: jobs + people + intel + news
- `interview-prep-generator` — Interview prep for specific company+role

---

## Output Deliverables

1. Updated `tracking/jobs/jobs.csv` with all discovered/scored jobs
2. Per-company job files in `job_research/companies/<slug>/jobs.md` and `.csv`
3. Per-role-family postings in `job_research/roles/<slug>/job-postings.csv`
4. Updated registries (`_company-registry.md`, `_role-registry.md`)
5. Search run log in `tracking/search_runs/search_runs.csv`
6. Application queue updates in `tracking/applications/applications.csv`
7. Market pattern updates in `docs/intelligence/JOB_MARKET_PATTERNS.md`
8. High-priority referral targets identified