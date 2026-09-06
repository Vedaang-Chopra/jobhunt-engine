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
