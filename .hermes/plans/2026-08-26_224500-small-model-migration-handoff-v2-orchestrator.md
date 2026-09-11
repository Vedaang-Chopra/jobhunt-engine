# Migration Handoff — Orchestrator Plan v2 (Parallel Subagent Execution)

> **For Hermes:** This is the ORCHESTRATOR plan. Execute via `delegate_task` batches per
> Workstream (fresh subagent per task). This plan SUPERSEDES
> `.hermes/plans/2026-08-26_222507-small-model-migration-handoff.md` — it keeps all of its
> content and adds Phase 0 (planning-artifact hygiene) and a parallel workstream graph.
> Read v1 for full task detail; this file defines ORDER, PARALLELISM, and GAPS FOUND.

**Goal:** Clean repo + portable small-model-ready job-hunt OS, handed off to a second machine via documented bootstrap, executed with maximum subagent parallelism.

**Architecture:** Five phases. Phase 0 first (alone — touches `.hermes/plans/` + `docs/plans/`, trivially fast). Then Workstreams W1–W4 run largely in parallel via delegate_task; each task's spec lives in v1 (§Task N.M references below). Verification gates between commits are per-task; final battery gates handoff.

**Tech Stack:** Python venv (.venv), pytest, NiceGUI, CSV stores under `$JOBHUNT_HOME`, Hermes cron → future OS cron, docker-compose optional.

---

## Phase 0 — Planning-Artifact Hygiene (the 6 temporary plan files)

**Problem (verified):** `.hermes/plans/` holds 3 generations of overlapping plans with no
status markers: five dated 2026-08-23 files (`job-discovery-overhaul`, `referral-engine`,
`master-pipeline`, `apply-loop-and-autonomy`, `daily-rhythm-and-on-demand`,
`master-execution-parallel`) where two explicitly "SUPERSEDE" earlier ones, plus the new v1
migration plan. Meanwhile `docs/plans/` mixes canonical numbered plans (`002_*`) with
one-off session prompts (`NEXT_SESSION_*`, `PROFILE_EVALUATION_SESSION_PROMPT`). Agents
picking up work cannot tell what is live, done, or dead.

**Decision framework (execute in this order):**

### Task 0.1: Build plan inventory + status verdicts
Read every file fully; classify against git history + actual code:
- `2026-08-23_003237-job-discovery-overhaul.md` — SUPERSEDED by master-pipeline → **archive**
- `2026-08-23_003754-referral-engine.md` — SUPERSEDED by master-pipeline → **archive**
- `2026-08-23_004459-master-pipeline.md` — check completion: discovery_cycle.py, engine/,
  search_strategy/ exist and tests pass ⇒ mostly DONE → mark completed sections; unfinished
  tasks migrate into the backlog table of Task 0.3
- `2026-08-23_010129-apply-loop-and-autonomy.md` — partially done (apply_pipeline.py,
  form_filler.py, extract_simplify_answers.py exist); unfinished items → backlog table
- `2026-08-23_015227-daily-rhythm-and-on-demand.md` — done (today_queue.py, UI today page
  exist) → **archive as completed**
- `2026-08-23_032410-master-execution-parallel.md` — orchestrator for above; obsolete → **archive**
- `docs/plans/NEXT_SESSION_*`, `PROFILE_EVALUATION_SESSION_PROMPT.md`,
  `POST_TRAINING_PROJECT_PLAN_2026-08-23.md` — session-prompt one-offs → **archive**

**Step:** Create `docs/plans/INDEX.md` — single table: plan id, title, status
(active | completed | superseded-by-X | backlog-items-migrated-to-BACKLOG.md), path.
This is the systematic entry point agents read first.

**Step:** Move archived files to `archive/plans_20260826/` with `MANIFEST.md`
(old path → destination → reason, per AGENTS.md rule 5).

**Step:** Verify nothing referenced them:
```
grep -rn "hermes/plans\|NEXT_SESSION_PLAN" --include='*.md' docs/ README.md AGENTS.md CRON_MANIFEST.md | grep -v archive
```
Fix dangling references found.

### Task 0.2: Consolidate live items into one canonical location
Create `docs/plans/BACKLOG.md`: table of every genuinely-unfinished item recovered from
master-pipeline / apply-loop / v1 migration plan, each row = {id, source-plan, task summary,
blocking?, suggested task id}. The migration plan below becomes `docs/plans/003_migration_small_models_handoff.md`
(copy of v1+this file's executable content, marked active, once work starts there instead of .hermes/plans).

### Task 0.3: Rule-capture
If recovery revealed recurring conventions (e.g. "plans must carry Status header"),
add 5-line convention note to `docs/plans/INDEX.md` header rather than new rule files
(AGENTS.md rule 6: no tiny markdown files).

**Commit:** `git commit -m "docs(plans): consolidate plan taxonomy, archive superseded plans, add INDEX + BACKLOG"`

---

## Parallel Workstream Graph (Phases from v1)

Dependency facts from v1 diagnosis:
- Fixation NameError fix is independent (1 file).
- Test order-independence touches tests/conftest + ~5 test files (independent of planner fix).
- Untracked-file triage MUST come after tests green (commit gate).
- Cron/env portability greps don't touch test files at all.
- Bootstrap script + HANDOFF independent of everything except final tree state (last merge).

```
P0 (sequential, main session)
 ├─► W1: Stabilize code ──► W1c triage/commit tree
 │        T1.1 fixation fix ─┐
 │        T1.2 test isolation┴→ T1.3 junk purge → T1.4 logical commits
 ├─► W2: Ops portability (parallel with W1 — different files)
 │        T2.1 env.sh + path scrub → T2.2 LLM chain audit/small-model gate
 │        T2.3 cron prompt rewrite → T2.4 crontab.sample
 └─► W3: Bootstrap/docs drafting (draft-only, commit after W1 merges)
          T3.1 bootstrap.sh → T3.2 HANDOFF.md → T3.4 docker smoke
                    ↓ (after W1+W2+W3 all merged)
          T3.3 fresh-clone dry-run in /tmp ← THE INTEGRATION GATE
          P4: docs update + final verification battery (main session)
```

**delegate_task batching:**
- Batch A (parallel): [W1a: T1.1], [W1b: T1.2], [W2a: T2.1], [W2b: T2.2 investigation+report]
- Batch B (parallel after A): [W1c: T1.3+T1.4], [W2c: T2.3+T2.4], [W3a: T3.1+T3.2]
- Batch C (serial): [T3.3 fresh-clone gate], then [P4 verification]

Each subagent prompt must include: exact v1 task text, repo path, "run
`.venv/bin/python -m pytest tests/ -q` before finishing; report PASS count",
and its file-boundary list ("touch ONLY these paths") to avoid merge conflicts.
Main session verifies each result personally (re-run pytest, `git log --oneline`)
before dispatching the next batch.

---

## Gap Check — additions to v1 (verified missing before writing v2)

1. **`.playwright-mcp/` tracked files**: `git rm --cached` was listed but the 4 already-tracked files need explicit mention in T1.3 — present in v1 ✓ (no change).
2. **`jobhunt-data/runs/`** untracked: decide track-vs-ignore during T1.4 — v1 mentioned it; add default: ignore (`runs/` = run-state) unless review CSVs land there.
3. **Cron output dir** `~/.hermes/profiles/job-hunt/cron/output/<id>/` is the evidence source for fixing jobs `05ac53fa1759` & `761c4d1c8a2f` — added to T2.3 spec here ✓.
4. **`scripts/search_strategy/cycle.py` + `exec_jobs.py` wiring**: tests exist (`test_search_strategy_{cycle,exec_jobs}.py` — currently passing? confirm at T1.1 time). If they fail due to same pollution class, fold into W1b scope.
5. **Everything else**: v1 Phases 1–4 stand unchanged; execute them verbatim inside the workstreams above.

---

## Final Verification Battery (unchanged from v1 §4.2)
```bash
.venv/bin/python -m pytest tests/ -q   # twice consecutively → 0 failed both times
git status --porcelain                 # empty (or only intentional data files)
grep -rn '/Users/' scripts/ ui/ setup/ | grep -vE 'legacy|archive'   # empty
bash -n setup/bootstrap.sh
```
Plus paste T3.3 fresh-clone dry-run output as handoff evidence. Docs updated
(README, session_state ×2) in same final commit per AGENTS.md rule 7.

## Risks / Tradeoffs
- **Archiving old plans loses context** — mitigated by BACKLOG.md migrating unfinished items + git history preserving originals.
- **Parallel test-file edits** (W1b while others run pytest) — subagents work on disjoint path sets; merge order enforced by batch discipline.
- **Hermes cron churn during rewrite** — jobs stay enabled until prompts verified; disable individual broken ones (`05ac53fa1759`, `761c4d1c8a2f`) only if fix isn't immediate.

## Open Questions (decide inline, don't block)
1. Merge the three 08:00 Hermes jobs? Default yes.
2. Systemd units now or document-only? Default document-only (YAGNI).
3. Should v1+v2 be copied into `docs/plans/003_*` at execution start so the active plan
   lives in canonical docs? Default yes (Phase 0 does it).
