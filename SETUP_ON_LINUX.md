# SETUP_ON_LINUX.md — Agent-Driven Setup for a New Linux Laptop

This document is the canonical setup procedure. It is written so that a
Hermes agent on the target machine can execute the entire setup with no
human guidance beyond SSH keys and one LinkedIn login.

**Companion doc:** `AGENTS_SETUP_PROMPT.md` — the exact prompt to paste into
a new Hermes session on the target machine.

## Architecture (read first)

| Repo | Visibility | Contents |
|---|---|---|
| `jobhunt-engine` (this repo) | **public** | engine code, scripts, ui, tests, docs. NO personal data — enforced by `tests/test_output_hygiene.py` |
| `jobhunt-data-private` | **private** | job registry (tracking/), profile_info, resumes (all_custom_resumes, export_packages), application answers, engine config.yaml with API keys |
| `~/.hermes/profiles/job-hunt/` | local | Hermes profile: 9 cron jobs, skills, memories, keys — copied from the old machine, not in git |

**Rule:** the engine repo must never contain personal data. If a test fails
in `tests/test_output_hygiene.py`, something dumped to the repo root — fix
the writer to use `config_lib.path(...)`, never move data back.

## Phase 1 — Machine prerequisites (agent may run, needs sudo)

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl jq rsync
# Chrome (automation browser for LinkedIn sweeps):
wget -qO /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y /tmp/chrome.deb
```

Hermes itself:
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

SSH key for GitHub (both repos are git@ URLs):
```bash
ssh-keygen -t ed25519 -C "$USER@$HOSTNAME" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub   # user adds this at github.com/settings/keys
ssh -T git@github.com       # verify: "Hi <user>!"
```

## Phase 2 — Clone + data + venv

```bash
mkdir -p ~/git && cd ~/git
git clone git@github.com:Vedaang-Chopra/jobhunt-engine.git
cd jobhunt-engine

# Private data: either clone alongside and rsync, or (simplest) clone into a
# worktree and copy the personal paths across:
git clone git@github.com:Vedaang-Chopra/jobhunt-data-private.git ~/git/jobhunt-data-private
./scripts/sync_data.sh pull     # uses ~/.config/jobhunt/data_repo remote;
                                # or set DATA_REPO_REMOTE env var instead

# Bootstrap: venv, deps, full test suite as the gate
./setup/bootstrap.sh
```

Expected: pytest ends `passed` (7 skips are personal-data-dependent tests).
`config_lib.data_root()` resolves to `<repo>/jobhunt-data` by default.

## Phase 3 — Hermes profile (copy from old machine)

On the OLD machine run:
```bash
tar -C ~/.hermes/profiles/job-hunt -cf - config.yaml .env SOUL.md profile.yaml skills memories cron \
  | ssh <newmachine> 'mkdir -p ~/.hermes/profiles/job-hunt && tar -xf - -C ~/.hermes/profiles/job-hunt'
```
(Or restore from `profile.tar` in the migration bundle if using the offline
path.) Then on the NEW machine:

```bash
chmod 600 ~/.hermes/profiles/job-hunt/.env
# Rewrite all cron prompt paths for this machine:
python3 setup/migrate_cron_paths.py \
  --jobs-file ~/.hermes/profiles/job-hunt/cron/jobs.json \
  --to-repo "$HOME/git/jobhunt-engine" --apply
# Expected output: "9 jobs total | rewritten: 8" and zero /Users/ residuals.

# Verify identity block exists in the private data config:
grep -A2 '^identity:' jobhunt-data/config.yaml
```

## Phase 4 — Background services (systemd user units)

```bash
mkdir -p ~/.config/systemd/user
for u in jobhunt-automation-chrome jobhunt-ui; do
  cp setup/systemd/$u.service ~/.config/systemd/user/$u.service
done
systemctl --user daemon-reload
systemctl --user enable --now jobhunt-automation-chrome.service jobhunt-ui.service
sudo loginctl enable-linger "$USER"    # survive logout — crons keep running
```

Shell env:
```bash
echo 'export JOBHUNT_HOME="$HOME/git/jobhunt-engine/jobhunt-data"' >> ~/.bashrc
```

## Phase 5 — LinkedIn login (HUMAN STEP, once)

Open the automation Chrome window (it starts via the systemd unit, profile
`~/.hermes/browser-profiles/job-hunt`) and log into LinkedIn manually once.
All sweeps attach over CDP `127.0.0.1:9333` and reuse that session.

Verify:
```bash
curl -s http://127.0.0.1:9333/json/version | head -3
```

## Phase 6 — Verification gate (agent runs; all must PASS)

```bash
cd ~/git/jobhunt-engine
.venv/bin/python -m pytest tests/ -q                                   # suite green
.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import config_lib; print(config_lib.data_root())"  # <repo>/jobhunt-data
grep -c '/Users/' ~/.hermes/profiles/job-hunt/cron/jobs.json           # 0
hermes doctor                                                          # healthy
hermes cron list                                                       # 9 jobs
curl -s http://127.0.0.1:9333/json/version                             # CDP answers
systemctl --user status jobhunt-ui                                     # active
```

## Phase 7 — Cron cutover (AFTER everything above passes)

On the OLD machine (pause, never delete — resume is the rollback):
```bash
for id in 64846a31d368 5a4de2a4d1b5 d107677b66fd 05ac53fa1759 2f780113e181 e9597fb81bea 344702a9a9cd 9a38cd651409 761c4d1c8a2f; do
  hermes cron pause "$id"
done
```

On the NEW machine (fire the cheapest first):
```bash
hermes cron run 344702a9a9cd     # ops-health — check output dir for status ok
hermes cron run 5a4de2a4d1b5     # discovery-freshness
hermes cron run 05ac53fa1759     # discovery-linkedin (needs LinkedIn login)
```
Output lands in `~/.hermes/profiles/job-hunt/cron/output/<job_id>/`.

**Iron rule:** never let both machines' crons run against the same data
simultaneously — old machine paused before new machine fires.

## Day-to-day on two machines

- Code changes: commit on either machine, `git push` (engine repo), pull elsewhere.
- Data changes (crons write tracking CSVs daily): run `./scripts/sync_data.sh push`
  when leaving a machine, `pull` when arriving on the other. One machine is
  authoritative per time window — never both writing between syncs.
- Registry cleanup runs weekly on the active machine (cron `registry-cleanup`
  if installed — see CRON_MANIFEST.md).
