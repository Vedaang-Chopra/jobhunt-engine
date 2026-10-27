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

## 4. discovery-linkedin — `20 */2 * * *`
LinkedIn discovery sweep (cron: discovery-linkedin). Workdir: `{{REPO}}`. Run exactly: `{{PY}} scripts/linkedin_job_sweep.py --live`.

The runner owns the complete query contract: exactly eight deterministic searches selected from `setup/linkedin-job-queries.yaml` or the canonical data-root override at `job_research/config/linkedin-job-queries.yaml`; four broad anchors, one query from each of three recurring technical families, and one coverage/yield-rotated frontier query. Do not invent, substitute, broaden, or add “equivalent” queries. The runner enforces US-only, past-week, and Associate/Mid-Senior filters for both the guest API and authenticated server-rendered LinkedIn fetch, then normalizes, deduplicates, qualifies, and records per-query history under the canonical data root.

Discovery is READ ONLY with respect to LinkedIn: never click Easy Apply, submit an application, connect, message, like, comment, or type credentials. Stop on CAPTCHA, warning, auth wall, or rate-limit signal. Report the actual JSON funnel emitted by the runner: planned searches, raw results, unique candidates, duplicates, hard rejections, eligible/appended jobs, APPLY/OPTIMISTIC outcomes, per-path retrieval status, query failures, and errors. A run is not successful unless `browser_retrieval_succeeded=true`; guest-only or planner-only execution is partial/failure, not success. Human approval remains mandatory for every application or outreach action.

## 5. daily-ops — `0 8 * * *`
Morning job-hunt digest (cron: daily-ops). cd `{{REPO}}` && run `{{PY}} scripts/daily_ops.py`. Then deliver the compiled morning digest (execution_results/digests/digest_<today>.md) to the user verbatim, and STOP — everything consequential (connections, applications) waits for explicit user input. Never auto-send outreach or submit applications.

## 6. apps-sync — `0 20 * * *`
Application status sync (cron: apps-sync). cd `{{REPO}}` && run `{{PY}} scripts/application_sync.py --check-portals` and `--suggest-followups`. Record any definitive status findings via --mark. Never send emails or messages. Report summary locally (deliver=local).

## 7. ops-health — `30 21 * * *`
Ops health check (cron: ops-health). cd `{{REPO}}` && run `{{PY}} scripts/ops_health.py --check`. If it exits non-zero, also produce --report output and append the alert lines to execution_results/ops/alerts.log so the next morning digest surfaces them. deliver=local; only alert content is worth saving.

## 8. linkedin-people-posts-2h — `40 */2 * * *`
LinkedIn people + hiring-posts sweep (cron: linkedin-people-posts-2h). Workdir: `{{REPO}}`.

SAFETY: all LinkedIn/browser activity is READ ONLY. Never message, connect, follow, like, comment, apply, email, or create outreach drafts. Stop on CAPTCHA, warning, auth wall, or rate-limit signal. Use the shared authenticated Chrome through the configured Playwright/browser session, reuse one search tab plus one temporary profile tab, and close temporary tabs.

PLANNING GATE: run `{{PY}} scripts/people_sweep.py --dry-run --json --limit 8`. If it exits nonzero, report `planning_config_validation_failure` with its actionable error and do not browse. Use only the returned ranked job/hiring-post packet and returned eight-or-fewer queries; never replace them with the first companies in YAML or bare company-only searches. The planner reads qualified APPLY/APPLY_NOW and strong OPTIMISTIC jobs, fresh actionable hiring posts, company fit tags, canonical contacts, and persisted coverage/yield history through `config_lib.data_root()` / `JOBHUNT_HOME`.

PART A — hiring-post-first: perform ONE logged-in feed pass (~10 main-container scrolls max), then execute the planner's four highest-priority content searches in order. For each filter change verify Posts + Past Week + Latest active chips and the result count before extracting. A bounded `site:linkedin.com/posts` query may substitute for the corresponding content slot only as secondary coverage; label it lower-confidence/freshness-sensitive. Require poster name/headline/company, freshness, post URL, role/team/family, application URL, poster influence, actionable-vs-market-signal classification, and canonical job linkage when identifiable. Old/generic/commentary posts are market signals, not outreach leads. Dedupe and persist only through canonical hiring_posts.csv. After persistence, rerun `{{PY}} scripts/people_sweep.py --dry-run --json --limit 8`; execute only its packet-linked people queries, because the four content-search slots were already consumed. This refresh lets a post discovered in the current feed/content pass drive current-run people research without exceeding eight searches.

PART B — job/post packet people research: execute the planner's relationship-filtered people searches in order (normally 1st degree, 2nd degree with named mutual, Georgia Tech alumni, then Fortinet overlap or role-specific manager/recruiter). After every native filter change verify active chips and result count before extracting. Inspect serious profiles and recent activity individually. Capture current company/title/location/team, job/post linkage, degree, named mutuals, GT/Fortinet overlap, technical alignment, hiring influence, recent hiring/referral activity, inspection timestamp, recommended ask, P0-P3, and evidence-based why-now. A generic employee with no role/post link, activity, shared context, or technical relevance is skipped; 3rd-degree is allowed only for an active matching poster, likely hiring manager/lead/founder, or exceptional shared context.

PART C — dedupe and persistence: use `PeopleDedupIndex`, `rank_candidate()`, `merge_extraction()`, and `append_rows()` from scripts/people_sweep.py against canonical contacts and prior sweeps. Never create a parallel contact store. A known identity may be recorded as `reevaluation_pending` only for a fresh relevant post, new matching job, or material activity/relationship change; this never authorizes duplicate outreach. Email pattern lookup remains dry-run-only and only for genuinely new contacts; never send and never mark guessed addresses usable.

METRICS: write one JSON object under the canonical execution-results root and call `{{PY}} scripts/people_sweep.py --record-results <json-path>`. Include packets selected, posts examined, fresh/actionable posts, people queries, profiles examined, new/live-job-linked contacts, active hiring posters, GT/Fortinet overlaps, degree distribution, duplicates, P0-P3 counts, and per-query/per-company yield. Set completed/browser_unavailable/planning_config_error honestly so status distinguishes dedupe-only, auth/browser failure, zero relevant results, validation failure, and successful completion.

DELIVERABLE: report selected packet(s), new actionable hiring posts, ranked P0-P3 people with role/job/post rationale, exact metrics/status, and email-pattern dry-run results. State explicitly that no outreach/application action was taken.
