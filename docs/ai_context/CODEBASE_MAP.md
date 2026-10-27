# Codebase Map

**Status:** Pre-migration baseline for restructuring 001
**Updated:** 2026-08-21

This map describes the repository as it exists before implementation. Planned
destinations are requirements, not current entry points, until the matching
plan and tasks are approved and executed.

## Current Dependency and Ownership Graph

```mermaid
graph TD
    JR[job_research legacy discovery and scoring]
    JS[job_research/job_search legacy workflow state]
    RC[resume_custom legacy combined workspace]
    RAW[resume_custom/raw_data preferred factual sources]
    RES[resume_custom/resumes resume assets]
    LI[resume_custom/linkedin LinkedIn rules and data]
    JH[resume_custom/job-hunt strategy and configuration]
    APP[resume_custom/applications job workspaces]

    JR --> JS
    JR -. duplicates candidate and job data .-> RC
    RC --> RAW
    RC --> RES
    RC --> LI
    RC --> JH
    RC --> APP
```

## Current Module Ownership

| Area | Current responsibility | Entry points / important assets | Migration concern |
|---|---|---|---|
| `job_research/` | Greenhouse discovery, filtering, scoring, analysis, and generated job reports | top-level Python scripts, `jobs_master.csv`, `job_descriptions/` | hard-coded obsolete absolute paths; mixed source, canonical state, and generated output |
| `job_research/job_search/` | second job-search workflow with policies, templates, handoffs, and CSV state | `AGENTS.md`, `README.md`, `state/*.csv` | duplicated job/profile/rules sources; some unsupported candidate claims |
| `resume_custom/raw_data/` | detailed profile, education, experience, projects, research, skills, publications, and accomplishments | domain Markdown files | preferred factual evidence source, but fragmented and not yet normalized |
| `resume_custom/resumes/` | master, base, and tailored resume assets | LaTeX templates and generated PDFs | facts and transformation/rendering logic are not fully separated |
| `resume_custom/linkedin/` | LinkedIn profile, search, networking, and outreach material | Markdown, CSV, and YAML | LinkedIn-specific rules are mixed with generic messaging and facts |
| `resume_custom/job-hunt/` | role strategy, company research, search configuration, and pipeline notes | configuration YAML and many Markdown files | overlaps job research, tracking, applications, and outreach |
| `resume_custom/applications/` | per-job application workspace template | `TEMPLATE_COMPANY_TEMPLATE_ROLE/` | useful pattern but contains duplicated job/profile material |
| `resume_custom/archive/` | earlier superseded structure | `pre_restructure/` | must be preserved; contains ignored sensitive-looking environment copies |

## Current Public Entry Points

Automation remains script-oriented. LinkedIn Jobs discovery now has a deterministic
production entry point: `scripts/linkedin_job_sweep.py --plan-only|--live`. It consumes
the code-owned `setup/linkedin-job-queries.yaml` catalog (optionally overridden under
`config_lib.data_root()`), performs guest plus authenticated server-rendered retrieval,
and persists per-query history below the canonical data root. The generic
`search_strategy.Planner` remains available for non-cron adaptive experiments but does
not own recurring LinkedIn Jobs query selection.

Recurring LinkedIn people/post research is owned by `scripts/people_sweep.py`.
It validates the active role-keyword schema, ranks bounded packets from qualified
jobs and fresh actionable hiring posts, allocates at most eight filter-first
searches (four post/content plus four relationship paths), scores extracted
people using live-role, activity, relationship, and technical evidence, and
stores run/yield metadata below `config_lib.data_root()`.

## Current Data Sources

| Data | Current location | Current status |
|---|---|---|
| Factual career source | `resume_custom/raw_data/` | preferred source pending canonical consolidation |
| Resume fact bank | `resume_custom/resume_fact_bank.yaml` | useful structured subset; incomplete |
| Discovered jobs | `job_research/jobs_master.csv` | 200 rows plus individual description files |
| Secondary job state | `job_research/job_search/state/jobs.csv` | 12 rows; partially overlaps master data |
| Application queue | `job_research/job_search/state/applications.csv` | 12 queued records; no verified submissions |
| Company/contact/outreach state | `job_research/job_search/state/*.csv` and `job_research/cohere_contacts/` | fragmented; contacts include duplicates and inferred email data |

## What Must Not Be Duplicated

- Verified career facts from the canonical profile source.
- The master job table and full job descriptions.
- Application lifecycle status.
- Contact identities and communication history.
- Resume templates and resume transformation rules.
- Job ranking policy or LinkedIn networking policy.

## Known Gaps

- Canonical directories and schemas do not yet exist.
- Historical path references point outside the current project root.
- Job records overlap without a migration ledger or stable cross-source merge.
- Generated reports contain candidate claims not supported by preferred factual
  sources.
- No repository validator, tests, or root dependency declaration exists yet.
  The root README currently documents the migration gate and must be updated to
  the implemented architecture during migration.
- A nested virtual environment and rebuildable clutter remain in the working
  directory but are ignored by Git pending approved cleanup tasks.
- Working automation has no formal regression suite, so consolidation must use
  focused before/after smoke checks and avoid opportunistic refactoring.

## Changelog

| Date | Change |
|---|---|
| 2026-08-21 | Constrained migration 001 to behavioral preservation; deferred interface redesign. |
| 2026-08-21 | Recorded audited pre-migration ownership and conflicts for spec 001. |
