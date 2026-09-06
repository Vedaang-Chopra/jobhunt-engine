# Job Discovery Rules

**Source Authority:** This document consolidates job discovery and qualification rules from HERMES_JOB_HUNT_SYSTEM_RULES.md and the modular rule files in `docs/hermes_job_hunt_rules_modular/`

## 1. Multi-Source Search is Mandatory

A request to "search for jobs" means search across the configured source registry, not only LinkedIn.

### Filter-first search rule (mandatory)

Whatever the source, use the site's native filter UI — never a bare keyword
query (see `docs/hermes_job_hunt_rules_modular/08_BROWSER_AND_TOOLS.md`
§ Filter-first search rule):

| Source | Required native filters |
|--------|------------------------|
| LinkedIn Jobs | Date posted, Experience level, Location/Remote, Job type; Company filter on company sweeps |
| LinkedIn People (referrals) | Connection degree (1st/2nd), Current company, Location, Keywords-in-profile |
| LinkedIn Posts | Date posted, Content type (posts), Sort: Latest |
| Indeed | Date posted, Location, Experience level, Remote |
| Company career pages | Department/team, Location, Category filters in the careers portal |

Navigate each search like an agent: open the page, read its filter panel and
result count, apply filters through the UI (or URL params that mirror them),
confirm active filter chips before extracting, then paginate. Record applied
filters in `tracking/search_runs/search_runs.csv`. A keyword-only search is an
incomplete run.

### Canonical Source Registry (`docs/sources/JOB_SOURCES.md`)

The source registry must be maintained in one canonical file and includes:

| Source | Type | Access Method | Priority |
|--------|------|---------------|----------|
| LinkedIn Jobs | Primary | Playwright MCP / Browser | High |
| LinkedIn Hiring Posts | Primary | Playwright MCP / Browser | High |
| Official Company Career Pages | Authoritative | Direct HTTP / Browser | Highest |
| Greenhouse Boards | Structured API | `fetch_greenhouse.py` | High |
| Lever Boards | Structured API | Future skill | Medium |
| Jobride.io | Aggregator | Browser | Medium |
| Indeed | Aggregator | Browser / API | Medium |
| Startup-specific boards (YC, a16z, etc.) | Niche | Browser | Medium |
| Research-oriented boards (AI2, etc.) | Niche | Browser | Medium |
| Search engines (Google, Bing) | Broad | Browser / API | Low |

## 2. Source-Specific Workers

Where runtime supports parallel workers, use logical workers:

1. **LinkedIn Jobs Search** — Search LinkedIn Jobs with role keywords, then apply
   the native filter UI: Date posted (past week), Experience level
   (Associate/Mid-Senior), Location (US / Remote-US), Job type, and
   Company filter for company-specific sweeps. Verify filters registered via
   the active filter chips before extracting results.
2. **LinkedIn Hiring-Post Search** — Search recent LinkedIn posts for hiring signals
3. **External Job-Board Search** — Search Greenhouse, Lever, Indeed, Jobride
4. **Company Career Page Search** — Direct crawl/verify on official career pages
5. **Company Discovery** — Discover new companies via job boards, hiring posts, trends
6. **Referral/People Research** — Find connections at target companies
7. **JD Intelligence** — Extract structured features from job descriptions
8. **Deduplication/Ranking** — Merge duplicates, score, rank

If sub-agents unavailable, execute sequentially. All workers write into the same canonical data model (`tracking/jobs/jobs.csv`).

## 3. Official Career Page is Authoritative

Third-party platforms are discovery sources and can be stale.

When a role matters:
1. Verify it on the company's official career page when possible
2. Prefer the official application URL
3. Retain all discovered source provenance
4. Deduplicate identical postings across platforms

## 4. Company-Specific Search

When given one or more company names:
- Inspect each official career page
- Search LinkedIn Jobs
- Search recent LinkedIn hiring posts
- Search configured external job boards when useful
- Identify relevant teams
- Identify relevant people
- Create/update the company's canonical records in `tracking/companies/`

Do not assume LinkedIn contains all current roles.

## 5. Search Coverage Tracking

Every search run must record in `tracking/search_runs/search_runs.csv`:
- Sources attempted
- Sources successfully searched
- Sources requiring authentication
- Failures
- Skipped sources and reason
- Last search time

Never claim a search was comprehensive if significant configured sources were not checked.

## 6. Job Discovery Configuration

Configuration files in `job_research/config/`:
- `target-companies.yaml` — Company list with tiers, career URLs, target teams, email formats
- `role-keywords.yaml` — Keywords per role family for classification and search
- `location-preferences.yaml` — Geographic tiers with city-level detail
- `search-schedule.yaml` — Cron schedules for automated searches

## 7. Role Classification

Every discovered job must be classified into a role family using `role-keywords.yaml`:
- `agentic-ai` — Agentic AI / Applied AI Research
- `evaluation-inference` — LLM Evaluation / Inference Research
- `ml-engineering` — ML Engineering / Applied Scientist (Production)
- `applied-ai` — Applied AI / Applied Scientist
- `research-engineer` — Research Engineer / Scientist (Frontier)
> **POST-TRAINING POLICY (CORRECTED 2026-08-22):** Post-training / RL /
RLHF / SFT / DPO / GRPO / reasoning / alignment roles are VALID TARGETS.
They are scored like any other role: deep-specialization requirements lower
attainability; transferable ML/research/systems strength raises it. The candidate's
stronger agentic/applied-AI evidence affects RANKING, never ELIGIBILITY. Resumes must
still obey PROFILE_RULES factuality rules (no unverified skill claims).

Classification uses primary keywords (min 2 matches), secondary keywords as tiebreaker, excludes post-training keywords.

## 8. Company Universe

Do not restrict search to AI labs. Include frontier labs, big tech, AI-native startups, semiconductor/inference, AI infrastructure, enterprise AI, robotics/autonomy, security, CAD/design/manufacturing AI, multimodal/vision, developer tools, and serious AI teams inside non-AI-first companies.

Examples such as OpenAI, Anthropic, DeepMind, NVIDIA, Apple, Google, Meta, Microsoft, Amazon, Salesforce, Adobe, Siemens, Cisco are examples only, never the complete universe.