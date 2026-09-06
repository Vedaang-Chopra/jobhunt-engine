# Spec 003 — UI Redesign (Foundation-First, NiceGUI)

**Date:** 2026-08-23
**Status:** DRAFT — awaiting human approval (Gate 1 of 3: spec → plan → task breakdown)
**Basis:** `execution_results/reviews/DESIGN-IS-2026-08-23/` audit (Rams 13/30, verdict REDESIGN)
**Approach:** Option B from `05-improvement-suggestions.md` — foundation-first redesign inside the existing NiceGUI application.

---

## 1. Product contract (confirmed by user, 2026-08-23)

| Decision | Value | Consequence |
|---|---|---|
| Mobile/tablet | **Not a working surface now**, but responsive code is wanted | Layouts must reflow and never clip at any width; full touch workflows are a non-goal. Verification viewports stay 375×812 / 768×1024 as regression floors, but mobile-specific features (drawer nav gestures etc.) are minimal. |
| Executable actions | **Decision deferred pending action inventory** (§5) | Tier 1 actions are approved for implementation; Tier 2/3 require separate sign-off before their phase. |
| Deployment | **Private single-user local tool** | No auth, no concurrency handling beyond existing ops lock, localhost binding only. |

## 2. Preserve (unchanged by this redesign)

- CSV canonical state under `<data_root>` (`tracking/jobs/jobs.csv` is the only master job table); no database.
- All engine scripts and entry points (`scripts/discovery_run.py`, `today_queue.py`, `connection_queue.py`, `apply_pipeline.py`, …) and their CLI signatures.
- Approval-before-send boundary: nothing in the UI ever sends externally; sending remains agent-driven, cap-enforced (≤25/day).
- Design tokens in `ui/theme.py` (palette, surfaces, radius, focus ring, reduced motion) — extended, not replaced.
- Thin page renderers over `ui/data.py`; business logic stays out of pages.
- Existing URL behavior during migration via compatibility redirects (§4.3).
- Unrelated uncommitted work in the tree (resume/settings split already in progress is absorbed as-is; `scripts/append_linkedin_sweep.py`, start/stop scripts untouched).

## 3. Replace / fix (audit findings driving scope)

1. Fixed desktop-first shell; KPI/filter/table rows that do not wrap (`ui/components.py:44-69`, `ui/app.py:53,356,379`).
2. Label-to-behavior mismatches: "Applications Sent" (local status only), "Connections Pending" (ledger meaning differs), `Closed → withdrawn` conflation (`ui/app.py:50-51`, `ui/data.py:347-374`).
3. Server controls fixed on every page; run/log panels inside the daily workspace (`ui/components.py:72-139`, queue/outreach Engine Triggers cards).
4. No loading/error/stale states — unreadable files silently become empty tables (`ui/data.py:38-52`).
5. Missing confirmations on consequential writes (saved-view delete, stage change, inbox accept/discard, settings save).
6. Dead affordance: disabled "Research company" button (`ui/pages_3_3.py:145-151`).
7. Semantic structure: one `h1` per page, landmarks, skip link, icon-button accessible names.

## 4. Target information architecture

### 4.1 Seven top-level areas

| # | Route | Area | Contents |
|---|---|---|---|
| 1 | `/today` | **Today** | Prioritized decision workspace: ranked jobs with evidence quality, fit, freshness, blocking reason, snapshot timestamp, and the safe next action per item. Run health strip only (no run buttons). |
| 2 | `/jobs` | **Jobs** | Full corpus: filters (+ filter chips), server-side sorting, saved views, comparison, score provenance tooltip, stale indicators, job detail dialog. |
| 3 | `/applications` | **Applications** | Stage board/list; stage ≠ outcome (explicit outcome values); transition confirmation + history. |
| 4 | `/network` | **Network** | Contacts, connection-request ledger (precise statuses), send-cap meter, follow-up timeline. |
| 5 | `/profile` | **Profile & Resume** | Canonical facts with provenance, inbox review (accept/discard w/ confirmation), tailored resume list, tailoring lifecycle (plan → approval gate → artifact). |
| 6 | `/insights` | **Insights** | Analytics (funnel, source, resume variants) + Company Research (honest unavailable-state card until its own spec exists). |
| 7 | `/operations` | **Operations** | Engine run panels, logs, server lifecycle (with confirmation), data health (per-source file freshness/row counts), Settings (config status, LLM endpoints). |

### 4.2 Navigation model

Desktop ≥1024px: persistent sidebar (current pattern, kept) grouped: *Work* (Today, Jobs, Applications, Network) / *Knowledge* (Profile & Resume, Insights) / *System* (Operations).
Below 1024px: same links behind a visible menu button in a top app bar (Quasar header + drawer overlay). Content grids collapse: KPI row → 2-col → 1-col; filter rows wrap; tables get horizontal containment inside their card (page never overflows).

### 4.3 Compatibility URLs (permanent 1:1 redirects)

| Old | New |
|---|---|
| `/` | `/today` |
| `/queue` | `/today` (deep-linkable section anchors preserved where feasible) |
| `/pipeline` | `/applications` |
| `/outreach` | `/network` |
| `/analytics` | `/insights` |
| `/companies` | `/insights#companies` |
| `/resume` | `/profile` |
| `/settings` | `/operations` |

Old bookmarks keep working forever; no deprecation window needed (single user).

## 5. Action inventory (decision artifact for the deferred §1 question)

Every mutation the UI could offer, tiered by risk. **Only Tier 1 ships without further approval.**

### Tier 1 — Local, reversible, already-approved semantics
| Action | Today | Change |
|---|---|---|
| Jobs filters/sort/saved-view create-apply | ✅ | Keep; add delete confirmation + overwrite warning |
| Saved-view delete | ✅ | Add confirmation dialog (undo optional v2) |
| Pipeline stage change | ✅ | Add before→after confirmation showing target status written to applications.csv |
| Profile inbox accept/discard | ✅ | Add confirmation showing destination file (accept) |
| Profile section YAML save | ✅ | Add diff preview (before/after) before write |
| LLM endpoints save | ✅ | Add confirmation listing which fields change (keys shown as "set/unset", never values) |
| Engine dry-run triggers (discovery, freshness, people sweep, poster sweep) | ✅ | Move to Operations; add concise summary line above expandable log |
| Server start/stop/restart | ✅ | Move to Operations; stop/restart get confirmation |

### Tier 2 — New local writes (safe but new behavior; needs sign-off per item)
| Candidate action | Notes |
|---|---|
| Job status edit from Jobs table (open/expired/filled/archived) | Currently script-only; writes via existing engine writers only |
| Application outcome recording (rejected/withdrawn/no-response/offer-declined/other) | Replaces overloaded `Closed`; new explicit column or status vocabulary |
| Follow-up snooze/date set on network ledger rows | Writes date columns via connection_queue writer |
| Mark job "locally submitted" from Applications | Distinct from external verification; label says exactly that |
| Data-health refresh button | Re-runs read-only integrity checks per source file |

### Tier 3 — External-facing or agent-driven (NOT automatable from UI; out of scope)
External send execution, LinkedIn actions, final application submission, company research execution, resume generation beyond the existing apply_pipeline trigger. These remain agent-driven with human approval per governance rules; the UI may display their results and gate states but never trigger them directly.

> **Open decision for the user (blocks Phase 4 only):** approve/reject each Tier 2 row.

## 6. Cross-cutting requirements

### 6.1 States (every data view implements all that apply)
`loading · empty · stale (with last-refresh time) · partial (some sources failed) · error (readable diagnostic + recovery hint) · success · disabled · approval-gated`. Missing/unparseable files render an error/partial banner naming the path — never a silent empty table (`ui/data.load_csv` gains an error channel; callers must consume it).

### 6.2 Truthful labels (rename map)
| Current | Becomes |
|---|---|
| Applications Sent | Submitted (local status) |
| Connections Pending | Awaiting outreach (ledger) |
| Closed (pipeline stage) | Removed as outcome; stages end at Applied/Interviewing; outcomes recorded separately |
| Research company (disabled) | Unavailable-state card: "Agent-driven workflow — see COMPANY_RESEARCH_WORKFLOW.md" |
| priority_v2 score chip | Score with tooltip: scale 0–100, computed <date>, input-quality note |

Local vs externally-verified states use different badge shapes/colors; nothing implies an external event happened unless it was recorded from an external source.

### 6.3 Safety
Confirmation dialog before: saved-view delete, stage transitions, inbox accept/discard, profile section save (diff preview), settings save, server stop/restart, and every Tier 2 action once approved. Dialogs trap focus; Escape cancels; destructive buttons styled negative with explicit object names ("Delete view 'X'").

### 6.4 Accessibility floor (WCAG 2.2 AA)
One semantic `h1` per route; `header/nav/main` landmarks; skip-to-content link; accessible names on all icon-only controls; tertiary text contrast raised to AA (audit flagged `#8a93a6` on cards); focus order verified; reduced-motion policy retained.

## 7. Component additions (new shared primitives in `ui/components.py`)

`page_shell(title)` rewritten (landmarks, h1, responsive nav) · `state_view(status, ...)` wrapper implementing §6.1 · `confirm_dialog(title, body, danger)` · `data_health_strip()` · `kpi_grid()` replacing the non-wrapping KPI row · `filter_bar()` wrapping chip-based filters · `run_panel` relocated behind Operations route (component reused unchanged).

## 8. Delivery phases & exit gates

| Phase | Scope | Exit gate |
|---|---|---|
| 0 | This spec approved; baseline screenshots + current 57-test pass recorded | Spec signed off |
| 1 | Shell: responsive nav, landmarks, grid reflow, contrast, focus; new components (§7); state system | All routes render at 375/768/1280/1440 with zero horizontal overflow; keyboard-reachable primary actions; 57 existing tests still pass |
| 2 | Semantics & safety: rename map (§6.2), confirmations (§6.3), provenance tooltips, stale/error states wired through `load_csv` | Label-behavior tests pass; zero consequential writes without confirmation |
| 3 | IA cutover: seven routes + redirects; Today workspace; Operations consolidation | Primary daily task completable within two screens; feature regression checklist green |
| 4 | Tier 2 actions (if approved) + Company Research/tailoring lifecycle specs | Per-feature acceptance criteria |
| 5 | Measurement: asset bytes, render timing, visual-regression screenshots | Perf budget + regression suite enforced in CI-style validation run |

Phases land as separate commits; each phase's tests run before the next starts.

## 9. Success metrics

- Zero horizontal overflow at 375/768/1280/1440.
- All primary actions keyboard-operable with visible focus; WCAG AA contrast.
- Zero label-to-behavior mismatches (each rename test-asserted).
- Zero consequential mutations lacking confirmation.
- Every data view shows freshness + distinguishes error/partial from empty.
- Today → prepared next action in ≤2 screens.
- All existing + new tests passing per phase gate.

## 10. Non-goals

No database; no rewrite of discovery/scoring/resume/outreach algorithms; no external send/submission automation from the UI; no frontend framework replacement (NiceGUI spike-first rule stands); no multi-user/auth; no mobile-only feature work.
