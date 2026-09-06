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

## Open items
- B6/B7 in BACKLOG.md (cron merge, systemd units) — deferred deliberately.
- Verify next fire (~00:00) of pinned LinkedIn crons succeeded.
- Server laptop setup: clone + `./setup/bootstrap.sh` + HANDOFF.md data transfer.

---

# Session State — 2026-08-28: "Right People" Feature (feat/right-people branch)

**Status:** COMPLETE on branch `feat/right-people` (not yet merged to main).
Suite: **826 passed, 1 skipped**. Plan: `.hermes/plans/2026-08-27_232352-right-people-feature.md`.

## What was built
`right_people` feature — company name OR job URL → ranked right-people list per
rules 05/08/09/10 (filter-first LinkedIn passes, activity-weighted scoring,
never-twice dedup, human-gated drafts).

**Modules:** `scripts/right_people_lib.py` (resolve_target), `jd_hints_lib.py`
(JD→team/manager/recruiter/keywords), `search_plan_lib.py` (10-pass rule-05 plan,
GT schoolFilter=16818), `scoring_lib.py` (weights + P0–P3 + active-poster +6),
`upsert_lib.py` (contacts/connections/people_sweep upserts, BLOCKED_STATUSES),
`right_people_ingest.py` (run_ingest/render_report/queue_drafts pending-only),
`right_people.py` (CLI: `plan` + `ingest` subcommands, top-level flags still alias).

**Live smoke (evidence):** Cohere company run — 53 real LinkedIn rows extracted
via shared Chrome :9333 (passes 01_existing_1st + 09_recruiters), ingested:
53 added, 10 inspected, ranked report at
`job_research/companies/cohere/connections_report.md`; idempotent re-run
(0 added/53 updated); search_runs.csv row appended. Zero messages sent.

## Key fix
`llm_jd_hints` used `asyncio.run()` → under py3.9 it unset the thread's event
loop and broke later NiceGUI imports in the same test session (3 order-dependent
tests/ui failures). Fix `0aba598`: private `new_event_loop()` + close.

## Open items
- Merge `feat/right-people` → main after review.
- Profile-inspection enrichment (Task 8 activity check) currently scores from
  search-page snippets; deeper per-profile activity crawl is a follow-up.
