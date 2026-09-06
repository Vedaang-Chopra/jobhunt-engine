# Linux Migration Runbook — Mac → Ubuntu/Debian Laptop

Cutover plan for moving the job-hunt system from this Mac to an Ubuntu/Debian
laptop where Hermes crons run in the background properly. Written 2026-09-06.
Supersedes the macOS-focused path in `CRON_MANIFEST.md → Server migration path`
and extends `HANDOFF.md`.

## 0. What moves, what does not

| What | How | Notes |
|---|---|---|
| Repo (code, engine, ui, scripts, docs) | `git clone` | fresh `.venv` via `setup/bootstrap.sh` — never copy `.venv` |
| `jobhunt-data/` personal data (tracking, execution_results, job_research, profile_info, applications, messaging, resume_custom, browser_runs, `config.yaml` with keys) | migration bundle | gitignored — **must** come from the bundle |
| Hermes `job-hunt` profile (config.yaml, `.env`, skills, SOUL.md, memories, cron/jobs.json) | migration bundle | includes the 9 cron jobs |
| Global Hermes config (`~/.hermes/config.yaml`, `~/.hermes/.env`) | migration bundle | providers, gateway keys |
| 9 Hermes cron jobs | inside profile `cron/jobs.json` | run `setup/migrate_cron_paths.py` on the target — all prompts carry Mac absolute paths |
| Chrome automation profile (LinkedIn logins, 2GB) | **not migrated** (decision: start fresh) | re-login once on Linux; profile recreates itself at `~/.hermes/browser-profiles/job-hunt` |
| `.venv` (333MB) | not migrated | rebuilt by bootstrap |
| `state.db` (224MB session history) | not migrated | old-machine history stays readable on the Mac |
| LaunchAgents (`com.jobhunt.*`) | not migrated | replaced by systemd units in `setup/systemd/` |

**Iron rule (from CRON_MANIFEST.md):** never let both machines' sweeps write to
the same tracking CSVs. Pause jobs on the Mac **before** the first fire on
Linux.

## 1. On the Mac — stage the migration bundle

```bash
cd <repo>   # your local checkout of application_hunting
mkdir -p /tmp/jh_bundle/profile
# Personal job-hunt data (everything gitignored that matters)
tar --exclude='jobhunt-data/runs' -cf - jobhunt-data > /tmp/jh_bundle/jobhunt-data.tar
# Hermes job-hunt profile essentials (skip state.db / sessions / logs / caches)
P=~/.hermes/profiles/job-hunt
tar -C "$P" -cf /tmp/jh_bundle/profile/profile.tar \
    config.yaml .env SOUL.md profile.yaml skills memories cron
# Global Hermes config + env (provider keys, gateway settings)
mkdir -p /tmp/jh_bundle/hermes-global
cp ~/.hermes/config.yaml ~/.hermes/.env /tmp/jh_bundle/hermes-global/
# Pack
tar -C /tmp/jh_bundle -cf - . | zstd -19 -o ~/jobhunt_migration_bundle.tar.zst \
  || tar -C /tmp/jh_bundle -czf ~/jobhunt_migration_bundle.tar.gz .
```

Copy `~/jobhunt_migration_bundle.tar.zst` (or `.tar.gz`) to the Linux laptop
(USB drive, `scp`, whatever is convenient).

## 2. On the Linux laptop — install Hermes

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

Then restore the global config and keys **before** first launch:

```bash
mkdir -p ~/.hermes
tar -xf ~/jobhunt_migration_bundle.tar.zst -C /tmp/jh_bundle
cp /tmp/jh_bundle/hermes-global/config.yaml ~/.hermes/config.yaml
cp /tmp/jh_bundle/hermes-global/.env      ~/.hermes/.env
chmod 600 ~/.hermes/.env
hermes doctor    # must come back healthy before continuing
```

## 3. On the Linux laptop — repo + data

```bash
sudo apt update && sudo apt install -y git python3-venv python3-pip
mkdir -p ~/git && cd ~/git
git clone git@github.com:Vedaang-Chopra/application_hunting.git
cd application_hunting

# Data root is repo-local (matches the Mac layout)
mkdir -p jobhunt-data

# Personal data from the bundle (overwrites the empty dir contents)
tar -xf /tmp/jh_bundle/jobhunt-data.tar -C .

# Hermes job-hunt profile
mkdir -p ~/.hermes/profiles/job-hunt
tar -xf /tmp/jh_bundle/profile/profile.tar -C ~/.hermes/profiles/job-hunt
chmod 600 ~/.hermes/profiles/job-hunt/.env
```

## 4. Bootstrap the repo

```bash
cd ~/git/application_hunting
./setup/bootstrap.sh     # creates .venv, installs -e .[dev], runs pytest
```

`bootstrap.sh` will not overwrite the existing `jobhunt-data/config.yaml`.

## 5. Rewrite the cron jobs for the new paths

```bash
cd ~/git/application_hunting
python3 setup/migrate_cron_paths.py \
  --jobs-file ~/.hermes/profiles/job-hunt/cron/jobs.json \
  --to-repo "$HOME/git/application_hunting"
# Review the dry-run diff, then:
python3 setup/migrate_cron_paths.py \
  --jobs-file ~/.hermes/profiles/job-hunt/cron/jobs.json \
  --to-repo "$HOME/git/application_hunting" --apply
```

Expected: 9 jobs total, 8 rewritten (repo-path + venv-python), 0 residual
`/Users/` references. `morning-job-digest` needs no rewrite.

Then set the data-root env var (bash):

```bash
echo 'export JOBHUNT_HOME="$HOME/git/application_hunting/jobhunt-data"' >> ~/.bashrc
source ~/.bashrc
```

## 6. Chrome + systemd (replaces macOS LaunchAgents)

```bash
# google-chrome-stable
wget -qO /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y /tmp/chrome.deb

mkdir -p ~/.config/systemd/user
cp setup/systemd/jobhunt-automation-chrome.service \
   setup/systemd/jobhunt-ui.service ~/.config/systemd/user/
# If the repo is NOT at ~/git/application_hunting, edit the %h paths in both files.
systemctl --user daemon-reload
systemctl --user enable --now jobhunt-automation-chrome.service
systemctl --user enable --now jobhunt-ui.service
sudo loginctl enable-linger $USER   # keep Chrome/UI alive when logged out
```

First run: `scripts/automation_chrome.sh` creates
`~/.hermes/browser-profiles/job-hunt` and opens a Chrome window — **log into
LinkedIn in that window once**, then all sweeps attach over CDP :9333.

## 7. Cutover sequence (order matters)

1. **Final data delta**: re-stage the bundle on the Mac (§1) on cutover day and
   re-unpack §3 on Linux, so tracking CSVs are current.
2. **Pause all 9 Hermes jobs on the Mac:**
   ```bash
   for id in 64846a31d368 5a4de2a4d1b5 d107677b66fd 05ac53fa1759 \
             2f780113e181 e9597fb81bea 344702a9a9cd 9a38cd651409 761c4d1c8a2f; do
     hermes cron pause "$id"
   done
   ```
3. **Verify jobs on Linux:** `hermes cron list` → all 9 jobs, correct schedules,
   models (`nvidia/nemotron-3-super-120b-a12b`), delivery targets.
4. **Fire a cheap job on Linux:** `hermes cron run 344702a9a9cd` (ops-health),
   then check `~/.hermes/profiles/job-hunt/cron/output/344702a9a9cd/` for a
   clean run. Repeat with `discovery-freshness` (`5a4de2a4d1b5`).
5. The Mac now holds no live jobs — keep it as cold standby. Jobs were paused,
   never removed; resuming them restores the old machine.
6. Jobs with `deliver: origin` (daily-ops, morning-job-digest, outreach-batch,
   linkedin-people-posts-2h) deliver to the signed-in desktop/gateway session —
   sign into the same Hermes account on the Linux laptop's desktop app.

## 8. Verification checklist (Linux, after cutover)

- [ ] `.venv/bin/python -m pytest tests/ -q` green
- [ ] `scripts/config_lib.py` resolves data_root to the repo-local `jobhunt-data`
- [ ] `hermes doctor` healthy; `hermes cron status` shows the scheduler running
- [ ] `hermes cron list` → 9 jobs, all enabled, correct schedules/models
- [ ] `jobs.json` has zero `/Users/` references:
      `grep -c '/Users/' ~/.hermes/profiles/job-hunt/cron/jobs.json` → 0
- [ ] Chrome CDP answers: `curl -s http://127.0.0.1:9333/json/version`
- [ ] LinkedIn logged in inside the automation Chrome window
- [ ] `ops-health` cron run completes with status ok
- [ ] `~/.bashrc` has `export JOBHUNT_HOME=$HOME/git/application_hunting/jobhunt-data`
- [ ] `systemctl --user status jobhunt-ui` active; dashboard reachable

## 9. Rollback

On Linux: `for id in <ids>; do hermes cron pause "$id"; done`. On the Mac:
`hermes cron resume <id>` for each. The Mac never loses anything — jobs are
only ever paused, never removed, and its data was never touched.

## 10. Provider keys

NVIDIA Build + OpenRouter keys live in two places; both must exist on Linux:
- `~/.hermes/.env` + `~/.hermes/config.yaml` (Hermes provider chain)
- `jobhunt-data/config.yaml` (repo engine config)

`hermes doctor` confirms the chain. Model policy from `CRON_MANIFEST.md` is
preserved by the profile copy: every job is explicitly pinned, so no
`[drift_skip]` errors — if one appears, re-pin with
`hermes cron edit <id> --provider nvidia --model nvidia/nemotron-3-super-120b-a12b`.
