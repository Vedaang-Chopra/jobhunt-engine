# Data Storage Rules

**Source Authority:** This document consolidates data and file management rules from HERMES_JOB_HUNT_SYSTEM_RULES.md, tracking/AGENTS.md, and the modular rule files in `docs/hermes_job_hunt_rules_modular/`

## 1. Structured Data vs Markdown

### Prefer CSV/JSON for:
- Jobs (`tracking/jobs/jobs.csv`)
- Applications (`tracking/applications/applications.csv`)
- Companies (`tracking/companies/companies.csv`)
- Contacts (`tracking/contacts/contacts.csv`)
- Emails/Contact info
- Hiring posts (`tracking/companies/<slug>/hiring_posts.csv`)
- Application queues
- Keyword counts
- Search coverage (`tracking/search_runs/search_runs.csv`)
- Extracted JD features (`job_research/data/jd_features.csv`)
- Outreach messages (`tracking/messages/outreach.csv`)

### Prefer Markdown for:
- Rules (`docs/rules/*.md`)
- Workflows (`docs/workflows/*.md`)
- Summaries and qualitative intelligence
- Architecture/navigation (`README.md`, subsystem `README.md`)
- Explanations and rationale
- Company intelligence narratives (`job_research/companies/<slug>/company-intel.md`)
- Role analysis narratives (`job_research/companies/<slug>/jobs.md`)
- Connection narratives (`job_research/companies/<slug>/connections.md`)

## 2. Canonical File Locations

| Data Type | Canonical Location | Schema |
|-----------|-------------------|--------|
| Master job table | `tracking/jobs/jobs.csv` | `tracking/jobs/SCHEMA.md` |
| Application lifecycle | `tracking/applications/applications.csv` | Inline (see APPLICATION_RULES.md) |
| Company intelligence | `tracking/companies/companies.csv` | Inline |
| Contact database | `tracking/contacts/contacts.csv` | Inline |
| Outreach history | `tracking/messages/outreach.csv` | Inline |
| Search execution logs | `tracking/search_runs/search_runs.csv` | Inline |
| Active job descriptions | `tracking/job_descriptions/active/` | Markdown files |
| Archived job descriptions | `tracking/job_descriptions/archive/YYYY-MM/` | Markdown files |
| Company research (narrative) | `job_research/companies/<slug>/` | Markdown files |
| Role family analysis | `job_research/roles/<slug>/` | Markdown files |
| Market intelligence | `docs/intelligence/JOB_MARKET_PATTERNS.md` | Markdown |
| Job source registry | `docs/sources/JOB_SOURCES.md` | Markdown |

## 3. Job ID Format

Stable identifier format: `{company_slug}_{title_slug}_{source_id_or_hash}`

Examples:
- `cohere_research_engineer_agentic_ai_12345`
- `salesforce_ml_engineer_platform_67890`
- `anthropic_research_engineer_post_training_5183051008`

Never change after creation. Use for all cross-references.

## 4. Description Integrity

Every job in `tracking/jobs/jobs.csv` must have:
- `full_description_hash` — SHA256 of the full job description text
- `description_file` — Path to the archived job description file

The hash must match the archived file content. This enables detection of JD changes.

## 5. Deduplication Rules

Before adding a new job/person/post:
1. Search existing records by stable identifier
2. If exists, update the canonical record in place
3. Retain multiple source URLs/provenance when relevant (append to `source_urls` field)
4. Do not create duplicate records merely because the same item appeared on another platform

### Job Deduplication Key
Primary: `job_id` (stable)
Secondary: `(company, title, location)` normalized

### Contact Deduplication Key
Primary: `contact_id` (stable)
Secondary: `(name, company, linkedin_url)` normalized

## 6. Freshness Tracking

Store `last_seen` / `last_verified` timestamps where useful:
- Jobs: `date_updated`, `last_checked`
- Companies: `last_checked`, `last_searched`
- Contacts: `last_verified_date`
- Search runs: `date` (of run)

Closed roles, stale leads, and superseded records should not remain mixed with active opportunities.

## 7. Archive Before Deletion

When cleaning the project:
1. Inspect the file/data
2. Preserve unique useful information
3. Merge it into the canonical source
4. Archive obsolete/redundant material under `archive/<reason-or-migration>/...` with a manifest
5. Delete only when safely redundant and consistent with project policy

Never perform blind destructive cleanup.

## 8. CSV Conventions

- Use stable identifiers
- ISO 8601 dates (YYYY-MM-DD)
- UTF-8 encoding
- Explicit schemas documented in `SCHEMA.md` or inline
- Quoted multiline fields (use double quotes for fields containing commas, newlines, or quotes)
- No `_new`, `_latest`, `_final`, or agent-name filename suffixes — version history belongs in Git

## 9. Path Conventions

- Use repository-relative paths everywhere
- Never hard-code a user's absolute path
- Scripts use `REPO_ROOT = Path(__file__).parent.parent` pattern

## 10. Schema Evolution

- Add columns only (never remove/rename without migration)
- Document changes in `tracking/jobs/SCHEMA.md` version history
- Migration scripts in `scripts/` for schema changes
- All CSV headers must match schema

## 11. Browser and Tool Usage

### Interface Preference (in order)
1. Reliable structured MCP/API/tool when available
2. Playwright/browser-control MCP for dynamic/interactive websites
3. Manual browser interaction only when necessary

### Browser-Control Rule
When real browser interaction is required, prefer Hermes' Playwright/browser-control MCP. Do not solve research by continuously spawning Chrome tabs.

### Tab Discipline
- Reuse tabs
- Keep a small working set
- Avoid one permanent tab per job/person
- Reuse LinkedIn/company search tabs
- Close temporary tabs when done
- Avoid duplicates
- Clean browser state after completing a task

Typical working set: one LinkedIn search tab, one company-careers tab, one job/application detail tab, temporary tabs only when necessary.

### Task-Oriented Browsing
Every browser session needs a defined objective: e.g. find NVIDIA roles, inspect 15 referral candidates, search recent hiring posts, verify 10 jobs, or fill one application. Complete the goal, persist results, then clean up.

### Authentication
If login is required, ask the user to authenticate directly in the browser and reuse authenticated sessions/autofill/extensions. Never ask to store passwords, OTPs, recovery codes, or secrets in project files/chat.

### Failure Handling
If a site blocks automation or requires login, record the failure, request authentication when needed, continue with other useful sources, and never mark the source as successfully searched when it was not.