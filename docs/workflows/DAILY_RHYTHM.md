# Daily Operating Rhythm Contract

Source plan: archived `archive/plans_20260826/2026-08-23_015227-daily-rhythm-and-on-demand.md` (Task 4) — see docs/plans/INDEX.md.
This file is the contract between the user and the automated system: what runs
by itself, what the user does when they sit down, and the exact commands behind
on-demand exceptions.

## EVERY DAY (automatic — no user action required)

The following run in the background via cron; the user never prompts them:

| Cadence | What | Mechanism |
|---|---|---|
| Every 2 hours | LinkedIn discovery sweeps + urgent-job alert fast path (`scripts/urgent_check.py`) | `discovery-linkedin` cron section (see `CRON_MANIFEST.md`) |
| Every 2 hours | Hiring-post monitor + people sweep + email enrichment | `linkedin-people-posts-2h` cron (job-hunt profile; supersedes 4x/day cadence) |
| Daily 8AM | `daily_ops`: career-ops scan (Mon/Thu), job scoring, review-queue rebuild, **MORNING DIGEST** (incl. per-person LinkedIn notes + email drafts) | `scripts/daily_ops.py` |

Hot jobs (<24h old, APPLY tier ≥68) are surfaced by `urgent_check` within one
3-hour cycle — no user prompt needed.

## WHEN I SIT DOWN (~30 min review flow)

1. Read the MORNING DIGEST (`execution_results/digests/digest_<date>.md`):
   ~10 ranked fresh jobs, each with fit tier + why + age.
2. Tick jobs to pursue → triggers resume fill plans for each ticked job.
3. Review the connection checkmark list → tick → sends go out
   (cap: 20–25 connection requests/day).
4. Say GO on staged applications → applications execute.

## ON-DEMAND EXCEPTIONS (natural phrase → exact command)

All commands run from the repo root with the project venv python.

| User says | Command |
|---|---|
| "jobs posted in the last 5 hours on LinkedIn" | `~/.hermes/hermes-agent/venv/bin/python scripts/discovery_run.py --recency 5h --source linkedin` |
| "ingest this job: <url>" | `~/.hermes/hermes-agent/venv/bin/python scripts/discovery_run.py --ingest <url>` |
| "search Wellfound now" / any single source now | `~/.hermes/hermes-agent/venv/bin/python scripts/discovery_run.py --source wellfound\|linkedin\|career_ops\|hiring_posts\|all` |

## The explicit answer

Crons run in the background. The user never prompts routine discovery.
The user only issues exceptions (the phrases above). Hot jobs (<24h,
APPLY tier ≥68) arrive automatically via `urgent_check` within one 3-hour
cycle of posting.

## Digest contract

`scripts/daily_ops.py` (step 6, `compile_morning_digest`, owned separately)
currently emits new jobs as:
`- [priority_v2] company — title (score=…, recommended_action) url`.

The plan requires each digest job entry to additionally show:

- **fit tier** (e.g. APPLY / MAYBE / SKIP from scoring),
- **why** (the top reason(s) driving the score/tier),
- **age** (time since posting).

Until daily_ops is updated by its owner to include these three fields per
entry, treat the current digest shape as a known gap against this contract;
this doc records the required shape so it can be reconciled without editing
the owning agent's in-progress code.
