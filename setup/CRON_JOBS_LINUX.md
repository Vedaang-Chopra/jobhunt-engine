# Cron jobs — jobhunt-engine (Linux laptop)

8 scheduled jobs. Dropped `morning-job-digest` (duplicate of `daily-ops`).
All were left DISABLED on the Mac before cutover — enable after onboarding checks pass.

On this machine, replace:
- `{{REPO}}` → the absolute path of the cloned jobhunt-engine repo
- `{{PY}}` → the repo venv python (e.g. `{{REPO}}/.venv/bin/python` after `scripts/bootstrap.sh` / `pip install -e .`)

`discovery-career-ops` additionally needs the `career-ops` sibling repo cloned
next to the engine repo (it scans `../career-ops`).

Create each with: `hermes cron create` via the agent, or paste the prompt as the
job `prompt` with the given schedule. Keep `enabled: false` until the
onboarding checklist in the onboarding prompt passes.

---

## 1. discovery-career-ops — `0 8 * * 1,4`
Automated job-discovery maintenance (cron: discovery-career-ops). cd into `{{REPO}}` and run: `{{PY}} scripts/discovery_run.py --sources career_ops` — this runs the ../career-ops scanner (node scan.mjs --quiet), imports the scan via scripts/import_career_ops_scan.py, and re-scores via scripts/score_jobs_v2.py. Use only the terminal and file toolsets.

HARD ELIGIBILITY GATES (docs/rules/ROLE_FIT_RULES.md §9): after import, apply gates G1-G6 to the newly imported rows before they count as pipeline jobs. Internships/new-grad/early-career (G3), Director/VP/Head/Chief/Principal/people-manager titles (G2), posted pay <$150k (G4), or clearly unrelated roles (G5) must be marked recommended_action=SKIP with the gate id in notes — never left as open+scored. Experience ceiling ~4.5 yrs hard minimum (G1) judged from JD text when available; flexible 'or equivalent' phrasing stays.

Then report: how many NEW job rows were added, how many were gated out (by gate id), plus any failures. Deliver locally; no chat delivery needed.

## 2. discovery-freshness — `0 21 * * *`
Automated job-discovery maintenance (cron: discovery-freshness). cd into `{{REPO}}` and run: `{{PY}} scripts/discovery_run.py --sources freshness` — this runs scripts/freshness_check.py --live, which re-verifies ATS job URLs by tier and flags stale/expired rows in tracking/jobs/jobs.csv (rows are never deleted). Use only the terminal and file toolsets. Then report a short summary of the freshness run outcome (verified/stale/expired counts from the discovery_<ts> summary line in tracking/search_runs/search_runs.csv) plus any failures. Deliver locally; no chat delivery needed.

## 3. outreach-batch — `0 10 * * *`
Daily outreach batch (cron: outreach-batch). cd into `{{REPO}}` and run: `{{PY}} scripts/connection_queue.py list` (if that fails, run: `{{PY}} scripts/poster_connect_sweep.py --dry-run`). Present the RANKED list of top people to connect with today as a checkmark-style list (name, role, company, why-now, priority) directly to the user in chat, then STOP and WAIT for the user's selection. NEVER auto-send any connection request or message — human-in-the-loop is mandatory. Do not take further action until the user replies.

## 4. discovery-linkedin — `0 */2 * * *`
LinkedIn discovery sweep (cron: discovery-linkedin). cd `{{REPO}}`. First run: `{{PY}} scripts/discovery_run.py --sources l1,l2` — it will report 'needs interactive session' if headless. THEN attempt the real sweep yourself using the Playwright MCP browser (persistent logged-in Chrome profile is already configured — never type passwords; if a login wall appears, stop and report): run ONE LinkedIn jobs sweep per the linkedin-job-sweep skill (guest API + logged-in fetch methods, scripts/linkedin_guest_sweep.py exists as reference), normalize results through scripts/discovery_lib.py, dedupe against tracking/jobs/jobs.csv, append new rows, log to tracking/search_runs/search_runs.csv. Keep it to ONE tab, ≤8 searches, close the tab after. If LinkedIn shows CAPTCHA/warning, stop immediately and note it.

HARD ELIGIBILITY GATES (docs/rules/ROLE_FIT_RULES.md §9): before appending any new row as open, apply gates G1-G6. Internships/new-grad/early-career (G3), Director/VP/Head/Chief/Principal/people-manager titles (G2), posted pay <$150k (G4), or clearly unrelated roles (G5) must NOT enter the pipeline as open+scored: either skip them at ingest or append with recommended_action=SKIP and the gate id in notes. Experience ceiling ~4.5 yrs hard minimum (G1) is judged from JD text when available; flexible 'or equivalent' phrasing stays. Report new-jobs count AND how many were gated out.

## 5. daily-ops — `0 8 * * *`
Morning job-hunt digest (cron: daily-ops). cd `{{REPO}}` && run `{{PY}} scripts/daily_ops.py`. Then deliver the compiled morning digest (execution_results/digests/digest_<today>.md) to the user verbatim, and STOP — everything consequential (connections, applications) waits for explicit user input. Never auto-send outreach or submit applications.

## 6. apps-sync — `0 20 * * *`
Application status sync (cron: apps-sync). cd `{{REPO}}` && run `{{PY}} scripts/application_sync.py --check-portals` and `--suggest-followups`. Record any definitive status findings via --mark. Never send emails or messages. Report summary locally (deliver=local).

## 7. ops-health — `30 21 * * *`
Ops health check (cron: ops-health). cd `{{REPO}}` && run `{{PY}} scripts/ops_health.py --check`. If it exits non-zero, also produce --report output and append the alert lines to execution_results/ops/alerts.log so the next morning digest surfaces them. deliver=local; only alert content is worth saving.

## 8. linkedin-people-posts-2h — `0 */2 * * *`
LinkedIn people + hiring-posts sweep (cron: linkedin-people-posts-2h). Workdir: `{{REPO}}`.

PART A — Hiring-post monitor: run the linkedin-hiring-post-monitor skill end-to-end (feed pass via Playwright MCP with logged-in Chrome profile; ONE feed pass, ~10 scrolls max, READ ONLY no likes/comments/connects; then site:linkedin.com/posts web searches rotating company coverage). Apply the fit gate from the skill. Dedupe against tracking/hiring_posts/hiring_posts.csv, append new rows, mirror to job_research/companies/<slug>/hiring_posts.csv when dir exists, log to tracking/search_runs/search_runs.csv (run_id lhp_<ts>). If a login wall/CAPTCHA appears, stop and note it.

PART B — People sweep: run scripts/people_sweep.py logic per its docstring — build queries via load_preferences()/build_queries(), run up to 8 LinkedIn people searches (Playwright MCP browser, same logged-in profile), normalize found people through merge_extraction() with the PeopleDedupIndex (never-twice dedup vs contacts.csv + prior sweeps), append accepted rows to tracking/people_sweeps/people_sweep.csv.

PART C — Email enrichment: for each NEW contact lacking an email, run `{{PY}} scripts/email_pattern_finder.py --company <company_slug>` (dry-run default) to attach pattern candidates; only confirmed patterns get marked usable — never send to guessed addresses. Record results in notes.

DELIVERABLE (final response): one-line-per-section digest — new hiring posts (poster/company/roles/URL), new people queued (name/company/type/why), emails resolved this run. If a section found nothing, say so in one line. NEVER send outreach or connection requests — queue/draft only (human-in-the-loop).
