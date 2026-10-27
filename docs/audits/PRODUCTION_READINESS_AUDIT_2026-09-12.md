# Production-Readiness Audit — 2026-09-12

## Purpose and scope

This is the authoritative audit handoff for converting the job-hunt automation
from its current partially reliable state into a production-ready,
human-in-the-loop system.

Audit mode: read-only. No source code, canonical data, cron, profile,
configuration, browser session, application, outreach, email, or external
service was modified while gathering this evidence.

Authoritative runtime audited:

- Engine repository: `/mnt/DATA/job_hunt/jobhunt-engine`
- Canonical live data root: `/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data`
- Current runtime profile: `job-hunt-fresh`
- Shared browser profile: `~/.hermes/browser-profiles/job-hunt`
- Shared Chrome CDP endpoint: `127.0.0.1:9333`

Do not treat stale repo-local `tracking/` mirrors as canonical. All production
I/O must resolve through `scripts.config_lib.data_root()` / `config_lib.path()`.

## Executive verdict

System status: MATERIALLY UNRELIABLE

The system has useful, tested building blocks: data-root resolution, structured
ATS source ingestion, deterministic scoring and eligibility checks, a shared
browser architecture, and meaningful human approval controls. However, its
production orchestration, health reporting, application-state integrity, and
source observability do not yet support high-volume autonomous operation.

### Readiness decision

- Audit complete: YES
- Safe for high-volume autonomy: NO
- Safe to keep operating only with careful human supervision: PARTIALLY
- Safe to auto-apply, send email, message, connect, comment, like, or submit:
  NO

### Top blockers before trusting automated operation

1. Two overlapping enabled cron fleets (`job-hunt-fresh` and `job-hunt`).
2. Career Ops is launched twice inside every `daily_ops` execution and can
   collide with the dedicated Career Ops cron.
3. LinkedIn authenticated extraction is blocked by login/auth walls and rate
   limits, yet its cron and health states can report success.
4. Application/autofill/recording scripts do not consistently use the
   canonical data root; direct recording can bypass the approval invariant.
5. Canonical data has missing job identifiers, missing job descriptions,
   malformed source-run records, unscored roles, and open-but-disqualified jobs.
6. Tests are not green, so regression prevention is not reliable.

## Verified components that should be preserved

### Canonical data-root resolution

The live runtime environment and `scripts.config_lib.data_root()` both resolve
canonical data to:

`/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data`

Core discovery/scoring logic inspected uses `config_lib` for canonical path
resolution. This should remain the only supported production storage interface.

### Structured source coverage

The live jobs ledger has 956 rows. Current source composition:

| Source | Jobs |
|---|---:|
| Ashby | 387 |
| Greenhouse | 271 |
| LinkedIn | 220 |
| Lever | 60 |
| Wellfound | 18 |

The codebase contains deterministic implementations and contract tests for:

- LinkedIn job discovery (`scripts/linkedin_job_sweep.py`)
- LinkedIn hiring-post collection (`scripts/linkedin_posts_sweep.py`)
- Career Ops import (`scripts/career_ops_sweep.py`, `scripts/import_career_ops_scan.py`)
- ATS scoring (`scripts/ats_check.py`)
- Job scoring (`scripts/score_jobs_v2.py`)
- Eligibility and deduplication (`scripts/discovery_lib.py`)
- Wellfound filtering (`job_research/scripts/wellfound_crawler.py`)

### Human-in-the-loop safeguards

Useful safety controls exist and should be retained:

- Connection queue status progression: pending -> approved -> sent.
- Poster connect logic requires an injected driver, applies a daily cap, and
  stops on CAPTCHA/warnings.
- Email-pattern logic does not permit drafts based on guessed/unverified
  patterns.
- The normal `form_filler --submit` path validates approval values.
- Browser goal contracts prohibit applying, messaging, connecting, posting,
  commenting, and settings actions by default.

### Browser architecture

The documented shared browser approach is directionally correct:

- one persistent job-hunt Chrome profile;
- CDP attachment at port 9333;
- profile and launch locks;
- semantic auth classification;
- immediate stop on auth wall/challenge;
- browser-run logging;
- deterministic action constraints around LLM decisions.

## Production inventory

### Canonical stores

| Store | Canonical path |
|---|---|
| Jobs | `tracking/jobs/jobs.csv` |
| Contacts | `tracking/contacts/contacts.csv` |
| Hiring posts | `tracking/hiring_posts/hiring_posts.csv` |
| Applications | `tracking/applications/applications.csv` |
| Outreach | `tracking/messages/outreach.csv` |
| Search runs | `tracking/search_runs/search_runs.csv` |
| Source health | `execution_results/ops/health.json` |
| Browser run log | `browser_runs/run_log.jsonl` |

All paths in this table are relative to the canonical data root.

### Current active cron fleet: `job-hunt-fresh`

| ID | Name | Schedule | Primary model | Browser dependent | Observed state |
|---|---|---|---|---|---|
| `82576201e9ee` | discovery-career-ops | Mon/Thu 08:00 | Codex Luna | No | Enabled; redundant with daily ops |
| `6b13096cb6ae` | discovery-freshness | Daily 21:00 | Codex Luna | Network | Enabled |
| `8e32da27ceb4` | outreach-batch | Daily 10:00 | Codex Luna | No | Enabled; queue-only intent |
| `b0a56b767fc0` | discovery-linkedin | Every 2h, :00 | Codex Luna | Yes | Enabled; latest run authwall/429 |
| `4ea61ff1eb60` | daily-ops | Daily 08:00 | Codex Luna | Indirect | Enabled; launches duplicate Career Ops work |
| `af86830e28e8` | apps-sync | Daily 20:00 | Codex Luna | HTTP portals | Enabled |
| `83dfabcc37bc` | ops-health | Daily 21:30 | Codex Luna | No | Enabled; incomplete health coverage |
| `e65e2f18c8e6` | linkedin-people-posts-2h | Every 2h, :40 | Codex Luna | Yes | Enabled; latest run authwall |
| `d29ce43ee5bb` | discovery-wellfound | Daily 12:00 | Codex Luna | Separate browser | Enabled; latest run timed out |

### Duplicate legacy fleet: `job-hunt`

The legacy `job-hunt` profile also contains nine enabled jobs, overlapping the
production fleet by name and schedule. It includes the obsolete
`morning-job-digest`, which is documented as a duplicate of `daily-ops`.

The legacy store is a dormant-but-dangerous duplicate until a read-only gateway
ownership check proves it cannot dispatch work. It must not remain enabled once
one production authority is selected.

### Runtime model policy

- `job-hunt-fresh` profile default: OpenAI Codex `gpt-5.6-terra`.
- Active cron jobs: explicitly pinned to OpenAI Codex `gpt-5.6-luna`.
- Fallback behavior could not be proven from cron-list metadata alone.

This profile-default versus per-cron override is allowed only if it is made
explicit in a canonical model policy with rationale, task class, token/runtime
budget, and verified fallback behavior.

## Findings

### F-01 — Critical: duplicate enabled cron fleets

Evidence:

- `~/.hermes/profiles/job-hunt-fresh/cron/jobs.json`: 9 enabled jobs.
- `~/.hermes/profiles/job-hunt/cron/jobs.json`: 9 enabled jobs with overlapping
  names/schedules.

Impact:

- Duplicate scans, scoring, writes, browser contention, and model usage.
- Conflicting old prompts/models can silently execute.
- Shared CSV and browser profile contention can corrupt state or create false
  results.

Required fix:

1. Establish a single production profile, recommended: `job-hunt-fresh`.
2. Verify which gateway can dispatch each store.
3. Pause/archive all legacy `job-hunt` jobs only after the verification.
4. Remove the obsolete `morning-job-digest`.

Acceptance criteria:

- Exactly one enabled scheduled job exists for each workflow name.
- Cron inventory and the chosen profile store agree.
- No duplicate run records appear during a normal scheduler cycle.

### F-02 — Critical: Career Ops runs twice in daily operations

Evidence:

- `scripts/daily_ops.py:62-68` invokes `scripts/career_ops_sweep.py`.
- `scripts/daily_ops.py:71-82` then invokes `discovery_run.py --sources
  career_ops,freshness`, which invokes Career Ops again.
- Dedicated `discovery-career-ops` also runs Monday/Thursday at 08:00, the
  same nominal time as `daily-ops`.

Impact:

- Duplicated external scanning, importing, scoring, and cost.
- Race and duplicate-write risk.
- Misleading digest counts because scanner-new, imported-new, historical rows,
  and duplicates are not clearly separated.

Required fix:

Choose one owner:

- Recommended: the dedicated Career Ops cron owns scan/import; daily ops only
  consumes the latest result and renders it.
- Alternative: daily ops owns scan/import and the dedicated cron is removed.

Acceptance criteria:

- One Career Ops scan/import occurs per intended cadence.
- Daily digest reports scanned, raw candidates, eligible, newly inserted,
  duplicates, gated, and failed counts distinctly.
- One locking mechanism protects all write-capable Career Ops paths.

### F-03 — High: LinkedIn browser extraction is not currently operational

Evidence from latest inspected LinkedIn job-discovery output:

- 8 searches planned.
- Guest API: 45 cards, 44 unique candidates.
- 3 guest requests received HTTP 429.
- Logged-in path: `checkpoint_lg_consumer_login` / authwall.
- 3 logged-in requests received HTTP 429.
- 0 jobs appended.

Evidence from latest people/hiring-post output:

- Planning gate passed with one target packet and eight planned surfaces.
- Fresh LinkedIn feed navigation redirected to `/uas/login`.
- 0 posts examined, people queries, profiles inspected, engagement candidates,
  or new contacts.

Impact:

- Current LinkedIn job, hiring-post, referral, and people discovery is not
  producing usable results.
- Cron `ok` does not mean required browser extraction occurred.
- Browser/model budget is wasted on repeated partial failures.

Required fix:

1. Restore the authenticated session manually in the dedicated Chrome profile
   if the session is genuinely expired.
2. Emit typed outcomes from every LinkedIn workflow:
   - browser reachable;
   - CDP attach success;
   - auth state;
   - challenge state;
   - rate-limit state;
   - guest retrieval count;
   - authenticated retrieval count;
   - new rows;
   - duplicates;
   - partial/failure reason.
3. Treat guest-only retrieval as partial/failure when authenticated retrieval is
   required by the workflow.
4. Do not call the run successful unless its required extraction path completed.

Acceptance criteria:

- Login/auth wall produces `AUTH_REQUIRED`, not `ok`.
- 429 produces `RATE_LIMITED`, not `ok`.
- A true zero-new run can be distinguished from no-browser/no-auth/partial run.
- Digest and health surface the exact state.

### F-04 — High: Wellfound crawler spends budget without demonstrated yield

Evidence:

Latest observed cron run:

- 243 listings found.
- Detail-page processing hung.
- Process terminated after approximately seven minutes.
- 0 jobs appended.

Impact:

- Daily browser/runtime cost without discovered canonical jobs.
- The run can be recorded as successful despite being incomplete.

Required fix:

- Add per-detail timeout.
- Add resumable cursor/checkpoint.
- Ingest explicitly safe partial results, with provenance.
- Persist incomplete/timeout outcome separately from success.
- Measure qualified-new-job yield before retaining daily cadence.

Acceptance criteria:

- One bad listing cannot hang the crawler.
- Run result reports listing count, details attempted, details completed,
  eligible, new, duplicate, and failure count.
- A measured pilot determines whether to keep, reduce, or retire the source.

### F-05 — Critical: application scripts split from canonical data root

Evidence:

Canonical application data is under the data root, and
`scripts/application_sync.py:44` uses it correctly. However:

- `scripts/form_filler.py:29` defaults to repo-local `tracking/applications`.
- `scripts/record_application.py:21-23` defaults to repo-local jobs and
  applications paths.
- `scripts/apply_pipeline.py:36-47` searches repo-local `tracking/jobs`.
- The repo-local jobs/application ledgers are absent; the canonical root has
  956 jobs and 2 applications.

Impact:

- Application readiness may fail to locate the live job.
- Fill plans/status records can be written outside canonical storage.
- UI, tailoring, submission, follow-up, and reporting can diverge.

Required fix:

- Convert every application reader/writer to `config_lib.path(...)`.
- Remove any default repo-root `tracking/` behavior from production paths.
- Add one hermetic, temporary-data-root integration test across the full flow.

Acceptance criteria:

`qualified job -> tailored artifact -> fill plan -> explicit approval ->
canonical application record -> canonical job/application status sync`

must succeed against one temporary canonical data root and no repo-local
tracking directory.

### F-06 — Critical: direct application recorder bypasses approval invariant

Evidence:

- `scripts/form_filler.py:118-128` rejects blank/placeholder approval values.
- `scripts/record_application.py:108-126` only requires a nonempty
  `--approved-by` CLI value.
- `scripts/record_application.py:94-105` exposes `record()` without an
  approval argument/guard.
- Existing end-to-end recorder testing calls `record()` directly without
  enforcing approval evidence.

Impact:

A direct caller can mark an application submitted without verified explicit
human authorization.

Required fix:

- Move approval validation into the core `record()` function.
- Require a structured approval artifact or named user approval record.
- Reject placeholders and unverified values in every entry point.
- Ensure CLI/form/UI paths call the same guarded primitive.

Acceptance criteria:

- Direct function invocation without verifiable approval fails.
- CLI with empty/placeholder/automatic approval fails.
- Only a valid explicit approval creates a submitted canonical record.

### F-07 — High: application answer-bank divergence

Evidence:

- `scripts/answers_lib.py` declares `profile_info/application_answers.yaml`
  canonical and describes the preferences copy as frozen legacy.
- `scripts/match_application_fields.py:31-40` reads
  `profile_info/preferences/application_answers.yaml`.
- Both files exist and differ.

Impact:

Form planning and final filling can use different user facts, including
work authorization, sponsorship, compensation, and EEO values.

Required fix:

- Select one canonical answer bank and one library API.
- Reconcile the two files with a reviewed conflict report.
- Treat protected/gated questions as `ASK_USER` if reconciliation is incomplete.
- Preserve provenance (`verified_by`, date, explicit user source).

Acceptance criteria:

- Planner and filler resolve the same value/provenance for every shared label.
- Legacy answer bank is read only during migration and is not used in production.
- Contradictory gated values cannot be auto-filled.

### F-08 — High: job-data completeness and linkage are inadequate

Measured live job ledger state:

| Metric | Count |
|---|---:|
| Total jobs | 956 |
| Missing `description_file` | 796 |
| Missing `date_posted` | 723 |
| Missing `last_checked` | 218 |
| Empty `last_verified` | 956 |
| Missing `job_id` | 29 |
| Missing score/action | 49 |
| Open but `fit_class=disqualified` | 264 |

Additional verified points:

- No duplicate nonblank `job_id` values were measured.
- 18 jobs lack `company_slug`.
- 24 fuzzy same-company/title collisions exist within the 45-day dedupe window.
- No jobs were measured with missing `source` or `canonical_application_url`.

Impact:

- Missing JDs undermine scoring, ATS checks, tailoring, compensation/experience
  screening, and referral targeting.
- Blank identifiers undermine canonical linkage.
- Unscored rows can bypass intended prioritization.
- Fuzzy collisions need deliberate resolution before merge/archive decisions.

Required fix:

1. Build a dry-run identity repair report for blank `job_id` and `company_slug`.
2. Reconcile fuzzy collision groups manually/with explicit policy.
3. Gate APPLY/OPTIMISTIC application or referral packets on usable JD/provenance.
4. Backfill high-priority JDs before broad historical backfill.
5. Persist explicit `JD unavailable`, `auth blocked`, `expired`, or `fetch failed`
   states instead of silently leaving blanks.

### F-09 — High: hard-disqualified jobs remain `open`

Evidence:

- 264 canonical jobs are `status=open` and `fit_class=disqualified`.
- Those same rows are generally `recommended_action=SKIP`.
- `qualify_sweep.py` is designed to archive hard-disqualified jobs under
  explicit apply mode.

Impact:

Any consumer filtering only on `status=open` can surface jobs that should not
be operationally actionable.

Required fix:

Recommended policy:

- Preserve rows historically, but transition hard-disqualified roles to
  `status=archived` with an explicit gate/audit reason.

Acceptance criteria:

- A dry-run report lists every proposed lifecycle transition.
- After reviewed application, zero jobs are both `open` and
  `fit_class=disqualified`.
- Every queue/digest/query has a regression test against this invariant.

### F-10 — High: search-run ledger is malformed and split

Evidence:

Canonical `tracking/search_runs/search_runs.csv`:

- 232 logical records.
- 13 have invalid/swapped date semantics.
- 2 have malformed widths; one record has 10 fields and one has 4 fields.

A legacy repo-local `tracking/search_runs/search_runs.csv` also exists:

- 4 columns / 4 rows.
- Canonical file has 9 columns / 232 rows.

Impact:

- Source recency, health, yield, and digest metrics can be wrong.
- Parsers can fail.
- Different readers may consume different ledgers.

Required fix:

- Centralize run logging through one schema-aware helper.
- Validate header, exact field count, ISO date/date-time format, source name,
  and numeric counters before append.
- Migrate malformed historical records with a reviewed report.
- Remove all production reads from the legacy mirror.

Acceptance criteria:

- Every canonical run record passes schema validation.
- No active writer opens the legacy repo-root file.
- Digest/source health totals reconcile to canonical run data.

### F-11 — High: people/referral pipeline is not evidence-complete

Evidence:

- `people_sweep.csv`: 97 rows, all `pending_review`.
- Zero rows carry `profile_inspected_at`, `recommended_ask`, or `ranking_score`.
- Hiring posts: 112 rows; 99 `new`, 7 `verify`, 3 `not_fit`, 3 `signal_only`.
- 28 hiring posts lack `posted_date`.
- Connection queue: 8 rows: 3 pending, 2 approved, 2 sent-no-note, 1 connected.

Impact:

Raw people-sweep records are research leads, not verified referral targets.
Without inspection/activity/job-link evidence, generic employees can enter
operational queues or digests.

Required fix:

Require the following before P0/P1 or actionable queue eligibility:

- live target job ID or hiring-post ID;
- profile inspection timestamp;
- current company/title/team confirmation;
- connection degree;
- named mutuals when claimed;
- Georgia Tech/Fortinet overlap evidence when claimed;
- recent hiring/referral activity evidence;
- evidence/source URLs;
- recommended ask;
- ranking rationale.

Acceptance criteria:

- Every P0/P1 person has complete evidence fields.
- Existing historical/pending leads stay `pending_review` until evidence is
  captured.
- Re-evaluation for a new job/post does not create duplicate outreach records.

### F-12 — High: outreach factuality gate is incomplete

Evidence:

Existing canonical outreach drafts contain statements about active RL/
post-training research and PPO/GRPO-style experience. The resume/evidence
policy requires more careful qualification for these areas.

Impact:

A resume may be factuality-gated while outreach still overclaims capabilities,
creating credibility risk with recruiters, hiring managers, and referrals.

Required fix:

- Reuse the canonical fact-bank/banned-claim validator for all outreach drafts.
- Flag existing drafts for factuality review before approval.
- Require coursework/self-study qualification where applicable.

Acceptance criteria:

- No draft can advance to approved when fact validation fails.
- Every material claim maps to the candidate evidence library.
- Existing draft review outcome is persisted.

### F-13 — Medium: source health is incomplete and mutates state in check mode

Evidence:

`ops_health.py` currently tracks `career_ops`, `freshness`, `l1`, and `l2`.
It does not cover:

- authenticated LinkedIn jobs extraction;
- LinkedIn people/hiring-post sweep;
- Wellfound;
- browser auth/challenge state;
- per-cron delivery/completion state.

Further, `ops_health.py --check` can write `health.json` and append alerts.

Impact:

- "No sources paused" does not mean the production discovery system is healthy.
- Supposedly read-only diagnostics have side effects.

Required fix:

- Add health records for every active source/workflow.
- Split pure evaluation from persistence/self-pausing.
- Support an explicit no-persist inspection mode.

Acceptance criteria:

- Health differentiates process alive, CDP reachable, browser authenticated,
  source rate-limited, partial, failed, dedupe-only, and successful ingestion.
- Read-only health check never changes files.

### F-14 — Medium: prompt payload and cron contracts are inconsistent

Evidence:

- Latest people/hiring-post cron output was 875 lines / approximately 53 KB,
  largely because it embeds multiple full skills plus a long cron prompt.
- Active LinkedIn prompt differs from the deterministic runner contract in
  `setup/CRON_JOBS_LINUX.md`.

Impact:

- Repeated model context cost.
- Conflicting instructions and agent drift.
- Deterministic work becomes prose-driven rather than code-governed.

Required fix:

- Use concise prompts with typed JSON input/output contracts.
- Move deterministic policy enforcement into scripts.
- Generate cron documentation/prompts from a single source of truth.
- Restrict toolsets for deterministic jobs.

Acceptance criteria:

- No production cron depends on duplicated long-form skill text.
- Exact runner/schedule/toolset/model policy is testable from one contract.
- Browser jobs receive only required browser/web/file/terminal access.

### F-15 — Medium: test baseline is not green

Observed suite result:

- 922 passed
- 6 failed
- 1 skipped
- 2 warnings

Failure classes include:

- missing scratch fixtures;
- stale cover-letter expectation;
- repo-root `execution_results` hygiene failure;
- many stray root scripts/artifacts;
- stale root test collection requiring an old data path;
- unregistered pytest mark.

Impact:

Regression prevention is not reliable. Root-level scratch files are a
provenance and accidental-execution risk.

Required fix:

- Repair hermetic fixtures.
- Register expected pytest marks.
- Archive/remove root scratch artifacts only after checking for unique data.
- Ensure tests never require live data or a machine-specific path.
- Make the full suite green before material production changes are enabled.

Acceptance criteria:

- `pytest tests -q` passes with no failures.
- Full collection excludes or safely handles scratch files.
- Output-hygiene tests pass.
- No test changes canonical live data.

## Measured operational state

| Metric | Value |
|---|---:|
| Jobs | 956 |
| Contacts | 141 |
| Hiring posts | 112 |
| Applications | 2 |
| Outreach drafts | 13 |
| Search-run records | 232 |
| APPLY jobs | 5 |
| OPTIMISTIC jobs | 19 |
| STRETCH jobs | 102 |
| LOW_PRIORITY jobs | 566 |
| SKIP jobs | 264 |
| Unscored jobs | 49 |
| Blank job IDs | 29 |
| Jobs without JD file reference | 796 |
| Open-but-disqualified jobs | 264 |
| Connection queue pending | 3 |
| Connection queue approved | 2 |
| Connection queue sent | 2 |
| Connection queue connected | 1 |

Email/contact evidence state:

| Status | Count |
|---|---:|
| Verified public-source email | 22 |
| Inferred email | 19 |
| Unavailable email | 34 |
| Blank email status | 66 |
| Contacts with blank `email_source` | 141 |
| Company-registry rows with `email_pattern_status=unknown` | 184 |

## Production target architecture

The production-ready system should have the following enforceable flow:

```text
SOURCE FETCH (typed outcome, immutable raw evidence)
  -> NORMALIZE + CANONICAL DEDUPE
  -> DETERMINISTIC ELIGIBILITY / LOCATION / SENIORITY FILTERS
  -> JD COMPLETENESS + FRESHNESS VALIDATION
  -> SCORE + EXPLICIT DECISION (APPLY / OPTIMISTIC / STRETCH / SKIP)
  -> CANONICAL JOB LIFECYCLE STATE
  -> JOB-LINKED PEOPLE/HIRING-POST RESEARCH
  -> PROFILE/ACTIVITY EVIDENCE VALIDATION
  -> HUMAN-REVIEW QUEUE
  -> FACT-GATED TAILORING PACKET
  -> EXPLICIT USER APPROVAL ARTIFACT
  -> FORM FILL / STOP BEFORE SUBMIT
  -> VERIFIED SUBMISSION RECORD
  -> CANONICAL APPLICATION STATUS + FOLLOW-UP SUGGESTIONS
```

System-wide invariants:

1. One canonical data root, never repo-local mirrors.
2. One active cron authority per workflow.
3. One machine-readable schema per ledger.
4. No ambiguous browser result can be called successful.
5. No job reaches apply/referral queue without source/JD evidence.
6. No person reaches P0/P1 without inspection and job/post linkage.
7. No outreach or resume claim bypasses evidence validation.
8. No application status becomes submitted without explicit human approval.
9. Every metric in digest/health reconciles to canonical state.
10. Tests must be green before enabling material automation changes.

## Implementation roadmap

### Phase 0 — containment and production ownership

Owner: orchestration / Hermes profile management

1. Select `job-hunt-fresh` as the sole production profile.
2. Read-only verify gateway ownership and no in-flight legacy work.
3. Pause/archive the legacy `job-hunt` cron fleet.
4. Remove obsolete duplicate digest cron.
5. Create a canonical cron manifest with name, ID, schedule, workdir, toolsets,
   model, fallback, script/agent ownership, inputs, outputs, and side effects.

Exit criteria:

- One enabled cron per workflow.
- No duplicate schedule/input/output conflict remains.

### Phase 1 — truthful execution and health contracts

Owner: discovery/browser/ops-health

1. Eliminate Career Ops double execution.
2. Add typed outcomes for all source runs.
3. Add browser process/CDP/auth/extraction states to health.
4. Add Wellfound timeout/checkpoint/partial completion handling.
5. Make daily digest consume typed outcomes, not optimistic text summaries.
6. Add no-persist health inspection mode.

Exit criteria:

- Authwall, rate limit, timeout, zero-new, and success states are distinct.
- Digest cannot claim successful discovery from a failed browser run.
- Each source has measurable cost/yield/health state.

### Phase 2 — canonical data and application correctness

Owner: data/model/application pipeline

1. Fix application/autofill/recorder paths to use `config_lib` only.
2. Move approval enforcement into the shared submission recorder.
3. Consolidate application answer banks.
4. Reconcile application rows to canonical job IDs.
5. Repair blank job IDs/company slugs through reviewed migration.
6. Repair search-run schema and eliminate legacy read paths.
7. Apply reviewed lifecycle transition for open-but-disqualified jobs.

Exit criteria:

- All production writers target the canonical root.
- No approval bypass exists.
- All new application records resolve to canonical job IDs.
- Schema validation passes for all canonical ledgers.

### Phase 3 — evidence-quality and conversion pipeline

Owner: scoring/referrals/resume/outreach

1. Require JD completeness for high-priority jobs.
2. Backfill high-priority job descriptions/provenance first.
3. Require people evidence fields before actionability.
4. Re-gate legacy outreach drafts against fact bank.
5. Gate tailored application packets on eligibility, freshness, JD, resume,
   factuality, and user approval status.
6. Persist funnel metrics from job discovery through submitted application.

Exit criteria:

- Every APPLY/OPTIMISTIC packet has an evidence-backed JD.
- Every actionable person is job/post-linked and inspected.
- Every draft is factuality validated.
- Conversion and source-yield metrics are reconcilable.

### Phase 4 — test, observability, and operational hardening

Owner: engineering quality

1. Restore green hermetic test baseline.
2. Add schema/invariant/property tests.
3. Add dry-run and no-write verification modes to all maintenance commands.
4. Add dashboard views for source yield, funnel, cron health, browser status,
   data validation, and remediation backlog.
5. Add alert routing for real failures only.

Exit criteria:

- Full suite green.
- Production changes require test verification.
- Health/digest metrics are grounded in canonical data.

## First implementation packet

Do not start a broad rewrite. Implement this packet first:

### Packet: production orchestration and LinkedIn health hardening

Scope:

1. Make `job-hunt-fresh` the sole enabled cron authority.
2. Remove duplicate Career Ops execution from `daily_ops`.
3. Introduce typed LinkedIn/browser result schema.
4. Make `ops_health` and daily digest consume/render those states honestly.
5. Add hermetic tests for all new states.

Required tests:

- duplicate cron inventory detector;
- daily ops calls Career Ops no more than once;
- LinkedIn authwall is not success;
- 429 is not success;
- guest-only is partial when authenticated fetch is required;
- true zero-new after authenticated extraction is success with zero-new;
- health/digest renders each outcome accurately.

Acceptance criteria:

- Exactly one enabled fleet is capable of dispatch.
- Career Ops executes once per planned cadence.
- A login wall cannot be shown as `ok`.
- Daily digest cannot say discovery succeeded if authenticated retrieval failed.
- Relevant full test suite passes.

## Decisions required from Vedaang

1. Confirm `job-hunt-fresh` as the sole production cron profile.
2. Choose Career Ops ownership/cadence:
   dedicated cron versus daily-ops-owned scan.
3. Confirm lifecycle policy for hard-disqualified jobs:
   recommended `archived` rather than `open`.
4. Confirm whether legacy outreach drafts with post-training/RL claims should be
   quarantined pending factuality review.
5. Confirm whether Wellfound receives one hardened yield-measurement pilot or
   is reduced/retired immediately.

## Audit limitations

- No live sweep, live browser login, external source crawl, application,
  submission, outreach, email send, LinkedIn interaction, or canonical ledger
  mutation was performed.
- Current fallback-model execution could not be proven solely from cron metadata.
- LinkedIn authentication state was inferred from existing cron outputs, not
  repaired or manually inspected.
- Historic duplicates and malformed rows need an explicit reviewed migration,
  not blind automatic changes.

## Final checkpoint

- AUDIT COMPLETE: YES
- SYSTEM READY FOR HIGH-VOLUME AUTONOMY: NO
- RECOMMENDED NEXT IMPLEMENTATION PACKET: production orchestration and LinkedIn
  health hardening only.
