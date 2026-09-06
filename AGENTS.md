# Job Applications — Project Agent Rules

Extends: `~/agent-governance/AGENTS.md`

Read the global file first. Its rules and skills apply unchanged. This file
contains only project-specific additions.

## Project Purpose

This repository is the canonical workspace for the user's job-application
workflow: discovery, qualification, resume customization, LinkedIn networking,
referrals, outreach, application execution, tracking, and follow-ups.

## Canonical Operating Model

The system operates per the modular rule files in `docs/hermes_job_hunt_rules_modular/` which define:
- Core operating principles (judgment over blind search, ask instead of assume, separate facts from judgments, preserve provenance, reuse successful patterns)
- Candidate profile and search strategy (`01_PROFILE_AND_PREFERENCES.md`)
- Geography rules (`01_PROFILE_AND_PREFERENCES.md`)
- Company discovery rules (`03_COMPANY_RESEARCH.md`)
- Job discovery sources (multi-source mandatory) (`02_JOB_DISCOVERY_AND_SOURCES.md`)
- LinkedIn hiring-post discovery (`06_LINKEDIN_HIRING_POSTS.md`)
- Role analysis: fit, difficulty, priority (separate fit from attainability) (`04_ROLE_FIT_DIFFICULTY_PRIORITY.md`)
- Job description intelligence (preserve source, extract structured intelligence, aggregate patterns) (`07_JOB_DESCRIPTION_INTELLIGENCE.md`)
- LinkedIn referral and connection research (`05_LINKEDIN_REFERRALS.md`)
- Email and contact discovery (`10_OUTREACH_AND_APPLICATIONS.md`)
- Outreach strategy (`10_OUTREACH_AND_APPLICATIONS.md`)
- Browser and tool rules (prefer MCP/API, then Playwright, then manual) (`08_BROWSER_AND_TOOLS.md`)
- Canonical project structure (`09_DATA_AND_MARKDOWN_STRUCTURE.md`)
- Markdown governance (`09_DATA_AND_MARKDOWN_STRUCTURE.md`)
- Data and file management (`09_DATA_AND_MARKDOWN_STRUCTURE.md`)
- Migration requirements (`12_EXISTING_PROJECT_MIGRATION.md`)
- End-to-end workflows (`docs/workflows/`)
- Human-in-the-loop policy (`10_OUTREACH_AND_APPLICATIONS.md`)

All agents must read the relevant modular rule files for their domain.

## Canonical Documentation Structure

```
docs/
├── hermes_job_hunt_rules_modular/  # Modular rule files (source of truth)
│   ├── 00_README.md
│   ├── 01_PROFILE_AND_PREFERENCES.md
│   ├── 02_JOB_DISCOVERY_AND_SOURCES.md
│   ├── 03_COMPANY_RESEARCH.md
│   ├── 04_ROLE_FIT_DIFFICULTY_PRIORITY.md
│   ├── 05_LINKEDIN_REFERRALS.md
│   ├── 06_LINKEDIN_HIRING_POSTS.md
│   ├── 07_JOB_DESCRIPTION_INTELLIGENCE.md
│   ├── 08_BROWSER_AND_TOOLS.md
│   ├── 09_DATA_AND_MARKDOWN_STRUCTURE.md
│   ├── 10_OUTREACH_AND_APPLICATIONS.md
│   ├── 11_SUBAGENT_ORCHESTRATION.md
│   ├── 12_EXISTING_PROJECT_MIGRATION.md
│   └── HERMES_BOOTSTRAP_PROMPT.md
├── rules/                          # Consolidated domain rules (derived from modular)
│   ├── PROFILE_RULES.md
│   ├── JOB_DISCOVERY_RULES.md
│   ├── COMPANY_RESEARCH_RULES.md
│   ├── ROLE_FIT_RULES.md
│   ├── LINKEDIN_REFERRAL_RULES.md
│   ├── JD_INTELLIGENCE_RULES.md
│   ├── DATA_STORAGE_RULES.md
│   ├── OUTREACH_RULES.md
│   └── APPLICATION_RULES.md
├── workflows/                      # Validated repeatable procedures
│   ├── JOB_SEARCH_WORKFLOW.md
│   ├── COMPANY_RESEARCH_WORKFLOW.md
│   └── REFERRAL_RESEARCH_WORKFLOW.md
├── intelligence/
│   └── JOB_MARKET_PATTERNS.md
├── sources/
│   └── JOB_SOURCES.md
├── specs/
├── plans/
├── tasks/
├── execution-plans/
├── ai_context/
└── session_state.md
```

## Canonical Ownership

- Reusable, verified career facts belong in `profile_info/`. Resume, scoring,
  LinkedIn, referral, and outreach workflows must reference these facts rather
  than copy them.
- Resume-specific selection, ATS, positioning, formatting, and rendering rules
  belong in `resume_custom/`.
- Job records and lifecycle state belong in `tracking/`; the canonical job
  record retains the full job description.
- Job discovery and qualification logic belongs in `job_research/`.
- LinkedIn-specific research and networking logic belongs in `linkedin/`.
- Generic message policy and reusable outreach templates belong in
  `messaging/`.
- Job-specific working artifacts belong in `applications/` while active and in
  the organized archive when superseded.
- Run-generated, reproducible reports belong in `execution_results/`, not in
  source or canonical-data directories.

## Agent Read and Update Rules

1. Read the root `README.md`, this file, and the mandatory files under
   `docs/ai_context/` before changing the repository.
2. Read a subsystem's `AGENTS.md` before changing that subsystem. Child files
   contain only local additions; root and global rules remain in force.
3. Update a canonical fact only when supported by evidence. Record provenance
   with the fact; do not infer accomplishments from job-search material.
4. Update canonical job rows in place by stable job identifier. Do not create a
   second master job table.
5. Preserve useful unique content before archiving a superseded file. The
   migration manifest must identify the old path, canonical destination, and
   reason.
6. Do not create a Markdown file for a small rule, note, or run result. Extend
   the appropriate canonical `README.md`, `RULES.md`, schema, or execution
   result unless the documentation taxonomy requires a separate artifact.
7. When structure, schemas, or workflow behavior change, update the root
   README, codebase map, workflow map, affected subsystem README, and session
   state in the same change.

## Migration Code-Preservation Rule

Migration 001 consolidates repository information architecture; it does not
redesign working job-discovery, scoring, resume-generation, or automation code.
Change working code only when required to resolve a moved path/reference or to
remove an actual duplicate implementation after equivalence is verified.
Preserve existing behavior and entry points. Propose architectural or code
refactoring separately after consolidation.

## Child Agent Instructions

Create a subsystem `AGENTS.md` only when specialized operational instructions
are genuinely required. Job research, resume customization, and LinkedIn are
the expected initial candidates, but candidacy alone does not justify a file.
Future subsystems may receive local instructions when their behavior becomes
sufficiently specialized. Child files must contain only local additions and
must not repeat root or global governance.

## Job Description Lifecycle

Individual job-description files are temporary working artifacts. Before an
application is marked `submitted`, verify that the canonical job row contains
the complete description and integrity metadata. Then append the record to the
appropriate monthly job-description archive and remove the individual active
copy. Lifecycle cleanup must support a dry-run and require an explicit apply
mode.

## Data and File Conventions

- CSV is the current persistence format; do not introduce a database during
  migration 001.
- Use stable identifiers, ISO 8601 dates, UTF-8, explicit schemas, and quoted
  multiline fields.
- Use repository-relative paths. Never hard-code a user's absolute path.
- Preserve historical artifacts under `archive/<reason-or-migration>/...` with
  a manifest. Do not use the archive for uncertain operational material.
- Version history belongs in Git, not `_new`, `_latest`, `_final`, or agent-name
  filename suffixes.

## Environment

The completed repository will use one root `.venv`. Nested environments are
legacy local state and not source material. Dependencies and validation
commands will be documented by migration 001.