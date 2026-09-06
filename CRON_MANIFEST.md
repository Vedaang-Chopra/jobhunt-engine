# Live Cron Registry — 2026-08-26 Migration Snapshot

> This section is the CURRENT STATE of the 9 Hermes cron jobs after the
> small-model migration (2026-08-26). The original consolidated plan below is
> preserved for design intent. OS-level equivalents: `setup/crontab.sample`.

## Current Hermes jobs (all pinned to small models)

| Job | ID | Schedule | Model | Deliver | Entrypoint | Status 2026-08-26 |
|---|---|---|---|---|---|---|
| daily-ops | `2f780113e181` | 0 8 * * * | nemotron-3-super-120b | origin | scripts/daily_ops.py | ok |
| discovery-career-ops | `64846a31d368` | 0 8 * * 1,4 | nemotron-3-super-120b | local | career_ops_sweep via discovery_run | never run |
| morning-job-digest | `9a38cd651409` | 0 8 * * * | nemotron-3-super-120b | **origin** (was origin,all — unresolvable) | daily ops cycle in-prompt | delivery fixed |
| outreach-batch | `d107677b66fd` | 0 10 * * * | nemotron-3-super-120b | origin | connection_queue present-batch (human-gated) | ok |
| discovery-linkedin | `05ac53fa1759` | 0 */2 * * * | nemotron-3-super-120b | local | discovery_run --sources l1,l2 + in-prompt gates G1–G6 | was erroring (config-drift skip); pinned → verify next fire |
| linkedin-people-posts-2h | `761c4d1c8a2f` | 0 */2 * * * | nemotron-3-super-120b | origin | cron_lhp_people_driver.py | was erroring (config-drift skip); pinned → verify next fire |
| apps-sync | `e9597fb81bea` | 0 20 * * * | nemotron-3-super-120b | local | application_sync.py | ok |
| discovery-freshness | `5a4de2a4d1b5` | 0 21 * * * | nemotron-3-super-120b | local | freshness_check.py | ok |
| ops-health | `344702a9a9cd` | 30 21 * * * | nemotron-3-super-120b | local | ops_health.py | ok |

**Model policy:** every job explicitly pinned (`hermes cron edit <id> --provider nvidia
--model nvidia/nemotron-3-super-120b-a12b`). Unpinned jobs hard-skip on any global config
drift (`[drift_skip]` error class) — pinning is now mandatory practice. No job references
the 550b model.

**Failure playbook:** check `~/.hermes/profiles/job-hunt/cron/output/<job_id>/<latest>.md`;
a `[drift_skip]` RuntimeError means re-pin the model; LinkedIn sweeps that report a login
wall require one manual login in the automation Chrome (see BROWSER_ARCHITECTURE.md).

**Known residual overlap:** three jobs share the 08:00 slot (daily-ops,
discovery-career-ops which only fires Mon/Thu, morning-job-digest). Tracked as BACKLOG B6;
not merged because digest and ops have distinct output contracts and d-c-o already
skips most days.

## Server migration path

When moving to the server laptop: install `setup/crontab.sample`, then pause the
matching Hermes jobs here (`hermes cron pause <id>`). Never run both machines'
sweeps against the same tracking CSVs simultaneously — rsync before/after, or make
one machine authoritative per window.

---

# CRON_MANIFEST — Original Consolidated Plan (design reference)

Consolidated cron plan (Task 13). Exact `hermes` commands below are to be
registered with the user present; existing working crons (hiring-post monitor
4×/day, wellfound daily) remain untouched.

Unified runner: `scripts/discovery_run.py`
(`--sources l1,l2,career_ops,newgrad,freshness`, default all-due;
per-source health in `tracking/search_runs/source_health.csv`;
streak ≥ 2 → self-paused + ALERT).

---

## 1. discovery-linkedin — every 3h

l1 (portal sweep) every run; l2 (recommended sweep) piggybacks on the 6h boundary.
> After the import step in this flow, append `&& ~/.hermes/hermes-agent/venv/bin/python scripts/urgent_check.py` so fresh hot jobs (age ≤24h, priority_v2 ≥68) alert immediately.

```bash
hermes cronjob add discovery-linkedin \
  --every 3h \
  --command "python3 scripts/discovery_run.py --sources l1,l2" \
  --note "LinkedIn portal sweep + recommended sweep (l2 on 6h boundary)"
```

If per-boundary split is preferred:

```bash
hermes cronjob add discovery-linkedin-l2 --every 6h \
  --command "python3 scripts/discovery_run.py --sources l2"
```

## 2. Existing monitors — UNCHANGED

- hiring-post monitor: 4×/day (existing cron, do not modify)
- wellfound crawler: daily (existing cron, do not modify)

## 3. discovery-career-ops — Mon/Thu 8AM

```bash
hermes cronjob add discovery-career-ops \
  --cron "0 8 * * 1,4" \
  --command "python3 scripts/discovery_run.py --sources career_ops" \
  --note "career-ops portal scan + import, twice weekly"
```

**Rule:** at the start of ANY on-demand job search session, run a live
career-ops scan first (`python3 scripts/career_ops_sweep.py`) so results are
fresh before qualification.

## 4. discovery-freshness — daily 9PM

```bash
hermes cronjob add discovery-freshness \
  --cron "0 21 * * *" \
  --command "python3 scripts/discovery_run.py --sources freshness" \
  --note "tiered staleness re-verification of jobs.csv"
```

## 5. outreach-batch — daily 10AM (human-in-the-loop)

Presents a ranked checkmark list of top referral candidates for the day's
target companies → user checks names → send connection requests ONLY for
checked entries.

Constraints:
- 20–25 requests/day max
- bare-connect fallback when no tailored message fits
- STOP immediately on any LinkedIn warning/captcha/rate-limit signal

```bash
hermes cronjob add outreach-batch \
  --cron "0 10 * * *" \
  --command "python3 scripts/connection_queue.py --present-batch" \
  --note "ranked checkmark list; send only user-checked; 20-25/day cap"
```

(Entry point = existing tracked connection-request queue; adjust flag name if
the queue CLI differs.)

---

## Health / self-pause policy

All scheduled runs go through `discovery_run.py`. Per-source consecutive
failures are recorded in `tracking/search_runs/source_health.csv`
(`source,date,exit_code,failure_streak,status`). At failure_streak ≥ 2 the
source is marked `self-paused`, an ALERT is printed, and it is skipped by
subsequent runs until manually reset.
