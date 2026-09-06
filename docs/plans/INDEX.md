# Plan Index — Canonical Taxonomy

Every plan/packet in this repo is classified here. Agents: read this file FIRST;
do not re-derive plan status from file names. Statuses: ACTIVE · COMPLETED ·
SUPERSEDED · BACKLOG (items only, in BACKLOG.md).

| Plan | Path | Status | Notes |
|---|---|---|---|
| 002 — Productization: UI, Wizard, Packaging | `docs/plans/002_productization_ui_onboarding.md` | COMPLETED | UI live (NiceGUI port 8080), setup/wizard.py shipped. Specs under docs/specs/002_*.md remain reference. |
| 003 — Migration: Small Models & Handoff | `docs/plans/003_migration_small_models_handoff.md` | COMPLETED (2026-08-27) | Executed; session orchestrator at `.hermes/plans/2026-08-26_224500_*`. Server setup follows this + HANDOFF.md. |

Related spec/task docs (reference, not plans): `docs/specs/001–004`, `docs/tasks/002`,
`docs/execution-plans/`. Executed/historical plans: `archive/plans_20260826/`
(see its MANIFEST.md for per-file disposition).

Unfinished work recovered from executed plans: `docs/plans/BACKLOG.md`.

## Convention for new plans
1. New plans go in `docs/plans/NNN_<slug>.md`; session-scoped orchestrators may live in
   `.hermes/plans/` but must be added to this index with status ACTIVE.
2. Every plan header must carry Goal + Status; superseded plans must name their successor.
3. On completion or supersession: move the file to `archive/plans_<date>/`, append a row to
   that archive's MANIFEST.md, and update this table.
4. Residual unfinished tasks from a partially-executed plan are migrated into BACKLOG.md
   before the plan is archived — never silently dropped.
