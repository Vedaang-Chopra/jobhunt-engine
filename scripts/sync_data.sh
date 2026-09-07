#!/usr/bin/env bash
# scripts/sync_data.sh — sync personal job-hunt data with the private data repo.
#
# Architecture: the ENGINE lives in a public repo; the PERSONAL DATA lives in
# a separate private repo. Both laptops clone both. This script is the only
# sanctioned way to move data between working tree and the private repo.
#
#   ./scripts/sync_data.sh pull    # private repo -> working tree (after clone/migration)
#   ./scripts/sync_data.sh push    # working tree -> private repo (commit+push)
#   ./scripts/sync_data.sh status  # diff summary, no changes
#
# Requires: DATA_REPO_REMOTE env var or ~/.config/jobhunt/data_repo file
# containing the SSH remote URL, e.g. git@github.com:<you>/jobhunt-data-private.git
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

DATA_ROOT="${JOBHUNT_HOME:-$REPO/jobhunt-data}"
WORKTREE="$REPO/.data-private"

remote() {
  if [ -n "${DATA_REPO_REMOTE:-}" ]; then echo "$DATA_REPO_REMOTE"; return; fi
  if [ -f "$HOME/.config/jobhunt/data_repo" ]; then
    cat "$HOME/.config/jobhunt/data_repo"; return
  fi
  echo "ERROR: set DATA_REPO_REMOTE or write the private repo URL to ~/.config/jobhunt/data_repo" >&2
  exit 2
}

# Paths that hold personal data (mirrored into the private repo root).
PERSONAL_PATHS=(
  "jobhunt-data/tracking"
  "jobhunt-data/profile_info"
  "jobhunt-data/applications"
  "jobhunt-data/messaging"
  "jobhunt-data/linkedin"
  "jobhunt-data/resume_custom"
  "jobhunt-data/resume_scoring"
  "jobhunt-data/execution_results"
  "jobhunt-data/browser_runs"
  "jobhunt-data/job_research"
  "jobhunt-data/config.yaml"
  "jobhunt-data/logs"
  "all_custom_resumes"
  "export_packages"
  "job-hunt-docs"
)

ensure_worktree() {
  if [ ! -d "$WORKTREE/.git" ]; then
    echo "==> Cloning private data repo into $WORKTREE"
    git clone "$(remote)" "$WORKTREE"
  else
    git -C "$WORKTREE" pull --ff-only
  fi
}

sync_to_worktree() {  # working tree -> private worktree
  for p in "${PERSONAL_PATHS[@]}"; do
    if [ -e "$REPO/$p" ]; then
      mkdir -p "$WORKTREE/$(dirname "$p")"
      rsync -a --delete "$REPO/$p/" "$WORKTREE/$p/"
    fi
  done
  # never sync secrets or caches into the data repo
  rm -f "$WORKTREE/jobhunt-data/config.yaml.bak" 2>/dev/null || true
  find "$WORKTREE" -name ".DS_Store" -delete 2>/dev/null || true
  find "$WORKTREE" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
}

sync_from_worktree() {  # private worktree -> working tree
  for p in "${PERSONAL_PATHS[@]}"; do
    if [ -e "$WORKTREE/$p" ]; then
      mkdir -p "$REPO/$(dirname "$p")"
      rsync -a --delete "$WORKTREE/$p/" "$REPO/$p/"
    fi
  done
}

cmd="${1:-status}"
case "$cmd" in
  status)
    ensure_worktree
    echo "Changes that 'push' would commit to the private repo:"
    sync_to_worktree
    git -C "$WORKTREE" status --short | head -40
    echo "(end of status)"
    ;;
  pull)
    ensure_worktree
    sync_from_worktree
    echo "==> Pulled personal data into working tree. Review with git status; data paths are gitignored in the engine repo."
    ;;
  push)
    ensure_worktree
    sync_to_worktree
    if git -C "$WORKTREE" status --short | grep -q .; then
      git -C "$WORKTREE" add -A
      git -C "$WORKTREE" commit -m "data sync $(date '+%F %T') from $(hostname -s)"
      git -C "$WORKTREE" push
      echo "==> Private data pushed."
    else
      echo "==> No data changes to push."
    fi
    ;;
  *)
    echo "usage: $0 {pull|push|status}" >&2; exit 1;;
esac
