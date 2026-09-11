# Linux Migration + Job-Hunt System Hardening Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Move the entire job-hunt system to the Ubuntu laptop with a one-command installer, keep development working on both machines, fix the identified flaws (job scrutiny, message-draft wiring, registry cleanup, repo hygiene, private personal-data branch), and verify all 9 cron pipelines end-to-end post-migration.

**Architecture:** Two changes in parallel tracks. Track A (migration): a `setup/install_linux.sh` bootstrap that chains every existing piece (Hermes install → clone → bundle unpack → venv → cron-path rewrite → systemd → verification) so the new laptop is one script, not 20 manual steps; personal data moves via a gitignored private branch (`private/jobhunt-data`) pushed to the same GitHub repo, replacing the ad-hoc tar bundle for data sync while the repo clone stays clean. Track B (hardening): fix the four functional gaps found during the 2026-09-06 audit — (1) low-relevance jobs entering the registry, (2) people-sweeps finding contacts but no tailored message drafted, (3) registry never cleaned of dead jobs, (4) 78 loose scripts + stray root files obscuring the pipeline.

**Tech Stack:** Bash installer, Python 3 (repo venv), Hermes Agent profile cron (9 jobs, pinned `nvidia/nemotron-3-super-120b-a12b`), systemd user units, GitHub private branch for personal data, CSV tracking (no DB, per AGENTS.md).

**Baseline facts (verified 2026-09-06):**
- Registry: `jobhunt-data/tracking/jobs/jobs.csv` = 1601 rows. Scoring: `scripts/scoring_lib.py` / `score_jobs_v2.py`, eligibility gates G1–G6 via `scripts/discovery_lib.py:373 scrutinize()` (priority_v2 ≥ 68 or exceptional=True for India; UK/CA hard-reject).
- Message drafts: `scripts/connection_queue.py` has full ledger (draft/approve/record-sent/record-connected/replied) but is NOT wired into the people/poster sweeps or cron.
- Cleanup: `scripts/cleanup_expired.py` exists (append-only status transitions, dry-run default) but is NOT cron-wired.
- Crons: 9 jobs in `~/.hermes/profiles/job-hunt/cron/jobs.json`; 2 LinkedIn jobs had error streaks (now passing as of today's run: 84 new / 83 gated / 283 dupes); 8/9 prompts carry Mac absolute paths — `setup/migrate_cron_paths.py` (already committed, 3e218ff) rewrites them.
- Migration kit already committed: `setup/MIGRATION_LINUX.md`, `setup/migrate_cron_paths.py`, `setup/systemd/*.service`, cross-platform `scripts/automation_chrome.sh`.
- Repo hygiene: 78 files in `scripts/`, stray root files (`cron_report_2026-09-01.txt`, `tmp_process.py`, `check_new_posts.py`, `workspace/`), `scripts/ingest_guest_sweep.py.bak`, `scripts/legacy/`.

---

## Track A — Migration to Linux laptop

### Task A1: Create private data branch and push personal data

**Objective:** Personal data lives on a private branch of the same repo — no tar bundle needed, migrates with a `git fetch`, never visible on main checkout.

**Files:**
- Create: `.gitattributes-private` (marker only; no tracked change to main)

**Step 1: Verify personal paths are fully gitignored on the working tree** (nothing personal leaks into the code branch).

Run: `git status --short | grep -E "jobhunt-data|profile_info|tracking/" | head`
Expected: only `jobhunt-data/execution_results/reviews/` review CSVs (those are intentionally tracked) and `jobhunt-data/browser_runs/run_log.jsonl`. If anything else appears, extend `.gitignore` first.

**Step 2: Create orphan branch with personal data**

```bash
git checkout --orphan private/jobhunt-data
git rm -rf --cached . -q
git add jobhunt-data profile_info tracking job-hunt-docs 2>/dev/null || git add jobhunt-data
git commit -m "private: personal job-hunt data snapshot 2026-09-06"
git push origin private/jobhunt-data
git checkout feat/right-people
```

**Step 3: Add a `.gitignore` guard note** so future agents never merge this branch into code branches (one line in `.gitignore` comments).

**Step 4: Commit + push main-side change**

```bash
git add .gitignore && git commit -m "chore: document private/jobhunt-data branch policy" && git push
```

**Verification:** `git ls-remote origin | grep private` shows the branch; `git checkout feat/right-people && ls jobhunt-data` unchanged.

> **Note:** Repo is `git@github.com:Vedaang-Chopra/application_hunting.git` — a private repo under the user's account, so the branch is not visible to other git users. Confirm repo visibility is Private in GitHub settings before relying on this.

### Task A2: Write `setup/install_linux.sh` — one-command installer

**Objective:** On the Linux laptop, a single script performs: Hermes install check → repo clone (or use existing) → private-branch data checkout → bootstrap → cron-path rewrite → systemd units → verification report.

**Files:**
- Create: `setup/install_linux.sh`

**Step 1: Write the installer** (complete logic, ~150 lines):

```bash
#!/usr/bin/env bash
# setup/install_linux.sh — one-command install of the job-hunt system on Ubuntu/Debian.
# Idempotent: safe to re-run. Run as the login user; sudo only for apt.
set -euo pipefail

REPO_URL="git@github.com:Vedaang-Chopra/application_hunting.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/git/application_hunting}"
DATA_BRANCH="private/jobhunt-data"
BRANCH="${BRANCH:-feat/right-people}"   # default: current dev branch

log()  { echo -e "\033[1;34m==>\033[0m $*"; }
fail() { echo -e "\033[1;31mFAIL:\033[0m $*" >&2; exit 1; }

# --- 1. System deps ---------------------------------------------------------
log "Installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv python3-pip curl jq >/dev/null
command -v google-chrome-stable >/dev/null || {
  wget -qO /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo apt-get install -y -qq /tmp/chrome.deb >/dev/null
}

# --- 2. Hermes ---------------------------------------------------------------
command -v hermes >/dev/null || {
  log "Installing Hermes Agent"
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
}
export PATH="$HOME/.local/bin:$PATH"

# --- 3. Repo -----------------------------------------------------------------
if [ ! -d "$INSTALL_DIR/.git" ]; then
  log "Cloning repo to $INSTALL_DIR"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
git remote get-url origin >/dev/null || git remote add origin "$REPO_URL"
git fetch origin "$BRANCH" "$DATA_BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

# --- 4. Personal data from private branch ------------------------------------
log "Restoring personal data from $DATA_BRANCH"
git checkout "$DATA_BRANCH" -- jobhunt-data profile_info tracking 2>/dev/null || \
  git checkout "$DATA_BRANCH" -- jobhunt-data
git reset -q   # unstage; files remain on disk, branch pointer back to code branch

# --- 5. Python env ------------------------------------------------------------
log "Bootstrapping venv + running tests"
./setup/bootstrap.sh

# --- 6. Hermes profile --------------------------------------------------------
if [ ! -f "$HOME/.hermes/profiles/job-hunt/cron/jobs.json" ]; then
  fail "Hermes job-hunt profile missing. Copy profile essentials first (see setup/MIGRATION_LINUX.md §3) then re-run."
fi
log "Rewriting cron job paths for this machine"
python3 setup/migrate_cron_paths.py \
  --jobs-file "$HOME/.hermes/profiles/job-hunt/cron/jobs.json" \
  --to-repo "$INSTALL_DIR" --apply

# --- 7. Shell env -------------------------------------------------------------
grep -q "JOBHUNT_HOME" "$HOME/.bashrc" 2>/dev/null || \
  echo "export JOBHUNT_HOME=\"$INSTALL_DIR/jobhunt-data\"" >> "$HOME/.bashrc"
export JOBHUNT_HOME="$INSTALL_DIR/jobhunt-data"

# --- 8. systemd units ----------------------------------------------------------
log "Installing systemd user units"
mkdir -p "$HOME/.config/systemd/user"
sed "s|%h/git/application_hunting|$INSTALL_DIR|g" \
  setup/systemd/jobhunt-automation-chrome.service \
  setup/systemd/jobhunt-ui.service > /dev/null
for unit in jobhunt-automation-chrome jobhunt-ui; do
  sed "s|%h/git/application_hunting|$INSTALL_DIR|g" "setup/systemd/$unit.service" \
    > "$HOME/.config/systemd/user/$unit.service"
done
systemctl --user daemon-reload
systemctl --user enable --now jobhunt-automation-chrome.service 2>/dev/null || \
  log "WARN: chrome unit did not start (no GUI session yet?) — start manually after first login"
sudo loginctl enable-linger "$USER" 2>/dev/null || true

# --- 9. Verification -----------------------------------------------------------
log "Verification"
PASS=0; FAIL=0
check() { if eval "$2" >/dev/null 2>&1; then echo "  [PASS] $1"; PASS=$((PASS+1)); else echo "  [FAIL] $1"; FAIL=$((FAIL+1)); fi; }
check "venv python"            "[ -x '$INSTALL_DIR/.venv/bin/python' ]"
check "pytest suite"           "cd '$INSTALL_DIR' && .venv/bin/python -m pytest tests/ -q --timeout=300"
check "data_root resolves"     "cd '$INSTALL_DIR' && .venv/bin/python -c 'import sys; sys.path.insert(0,\"scripts\"); import config_lib; assert \"jobhunt-data\" in config_lib.data_root()'"
check "cron jobs present"      "python3 -c \"import json; d=json.load(open('$HOME/.hermes/profiles/job-hunt/cron/jobs.json')); assert len(d['jobs'])==9\""
check "no /Users/ in crons"    "! grep -q '/Users/' '$HOME/.hermes/profiles/job-hunt/cron/jobs.json'"
check "JOBHUNT_HOME in bashrc" "grep -q 'JOBHUNT_HOME' '$HOME/.bashrc'"
check "hermes doctor"          "hermes doctor"
check "chrome CDP :9333"       "curl -sf --max-time 3 http://127.0.0.1:9333/json/version"

echo
if [ "$FAIL" -eq 0 ]; then
  log "ALL CHECKS PASSED. Manual step remaining: log into LinkedIn in the automation Chrome window once."
else
  log "$FAIL check(s) failed — fix before cron cutover."
  exit 1
fi
```

**Step 2: Make executable, syntax-check, dry-run the check function locally**

Run: `chmod +x setup/install_linux.sh && bash -n setup/install_linux.sh`
Expected: no output (syntax OK).

**Step 3: Commit + push**

```bash
git add setup/install_linux.sh && git commit -m "feat(migration): one-command Linux installer with verification gate" && git push
```

### Task A3: Update MIGRATION_LINUX.md to reference installer + private branch

**Objective:** Runbook collapses to: run installer → copy profile essentials → re-login LinkedIn → cutover.

**Files:**
- Modify: `setup/MIGRATION_LINUX.md` (replace §1 bundle staging and §3 manual unpack with installer flow; keep cutover/rollback sections)

**Step 1:** Rewrite §1 and §3 to:
1. Mac: push `private/jobhunt-data` (Task A1) — this IS the data transfer.
2. Linux: `bash setup/install_linux.sh` (clones code branch, checks out personal data, bootstraps, rewrites crons, installs units, verifies).
3. Copy only the 4 profile files (`config.yaml .env SOUL.md profile.yaml`) + `skills/` + `memories/` + `cron/` from the Mac profile — keep the small tar command for just these.

**Step 2:** Commit: `git commit -am "docs(migration): installer-first flow, private-branch data transfer" && git push`

---

## Track B — System hardening

### Task B1: Job scrutiny — hard floor before registry entry

**Objective:** No job below a minimum relevance bar enters `jobs.csv`, regardless of source. Currently gates G1–G6 run, but 84 jobs entered from one sweep with 83 gated — the 1-in-N noise still accumulates (1601 rows).

**Files:**
- Modify: `scripts/discovery_lib.py` (`scrutinize()` at line 373)
- Modify: `scripts/ingest_lib.py` (pre-insert call site)
- Test: `tests/test_scrutinize_floor.py`

**Step 1: Write failing test**

```python
# tests/test_scrutinize_floor.py
from discovery_lib import scrutinize

def test_below_floor_rejected():
    row = {"title": "Sales Manager", "company": "Acme", "location": "US",
           "priority_v2": "40", "role_family": "sales", "source": "l1"}
    status, reasons = scrutinize(row)
    assert status == "rejected"
    assert any("floor" in r for r in reasons)

def test_above_floor_accepted():
    row = {"title": "Senior ML Engineer", "company": "Acme", "location": "Remote-US",
           "priority_v2": "75", "role_family": "ml_engineering", "source": "l1"}
    status, reasons = scrutinize(row)
    assert status == "accepted"

def test_exceptional_overrides_floor():
    row = {"title": "Research Engineer", "company": "DeepMind", "location": "London, UK",
           "priority_v2": "80", "exceptional": "True"}
    status, _ = scrutinize(row)
    assert status != "rejected"
```

**Step 2:** Run: `.venv/bin/python -m pytest tests/test_scrutinize_floor.py -v` → expect FAIL (no floor logic).

**Step 3: Implement** in `scrutinize()`: a `RELEVANCE_FLOOR = 55` constant (configurable via `jobhunt-data/job_research/config/scoring-config.yaml` key `relevance_floor`); any row with `priority_v2 < floor` and no `exceptional` mark → `rejected` with reason `"below relevance floor (<55)"`. UK/Canada hard-reject stays ahead of the floor check. Keep 68 as the India/priority threshold — the floor is a NEW lower bar for all geographies.

**Step 4:** Tests pass; then run the existing suite: `.venv/bin/python -m pytest tests/ -q` (must stay green).

**Step 5:** Backfill sweep over the existing registry: `.venv/bin/python scripts/categorize_roles.py --apply` is NOT this — instead add a one-shot `scripts/backfill_floor_check.py` that marks rows `status=below_floor` (new terminal status) where `priority_v2 < 55 AND status == open`. Dry-run first, show counts, then `--apply`. Report counts in the final message.

**Step 6:** Commit: `feat(scrutiny): relevance floor gate + registry backfill`.

### Task B2: Wire tailored message drafts into people/poster sweeps

**Objective:** Every person the sweeps surface (poster with hiring signal, referral candidate for a registry job) gets a drafted, tailored connection note in `connection_queue` automatically — human approves before anything is sent (per outreach human-in-the-loop policy).

**Files:**
- Modify: `scripts/people_sweep.py` and `scripts/poster_connect_sweep.py` (end of each result loop)
- Modify: `scripts/connection_queue.py` (expose `queue_draft()` as an importable function if it's CLI-only today)
- Test: `tests/test_auto_draft.py`

**Step 1: Write failing test** — a fake contact `{name, company, title, reason, job_id}` passed to `queue_draft()` lands in `tracking/contacts/connection_requests.csv` with status `pending` and a non-empty `note_draft` containing the company name and job title.

**Step 2:** Implement:
1. In `connection_queue.py`, extract the draft-generation body of `cmd_draft` into `def queue_draft(contact: dict, job_row: dict | None) -> str` (returns request_id). The CLI `draft` subcommand loops over this.
2. Template (mirrors `messaging/` rules — short, specific, no flattery):
```
Hi {first_name} — I'm applying for {job_title} at {company} (my background: {one_line_background}). If the role looks like a fit from your side, I'd appreciate a referral. Either way, happy to connect.
```
`one_line_background` comes from `profile_info/profile.md` summary field (read via `config_lib.data_root()`).
3. In both sweeps, after each contact passes the activity filter (active-poster rule from LINKEDIN_REFERRAL_RULES.md), call `queue_draft(contact, matching_job_row)`; sweep summary reports `drafted: N`.

**Step 3:** Tests pass + full suite green. **Step 4:** Commit: `feat(outreach): auto-draft tailored notes in people/poster sweeps`.

### Task B3: Registry cleanup cron

**Objective:** Dead jobs leave the active pipeline automatically.

**Files:**
- Modify: `scripts/cleanup_expired.py` — no change needed if CLI is solid (it is: dry-run default, `--apply`, JSON report)
- Modify: cron `jobs.json` via `hermes cron create` — NOT hand-edited; use the CLI with `--apply` semantics:
  - name: `registry-cleanup`, schedule `0 6 * * 0` (weekly, Sunday 6am — no collision with existing slots), deliver `local`, model pinned `nvidia/nemotron-3-super-120b-a12b`, toolsets `terminal,file`, prompt: cd to repo, run `cleanup_expired.py --apply`, then `freshness_check.py --live` for open ATS URLs, report counts.
- Test: `hermes cron run <new-id>` after create; check output dir.

**Verification:** `hermes cron list` shows 10 jobs; cleanup run output shows `totals_by_action` JSON; `jobs.csv` open-count drops.

**Commit:** runbook/cron-manifest update row: `docs(cron): registry-cleanup weekly job`.

### Task B4: Repo organization

**Objective:** Predictable layout; no random files.

**Files:**
- Move: `cron_report_2026-09-01.txt` → `archive/cron_reports/`; `tmp_process.py` → delete (inspect first); `check_new_posts.py` → `scripts/legacy/` if superseded by `linkedin_posts_sweep.py` (verify with `grep -rn check_new_posts` first); `scripts/ingest_guest_sweep.py.bak` → delete; `workspace/` → add to `.gitignore` (scratch dir).
- Create: `scripts/README.md` — one-line purpose per script, grouped by pipeline stage (discovery / ingest / scoring / people / outreach / ops / legacy). Generate the grouping from the docstrings; agents maintain it when adding scripts.

**Steps:** inspect each stray file → move/delete with `git mv`/`git rm` → write README table → full test suite → commit `chore(repo): organize scripts, archive stray files, scripts README`.

**Verification:** `ls` at repo root shows only canonical entries (per AGENTS.md structure); `git status` clean after push.

### Task B5: Portal coverage — verify, don't rebuild

**Objective:** Confirm all sources actually produce jobs; fix only what's broken. (Wellfound, Google, Indeed/Greenhouse/Lever boards, Career Ops.)

**Files:**
- Read-only audit first: `tracking/search_runs/source_health.csv` (streak-based self-pause already built into `discovery_run.py`).

**Steps:**
1. Run `scripts/discovery_run.py --sources career_ops,newgrad --dry-run`-equivalent / read last 7 days of `source_health.csv`.
2. For any source with streak ≥ 2 or last success > 3 days: diagnose (credential? selector drift? rate limit?), fix, note fix in the plan's follow-up.
3. Wellfound crawler: run `wellfound_daily_crawler` skill flow once; confirm rows land with `source=wellfound` and pass Task B1's floor.
4. Career Ops (NVIDIA/Scale/OpenAI careers pages): run `career_ops_sweep.py` once; confirm `source=career_ops` rows and that the shortlist file (`job_research/config/*.yaml`) includes nvidia, scale-ai, openai.

**Verification:** every configured source has a healthy row in `source_health.csv` within 24h of Linux cutover; report a per-source table (source → last success → rows added 7d).

### Task B6: Post-migration end-to-end verification (on Linux)

**Objective:** Prove the whole system works there, not just installs.

**Steps (in order, on the Linux laptop):**
1. `bash setup/install_linux.sh` → all 8 checks PASS.
2. LinkedIn login in automation Chrome; `curl http://127.0.0.1:9333/json/version` OK.
3. `hermes cron run` each in sequence, checking output dirs: `ops-health` → `discovery-freshness` → `discovery-linkedin` (first real sweep — verify gated count > 0, floor gate active) → `linkedin-people-posts-2h` (verify `drafted: N > 0` in summary — Task B2 proof) → `registry-cleanup` (manual trigger).
4. 48h soak: let the 2h LinkedIn jobs fire naturally twice; confirm no error streaks, no double-writes to CSVs (Mac paused).
5. Verify delivery: `deliver: origin` jobs arrive in the signed-in Hermes desktop on Linux.

---

## Risks / tradeoffs / open questions

1. **Private branch ≠ access control.** The branch is private only because the repo is private. If the repo ever goes public, personal data leaks. Mitigation: GitHub repo visibility check is step 0 of Task A1; alternative is a separate private repo (open question for user).
2. **Relevance floor value (55) is a judgment call.** Too high starves the pipeline (few new jobs), too low keeps noise. The backfill report (Task B1 Step 5) shows the effect before it matters; tune via scoring-config without code change.
3. **Auto-drafting volume.** People sweeps currently surface dozens of contacts/run; drafts accumulate in `pending` awaiting human approval. This is by design (human-in-the-loop), but the connection_queue "refuse while approved batch outstanding" interlock means approval cadence becomes the bottleneck — expected behavior, flag to user.
4. **Cron prompt drift.** The path rewriter covers repo path + venv python. If prompts gain new machine-specific paths later, re-run the rewriter — it fails loudly on residual `/Users/`.
5. **Cron `jobs.json` editing via `hermes cron create`** (Task B3) requires the user present for hooks/approvals on this Mac; the new registry-cleanup job must ALSO be created on the Linux side after profile migration (or created on Mac pre-copy — simplest: create before bundle/profile copy so it migrates in the file; path-rewrite covers it).
6. **Two-machine dev.** Rule needed: `feat/*` branches on Mac, `private/jobhunt-data` re-push from whichever machine has fresher data, never merge the private branch into code branches.

## Sequencing

A1 → A2 → A3 (migration ready) can run parallel to B4 (hygiene) → B1 → B2 → B3 → B5 (hardening), with B6 last (needs the Linux laptop in hand). Each task ends with a commit + full pytest run.
