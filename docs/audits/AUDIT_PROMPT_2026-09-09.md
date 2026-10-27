# Full System Audit — Cron-to-Button Feature Verification

## Mission
Systematically verify EVERY feature of the job-hunt system: each of the 8 cron jobs AND its equivalent manual trigger (UI button / script), plus every UI feature. One at a time, properly. No batching — each item gets its own explicit verdict (PASS / FAIL / PARTIAL) backed by real evidence (command output, row counts, file diffs). Never claim done without showing the actual result.

## Environment
- Engine repo: /mnt/DATA/job_hunt/jobhunt-engine
- Data root: /mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data (JOBHUNT_HOME)
- Python: /mnt/DATA/job_hunt/jobhunt-engine/.venv/bin/python (symlink to ~/venvs/jobhunt) — invoke as `/mnt/DATA/job_hunt/jobhunt-engine/.venv/bin/python scripts/<script>.py`
- UI: NiceGUI on http://localhost:8080 (systemd: hermes-gateway-job-hunt-fresh not involved; UI unit separate). Verify with `curl -s http://localhost:8080/` → 200. If the UI needs a restart, use `systemctl --user restart <unit>` — find the unit with `systemctl --user list-units | grep -i jobhunt`.
- Automation Chrome: CDP :9333, profile ~/.hermes/browser-profiles/job-hunt. Check health with `curl -s --max-time 3 http://127.0.0.1:9333/json/version` — if empty/dead, unit `jobhunt-automation-chrome.service` may still say "active (exited)"; re-run `bash /mnt/DATA/job_hunt/jobhunt-engine/scripts/automation_chrome.sh` (idempotent, LinkedIn login persists).
- Cron fleet: inspect with cronjob_manage action='list' (profile job-hunt-fresh). 8 jobs: daily-ops (4ea61ff1eb60), discovery-linkedin (b0a56b767fc0), linkedin-people-posts-2h (e65e2f18c8e6), discovery-career-ops (82576201e9ee), outreach-batch (8e32da27ceb4), apps-sync (af86830e28e8), discovery-freshness (6b13096cb6ae), ops-health (83dfabcc37bc).
- Fallback chain verified via `hermes fallback list` (primary nvidia 550b → nemotron-3-super-120b). If crons die with "Service temporarily overloaded", restart `hermes-gateway-job-hunt-fresh.service` — the running gateway keeps old config.

## Audit checklist — walk IN THIS ORDER

### Phase 1 — Cron fleet (8 items)
For each cron: read its prompt (cronjob list), fire it with action='run', verify the background result when it re-enters the conversation, and check the data side-effect (CSV row counts, output md file in ~/.hermes/profiles/job-hunt-fresh/cron/output/<job_id>/).
1. daily-ops — expect digest; verify last output md exists and reports counts.
2. discovery-linkedin — verify new rows in jobhunt-data/tracking/jobs/jobs.csv + run logged in tracking/search_runs/search_runs.csv.
3. linkedin-people-posts-2h — verify hiring_posts.csv and people_sweeps/people_sweep.csv deltas + run log lhp_*.
4. discovery-career-ops — expect "N new jobs, M gated (gate id)" report; verify jobs.csv delta.
5. outreach-batch — verify tracking/messages or outreach queue updates; NO messages sent (human-in-the-loop only).
6. apps-sync — verify tracking/applications changes; check status updates.
7. discovery-freshness — verify stale/expire updates on jobs.csv (recommended_action changes for old posts).
8. ops-health — verify health report output; confirm it actually detects problems (e.g. that it would flag a dead Chrome).

### Phase 2 — UI (10 pages, ~49 buttons)
UI lives at http://localhost:8080. Pages: /today, /jobs, /job-search, /linkedin-posts, /applications, /network, /right-people, /insights, /runs, /operations.
Use the browser (Playwright MCP, CDP :9333 attached Chrome is the automation profile — the UI is a separate tab, do NOT close it) to visit each page:
- /today — verify top_queue / fresh_jobs / needing_attention buckets render and are mutually exclusive; test the job detail dialog buttons (Track this role, Mark completed, Mark for later, Mark expired, Run evaluation) and confirm each writes back to the CSV.
- /jobs — test filter chips, Clear filters, Save view, Apply view; verify filtered results actually change.
- /job-search, /linkedin-posts, /applications, /network, /right-people, /insights, /runs, /operations — for each: does it load without error, do its buttons fire their intended action, does the data change where expected.
- /operations page: check it exposes manual equivalents of the cron tasks — compare one-by-one against Phase 1 crons (this is the cron↔button mapping the user wants).
Every failed click/console error gets reported with the actual error, not "it seems fine".

### Phase 3 — Cross-checks (3 items)
9. Cron ↔ button parity: for every cron action find the UI/manual equivalent (or explicitly note it has none). Build a small table at the end: cron | schedule | manual equivalent | status.
10. Data integrity: jobs.csv row count stable before/after each test (only expected deltas), no duplicate job_ids introduced by repeated test runs; search_runs.csv append-only.
11. End state: leave the fleet running, all crons enabled, Chrome CDP alive, UI on :8080. Report any item left FAILing.

## Rules
- Show evidence for every verdict: exact command + key output lines.
- Don't re-run whole sweeps when a dry-run/count check proves the mechanism; but at least one real write-back per page/button category must be demonstrated.
- Backup jobs.csv before any manual append test (cp jobs.csv jobs.csv.bak_<ts>) and delete test rows after (only rows you added, tagged e.g. notes containing "AUDIT-TEST").
- If something fails: fix it if the fix is obvious and safe, re-test, then record the fix in the report. If not fixable now, mark FAIL with root cause and propose the fix.
- Keep LinkedIn interaction read-only (no likes/comments/connects); stop on CAPTCHA/login-wall and note it.
- Final deliverable: a verdict table covering all 8 crons + 10 pages + parity/integrity checks, with PASS/FAIL/PARTIAL per item and one-line evidence each.