# Session State — 2026-08-26/27: Small-Model Migration & Handoff

**Status:** COMPLETE. Final battery: main repo 698 passed/1 skipped (twice); fresh clone 652 passed/8 skipped clean; tree clean; HANDOFF verified.

## What happened

Executed plan `.hermes/plans/2026-08-26_224500-small-model-migration-handoff-v2-orchestrator.md`
via parallel subagent waves. All work committed on `main`.

### Completed
1. **Plan taxonomy** — 11 stale/superseded plans archived to `archive/plans_20260826/`
   with MANIFEST; `docs/plans/INDEX.md` is the canonical status table;
   `docs/plans/BACKLOG.md` holds 8 recovered unfinished items (B1–B8).
2. **Small-model migration of crons** — all 9 Hermes jobs pinned to
   `nvidia/nemotron-3-super-120b-a12b` (unpinned jobs hard-skip on config drift —
   that was the root cause of the two erroring LinkedIn jobs). Digest delivery fixed.
   `CRON_MANIFEST.md` = live registry + failure playbook; `setup/crontab.sample` =
   inert OS-cron equivalents for server migration.
3. **Portability** — `scripts/env.sh` (JOBHUNT_HOME/JOBHUNT_REPO), all `/Users/...`
   hardcodes removed from live code, canonical LLM provider chain in
   `config_lib.llm_config()` (openrouter-free → nvidia → custom); every consumer
   delegates to it. `config.example.yaml` documents small-model defaults.
4. **Repo cleanup** — 27 root junk files → `archive/root_scatter_20260826/`;
   16 dated one-off cron scripts → `scripts/legacy/`; `.playwright-mcp/` untracked
   and ignored; working tree fully committed and clean.
5. **Bug fixes found by execution**: planner missing `fixation` import (NameError);
   `PlannedQuery.justification` silently dropped in serialization so the fixation
   gate rejected justified entity queries; ambient `JOBHUNT_HOME` env var poisoned
   18 tests → `tests/conftest.py` pins it to repo-local data root.
6. **Suite green**: **698 passed, 1 skipped**, twice consecutively.
7. **Deployment path**: `setup/bootstrap.sh` (idempotent one-shot) + `HANDOFF.md`
   (data transfer rsync list, LinkedIn session caveat, ops command table).
   Fresh-clone integration gate ran; exposed engine-config YAMLs not tracked → fixed;
   personal-data-dependent tests now skip-with-reason on fresh clones; playwright is optional [browser] extra.

## 2026-09-11 — Deterministic LinkedIn Jobs discovery

- Recurring LinkedIn Jobs discovery now uses `scripts/linkedin_job_sweep.py`,
  driven by the code-owned eight-slot catalog in `setup/linkedin-job-queries.yaml`.
- Four broad anchors and three recurring technical families run every sweep; one
  frontier family rotates by oldest coverage with historical yield as a stable
  secondary signal. No LLM chooses or rewrites cron queries.
- Per-query funnel history resolves through `config_lib.data_root()` to
  `job_research/search_memory/linkedin_job_query_runs.csv`.
- Qualification records structured seniority, experience flexibility, salary,
  technical-family, eligibility, and stretch-review evidence. Cheap hard gates
  precede JD retrieval; hard 5+ year requirements are not auto-admitted.
- Linux cron source-of-truth offsets `discovery-linkedin` to minute 20 to avoid
  contention with the top-of-hour people/posts browser job.

## 2026-09-12 — Packet-driven LinkedIn people/posts research

- `scripts/people_sweep.py` now validates `primary_keywords` (with explicit
  legacy compatibility), fails on unrecognized present schemas, and emits
  machine/human-readable validation reports.
- The recurring plan starts from qualified jobs and fresh actionable posts,
  ranks company packets using configured fit tags plus coverage/yield/contact
  history, and hard-caps allocation at eight filter-first searches: four recent
  post families and four job-linked relationship paths including Georgia Tech.
- Structured candidate ranking records live-role/post linkage, named mutuals,
  GT/Fortinet overlap, technical alignment, hiring influence, recent activity,
  recommended ask, P0-P3, and why-now. Known identities can re-enter only as
  research re-evaluations; this never permits duplicate outreach.
- Live `linkedin-people-posts-2h` moved from minute 0 to minute 40 to avoid the
  shared Chrome collision with the still-live minute-0 `discovery-linkedin` job.

## Open items
- B6/B7 in BACKLOG.md (cron merge, systemd units) — deferred deliberately.
- Verify next fire (~00:00) of pinned LinkedIn crons succeeded.
- Server laptop setup: clone + `./setup/bootstrap.sh` + HANDOFF.md data transfer.

## 2026-09-07 — Right People UI page (/right-people)

- **New page**: `/right-people` (`ui/pages_right_people.py`), nav entry
  "Right People" after LinkedIn Posts. Drop a job URL / LinkedIn post /
  company name -> resolves via `right_people_lib.resolve_target` ->
  deep-link `?company=<slug>` opens that company's people workspace.
- **Data layer** (`ui/data.py`): `right_people_companies()` (per-company
  job_research/companies/<slug>/ dirs + registry merge),
  `right_people_company()`, `right_people_people()` (connections.csv +
  contacts.csv merge, contacts wins for email/status),
  `right_people_add()` (append/upsert into per-company connections.csv
  ONLY — never touches contacts.csv/ledger), `right_people_email_pattern()`
  + `right_people_render_email()` (email_pattern_finder confirmed/unverified
  only; guessed never rendered).
- **Verified live** (Playwright): Cohere shows 147 merged people, confirmed
  pattern first@cohere.com, search "grace" filters to 1 row with
  grace@cohere.com mailto; typed "Mistral AI" resolved + navigated to
  mistral_ai workspace. Query params read via `nicegui.context.client.request`
  (Client.request on the class returns the raw property — pitfall).
- **Tests**: `tests/ui/test_right_people_page.py` (7) + nav registry count
  bumped 11→12 in test_shell_components. Suite: 864 passed, 1 skipped.
- Pre-existing failure in test_output_hygiene (repo-root tracking/ leak)
  is unrelated to this change — still open.
