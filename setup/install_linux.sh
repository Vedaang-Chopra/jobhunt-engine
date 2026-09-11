#!/usr/bin/env bash
# setup/install_linux.sh — one-command install of the job-hunt system on Ubuntu/Debian.
#
# Two-repo architecture:
#   Engine (public):  git@github.com:<you>/jobhunt-engine.git
#   Data   (private): git@github.com:<you>/jobhunt-data-private.git
#
# Idempotent: safe to re-run. Set env overrides:
#   ENGINE_REPO / DATA_REPO   SSH URLs (or edit defaults below)
#   INSTALL_DIR               where the engine lands (default ~/git/jobhunt-engine)
#   SKIP_SYSTEM=1             skip apt packages (no sudo)
set -euo pipefail

ENGINE_REPO="${ENGINE_REPO:-git@github.com:Vedaang-Chopra/jobhunt-engine.git}"
DATA_REPO="${DATA_REPO:-git@github.com:Vedaang-Chopra/jobhunt-data-private.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/git/jobhunt-engine}"

log()  { echo -e "\033[1;34m==>\033[0m $*"; }
fail() { echo -e "\033[1;31mFAIL:\033[0m $*" >&2; exit 1; }

# --- 1. System deps ---------------------------------------------------------
if [ "${SKIP_SYSTEM:-0}" != "1" ]; then
  log "Installing system packages"
  sudo apt-get update -qq
  sudo apt-get install -y -qq git python3 python3-venv python3-pip curl jq rsync >/dev/null
  if ! command -v google-chrome-stable >/dev/null 2>&1; then
    log "Installing Google Chrome"
    wget -qO /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt-get install -y -qq /tmp/chrome.deb >/dev/null
  fi
fi

# --- 2. Hermes ---------------------------------------------------------------
if ! command -v hermes >/dev/null 2>&1; then
  log "Installing Hermes Agent"
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi
export PATH="$HOME/.local/bin:$PATH"

# --- 3. Engine repo ----------------------------------------------------------
if [ ! -d "$INSTALL_DIR/.git" ]; then
  log "Cloning engine repo to $INSTALL_DIR"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone "$ENGINE_REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
git pull --ff-only origin main

# --- 4. Private data repo ----------------------------------------------------
log "Registering private data repo"
mkdir -p "$HOME/.config/jobhunt"
echo "$DATA_REPO" > "$HOME/.config/jobhunt/data_repo"
./scripts/sync_data.sh pull

# --- 5. Python env + tests -----------------------------------------------------
log "Bootstrapping venv + running tests"
./setup/bootstrap.sh

# --- 6. Hermes profile ---------------------------------------------------------
PROFILE="$HOME/.hermes/profiles/job-hunt"
if [ ! -f "$PROFILE/cron/jobs.json" ]; then
  fail "Hermes job-hunt profile missing at $PROFILE.
Copy from the old machine (Mac):
  tar -C ~/.hermes/profiles/job-hunt -cf - config.yaml .env SOUL.md profile.yaml skills memories cron | \\
    tar -xf - -C ~/.hermes/profiles/job-hunt
Then re-run this script."
fi
log "Rewriting cron job paths for this machine"
python3 setup/migrate_cron_paths.py \
  --jobs-file "$PROFILE/cron/jobs.json" \
  --to-repo "$INSTALL_DIR" --apply

# --- 7. Identity check ----------------------------------------------------------
log "Checking identity block in data config"
if ! grep -q "^identity:" "$INSTALL_DIR/jobhunt-data/config.yaml" 2>/dev/null; then
  fail "No 'identity:' block in jobhunt-data/config.yaml — add it (see config.example.yaml identity section)."
fi

# --- 8. Shell env ----------------------------------------------------------------
ENVRC="$HOME/.bashrc"
grep -q "JOBHUNT_HOME" "$ENVRC" 2>/dev/null || \
  echo "export JOBHUNT_HOME=\"$INSTALL_DIR/jobhunt-data\"" >> "$ENVRC"
export JOBHUNT_HOME="$INSTALL_DIR/jobhunt-data"

# --- 9. systemd user units --------------------------------------------------------
log "Installing systemd user units"
mkdir -p "$HOME/.config/systemd/user"
for unit in jobhunt-automation-chrome jobhunt-ui; do
  sed "s|%h/git/jobhunt-engine|$INSTALL_DIR|g" "setup/systemd/$unit.service" \
    > "$HOME/.config/systemd/user/$unit.service"
done
systemctl --user daemon-reload
systemctl --user enable --now jobhunt-automation-chrome.service 2>/dev/null || \
  log "WARN: chrome unit did not start (headless session?) — run scripts/automation_chrome.sh after first GUI login"
sudo loginctl enable-linger "$USER" 2>/dev/null || true

# --- 10. Verification ---------------------------------------------------------------
log "Verification"
PASS=0; FAIL=0
check() { if eval "$2" >/dev/null 2>&1; then echo "  [PASS] $1"; PASS=$((PASS+1)); else echo "  [FAIL] $1"; FAIL=$((FAIL+1)); fi; }
check "venv python"           "[ -x '$INSTALL_DIR/.venv/bin/python' ]"
check "pytest suite"          "cd '$INSTALL_DIR' && .venv/bin/python -m pytest tests/ -q"
check "data_root resolves"    "cd '$INSTALL_DIR' && JOBHUNT_HOME='$INSTALL_DIR/jobhunt-data' .venv/bin/python -c 'import sys; sys.path.insert(0,\"scripts\"); import config_lib; assert \"jobhunt-data\" in str(config_lib.data_root())'"
check "identity configured"   "grep -q '^identity:' '$INSTALL_DIR/jobhunt-data/config.yaml'"
check "jobs registry present" "[ -f '$INSTALL_DIR/jobhunt-data/tracking/jobs/jobs.csv' ]"
check "cron jobs present"     "python3 -c \"import json; d=json.load(open('$PROFILE/cron/jobs.json')); assert len(d['jobs'])>=9\""
check "no /Users/ in crons"   "! grep -q '/Users/' '$PROFILE/cron/jobs.json'"
check "JOBHUNT_HOME in rc"    "grep -q 'JOBHUNT_HOME' '$ENVRC'"
check "hermes doctor"         "hermes doctor"
check "chrome CDP :9333"      "curl -sf --max-time 3 http://127.0.0.1:9333/json/version"

echo
if [ "$FAIL" -eq 0 ]; then
  log "ALL CHECKS PASSED."
  log "Remaining manual steps:"
  log "  1. Log into LinkedIn once in the automation Chrome window."
  log "  2. Pause the 9 cron jobs on the OLD machine (see setup/MIGRATION_LINUX.md §7)."
  log "  3. Test-fire: hermes cron run <ops-health job id>."
else
  log "$FAIL check(s) failed — fix before cron cutover."
  exit 1
fi
