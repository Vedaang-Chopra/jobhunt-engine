# Daily Ops Workflow — unattended morning cycle

Entry point: `python scripts/daily_ops.py` (add `--dry-run` to preview).
Locking: shares `.hermes/ops.lock` with `scripts/discovery_run.py`, so the
morning cycle never overlaps a discovery cron run. Health monitoring:
`scripts/ops_health.py --check | --report`.

## What runs unattended (in order, each try/except-isolated)

| # | Step | Command | Notes |
|---|------|---------|-------|
| 1 | career-ops scan + import (live) | `scripts/career_ops_sweep.py` | node scan → import new rows |
| 2 | discovery sweeps due | `discovery_run.py --sources career_ops,freshness` | l1/l2 self-skip headless — expected |
| 3 | hiring-post ingestion note | reads `tracking/hiring_posts/hiring_posts.csv` | ingestion itself is the existing 4x/day cron; here we only verify readability + count recent rows |
| 4 | scoring | `scripts/score_jobs_v2.py` | scores unscored/open rows |
| 5 | review CSVs | `scripts/today_queue.py` | rebuilds `execution_results/reviews/*` |
| 6 | morning digest | writes + prints `execution_results/digests/digest_<date>.md` | see sections below |

Digest sections: **new jobs worth eyes** (≤10 ranked from
`reviews/top_queue.csv`), **people to connect** (connection_requests pending /
approved / sent / connected counts + poster-connect dry-run summary),
**applications needing action** (`status=ready_to_apply` rows awaiting GO /
fill-plan approval), **status changes since yesterday** (new jobs, application
status changes), **system health** (paused sources, failure streaks,
`execution_results/ops/alerts.log` tail).

## What STOPS and waits for user input

Step 7 is a hard STOP. The cycle never, on its own:

- approve or send connection requests (`connection_queue.py approve`,
  `poster_connect_sweep.py --live`)
- generate or submit applications / fill plans
- mark jobs applied, archive JDs, or change canonical job status beyond what
  scoring/freshness already write

## Health monitoring (Task 9)

`ops_health.py --report` prints a per-source table (status, failure streak,
last result, recency vs `tracking/search_runs/search_runs.csv`).
A source whose `failure_streak >= 2` in `execution_results/ops/health.json`
is marked `self-paused`, an alert line is appended to
`execution_results/ops/alerts.log`, and `--check` exits non-zero.
Reset a paused source by editing `health.json` (set `failure_streak: 0`,
`status: "active"`, drop `alerted_at_streak`).

No cron jobs are registered by these scripts; scheduling belongs to the
parent orchestrator.
