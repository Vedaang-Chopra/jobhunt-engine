# Spec: Job Applications Repository Restructure

**ID:** 001
**Status:** Draft
**Owner:** Project user
**Created:** 2026-08-21

## Purpose

Restructure the existing repository into one coherent Job Applications system
that shares verified career facts and canonical job state across job discovery,
qualification, resume customization, and LinkedIn networking, while leaving
clean extension points for referrals, outreach, application execution,
tracking, and follow-ups.

This is an information-architecture and preservation migration, not a folder
rename. Existing useful information must be understood, consolidated, and
verified before any superseded active copy is archived.

## Affected Modules

- Root governance, README, conventions, dependency/environment declarations,
  and repository validation
- `resume_custom/`, especially `raw_data/`, resume templates, applications,
  job-hunt, LinkedIn, scripts, and the existing archive
- `job_research/`, including discovery/scoring scripts, job descriptions,
  reports, contacts, master CSV, and `job_search/` state
- New canonical profile, LinkedIn, messaging, tracking, application, generated
  output, documentation, and archive areas established by the approved plan
- Top-level historical planning files whose useful content must be consolidated
  before archival

## Requirements

### R1 — Canonical project architecture

The current working directory remains the repository root and becomes one
deliberately organized Job Applications project. Major directories must be
function-oriented, limited in number, and clearly own shared profile data, job
research, resume customization, LinkedIn, messaging, applications, tracking,
scripts, documentation, generated output, and archives.

The design must make referrals, recruiter/email outreach, application
execution, application tracking, and follow-ups natural additions without fully
implementing those future workflows now.

### R2 — Agent and documentation hierarchy

The root `AGENTS.md` must extend the global governance file and define canonical
ownership, read/update behavior, generated-data handling, duplicate resolution,
file conventions, documentation synchronization, and local-instruction
discovery. Initially, a child `AGENTS.md` may be created only where specialized
operational instructions are genuinely required. Job research, resume
customization, and LinkedIn are the expected initial candidates, but each file
must be justified by actual local behavior. Future subsystems may receive one
when their behavior becomes sufficiently specialized. Child files must contain
only local additions.

The root README must concisely explain purpose, current and future workflows,
architecture, canonical sources, generated data, tracking, and agent
navigation. Fragmented Markdown rules must be consolidated by domain.

### R3 — Verified shared career source

Reusable factual career information must have one canonical, structured,
human-reviewable home. The migration must reconcile all relevant material from
`resume_custom/raw_data/`, the structured resume fact bank, resume sources,
evidence indexes, and supporting career documents.

Canonical information must cover profile, education, work experience,
projects, research, skills, publications/patents, accomplishments, career
preferences, and evidence/provenance. Unsupported claims from generated job
reports, candidate profiles, or other agent-created summaries must not enter the
canonical source. Conflicts must be surfaced and resolved conservatively.

Resume-specific transformation and rendering rules must remain in the resume
subsystem and reference shared facts rather than duplicating them.

### R4 — Canonical CSV job and workflow state

CSV remains the persistence format. A documented, migration-friendly schema
must provide canonical tables for jobs and the related application workflow.
The job schema must support at least company, role, location, job URL, source,
date discovered, complete job description, qualification score, rank,
application status, and notes. It must also support stable identity,
description integrity, and lifecycle timestamps needed for safe consolidation.

Existing `jobs_master.csv` and `job_search/state/*.csv` data must be reconciled
without silent loss. The audit found 200 master-job rows and 12 secondary-job
rows with six overlaps, implying approximately 206 distinct records subject to
deterministic migration verification. The 12 queued application rows must be
preserved as queue state, not represented as completed submissions.

Medical/anesthesia jobs and other obvious discovery false positives must remain
traceable historical data but must be explicitly marked rejected or otherwise
excluded from active qualification results.

### R5 — Job-description lifecycle

Individual job-description files may exist only as temporary active working
artifacts. When an application becomes submitted, the system must verify that
the canonical job row retains the complete description and integrity metadata,
append the record to a dated/monthly organized description archive, and remove
the individual active file. Cleanup must be dry-run by default and require an
explicit apply operation.

### R6 — Workflow separation with shared inputs

The active workflow must support this sequence:

```text
Job Discovery
    -> Qualification / Ranking
    -> Resume Customization
    -> LinkedIn Networking
```

Job research owns discovery and scoring logic. Resume customization owns
content selection, ATS optimization, role positioning, formats, variants, and
rendering. LinkedIn owns platform-specific research and networking logic.
Generic reusable message policy/templates belong outside LinkedIn. All consume
the same canonical profile and job state.

### R7 — Scripts, paths, and environment

Reusable automation must be placed with its owning subsystem or in a small
shared scripts area. Moved scripts, imports, shell commands, configuration, and
documentation must use valid repository-relative paths. No active reference may
retain the obsolete external `hermes/job_research` or `hermes/resume_custom`
locations.

The repository must use one root virtual environment and one dependency
declaration. The nested legacy environment, caches, OS metadata, and
rebuildable LaTeX intermediates must be removed only through an approved cleanup
task after their lack of canonical content is verified. Sensitive-looking
archived environment files require separate confirmation before being touched.

### R8 — Preservation and archive provenance

Every superseded file must be read fully before archival. Unique useful content
must be merged into its canonical destination and verified first. Archived
material must be organized by migration/subsystem or lifecycle date and
recorded in a manifest containing original path, archive path, canonical
destination, reason, and preservation status.

The existing `resume_custom/archive/pre_restructure/` history must remain
recoverable. The archive must not become a dumping ground for uncertain active
material.

### R9 — Generated outputs and active state

Reproducible reports and run artifacts must be written under
`execution_results/` with enough run context to reproduce or audit them.
Persistent operational state belongs in canonical tracking CSVs. Generated
reports must not act as factual profile sources or competing master job tables.

### R10 — Repository verification

The completed migration must include automated validation for repository
structure, canonical schema headers and controlled values, record counts and
deduplication, full-description preservation, path/reference validity, archive
manifest completeness, and agent/documentation hierarchy. Existing resume
templates selected as canonical must still render successfully.

### R11 — Working-code preservation

Migration 001 must not redesign working job-discovery, scoring,
resume-generation, or automation code. Code changes are permitted only where a
moved path or reference requires compatibility work, or where an actual
duplicate implementation is eliminated after its equivalence and canonical
owner are verified. Existing behavior and operational entry points must be
preserved.

Architectural or code-quality refactoring that is not required for repository
consolidation must be documented as a separate proposal after this migration;
it must not be bundled into migration 001.

## Out of Scope

- Introducing SQLite, PostgreSQL, or another database
- Submitting real applications or sending messages to external people
- Running a new live job-discovery campaign during the migration
- Fully implementing referral, email, recruiter, application-execution, or
  follow-up automation
- Redesigning, modernizing, layering, or otherwise refactoring working
  discovery, scoring, resume-generation, or automation implementations beyond
  moved-path compatibility and verified duplicate elimination
- Introducing new public-interface architecture solely to satisfy a preferred
  code organization pattern
- Inventing or upgrading career claims without verified supporting evidence
- Renaming the current project-root directory
- Deleting the historical archive created before or during this migration
- Modifying sensitive environment, secret, credential, key, or certificate
  files without a separate explicit confirmation

## Acceptance Criteria

- [ ] The active tree has one documented project architecture with no competing
   legacy project roots and no unnecessary documentation sprawl.
- [ ] One canonical profile source contains all preserved verified facts and
   provenance; active workflow files do not duplicate unsupported factual
   profiles.
- [ ] Resume rules and templates are separated from shared facts, and the retained
   canonical resume variants render successfully.
- [ ] One documented jobs CSV contains the reconciled distinct job population,
   complete descriptions, stable identifiers, scores/ranking fields, lifecycle
   status, and integrity metadata. A migration report accounts for every source
   job row and every description file.
- [ ] All 12 existing queued application records are preserved with accurate
   non-submitted state, and clear schemas exist for applications, companies,
   contacts, messages, and search runs.
- [ ] Obvious false-positive medical roles are excluded from active candidate
   results while remaining traceable.
- [ ] Job research, resume customization, and LinkedIn each have consolidated local
   documentation and only genuinely necessary local agent instructions.
- [ ] All active scripts and documents resolve current repository-relative paths;
   no stale references to the old external Hermes paths remain.
- [ ] Superseded material is archived with a complete migration manifest only
   after useful content is preserved. Redundant active copies and empty
   directories are removed afterward.
- [ ] One root environment/dependency model is documented; nested environments,
    caches, OS metadata, and rebuildable intermediates are absent from the clean
    active project, subject to required destructive-action approval.
- [ ] Root README, root AGENTS, codebase map, workflow map, subsystem documentation,
    and session state agree about canonical ownership and current behavior.
- [ ] The repository validator and focused workflow checks pass, and the final
    change report identifies migrations, consolidations, archives, removals,
    agent hierarchy, workflow, extension points, validation, and genuine
    unresolved issues.
- [ ] Existing job-discovery, scoring, resume-generation, and automation entry
  points retain their pre-migration behavior, except for documented path updates
  and verified removal of duplicate implementations.
- [ ] Every child `AGENTS.md` created during migration is supported by documented
  specialized operational instructions; no child file merely repeats root or
  global rules.

## Validation Plan

- Compare pre-migration and post-migration inventory manifests by original path,
  content hash, disposition, and canonical destination.
- Validate all canonical CSV headers, row identifiers, required values,
  controlled statuses, description completeness, description hashes, and
  cross-table references.
- Reconcile source-to-target counts and explicitly inspect duplicate and
  conflicting records rather than relying on counts alone.
- Search the full active tree for stale absolute paths, obsolete filenames,
  duplicate rule variants, and references to archived active paths.
- Compile Python sources and run focused unit tests for import, migration,
  scoring, schema, and lifecycle behavior.
- Run representative pre/post-move smoke checks through the existing discovery,
  scoring, resume-generation, and automation entry points and compare outputs
  where deterministic.
- Render each retained canonical LaTeX resume template and confirm expected PDF
  outputs outside source directories.
- Run the repository validator and inspect the important final tree, Git diff,
  and status.

## Known Risks / Limitations

- CSV sources use different identifiers and schemas; naïve URL or title matching
  could merge different jobs or duplicate the same job.
- Existing generated profiles and reports mix accurate facts with unsupported
  model-training and project-impact claims.
- Some contact emails appear inferred rather than verified and must retain an
  explicit verification state.
- Job descriptions contain multiline text/HTML that can be corrupted by unsafe
  CSV handling.
- Existing scripts contain absolute paths and may rely on implicit working
  directories.
- Moving code without redesign still risks behavioral drift through changed
  working-directory assumptions, imports, configuration lookup, or output
  locations.
- Ignored archived environment files may contain sensitive values and cannot be
  inspected or moved under the current authorization.

## Open Questions

None. The project root, function-oriented subsystem organization, Git baseline,
single root environment, mixed Markdown/YAML/CSV canonical formats, and
applied-job-description lifecycle were confirmed during planning. Technical
file-level decisions remain for the plan after this spec is approved.
