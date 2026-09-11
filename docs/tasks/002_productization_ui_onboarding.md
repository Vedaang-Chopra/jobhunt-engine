# Tasks 002 — Productization (UI, Wizard, Packaging)

**Plan:** docs/plans/002_productization_ui_onboarding.md · **Spec:** docs/specs/002_productization_ui_onboarding.md
**Status:** [ ] = pending, [x] = complete

## Phase 1 — Config & Path Separation
**Goal:** engine runs unchanged with `JOBHUNT_HOME` data-dir override.
**Entry condition:** clean git tree. **Exit:** suite green incl. new config tests.
**Type A:** write-tests applies. **Type B:** no — refactor only.

| Task | Reads | Writes | Depends |
|---|---|---|---|
| 1.1 | agent_helpers.py consumers | scripts/config_lib.py + tests/test_config_lib.py | none |
| 1.2 | config_lib | agent_helpers.py, career_ops_sweep.py, extract_simplify_answers.py | 1.1 |
| 1.3 | — | .gitignore hardening | none |

### Group 1-A sequential → Task 1.final verify-checkpoint: pytest tests/ -q green; grep confirms zero /Users/vedaangchopra in scripts/.

## Phase 2 — Foundations (4 parallel subagents)
**Goal:** UI shell, followups engine lib, wizard skeleton exist and import cleanly.
**Exit:** each component's tests pass; app boots to empty shell page.
**Type B:** yes — boot screenshot of empty app.

- [ ] 2.1 (A2): ui/app.py, ui/theme.py, ui/data.py (+tests) — NiceGUI dark shell, sidebar nav for 8 pages, CSV wrappers.
- [ ] 2.2 (A3): scripts/followups_lib.py (+tests/test_followups_lib.py) — pure nudge rules.
- [ ] 2.3 (A4): setup/wizard.py skeleton — step functions with --dry-run; seeds canonical dir layout.
### SYNC POINT 2: all verifies pass before Phase 3.

## Phase 3 — Pages (3 parallel subagents)
**Goal:** all 8 pages render real tracking CSV data.
**Type B:** yes — screenshots of populated pages.

- [ ] 3.1 (B1): dashboard.py, jobs.py, queue.py (read-only)
- [ ] 3.2 (B2): pipeline.py (Kanban w/ status selectbox), outreach.py (ledger view)
- [ ] 3.3 (B3): analytics.py (funnel), company_research.py, resume_settings.py (read-only parts)
### SYNC POINT 3.

## Phase 4 — Engine Triggers
**Goal:** sweeps/discovery/tailoring/LLM-editor controllable from UI.
- [ ] 4.1 (C1): ui/runs.py registry + trigger buttons wired on pages + Settings LLM endpoint editor editing <data>/config.yaml.
**Verify:** start a freshness-check run from UI, see streamed log; ledger rules still enforced (unit test).

## Phase 5 — Packaging & Publish Prep
- [ ] 5.1 (D1): pyproject.toml, docker-compose.yml, config.example.yaml, wizard completion, README rewrite.
- [ ] 5.2 (D1): publish audit script — scan tree+history for PII/paths/secrets; must report clean.
### Final checkpoint: A1 acceptance criteria of spec verified; HARD STOP for human publish decision.
