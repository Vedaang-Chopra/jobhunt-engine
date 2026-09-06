# Browser Automation Architecture — Canonical BrowserSessionManager + Web Navigation Agent

**Date:** 2026-08-26
**Status:** Implemented and validated

## Root cause

Before this change, browser infrastructure was fragmented:

1. `scripts/cron_cdp_driver.py` opened its own raw websocket CDP connection to
   :9333, bypassing all session logic.
2. Ten+ one-off `_cron_*.py` scripts each hand-rolled their own Playwright or
   CDP access with ad-hoc login-wall checks.
3. `browser_session_lib` (added 2026-08-25) fixed most of this but had gaps:
   it did not auto-start the shared Chrome, had no cross-process launch lock,
   no auth-state API, no observability, and a SingletonLock pre-check that
   missed dangling symlink locks.

The result: competing Chrome processes against the same user-data dir,
authwall failures on runs that should have reused the logged-in browser, and
no way to tell cron callers "auth expired, human needed."

## Previous behavior

- Cron jobs could spawn independent browsers; UI triggers used the MCP path;
  manual sweeps used `open_logged_in_session()` — three parallel paths that
  only sometimes converged on the same Chrome.
- No process ever started the automation Chrome itself; if the LaunchAgent
  hadn't run yet, jobs failed.
- Auth detection was scattered `"/login" in url` checks in domain scripts.

## New browser lifecycle

```
request browser (any source: cron / UI / manual / agent)
        |
        v
CDP endpoint answering on :9333? --YES--> connect_over_cdp attach
        |                                       -> reuse/create tab
        NO
        v
ensure_automation_chrome()  [chrome-launch.lock held]
  -> bash scripts/automation_chrome.sh (idempotent)
  -> poll /json/version until ready
        |
        v
attach over CDP to the ONE persistent-profile Chrome
```

Fallback (only when the LaunchAgent cannot bring Chrome up): direct
`launch_persistent_context` on the same profile, guarded by a cross-process
`ProfileLock`. The SingletonLock check now uses `os.path.exists`, which sees
dangling symlinks (the old `isfile` missed them).

## Persistent profile

- Path: `~/.hermes/browser-profiles/job-hunt` (outside any tmp/cache dir).
- Launched by `scripts/automation_chrome.sh` via LaunchAgent
  `com.jobhunt.automation-chrome`; survives Hermes/process restarts.
- Never `--isolated`, never per-run dirs, never the user's normal Chrome
  profile.
- The Playwright MCP server attaches via `--cdp-endpoint=http://127.0.0.1:9333`
  so agent-driven MCP browsing lands in the SAME browser as Python sweeps.

## Authentication lifecycle

`BrowserSession.check_auth_state(site)` classifies semantically from URL +
body text:

| State | Meaning |
|---|---|
| `AUTHENTICATED` | In-app URL pattern seen (feed/search/jobs/notifications) |
| `AUTH_REQUIRED` | Login/authwall URL or text |
| `CHALLENGE_OR_2FA` | checkpoint/challenge/verify markers |
| `UNKNOWN` | No decisive signal |

On `AUTH_REQUIRED`/`CHALLENGE_OR_2FA`: stop immediately (exit code 3 for CLI
runs), never retry or bypass, preserve the browser so the user can log in
manually in that same window; the next run reuses the repaired session.
Playwright storage_state remains available as a secondary backup; the
persistent profile is primary. Auth state is never logged with cookies/tokens.

## Web Navigation Agent design (`scripts/web_nav_agent/`)

Layers, strictly separated:

```
BrowserSessionManager (browser_session_lib)      deterministic
        ↓
web_nav_agent.actions (Playwright executor)       deterministic
web_nav_agent.observer (a11y snapshot + text)     deterministic
web_nav_agent.goal   (GoalContract validation)    deterministic
        ↓
web_nav_agent.agent  (decide loop)                LLM decides, code guards
        ↑
Domain task (linkedin_hiring_posts_agent.py etc.) goals + schemas only
```

Loop: GOAL → OBSERVE → LLM DECIDE → EXECUTE → VERIFY → CONTINUE/RECOVER/FINISH.
The LLM receives goal, URL/title, condensed accessibility outline, text head,
recent action history, extracted entities, and remaining budget; it returns a
JSON decision. Deterministic guardrails live in code: per-step auth check,
action/time budgets, allowed-domain enforcement, prohibited-action refusal,
3x-duplicate-click NO_PROGRESS breaker, double-LLM-failure ERROR stop.

Observation is accessibility-snapshot-first; screenshots/vision are not used
unless semantics are insufficient.

## Goal contracts

Every agent run declares: description, success_conditions, stop_conditions,
allowed_actions, prohibited_actions (default: apply/message/connect/post/
comment/settings), max_actions (40), max_seconds (600), allowed_domains.
See `scripts/linkedin_hiring_posts_agent.py` for the reference contract.

## Cron behavior

Cron prompts/wrappers must obtain browsers ONLY via
`open_logged_in_session(source='<job-name>')` or
`python -m web_nav_agent --goal-yaml ...`. Both reuse the running Chrome and
create tabs; neither spawns a competing process. AUTH_REQUIRED exits 3 and
surfaces a clear notification instead of looping.

## UI behavior

UI triggers subprocess the sweep scripts, which all import
`browser_session_lib` — same manager, same profile, same browser as cron.

## Concurrency rules

- `ProfileLock`: flock-based mutex with JSON ownership metadata
  (pid/host/acquired_at/cmd) and dead-pid stale recovery, under
  `<data_root>/browser_runs/`.
- `chrome-launch.lock` serializes Chrome startup across processes.
- OS ProcessSingleton remains the final backstop.
- Multiple tasks may share the one browser via separate tabs
  (`session.new_page()`).

## Observability

Every run appends JSONL events (session_open, tab_opened, auth_state,
agent actions) to `<data_root>/browser_runs/run_log.jsonl` with run_id,
source label, profile, browser_reused flag, and stop reasons. No secrets.

## Tests performed

| Test | Result |
|---|---|
| Unit suite `tests/test_web_nav_agent.py` (contract validation, observer on file:// page, scripted-decision loop, NO_PROGRESS breaker, AUTH stop, LLM-failure stop) | 10/10 pass |
| Reuse test: two concurrent sessions attach to one CDP browser, second opens its own tab, `browser_reused=true` both | PASS |
| Auth classifier: AUTHENTICATED detected on feed/search URLs; AUTH_REQUIRED unit-tested via monkeypatch | PASS |
| Persistence: profile at fixed path survives restarts; LaunchAgent restarts Chrome with same profile (verified across this session's Chrome bounce) | PASS |
| Agent adaptation: goal-driven loop navigates unseen pages by semantic outline (file:// pages in tests); no fixed selector sequences | PASS |
| Full repo suite regression | see commit |

## Remaining limitations

- Playwright↔Chrome CDP attach can intermittently fail with
  "Browser context management is not supported" after long Chrome uptimes
  (observed once); recovery = bounce the shared Chrome
  (`pkill -f 'user-data-dir=.*browser-profiles/job-hunt' && bash
  scripts/automation_chrome.sh`). A future hardening could detect this error
  signature and auto-bounce.
- Live LinkedIn end-to-end agent run not executed during this refactor
  (deliberately read-only-safe); first production cron run should be watched.
- Legacy `_cron_*` scripts moved to `scripts/legacy/` with a README; they are
  not deleted for history but must not be run.
