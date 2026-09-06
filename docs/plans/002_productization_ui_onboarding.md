# Plan 002 — Productization: NiceGUI UI, Onboarding Wizard, Multi-User Packaging

**Spec:** `docs/specs/002_productization_ui_onboarding.md` (approved)
**Status:** DRAFT — awaiting human confirmation
**Date:** 2026-08-23

## Section 1 — Summary

Converts the single-user engine into a shippable open-source product per Spec
002: path/data separation via a config layer, an 8-page NiceGUI UI that both
displays and *triggers* every engine component, a first-run onboarding wizard,
and packaging (pyproject, docker-compose). Engine behavior is otherwise
preserved; the existing suite must stay green at every checkpoint.

## Section 2 — Layer Assignment

| Component | Layer | File | Responsibility |
|---|---|---|---|
| Config resolution | L5 utils | `scripts/config_lib.py` (new) | data_root(), load_config(), JOBHUNT_HOME precedence |
| Path helpers change | L5 utils | `scripts/agent_helpers.py` (modify) | DATA_DIR/JOBS_DIR derive from config_lib |
| Follow-up derivation | L4 core | `scripts/followups_lib.py` (new) | nudge rules from application dates |
| Run registry | L3 orchestration | `ui/runs.py` (new) | background subprocess start/status/cancel, one run per component |
| Data wrappers | L3 orchestration | `ui/data.py` (new) | read tracking CSVs, call engine entry points |
| UI app + theme | L2 interface | `ui/app.py`, `ui/theme.py`, `ui/pages/*.py` (new) | 8 pages, dark theme, triggers |
| Wizard | L3 orchestration | `setup/wizard.py` (new) | onboarding flow, seeding, smoke test |
| Packaging | repo root | `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.gitignore` (modify) | install + one-command run |

## Section 3 — Interface Design Decisions

| Symbol | Form | Expression | Reason |
|---|---|---|---|
| `data_root()` | Wrapper | in `config_lib.py`: env var → config pointer → legacy REPO_ROOT | adds precedence logic; no equivalent exists |
| `load_config()` | Wrapper | returns dict from `<data>/config.yaml`, chmod-checked | validation of secrets presence |
| `get_followups(apps_csv)` | New core function | pure function → list[dict] | testable rule engine |
| UI imports engine libs directly (`from scripts import today_queue`) | Re-export style direct import | pages call existing public functions | zero duplication |

## Section 4 — Error and Return Contracts

| Function | Success return | Missing/invalid input | Failure case | Raises |
|---|---|---|---|---|
| `data_root()` | `Path` | falls back to legacy repo-local dir | unwritable dir | `RuntimeError` |
| `load_config()` | `dict` | `{}` when file absent | malformed YAML logged, `{}` | never raises |
| `get_followups(df)` | `list[dict]` | `[]` for empty df | — | `ValueError` on bad schema |
| `RunRegistry.start(name, cmd)` | `run_id: str` | raises if same component already running | process spawn failure | `RuntimeError` |

## Section 5 — Files to Create

| Path | Layer | Purpose |
|---|---|---|
| `scripts/config_lib.py` | L5 | path/config resolution |
| `scripts/followups_lib.py` | L4 | follow-up/nudge rules |
| `ui/app.py` | L2 | NiceGUI entry, routing, sidebar |
| `ui/theme.py` | L2 | dark theme, brand tokens |
| `ui/data.py` | L3 | data access wrappers |
| `ui/runs.py` | L3 | background run registry |
| `ui/pages/dashboard.py` … `.py` ×8 | L2 | dashboard, pipeline, jobs, queue, outreach, resume_settings, analytics, company_research |
| `setup/wizard.py` | L3 | onboarding CLI flow |
| `tests/test_config_lib.py`, `tests/test_followups_lib.py`, `tests/ui/*` | tests | per-module tests |
| `pyproject.toml`, `docker-compose.yml`, `config.example.yaml` | root | packaging |

## Section 6 — Files to Modify

| Path | What changes | Layer | Impact on callers |
|---|---|---|---|
| `scripts/agent_helpers.py` | DATA_DIR/JOBS_DIR via config_lib.data_root() | L5 | none when JOBHUNT_HOME unset (legacy default identical) |
| `scripts/career_ops_sweep.py` | remove absolute user path → config-based | L5 | behavior unchanged |
| `scripts/extract_simplify_answers.py` | Chrome path via env var with current default | L5 | behavior unchanged |
| `.gitignore` | add data dirs, config.yaml, *.key patterns | — | prevents personal-data commits |
| `README.md`, `docs/ai_context/CODEBASE_MAP.md`, `docs/session_state.md` | document new structure | docs | required by governance §Agent Rules 7 |

## Section 7 — Dependency Order

1. Phase 1: config_lib + path refactor + .gitignore hardening (+ tests green)
2. Phase 2 (parallel): ui/theme+app shell ∥ followups_lib ∥ wizard skeleton
3. Phase 3 (parallel): read-only pages (dashboard, jobs, pipeline, analytics, company research, queue, outreach views)
4. Phase 4: runs.py + trigger controls + LLM endpoint editor
5. Phase 5: wizard completion + packaging + publish-prep audit (PII scan)

## Section 8 — Task Complexity Budgets

| Task group | Expected new functions | Max call depth | Interface constraint |
|---|---|---|---|
| config_lib | 4 | 3 | wrapper only |
| followups_lib | 3 | 3 | pure functions |
| ui/data.py | ~8 thin wrappers | 2 | re-export/composition over engine |
| each page | ≤3 render funcs | 2 | render-only |
| runs.py | 4 | 3 | registry API |
| wizard | 5 steps as functions | 3 | preview-before-write for destructive steps |

## Section 9 — Integration Points

- `agent_helpers.py` consumers: all scripts — protected by identical legacy default.
- Outreach ledger interlocks: UI send actions must route through existing ledger functions only.
- Cron jobs unaffected (they invoke the same CLIs).
- Suite: `pytest tests/ -q` gate at every checkpoint.

## Section 10 — Risks and Open Questions

| Risk | Mitigation |
|---|---|
| Hidden PII reaches public repo | dedicated audit task scanning tree + git history before publish |
| NiceGUI subprocess streaming complexity | runs.py isolated + tested independently of UI |
| Path refactor breaks crons | crons use same repo-relative defaults; verified at Phase 1 checkpoint |

Open questions: none blocking.

## Section 11 — Validation Criteria

- `pytest tests/ -q` → all green (existing + new) after every phase.
- `JOBHUNT_HOME=/tmp/fresh python -m setup.wizard --dry-run` completes seeding plan without touching repo data.
- `python -m ui.app` serves all 8 pages against real tracking CSVs.
- Publish audit script reports zero `/Users/<name>` matches, zero key files tracked.

## Parallel Execution Note (user requirement: 4–6 subagents)

Phase 2 and Phase 3 are designed as parallel groups: independent files, no
shared writes. Subagent mapping:
- **A1:** config/path separation (Phase 1, serial — everything depends on it)
- **A2:** ui/app.py + theme.py + ui/data.py (Phase 2)
- **A3:** followups_lib + tests (Phase 2)
- **A4:** setup/wizard.py (Phase 2)
- **B1–B3:** page groups (Phase 3, split across 3 subagents by page sets)
- **C1:** runs.py + triggers + settings editor (Phase 4, after A2)
- **D1:** packaging + publish audit (Phase 5)
Peak concurrency: 4 subagents (A2/A3/A4 after A1 lands), then 3 in Phase 3.
