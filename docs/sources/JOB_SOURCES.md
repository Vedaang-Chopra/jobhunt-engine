# Job Sources Registry

**Source Authority:** Canonical registry of all configured job discovery sources per HERMES_JOB_HUNT_SYSTEM_RULES.md §6.1

## Purpose

Single source of truth for all job discovery sources. Update this file when adding/removing sources. Do not create separate rules files for new sources.

---

## Source Catalog

| Source ID | Name | Type | Access Method | Auth Required | Rate Limit | Status | Notes |
|-----------|------|------|---------------|---------------|------------|--------|-------|
| `linkedin_jobs` | LinkedIn Jobs | Primary | Playwright MCP / Browser | Yes (LinkedIn login) | 30 req/hr | Active | Primary discovery source |
| `linkedin_hiring_posts` | LinkedIn Hiring Posts | Primary | Playwright MCP / Browser | Yes (LinkedIn login) | 30 req/hr | Active | High-signal, human paths |
| `company_careers` | Official Career Pages | Authoritative | Direct HTTP / Browser | No | 20 req/hr | Active | Source of truth for verification |
| `greenhouse` | Greenhouse Boards | Structured API | `fetch_greenhouse.py` | No | 60 req/hr | Active | 50+ companies supported |
| `lever` | Lever Boards | Structured API | Future skill | No | 60 req/hr | Planned | Many startups use Lever |
| `indeed` | Indeed | Aggregator | Browser / API | No | 60 req/hr | Active | Broad coverage, noisy |
| `jobride` | Jobride.io | Aggregator | Browser | No | 30 req/hr | Active | Startup-focused |
| `yc_jobs` | Y Combinator Jobs | Niche Board | Browser | No | 20 req/hr | Active | Early-stage startups |
| `a16z_jobs` | a16z Portfolio Jobs | Niche Board | Browser | No | 20 req/hr | Planned | AI-heavy portfolio |
| `wellfound` | Wellfound (AngelList) | Niche Board | Browser | Yes | 30 req/hr | Planned | Startup jobs |
| `google_careers` | Google Careers | Company | Browser | No | 20 req/hr | Active | Direct for Google roles |
| `meta_careers` | Meta Careers | Company | Browser | No | 20 req/hr | Active | Direct for Meta roles |
| `amazon_jobs` | Amazon Jobs | Company | Browser | No | 20 req/hr | Active | Direct for Amazon roles |
| `microsoft_careers` | Microsoft Careers | Company | Browser | No | 20 req/hr | Active | Direct for Microsoft roles |
| `nvidia_careers` | NVIDIA Careers | Company | Browser | No | 20 req/hr | Active | Direct for NVIDIA roles |
| `ai2_careers` | Allen Institute Careers | Company | Browser | No | 20 req/hr | Active | Research-focused |
| `career_ops_scan` | career-ops Portal Scanner | Structured API (multi-ATS) | `scripts/career_ops_sweep.py` (one command: scan + import + coverage log) | No | Per-run batch | Active | Zero-LLM scanner over public Greenhouse/Ashby/Lever/Workday/SmartRecruiters APIs for ~119 tracked companies (expanded 2026-08-23 from ~32 via `scripts/probe_boards.py` board discovery — 87 live boards added). Results imported into `tracking/jobs/jobs.csv` with `career-ops scan import` provenance in notes; coverage logged to search_runs.csv. Config: `career-ops/portals.yml` (companies + title/location filters), synced from `job_research/config/target-companies.yaml`. Scheduled Mon/Thu 8AM in search-schedule.yaml. Companies without public ATS APIs (Google, Meta, Microsoft, Apple, NVIDIA, Snowflake, W&B, AI2…) still need browser sweeps via linkedin_jobs/company_careers |
| `linkedin_saved_searches_l1` | LinkedIn Saved-Search Sweep (L1) | Primary (browser) | `scripts/linkedin_portal_sweep.py` via `scripts/discovery_run.py --sources l1` | Yes (LinkedIn login) | 30 req/hr | Active | Registry-driven LinkedIn Jobs sweep: 31 saved searches = 8 base (role-family keyword × geo) + 23 C2 company-filtered searches for target companies WITHOUT public ATS coverage. Config: `job_research/config/linkedin_saved_searches.yaml` |
| `linkedin_recommended_l2` | LinkedIn Recommended-Jobs Sweep (L2) | Primary (browser) | `scripts/linkedin_recommended_sweep.py` via `scripts/discovery_run.py --sources l2` | Yes (LinkedIn login) | 30 req/hr | Active | Sweeps LinkedIn's "recommended for you" feed (preferences-driven) and merges deduped rows into `tracking/jobs/jobs.csv` |

---

## Source Configuration

### LinkedIn Jobs (`linkedin_jobs`)
- **Base URL**: `https://www.linkedin.com/jobs/search/`
- **Parameters**: `keywords`, `location`, `origin=JOB_SEARCH_PAGE_JOB_FILTER`, `currentCompany=[company_id]`
- **Search Strategy**: Role keywords from `job_research/config/role-keywords.yaml` + location from `location-preferences.yaml`
- **Filter-first rule (mandatory)**: apply the native Jobs filter UI — Date posted (past week), Experience level (`f_E=2,3`), Location / Remote (`geoId`, `f_WT=2`), Company (`currentCompanyId`) — then verify the active filter chips in the page before extracting. Navigate the UI like an agent; URL params are shortcuts only when they mirror what the UI would set. Record applied filters in `tracking/search_runs/search_runs.csv`.
- **Output**: Job title, company, location, URL, date posted, applicant count, job description
- **Authentication**: User logs in manually; reuse session

### LinkedIn Hiring Posts (`linkedin_hiring_posts`)
- **Base URL**: `https://www.linkedin.com/search/results/content/`
- **Parameters**: `keywords="hiring" OR "we're hiring" OR "join my team"`, `origin=GLOBAL_SEARCH_HEADER`, `currentCompany=[company_id]`
- **Date Filter**: Past 7-14 days
- **Filter-first rule (mandatory)**: use the search UI's Content type = Posts, Date posted = Past Week, Sort = Latest filters; verify chips before extracting.
- **Signals**: "we're hiring", "join my team", "hiring [role]", "new role", "looking for"
- **Output**: Poster, poster role, company, team, role(s) mentioned, date, post URL, job URL, connection degree, mutual signals
- **Authentication**: User logs in manually; reuse session

### LinkedIn Saved-Search Sweep (L1, `linkedin_saved_searches_l1`)
- **Registry**: `job_research/config/linkedin_saved_searches.yaml` — 31 searches total:
  8 `tier: base` searches (role-family keyword × geo: us_remote, atlanta) plus
  23 C2 company-filtered searches generated at registry-load time for target
  companies WITHOUT a public ATS endpoint in `career-ops/portals.yml`
  (`c2_companies_uncovered_by_ats` list; one search per uncovered company).
- **URL params**: `f_TPR=r604800` (posted within last 7 days = freshness),
  `f_E=2%2C3` (Associate + Mid-Senior), `geoId`, `f_WT=2` (Remote).
- **Filter-first rule**: these params mirror LinkedIn's native filter UI
  (Date posted / Experience / Location / Remote). After navigating, verify from
  the page that the filters registered (active filter chips + result count)
  before extracting; if a param is ignored, apply the filter via the UI
  controls instead. Never run a keywords-only search without these facets.
- **Defaults**: max 8 searches per run, 2.0s scroll pause, max 12 scrolls per search.
- **Runner**: `scripts/linkedin_portal_sweep.py --live` (needs interactive,
  logged-in browser; auto-skipped when run unattended/headless).

### LinkedIn Recommended-Jobs Sweep (L2, `linkedin_recommended_l2`)
- **Runner**: `scripts/linkedin_recommended_sweep.py --live` — sweeps the
  logged-in user's "recommended jobs" feed and merges deduped rows into
  `tracking/jobs/jobs.csv`. Same interactive-session requirement as L1.

### Unified Discovery Entrypoint (`discovery_run`)
- `python3 scripts/discovery_run.py [--sources l1,l2,career_ops,freshness|all-due] [--dry-run]`
- Wraps each source in try/except, records per-source status in one summary row
  of `tracking/search_runs/search_runs.csv` (`run_id=discovery_<ts>`).
- Health tracking: failure streaks per source in `execution_results/ops/health.json`;
  streak ≥ 2 self-pauses the source and appends to `execution_results/ops/alerts.log`.
- `.hermes/ops.lock` prevents concurrent double-execution.

### Freshness Tiers (`freshness_check.py`)
Tiered re-verification policy over `tracking/jobs/jobs.csv`, driven by
`priority_v2` score (freshness clock = newest of date_updated/date_posted):
| Tier | Condition | Re-verify interval |
|------|-----------|--------------------|
| weekly | priority_v2 ≥ 68 | every 7 days |
| biweekly | 55 ≤ priority_v2 < 68 | every 14 days |
| stale | below 55 / missing score | re-check after 30 days; expire at 90 days |

HTTP-verified ATS/Greenhouse URLs are expired on 404/410; non-ATS rows past the
stale horizon are flagged rather than force-expired.

### Company Career Pages (`company_careers`)
- **URLs**: From `job_research/config/target-companies.yaml` → `career_url`
- **Platforms**: Workday, Greenhouse, Lever, custom, Ashby, SmartRecruiters
- **Search Strategy**: Site search or filter by department/keywords
- **Verification**: Cross-reference with third-party postings
- **Output**: Official job description, canonical application URL, team/department
- **Authentication**: Usually none required

### Greenhouse API (`greenhouse`)
- **API Endpoint**: `https://boards-api.greenhouse.io/v1/boards/{board_name}/jobs?content=true`
- **Board Names**: From `job_research/config/target-companies.yaml` or maintained list
- **Companies**: 50+ verified boards (Anthropic, Databricks, Together AI, Scale AI, Cohere, etc.)
- **Filtering**: Client-side using `role-keywords.yaml` primary/secondary/exclude keywords
- **Output**: Full job content, metadata, departments, locations
- **Rate Limit**: 60 req/hr, 0.5s delay between requests

### Indeed (`indeed`)
- **Base URL**: `https://www.indeed.com/jobs`
- **Parameters**: `q=[keywords]`, `l=[location]`, `fromage=7` (last 7 days)
- **Search Strategy**: Role keywords + "H1B" filter when available
- **Output**: Job title, company, location, URL, snippet, salary (if listed)
- **Challenges**: Anti-bot, pagination, noisy results

### Jobride (`jobride`)
- **Base URL**: `https://jobride.io/`
- **Focus**: Startup jobs, AI/ML categories
- **Search Strategy**: Category filters + keywords
- **Output**: Curated startup roles, often with direct contact info

---

## Source Priority Matrix

| Scenario | Primary Source | Verification Source | Supplemental |
|----------|---------------|---------------------|--------------|
| General search | LinkedIn Jobs + Greenhouse | Company Careers | Indeed, Jobride |
| Company-specific | Company Careers + LinkedIn Jobs | Greenhouse (if applicable) | Hiring Posts |
| Referral research | LinkedIn Hiring Posts + LinkedIn People | Company Team Pages | — |
| Fresh postings | LinkedIn Jobs (sort by date) | Company Careers | Greenhouse |
| Startup roles | Jobride + YC Jobs + Wellfound | Company Careers | LinkedIn Jobs |
| Research roles | Company Careers (Research pages) | LinkedIn Jobs | AI2, university boards |

---

## Search Coverage Requirements

Every search run MUST record in `tracking/search_runs/search_runs.csv`:
- `sources_attempted` — list of source IDs tried
- `sources_successful` — list of source IDs that returned results
- `sources_auth_required` — list of source IDs requiring authentication
- `sources_failed` — list of source IDs with errors
- `sources_skipped` — list of source IDs skipped with reason
- `last_search_time` — ISO timestamp

**Never claim comprehensive search if significant configured sources were not checked.**

---

## Adding New Sources

To add a new source:
1. Add row to Source Catalog table above
2. Add configuration section below
3. Update `job_research/config/search-schedule.yaml` if scheduled
4. Create/update skill for access method (Playwright, API, etc.)
5. Test and verify deduplication works with canonical `job_id`

---

## Source-Specific Skills

| Source | Skill | Description |
|--------|-------|-------------|
| LinkedIn Jobs | `linkedin-job-scraper` | Playwright-based LinkedIn Jobs search |
| LinkedIn Posts | `linkedin-hiring-post-scraper` | Playwright-based hiring post search |
| LinkedIn People | `linkedin-referral-strategy` | Connection research workflow |
| Greenhouse | `career-automation` (built-in) | `fetch_greenhouse.py` script |
| Company Careers | `career-automation` / `web-search` | Browser automation for career pages |
| Indeed | `web-search` / `browser-automation` | Browser-based Indeed search |

---

## Rate Limits & Safety

From `job_research/config/search-schedule.yaml`:

```yaml
rate_limits:
  linkedin_requests_per_hour: 30
  indeed_requests_per_hour: 60
  career_page_requests_per_hour: 20
  delay_between_requests_seconds: 5
  max_pages_per_search: 10
  max_profiles_per_company: 200

retry:
  max_attempts: 3
  base_delay_seconds: 10
  exponential_backoff: true
```

---

## Authentication Handling

**LinkedIn**: User must authenticate manually in browser. Reuse existing session. Never store credentials.

**Company Career Pages**: Usually no auth required. Some Workday instances may require login for application (not for viewing).

**API Sources (Greenhouse, Lever)**: No authentication required for public job boards.

**Email/Contact Discovery**: Only use publicly listed information. Never guess emails or use third-party finders.

---

## Deprecated / Removed Sources

| Source | Reason | Date Removed |
|--------|--------|--------------|
| (none yet) | — | — |

---

## Validation Checklist

Before each search run, verify:
- [ ] Source registry is current (no deprecated sources active)
- [ ] Rate limits configured in search-schedule.yaml
- [ ] Authentication sessions available for LinkedIn
- [ ] Target company list loaded from target-companies.yaml
- [ ] Role keywords loaded from role-keywords.yaml
- [ ] Output directories exist (tracking/job_descriptions/active/, job_research/data/)
- [ ] Search run logging ready (tracking/search_runs/search_runs.csv)