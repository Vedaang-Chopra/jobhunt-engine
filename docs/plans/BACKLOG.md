# Backlog — Recovered Unfinished Items

Rows recovered from executed/partially-executed plans at archive time (2026-08-26).
Each row survives its source plan; nothing was silently dropped.

| ID | Source plan | Item | Blocking? | Notes |
|---|---|---|---|---|
| B1 | master-pipeline T11 | Poster fast-path: sending connection requests via Playwright MCP end-to-end | no | Connection queue + notes exist (connection_queue.py); automated send untested against live LinkedIn. |
| B2 | master-pipeline T14 | Full end-to-end validation pass of discovery→people→outreach chain with real data snapshot | yes (before trusting nightly outputs) | Component tests green; E2E rehearsal not recorded. |
| B3 | apply-loop & autonomy | Autonomy layer: unattended small-batch apply runs (>N/day cap, stop-on-anomaly) | no | apply_pipeline.py + form_filler.py exist single-shot; loop/safety-cap wrapper absent. |
| B4 | apply-loop & autonomy | Cover-letter generation wired into apply pipeline UI trigger | no | generate_cover_letter.py exists standalone; not registered in ui/triggers.py pipeline. |
| B5 | referral-engine | Email-pattern outreach lane verification against real found patterns | no | email_pattern_finder.py shipped; accuracy eval on live domains pending. |
| B6 | migration v2 §OpenQ | Merge the three overlapping 08:00 Hermes crons into one orchestrator job | no | Decided during cron rewrite (W2c). |
| B7 | migration v2 §OpenQ | OS-level systemd user units for server laptop | no | Document-only until server actually flips from Hermes crons. |
| B8 | master-pipeline T10 | Automated connection-note personalization beyond first-touch templates | no | Templates exist in messaging/; per-contact research layer pending. |

Add new items here with next free ID. When picked up, promote the item to a numbered
plan (`docs/plans/NNN_*.md`) and mark this row PROMOTED→plan-id.
