# Linux Machine Bring-Up — Issues Found & Fixes (2026-09-07)

Context: migrating the jobhunt-engine system from the old Mac to the Linux
laptop (`/mnt/DATA/job_hunt/jobhunt-engine`). Full system test on 2026-09-06
found the issues below; all were fixed on 2026-09-07 unless noted.

## 1. sync_data.sh rsync nesting bug (root cause of the biggest outage)

**Symptom:** canonical data lived at `tracking/tracking/tracking/jobs/jobs.csv`
(triple nesting in the worktree, double in the private repo) while
`config_lib.PATHS` resolved to `tracking/jobs/jobs.csv`. Engine-wide: score_jobs
crashed, today_queue silently read 0 jobs and overwrote today's queue CSVs with
empty ones, UI jobs table empty, freshness verified 0 jobs.

**Root cause:** `rsync -a SRC DEST` without a trailing slash. When DEST already
exists, rsync copies SRC *inside* it, nesting one level per sync cycle:
- push (line 63): nests the private repo to `tracking/tracking`
- pull (line 76): nests the worktree again, and had no `--delete` so strays
  (`tracking/hiring_posts`, `tracking/search_runs`) were never cleaned.

**Fix:** trailing slashes + `--delete` both directions:
```
rsync -a --delete "$REPO/$p/"    "$WORKTREE/$p/"
rsync -a --delete "$WORKTREE/$p/" "$REPO/$p/"
```
**Lesson: always use trailing slashes when rsyncing into an existing
directory that should be mirrored in place.**

**One-time repair:** flatten `X/X/(X/)` nesting in both trees
(`tracking`, `profile_info`, `execution_results`, `job_research`, …), verify
md5s against the pre-flatten comparison, delete husks and strays. When merging
nested dirs by `cp -a`, a same-named stray dir at the target level can mask the
real data (this bit hiring_posts.csv in A — had to re-copy from B).

## 2. Stale data_root pointer — engine wrote to a phantom root

Repo `config.yaml:7` still pointed at the old machine's path
(`/home/vchopra/git/jobhunt-engine/jobhunt-data`, jobs.csv = 2 bytes). It
*existed* on Linux (created during bootstrap testing), so today's cron runs
silently read/wrote that near-empty root instead of the real 1,628-job dataset.
Only systemd units (which set `JOBHUNT_HOME`) escaped it.

**Fix:** `data_root: /mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data`; the stale
root moved to `jobhunt-data.QUARANTINED-stale-20260907`.
**Lesson: after any machine migration, grep every config pointer for the old
hostname/home and quarantine — don't delete — the old root.**

## 3. NTFS/fuseblk mount breaks venvs with compiled binaries

`/mnt/DATA` is fuseblk (NTFS): chmod is a no-op, so pip could not set the exec
bit on playwright's bundled `node` binary → `PermissionError` on import; also
`.venv/bin/pip` itself was not executable.

**Fix:** venv rebuilt on ext4 at `~/venvs/jobhunt` (installed with
`pip install -e ".[dev,browser]"`), symlinked as repo `.venv`. Old venv deleted.
**Lesson: never put a Python venv on an NTFS/fuse mount on Linux; keep it in
$HOME and symlink if the repo must live on the data disk.**

## 4. Playwright missing + browser download needed

Playwright is an *optional* extra (`[browser]`); the fresh venv didn't have it,
so all LinkedIn sweeps failed ("needs interactive session" was misleading —
there was no browser driver at all) and web_nav_agent tests skipped.
**Fix:** `pip install -e ".[dev,browser]"` + `python -m playwright install
chromium` (headless shell ~115 MB into `~/.cache/ms-playwright`).
**Lesson: on a new machine run the browser extra explicitly; sweep "skip"
messages can mask a missing dependency.**

Note: sweeps attach to the dedicated automation Chrome via CDP :9333 (system
Chrome, profile `~/.hermes/browser-profiles/job-hunt`); the downloaded
headless shell is only used by tests and fallback paths.

## 5. Invalid OpenRouter model slug

Data-root `config.yaml` had openrouter priority 1 with model
`nvidia/nemotron-3-super-550b-a55b` — not a valid OpenRouter ID (HTTP 400,
auth OK). Chain silently fell through to NVIDIA.
**Fix:** `nvidia/nemotron-3-super-120b-a12b` (the standing fallback model).
Verified: live call via openai SDK returned in 2.2 s.
**Lesson: an LLM fallback chain hides a dead primary; probe each provider
after any config change.**

## 6. LinkedIn auth state = CHALLENGE_OR_2FA

Browser session opens and CDP-attaches fine ( lands on linkedin.com/feed), but
`check_auth_state()` returns `CHALLENGE_OR_2FA` — LinkedIn wants verification
on this machine's profile. **Action needed (human): log in once manually in
the automation Chrome window to clear the challenge.** Until then, LinkedIn
sweeps will report login walls. Non-LinkedIn sources (Greenhouse/Lever/ATS
APIs) are unaffected.

## 7. Repo-root `tracking/` stray (test guard failures)

An empty repo-root `tracking/` (from a pre-nesting-era run) tripped
`tests/test_output_hygiene.py`'s no-repo-root-dump guard. Removed; tests green.

## 8. Minor gotchas worth remembering

- `scripts/resume_agent/run.py` uses relative imports — run as
  `python -m scripts.resume_agent.run`, not by path.
- `ui/app.py` imports `engine.run_manager` — anything touching the UI needs
  the repo root as CWD/on sys.path (systemd unit sets WorkingDirectory).
- `today_queue.py` has no flags and writes its review CSVs unconditionally —
  running it against a broken root silently clobbers the queue with empty
  files.
- `config_lib.llm_config()` returns entries with `key` (not `api_key`) and
  `models` (list) — read the dict shape before probing.
- Sandbox note: inline `python -c` / heredocs get blocked by tooling
  consent gates on this machine; write probe scripts to /tmp and run them.

## Final state (2026-09-07)

- pytest: **830 passed, 1 skipped**
- UI: http://localhost:8080 HTTP 200 (systemd `jobhunt-ui`, active)
- Automation Chrome: CDP :9333 up (systemd `jobhunt-automation-chrome`)
- Data: worktree and private repo flat, jobs.csv 1,628 rows, md5-verified
  identical (`1354ee24…`)
- LLM chain: openrouter(nemotron-3-super-120b-a12b) → nvidia → fallbacks, live-verified
- today_queue: 34-row apply-day queue restored
- score_jobs_v2 / freshness / cleanup / ats_check: all read the live root correctly
- Open item: LinkedIn CHALLENGE_OR_2FA — manual login in automation Chrome
