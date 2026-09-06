# Spec 002 — Productization: Open-Source Job-Hunt Engine with UI and Onboarding

**Status:** DRAFT — awaiting human approval
**Date:** 2026-08-23
**Ambition (user-stated):** Public open-source project. Anyone (friend/sister)
clones it, runs an onboarding wizard with their resume + credentials, and gets
a working system with a UI.

---

## 1. Problem

The repository today is a working single-user system: engine code in
`scripts/` (~42 modules), canonical state in `tracking/*.csv`, verified facts in
`profile_info/`, cron-driven sweeps, and a 243-test suite. Two things block it
from being a shippable open-source product:

1. **No UI.** Everything runs through agents/cron/CLI.
2. **Code and personal data are entangled.** A clone carries the owner's
   profile, resumes, contacts, and application history, and there is no
   onboarding path for a second user.

## 2. Goals

- G1: A multipage local web UI over the existing engine (no engine rewrites).
- G2: Strict code/data separation so the public repo contains zero personal
  data and every user's data lives outside or beside the code tree.
- G3: One-command setup: clone → wizard → running dashboard.
- G4: All existing entry points, cron jobs, and tests keep working unchanged.

## 3. Non-Goals

- No hosted multi-user SaaS, no auth server, no cloud deployment.
- No rewrite of discovery/scoring/outreach logic (Migration Code-Preservation
  Rule applies).
- No fully automated LinkedIn login by password storage; users supply their own
  browser session (Playwright persistent profile), consistent with existing
  human-in-the-loop rules.

## 4. Architecture

```
<repo>/                        # public, shareable
├── scripts/                   # engine (unchanged behavior)
├── ui/                        # NEW Layer 3 UI app
│   ├── app.py                 # streamlit multipage entry point
│   ├── pages/                 # dashboard, jobs, resume, outreach, digest
│   └── README.md
├── setup/                     # NEW onboarding
│   ├── wizard.py              # interactive first-run setup
├── config.example.yaml        # NEW template config
├── docker-compose.yml         # NEW optional one-command run
├── pyproject.toml             # NEW dependency declaration
└── .venv/

$JOBHUNT_HOME/<user>/          # per-user data, default <repo>/jobhunt-data
├── profile_info/
├── tracking/
├── linkedin/, messaging/, resume_custom/
└── config.yaml                # secrets + keys (never in repo)
```

### Layer Plan

#### Layer 5 — Schemas / Utils
- `scripts/config_lib.py`: resolves root directory order:
  `$JOBHUNT_HOME` env var → `./config.yaml` pointer → legacy repo-local
  (current behavior). Exposes `data_root()`, `load_config()`.
- Change to `scripts/agent_helpers.py`: `DATA_DIR` / `JOBS_DIR` derive from
  `config_lib.data_root()` instead of bare `REPO_ROOT`. Legacy default keeps
  current paths working.

#### Layer 4 — Core (no changes)
- All `scripts/` libs keep behavior. Only path-resolution and the two files
  with absolute user paths are touched.

#### Layer 3 — Orchestration / UI
- `ui/pages/*` call existing public entry points (`today_queue`,
  `connection_queue`, `apply_pipeline`, digest) as library functions or
  subprocess CLI calls. No business logic in UI files.
- `setup/wizard.py` orchestrates: profile ingest → keys → email creds →
  smoke test (`freshness_check`) → launch dashboard.

#### Layer 2 — Public Interface
- `ui/app.py` (`streamlit run ui/app.py`)
- `python -m setup.wizard`
- Engine CLIs unchanged.

## 5. UI Design (MVP)

### Framework research conclusion (user constraint: pure Python, polished UI)

Surveyed open-source trackers: JobSync (Next.js+Prisma, 746 stars),
JobTrackr Pro (Next.js+MongoDB), JustAJobApp (FastAPI+React). All converge on
three screens: KPI dashboard, Kanban/list application pipeline, filterable
jobs table. Forking any front-end means adopting their DB schema and dropping
the CSV engine — rejected. User requires a Python-native stack with genuinely
good looks; **NiceGUI selected** over Streamlit (full-page-rerun latency,
limited layout control) and Reflex (heaviest toolchain). NiceGUI is FastAPI +
Quasar/Vue under the hood but authored entirely in Python, gives real SPA
behavior, Tailwind utility classes, dark mode, grid/flex layout, and native
drag-and-drop support.

### Page structure (`ui/pages/`, single-process NiceGUI app)

1. **Dashboard** — KPI cards row (fresh jobs today, queue depth, applications
   sent, connections pending), freshness-tier chart (Plotly via
   `ui.echart`), ops-health strip.
2. **Pipeline** — true drag-and-drop Kanban (`ui.element`-based columns):
   Saved → Preparing → Applied → Interviewing → Closed; drop writes status to
   the canonical tracking CSV through the engine layer.
3. **Jobs** — filterable table (`ui.table`) over tracking/jobs CSVs; sidebar
   filters (fit, priority, freshness) shared app-wide via app.storage; JD in
   expandable dialog.
4. **Today's Queue** — review views (fresh_jobs / top_queue /
   needing_attention) with approve actions.
5. **Outreach** — connection approve/send ledger state, ≤25/day cap progress
   meter; drafts read-only (human-in-the-loop preserved).
6. **Resume & Settings** — tailored resume list + tailoring trigger; config
   status (keys present/absent), link to wizard.

### Engine control (user requirement: trigger every component from the UI)

The UI is a control surface for the whole engine, not a read-only viewer.
Every existing engine capability gets a trigger affordance:

| Component | UI trigger | Mechanism |
|---|---|---|
| LinkedIn/people discovery sweeps (`people_sweep`, `poster_connect_sweep`, `linkedin_*_sweep`) | "Run sweep" buttons with progress log | Background subprocess, streaming stdout into an on-page log panel |
| Job discovery (`discovery_run`, board scans) | "Run discovery" button + tier selector | Same background-run pattern |
| Resume customization | Select job → "Tailor resume" | Calls the tailoring entry point in-process |
| Cover letter / role views | Per-job action buttons | In-process calls |
| Connection queue send batches | Approve + send controls honoring ledger rules | Engine library calls (ledger interlocks enforced server-side) |
| LLM endpoints & providers (OpenRouter/NVIDIA models, base URLs, keys) | Settings → LLM Endpoints editor | Edits `<data>/config.yaml`; live-reloaded by `config_lib` |
| Freshness check, digest build | Maintenance buttons | Subprocess |

Run discipline: long sweeps run as background subprocesses with a run registry
(`ui/runs.py`: start/status/cancel, one concurrent run per component), output
streamed to the page — mirroring how crons invoke the same scripts today. The
outreach ledger's approve-before-send and daily-cap rules remain enforced in
the engine layer regardless of what the UI shows.

Conventions: `ui/theme.py` owns dark theme + brand color (single place);
pages are thin render functions — all data access via `ui/data.py` wrappers
around existing engine entry points; no JavaScript written by us.

## 5b. Additional MVP Features (user-selected from gap analysis)

1. **Reminders & nudges** — new engine lib `followups_lib.py`: derives
   follow-up actions from application dates (e.g., applied ≥7 days with no
   response → nudge recruiter draft; interview in ≤2 days → prep prompt).
   Surfaces on Dashboard as a "Needs action" panel and feeds the digest.
2. **Analytics funnel page (7th UI page)** — weekly applications, response
   rate, screen/interview counts; breakdown by source board and resume
   version. Read-only aggregation over existing tracking CSVs.
3. **Company research page (8th UI page)** — shows gathered company intel
   beside its jobs; "Research company" trigger invokes the company research
   workflow.

Deferred post-launch (documented, not built): notifications push
(email/Telegram), backup snapshots, global search, resume A/B insight,
interview-prep workspace, remote access, browser extension.

## 6. Onboarding Wizard Flow

1. Choose/create data directory (`JOBHUNT_HOME`), seed canonical structure.
2. Ingest resume PDF/DOCX → extract facts to draft `profile_info/` YAMLs
   (marked unverified until user reviews — provenance rule respected).
3. LLM provider keys (OpenRouter / NVIDIA) written to `<data>/config.yaml`
   with `chmod 600`; never echoed.
4. Optional email credentials (for outreach drafting only).
5. Browser-session note: instructions + command to create the Playwright
   persistent profile for LinkedIn (user logs in themselves, once).
6. Smoke test: freshness check + tiny Greenhouse fetch to prove pipeline;
   report pass/fail explicitly.
7. Print next steps and launch command.

## 7. Constraints

- CONVENTIONS.md: pathlib, no hardcoded user dirs (this spec *enforces* that),
  guarded CLI entry points, destructive ops preview-by-default.
- Governance: layered architecture, logging not print, no wildcard imports,
  verify checkpoints per phase, commit per task.
- Personal data must never be committed: `.gitignore` gains data-dir and
  config patterns before any refactor merges.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Hidden personal data leaks into public repo | Pre-publish audit task scanning history + tree for PII/paths |
| Path refactor breaks 243-test suite | Phase 1 is only path resolution; full suite gate per checkpoint |
| Streamlit subprocess calls brittle | Prefer importing libs; subprocess only for CLI-only entry points |
| LinkedIn fragility misleads new users | README states assisted/human-in-the-loop positioning honestly |

## 9. Acceptance Criteria

- A1: Fresh clone + wizard completes with zero edits and launches the UI.
- A2: Owner's existing workflow (`git log`, crons, suite 243 green) unchanged.
- A3: Repo contains no `/Users/<name>`, resume PDFs, contact rows, or API keys.
- A4: All six UI pages render real data from the tracking CSVs.
- A5: Wizard smoke test reports explicit pass/fail with evidence.
