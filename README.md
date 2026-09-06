# Job Applications

This repository is a consolidated, evidence-controlled system for **assisted, human-in-the-loop job search** — from discovery through tracking and follow-ups. It is not an auto-apply bot: every outward-facing action (outreach messages, applications) is drafted by the engine and requires explicit human approval.

**Honest positioning:**

- This is a *decision-support* system. It discovers, scores, drafts, and tracks — it does not submit applications or send outreach on its own.
- LinkedIn automation is fragile: page layouts change, rate limits bite, and logged-in scraping violates ToS. Discovery via hiring posts degrades without warning.
- Workday-hosted applications sit behind account walls; no automated path exists for them. Applications to Workday portals are manual by design.

## Quickstart

```bash
git clone <this-repo> && cd application_hunting
./setup/bootstrap.sh                            # venv, deps, data tree, config seed, test verify
source scripts/env.sh                           # JOBHUNT_HOME / JOBHUNT_REPO / .venv PATH
python -m setup.wizard --apply                  # interactive seeding (optional)
python -m ui.app                                # dashboard at http://localhost:8080
```

Migrating to a new machine? See **`HANDOFF.md`** — it covers data transfer from an
existing install (rsync list), LinkedIn session caveats, and the cron migration path
(`setup/crontab.sample`). Ops schedule & failure playbook: **`CRON_MANIFEST.md`**.
LLM providers are config-driven with a small-model default chain: OpenRouter free
models primary → NVIDIA Build nemotron-super backup (see `config.example.yaml`).

Console scripts after install: `jobhunt-ui` (same as `python -m ui.app`) and
`jobhunt-wizard` (same as `python -m setup.wizard`). See `config.example.yaml`
for LLM provider / email configuration placeholders. Docker alternative:
`docker compose up --build` (UI on port 8080, data persisted in the
`jobhunt-data` volume mounted at `/data`).

## Screenshots

<!-- TODO: add screenshots of the dashboard, jobs, queue, and wizard pages -->
| Page | Screenshot |
|------|------------|
| Dashboard | _placeholder_ |
| Jobs table | _placeholder_ |
| Onboarding wizard | _placeholder_ |

## Architecture

```
job-applications/
├── profile_info/              # Canonical verified career facts (source of truth)
│   ├── profile.md
│   ├── education/
│   ├── experience/
│   ├── projects/
│   ├── research/
│   ├── skills/
│   ├── publications_patents/
│   ├── accomplishments/
│   ├── preferences/
│   └── resume_fact_bank.yaml  # Machine-readable structured facts
├── job_research/              # Job discovery, qualification, scoring
│   ├── config/                # Search configuration (companies, roles, locations)
│   ├── companies/             # Per-company research & intelligence
│   ├── roles/                 # Per-role-family analysis
│   ├── data/                  # Output data (jd_features, market_analysis)
│   └── scripts/               # Automation scripts (discovery, scoring, analysis)
├── resume_custom/             # Resume generation & customization
│   ├── base_variants/         # Canonical LaTeX templates (4 variants)
│   ├── workflows/             # Customization workflow docs
│   ├── positioning/           # Role-family positioning strategies
│   └── evidence/              # Evidence mapping for resume bullets
├── linkedin/                  # LinkedIn profile & networking strategy
├── messaging/                 # Generic outreach templates & policies
├── applications/              # Active per-job application workspaces
├── tracking/                  # Canonical CSV state (jobs, apps, companies, contacts)
│   ├── jobs/                  # Master job table with full descriptions
│   ├── applications/          # Application lifecycle state
│   ├── companies/             # Company intelligence
│   ├── contacts/              # Contact database
│   ├── messages/              # Outreach history
│   ├── search_runs/           # Search execution logs
│   └── job_descriptions/      # Active + archived JD files
├── scripts/                   # Shared automation scripts
├── docs/                      # Project documentation
│   ├── rules/                 # Consolidated domain rules
│   ├── workflows/             # Validated repeatable procedures
│   ├── intelligence/          # Cumulative market intelligence
│   ├── sources/               # Job source registry
│   ├── specs/                 # Specifications (what must be built)
│   ├── plans/                 # Technical plans (how to build)
│   ├── tasks/                 # Executable task breakdowns
│   ├── execution-plans/       # Approved sequential prompts
│   ├── ai_context/            # Machine-readable context
│   ├── human_docs/            # Durable human guides
│   └── session_state.md       # Current phase, blockers, next action
└── archive/                   # Superseded material with manifests
    └── migration_001/         # Migration 001 archived material
```

## Current Workflow

```
Job Discovery (job_research/)
    → Qualification / Ranking (scripts/score_jobs.py)
    → Resume Customization (resume_custom/)
    → LinkedIn Networking (linkedin/)
    → Application Execution (applications/)
    → Tracking & Follow-ups (tracking/)
```

## Canonical Sources of Truth

| Domain | Source |
|--------|--------|
| Career facts (profile, education, experience, projects, research, skills, publications, accomplishments) | `profile_info/` |
| Resume facts & role-family priorities | `profile_info/resume_fact_bank.yaml` |
| Job records & lifecycle | `tracking/jobs/jobs.csv` (schema: `tracking/jobs/SCHEMA.md`) |
| Application state | `tracking/applications/applications.csv` |
| Company intelligence | `tracking/companies/companies.csv` |
| Contacts & outreach | `tracking/contacts/contacts.csv`, `tracking/messages/outreach.csv` |
| Resume templates | `resume_custom/base_variants/` (4 variants) |
| Role positioning | `resume_custom/positioning/` (5 role families) |
| LinkedIn strategy | `linkedin/LINKEDIN_STRATEGY.md` |
| Messaging templates | `messaging/templates/` |

## Canonical Rule Files (Source of Truth for Operations)

| Rule Domain | File |
|-------------|------|
| Profile & Factuality | `docs/rules/PROFILE_RULES.md` |
| Job Discovery & Sources | `docs/rules/JOB_DISCOVERY_RULES.md` |
| Company Research | `docs/rules/COMPANY_RESEARCH_RULES.md` |
| Role Fit, Difficulty, Priority | `docs/rules/ROLE_FIT_RULES.md` |
| LinkedIn Referrals | `docs/rules/LINKEDIN_REFERRAL_RULES.md` |
| JD Intelligence | `docs/rules/JD_INTELLIGENCE_RULES.md` |
| Data Storage & Browser | `docs/rules/DATA_STORAGE_RULES.md` |
| Outreach & Applications | `docs/rules/OUTREACH_RULES.md` |
| Application Workflow | `docs/rules/APPLICATION_RULES.md` |

## Resume Variants (4 Canonical Templates)

| Variant | Template | Target Role Families |
|---------|----------|---------------------|
| Agentic AI | `base_agentic_ai.tex` | Agentic AI / Applied AI Research |
| Evaluation/Inference | `base_eval_inference.tex` | LLM Evaluation / Inference Research |
| Applied ML | `base_applied_ml.tex` | Applied Scientist / ML Engineering (Production) |
| Agent Reasoning | `base_agent_reasoning.tex` | Research Engineer — Agents/Reasoning (Frontier) |

All templates compile with `pdflatex` and reference `resume_style.sty`.

## Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/fetch_greenhouse.py` | Discover jobs from Greenhouse boards |
| `scripts/score_jobs_v2.py` | Canonical 12-dimension scorer (reads scoring-config.yaml) |
| `scripts/analyze_market.py` | Analyze job market patterns |
| `scripts/agent_helpers.py` | Browser automation helpers |

## Company Tiering

- **T1 (Quick Wins):** Strong fit, known H-1B sponsors, GT alumni, referral accessible — Apply Week 1-2
- **T2 (Strong Fit):** Excellent fit, competitive, some connections — Apply Week 2-4
- **T3 (Stretch):** Frontier labs, referral mandatory, PhD preference — Apply Week 4+ with referral + preprints
- **T4 (Specialist):** CAD/geometry AI, Siemens-adjacent — Anytime (high differentiation)

## Visa Status

- **Current:** F-1 (OPT eligible Dec 2026)
- **Requirement:** H-1B sponsorship required for long-term roles
- **Strategy:** Target H-1B sponsors; referrals bypass ATS filters

## Validation

Run repository validator:
```bash
python scripts/validate_repo.py  # (to be created)
```

## Agent Navigation

All agents first read:
1. `~/agent-governance/AGENTS.md` (global)
2. `AGENTS.md` (this file, project-specific)
3. `CONVENTIONS.md` (project conventions)
4. `docs/ai_context/` (CODEBASE_MAP.md, SYSTEM_WORKFLOW_MAP.md, DOC_TAXONOMY.md)

Subsystem agents also read their local `AGENTS.md` before operating.

## Status

Migration 001: **Complete** — Repository restructured from legacy `job_research/` + `resume_custom/` split layout into unified architecture. All canonical sources consolidated. Legacy material archived under `archive/migration_001/` with manifest.

Migration 002: **Complete** — Canonical rules, workflows, and documentation structure established per HERMES_JOB_HUNT_SYSTEM_RULES.md and modular rule files in `docs/hermes_job_hunt_rules_modular/`. Subsystem AGENTS.md updated. Validation pending.

Migration 003: **In Progress** — Aligning consolidated rules in `docs/rules/` with modular rule files, reorganizing data into canonical CSV datasets, creating specialized skills/workers per `11_SUBAGENT_ORCHESTRATION.md`, and validating end-to-end workflow on representative companies (Cohere, Salesforce).