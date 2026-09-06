#!/usr/bin/env bash
# Start the Job Hunt UI. Safe to run repeatedly — refuses if already running.
set -euo pipefail
cd "$(dirname "$0")"

if lsof -ti :8080 >/dev/null 2>&1; then
  echo "UI already running at http://localhost:8080 (stop with ./stop.sh)"
  exit 0
fi

source .venv/bin/activate
# JOBHUNT_HOME is inherited from your shell profile; default if unset:
export JOBHUNT_HOME="${JOBHUNT_HOME:-$(cd "$(dirname "$0")" && pwd)/jobhunt-data}"

nohup python -m ui.app > /tmp/jobhunt-ui.log 2>&1 &
echo "Started (PID $!). Log: /tmp/jobhunt-ui.log — http://localhost:8080"
