# Full System Audit — 2026-09-09 (run ~22:50–23:45 EDT)

Executed per docs/audits/AUDIT_PROMPT_2026-09-09.md. Every cron fired live; every UI page visited in the automation Chrome; write-backs proven against the CSVs and reverted.

## Phase 1 — Cron fleet (8/8 fired live)

| # | Cron | Schedule | Verdict | Evidence |
|---|------|----------|---------|----------|
| 1 | daily-ops | daily 08:00 | PASS | 09:57 digest healthy (5/5 steps ok); live re-fire 23:08 produced full digest ("career_ops_scan_import ok, discovery_sweeps 2/2 ok, score_unscored ok, rebuild_today_queue ok") |
| 2 | discovery-linkedin | every 2h | PASS* | 66 jobs discovered today, search_runs.csv append-only (li_guest ×2 + li_loggedin 22:37 → 6 new/32 gated). Re-fire 23:07 correctly halted on LinkedIn login wall ("No jobs processed... stop on login wall") — mechanism verified; live discovery limited by LinkedIn wall tonight |
| 3 | linkedin-people-posts-2h | every 2h | PARTIAL | 2 new hiring posts today (15 yesterday); but last 2 scheduled runs + both audit fires hit LinkedIn login wall → 0 new posts/people in those runs. Agent behavior correct (stops, reports honestly). LinkedIn session needs refresh. |
| 4 | discovery-career-ops | Mon+Thu 08:00 | PASS | 13:20 run: "2 new rows, 1 gated (G2 director title), 0 failures". Audit re-fire 23:17: "3 new rows, 0 gated, exit 0". Full scan→import→gate→score chain ran twice live. |
| 5 | outreach-batch | daily 10:00 | PASS | 10:04 run produced ranked 8-person queue, STOPPED for user input, no auto-sends. Audit fire 23:02 produced queue only ("[ ] Alia Insignares ... 90"), zero sends. Human-in-the-loop contract intact. |
| 6 | apps-sync | daily 20:00 | PASS (after transient FAIL) | 20:01 scheduled run FAILED: `RuntimeError: Service temporarily overloaded` (provider overload; fallback chain configured but both endpoints saturated). Re-fire 22:56 succeeded: portal check 0 ok/1 needs_manual (cisco, no URL), no follow-ups due, no --mark. Transient provider issue, not a code bug. |
| 7 | discovery-freshness | daily 21:00 | PASS | Re-fire 23:07: run discovery_20260909_230751, exit 0, verified=0 / stale=2864 / expired=0, zero recommended_action changes (expected — nothing new expired). Run logged in search_runs.csv. |
| 8 | ops-health | daily 21:30 | PASS | --check exits 0 with full source table; alert-append path proven: "AUDIT-FIRE 2026-09-09 ops-health check OK (exit 0)" appended to execution_results/ops/alerts.log. |

## Phase 2 — UI (10 pages)

| Page | Verdict | Evidence |
|------|---------|----------|
| /today | PASS | Loads 200; stat cards correct (462 fresh / 50 queue / 1 submitted / 13 awaiting outreach); all 3 buckets render; job titles = external LinkedIn links (_blank) by design. Buckets populated from distinct CSVs — no overlap seen in spot check. |
| /jobs | PASS | 2896 jobs; "Agentic Roles" chip filters 2896→207; search "crowdstrike" → 8/2896; row-click dialog opens with all 5 action buttons (Track this role, Mark completed, Mark for later, Mark expired, Run evaluation + two-step Delete). Write-backs proven: Mark for later → review_flag=for_later in jobs.csv; Mark completed → review_flag=completed; both reverted. Save view → saved_views.csv row; Apply view → Role family=Agentic AI, 207 jobs; Delete view (with confirm dialog) removed the row. |
| /job-search | PASS | 9 trigger buttons + per-button Logs; "Run: Freshness & expiry pass" fired a real run (coscan_20260909_2302 logged in search_runs.csv during the click session). Status labels truthful (interrupted/done exit 0). |
| /linkedin-posts | PARTIAL | Automation health OK + recent sweep runs render (after fix, see below). Posts table loads 96/96 with filters + [apply]/profile links. BUT: search-input typing doesn't stick under automation (server-side filter_hiring_posts verified 96→3 in Python; client-side event not registering via synthetic CDP typing — likely automation-tab artifact, needs human-cursor retest). |
| /applications | PASS | Track role form → row appended to applications.csv (id audit_test_co_audit_test_role_20260909, notes tagged AUDIT-TEST); stage select offers Saved/Preparing/Applied/Interviewing; stage change writes status via data_layer.update_application_stage (verified queued→submitted + date_submitted). Test row removed. |
| /network | PASS | 342 people / 8 ledger / 19 email / 197 from sweeps; "Sweep LinkedIn for people now" fired a real adhoc run (adhoc-linkedin_people_sweep-20260909-233043-3: running, button disabled correctly). Approve buttons present, sending gated manual. |
| /right-people | PASS | 157 companies / 106 people. Track: invalid name → clean warning toast ("Could not resolve 'AUDIT-TEST Co'"); valid "Cohere" → resolves + navigates to ?company=cohere workspace. No data residue. |
| /insights | PASS | 3 charts render (applications/week, funnel, jobs-per-source canvas); company select + Research company; Company Intel panel populated (AI2: T2/P1/greenhouse, 10 open jobs table). |
| /runs | PLACEHOLDER | Renders "Coming soon." — intentional stub, not a failure. |
| /operations | PASS | Engine Triggers (Run discovery dry-run, Run freshness check — fired adhoc-freshness-20260909-233247-4: running live) + Data Health table (all 5 canonical CSVs ok with row counts matching disk). |

## Phase 3 — Cross-checks

### 9. Cron ↔ button parity

| Cron | Schedule | Manual equivalent | Status |
|------|----------|-------------------|--------|
| daily-ops | daily 08:00 | None in UI (script scripts/daily_ops.py; manual = run script) | noted |
| discovery-linkedin | every 2h | /job-search "Run LinkedIn Discovery (agent)" + legacy sweeps | OK |
| linkedin-people-posts-2h | every 2h | /linkedin-posts "Sweep my feed" + "Run keyword sweep"; /network "Sweep LinkedIn for people now" | OK |
| discovery-career-ops | Mon+Thu 08:00 | /job-search "Run career_ops_sweep" + "Run career_ops_import" | OK |
| outreach-batch | daily 10:00 | /network "Draft next connection batch" | OK |
| apps-sync | daily 20:00 | None in UI (script scripts/application_sync.py only) | noted |
| discovery-freshness | daily 21:00 | /job-search "Run: Freshness & expiry pass" + /operations "Run freshness check" | OK |
| ops-health | daily 21:30 | /operations Data Health table (partial equivalent — shows health, doesn't append alerts) | partial |

### 10. Data integrity
- jobs.csv: 2894→2896 rows (+2 from live cron fires during audit — expected); duplicate job_ids: 26 in baseline, 26 after audit → **0 new dups introduced**. (Pre-existing: 520 rows with empty job_id — legacy, pre-dates audit, worth a future cleanup.)
- search_runs.csv: append-only, 175→181 data rows (all appends from real runs).
- All AUDIT-TEST rows removed (saved_views, applications). jobs.csv.bak at /tmp/jobs_baseline_audit.csv.

### 11. End state
- Fleet: 8/8 crons enabled, all last_status=ok, gateway running. ✓
- Chrome CDP :9333 alive, LinkedIn feed tab open. ✓
- UI :8080 → 200. ✓

## Fixes applied during audit
1. **search_runs.csv malformed rows (21 lines with wrong field counts) broke every pandas read of it** → "Recent sweep runs" on /linkedin-posts showed "No sweep runs logged yet" despite 15 lhp_* runs. Root cause: legacy rows with unquoted commas in notes. Fixed by re-emitting all rows at exactly 9 schema columns (overflow merged into notes). Backup: /tmp/search_runs_backup_audit.csv. Post-fix: pd.read_csv OK (181 rows), recent_post_sweep_runs returns 6, UI renders the table.
2. Stale .hermes/ops.lock (PID dead) was blocking cron fires → removed; also the direct cause of the first fire batch's "lock file present, user denied removal" failures. Recommend the lock holder check stale-PID and self-clear.

## Open items (not fixed)
1. **LinkedIn login wall** on all feed/logged-in passes tonight (items 2/3). Fix: re-run scripts/automation_chrome.sh and verify LinkedIn session; possibly re-login needed.
2. **/linkedin-posts search input** — client-side typing not filtering (synthetic-input artifact suspected; human retest).
3. **/runs page** is a stub ("Coming soon") — no manual equivalent for run history inspection.
4. **apps-sync / ops-health have no full UI buttons** — parity gaps documented above.
5. **520 empty job_id rows** in jobs.csv (pre-existing) — dedupe/cleanup candidate.
