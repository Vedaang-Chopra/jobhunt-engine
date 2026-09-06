# Agent Execution Log

**Location:** `docs/ai_context/AGENT_EXECUTION_LOG.md`
**Required:** read before starting a task; add an entry after every completed,
failed, or partial task attempt.

## Entries

## UI-DESIGN-AUDIT-2026-08-23 — Full website design and feature audit

**Date:** 2026-08-23
**Agent:** Codex with three read-only evidence subagents
**Model:** GPT-5 / GPT-5.6 Terra evidence passes
**Status:** ✓ Complete

**Approach taken:** Read mandatory repository context, mapped the full NiceGUI
UI and test surface, inspected all nine live routes at desktop/tablet/mobile
viewports, collected structural/visual/copy/performance/accessibility evidence,
scored the shipped design against Dieter Rams' ten principles, and wrote a
prioritized foundation-first redesign recommendation. The audit remained
read-only with respect to website code and canonical job/profile/application
data.

**What worked:** The live server exposed all nine routes. Code and live evidence
agreed on the main gaps: inaccessible mobile navigation, non-reflowing content,
label-to-behavior mismatches, incomplete Company Research and tailoring
affordances, missing mutation confirmations/undo, and incomplete semantic and
state handling. Existing centralized design tokens, UI data separation, and
approval-before-send boundary were identified for preservation.

**What failed:** Exact transferred JavaScript bytes, request count, and
time-to-interactive were not available from the selected browser surface.

**Root cause:** The browser surface exposed loaded asset inventory but not wire
timing/response headers.

**Resolution:** Recorded 22 observed static assets and treated performance as
unverified, applying the audit's lower-score tie breaker. Recommended an
explicit performance-measurement phase.

**Files modified:**

- `execution_results/reviews/DESIGN-IS-2026-08-23/00-scope.md`
- `execution_results/reviews/DESIGN-IS-2026-08-23/01-evidence.md`
- `execution_results/reviews/DESIGN-IS-2026-08-23/02-scorecard.md`
- `execution_results/reviews/DESIGN-IS-2026-08-23/03-verdict.md`
- `execution_results/reviews/DESIGN-IS-2026-08-23/04-handoff-prompt.md`
- `execution_results/reviews/DESIGN-IS-2026-08-23/05-improvement-suggestions.md`
- `docs/session_state.md`
- `docs/ai_context/AGENT_EXECUTION_LOG.md`

**Verify result:** All nine routes were live-inspected; source findings cite
exact files/lines; `.venv/bin/python -m pytest -q tests/ui` passed all 57 tests;
artifact placeholder and link checks passed; `git diff --check` passed.

**Model fallback used:** no

**DO NOT REPEAT:** Do not treat this audit as implementation approval. Do not
rewrite the working CSV/data/automation layers as part of a visual redesign.
Do not claim current queue/send/application metrics are externally verified.
Do not hide unavailable workflows behind active-looking controls.

---

## 001-SPEC-REVISION — Preserve working code and tighten child-agent scope

**Date:** 2026-08-21
**Agent:** Codex
**Model:** GPT-5
**Status:** ✓ Complete

**Approach taken:** Incorporated human review feedback into draft spec 001 and
the current governance/context documents. Removed an earlier interface-design
requirement and made behavioral preservation an explicit migration boundary.

**What worked:** The revised scope permits only moved-path compatibility changes
and verified duplicate elimination in working automation. Child agent files now
require demonstrated specialized behavior, with job research, resume
customization, and LinkedIn treated as candidates rather than automatic files.

**What failed:** None.

**Root cause:** None.

**Resolution:** Keep spec 001 in Draft until the human explicitly approves the
revised version.

**Files modified:**

- `README.md`
- `AGENTS.md`
- `docs/ai_context/CODEBASE_MAP.md`
- `docs/ai_context/SYSTEM_WORKFLOW_MAP.md`
- `docs/ai_context/AGENT_EXECUTION_LOG.md`
- `docs/session_state.md`
- `docs/specs/001_job_applications_restructure.md`

**Verify result:** `git diff --check` passed; all required spec sections remained
present; the revised spec contained 14 observable acceptance criteria; targeted
search confirmed the code-preservation and conditional-child-agent constraints
in root governance, architecture context, and spec 001.

**Model fallback used:** no

**DO NOT REPEAT:** Do not introduce interfaces, layers, rewritten algorithms,
or opportunistic code cleanup during migration 001. Do not create child agent
files solely because a subsystem directory exists.

---

## 001-BOOTSTRAP — Capture baseline and initialize planning context

**Date:** 2026-08-21
**Agent:** Codex
**Model:** GPT-5
**Status:** ✓ Complete

**Approach taken:** Audited the repository before proposing architecture,
excluded local environments and rebuildable clutter, initialized Git, and
captured an immutable pre-migration baseline. Began the mandatory governance and
specification phase; migration implementation is intentionally not started.

**What worked:** The baseline commit preserves 458 audited source, data,
resume, report, template, and historical archive files. Sensitive-looking
environment copies and the nested virtual environment were excluded without
reading, moving, or deleting them.

**What failed:** Initial `git init` and `git add -A` attempts could not write
Git metadata in the managed sandbox and returned `Operation not permitted`.
One read-only documentation check then returned `command not found: basename`
and `command not found: rg`.

**Root cause:** The workspace permission profile permitted project-file writes
but treated `.git` metadata writes as approval-gated operations. The validation
loop used `path` as a zsh variable, which overwrote zsh's special command-search
path for later loop commands.

**Resolution:** Re-ran the Git metadata operations with explicit managed
approval. Baseline commit: `cbd7292 agent: capture pre-migration baseline`.
Re-ran the documentation check with `item` as the loop variable; it passed.

**Files modified:**

- `.gitignore`
- `README.md`
- `AGENTS.md`
- `CONVENTIONS.md`
- `docs/ai_context/DOC_TAXONOMY.md`
- `docs/ai_context/CODEBASE_MAP.md`
- `docs/ai_context/SYSTEM_WORKFLOW_MAP.md`
- `docs/ai_context/AGENT_EXECUTION_LOG.md`
- `docs/session_state.md`
- `docs/specs/001_job_applications_restructure.md`

**Verify result:** `git diff --check` passed; every mandatory context file and
the root README were present and non-empty; spec 001 contained all sections
required by the `write-spec` skill; documentation reference checks passed after
the corrected retry; the only matches for obsolete Hermes paths in new
documents were intentional requirements to remove those references during
migration.

**Model fallback used:** no

**DO NOT REPEAT:** Do not stage nested virtual environments, archived
environment files, LaTeX intermediates, caches, or OS metadata. Do not treat
legacy candidate profiles or generated scoring reports as verified career
facts. Do not use `path` as a zsh loop variable. Do not begin migration before
the spec, plan, and tasks receive their required separate approvals.

---

## 002-WELLFOUND-DISCOVERY — First Wellfound job-discovery pass

**Date:** 2026-08-21
**Agent:** Codex
**Model:** GPT-5
**Status:** ✓ Complete

**Approach taken:** Used the existing Wellfound browser tab through browser-use/CDP interaction, searched the saved Machine Learning Engineer state, expanded it with Research Engineer and Applied Scientist role terms, then opened individual Wellfound listings for description-level verification. Kept company-size and visa constraints explicit and did not apply or contact anyone.
**What worked:** Verified seven retained roles across Mercor, Mirage, Mapgenesys, Unlearn.AI, and Luminary; captured direct Wellfound URLs, role/company metadata, relative freshness, salary, experience requirements, visa/onsite blockers, and profile-fit judgments. Created the requested CSV and report with a resumable search ledger.
**What failed:** Exact external application destinations were not captured separately; retained `application_url` values therefore use the direct Wellfound listing URL. The browser session exposed result-pool counts and a limited loaded card set rather than a fully inspectable 630-description corpus.
**Root cause:** Wellfound uses a dynamic saved-search UI and internal Apply flow; individual page inspection was possible, but the first pass did not expose a stable external destination for every listing.
**Resolution:** Treat the report as a verified first pass, not exhaustive market coverage. Continue with the recommended role-family searches and employer-page sponsorship verification before applying.
**Files modified:** `wellfound_jobs.csv`, `WELLFOUND_SEARCH_REPORT.md`, `docs/session_state.md`
**Verify result:** `python3` CSV parse passed with 7 rows and 24 columns; `git diff --check` passed.
**Model fallback used:** no
**DO NOT REPEAT:** Do not count Wellfound result-pool totals as fully inspected listings. Do not infer sponsorship, exact posting dates, or external application URLs when the individual page does not expose them.

## Entry Template

## [TASK_ID] — [Task name]

**Date:** YYYY-MM-DD
**Agent:** Pi | Codex | Claude Code
**Model:** model actually used
**Status:** ✓ Complete | ✗ Failed | ⚠ Partial

**Approach taken:** 1–3 sentences.
**What worked:** specific successes.
**What failed:** exact failures or `None`.
**Root cause:** specific cause or `None`.
**Resolution:** fix or recommendation.
**Files modified:** paths.
**Verify result:** exact command and result.
**Model fallback used:** yes or no.
**DO NOT REPEAT:** specific anti-patterns or `None`.
