#!/usr/bin/env bash
# setup/bootstrap.sh — one-shot from-scratch deployment for the jobhunt repo.
# Idempotent: safe to re-run at any time.
set -euo pipefail

# Resolve repo root relative to this script (handles spaces in paths).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Repo root: $REPO_ROOT"

# ---------------------------------------------------------------- venv + deps
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
    echo "==> Creating virtualenv (.venv) with python3"
    python3 -m venv .venv
else
    echo "==> .venv already exists, reusing"
fi

echo "==> Upgrading pip"
.venv/bin/pip install --upgrade pip

echo "==> Installing repo in editable mode with [dev] extras"
.venv/bin/pip install -e ".[dev]"

# ------------------------------------------------------- portable environment
export JOBHUNT_HOME="${JOBHUNT_HOME:-$HOME/jobhunt-data}"
echo "==> JOBHUNT_HOME = $JOBHUNT_HOME"
mkdir -p "$JOBHUNT_HOME"/tracking/jobs \
         "$JOBHUNT_HOME"/tracking/hiring_posts \
         "$JOBHUNT_HOME"/tracking/applications \
         "$JOBHUNT_HOME"/tracking/contacts \
         "$JOBHUNT_HOME"/tracking/companies \
         "$JOBHUNT_HOME"/profile_info/inbox \
         "$JOBHUNT_HOME"/browser_runs \
         "$JOBHUNT_HOME"/logs

# Repo-local seed config (gitignored; never overwrites existing).
if [ ! -f "$REPO_ROOT/config.yaml" ] && [ -f "$REPO_ROOT/config.example.yaml" ]; then
    cp config.example.yaml config.yaml
    echo "==> Created config.yaml from config.example.yaml (fill in your keys)"
fi

# ----------------------------------------------------------------- verify
echo "==> Running test suite"
.venv/bin/python -m pytest tests/ -q

echo "==> Resolved data_root:"
.venv/bin/python scripts/config_lib.py 2>/dev/null || true
# Fallback print if config_lib.py has no __main__ entrypoint:
.venv/bin/python -c "import sys; sys.path.insert(0, 'scripts'); import config_lib; print('data_root =', config_lib.data_root())"

cat <<'EOF'

============================================================
Bootstrap complete. Next manual steps:
1. Put API keys in <data_root>/config.yaml (see config.example.yaml),
   or export OPENROUTER_API_KEY / NVIDIA_API_KEY in your shell.
2. Run the interactive wizard:   .venv/bin/python -m setup.wizard --apply
3. Daily ops:                    .venv/bin/python scripts/daily_ops.py
4. Start the UI:                 ./start.sh   (entry point: jobhunt-ui)
5. See HANDOFF.md for data transfer from an old machine and cron setup.
============================================================
EOF
