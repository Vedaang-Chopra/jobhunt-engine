#!/usr/bin/env bash
# Source this to get a portable job-hunt environment. Idempotent.
export JOBHUNT_HOME="${JOBHUNT_HOME:-$HOME/jobhunt-data}"
export JOBHUNT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$JOBHUNT_REPO/.venv/bin:$PATH"
