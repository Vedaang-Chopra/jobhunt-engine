#!/usr/bin/env python3
"""Rewrite Hermes cron job paths for a new machine (migration helper).

Reads the job-hunt profile's cron/jobs.json and rewrites machine-specific
absolute paths in job prompts:

  1. The old repo absolute path  -> the new repo absolute path (--to-repo).
  2. The macOS hermes-agent venv interpreter (~/.hermes/hermes-agent/venv/bin/python)
     -> the repo's own virtualenv (<repo>/.venv/bin/python), which is what
     bootstrap.sh creates on the target machine.

Nothing else is touched: schedules, models, providers, delivery targets,
toolset restrictions and skills stay byte-identical.

Usage (run on the TARGET machine, after `hermes` is installed and the
profile directory is in place):

    python3 setup/migrate_cron_paths.py \
        --jobs-file ~/.hermes/profiles/job-hunt/cron/jobs.json \
        --from-repo "/old/mac/repo/path" \
        --to-repo "/home/<you>/git/jobhunt-engine" \
        --apply          # omit --apply for a dry-run diff

Also scans for any residual '/Users/' references after rewriting and exits
non-zero if any remain (unless --allow-residual is passed).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

MAC_VENV = "~/.hermes/hermes-agent/venv/bin/python"
OLD_DEFAULT_REPO = "/old/mac/repo/path"


def rewrite_text(text: str, from_repo: str, to_repo: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    if from_repo and from_repo in text:
        text = text.replace(from_repo, to_repo)
        changes.append("repo-path")
    if MAC_VENV in text:
        text = text.replace(MAC_VENV, f"{to_repo}/.venv/bin/python")
        changes.append("venv-python")
    return text, changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs-file", required=True, help="path to cron/jobs.json")
    ap.add_argument("--from-repo", default=OLD_DEFAULT_REPO)
    ap.add_argument("--to-repo", required=True, help="new absolute repo path on this machine")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--allow-residual", action="store_true",
                    help="do not fail if /Users/ references remain")
    args = ap.parse_args()

    jobs_path = Path(args.jobs_file).expanduser().resolve()
    if not jobs_path.exists():
        print(f"ERROR: {jobs_path} not found", file=sys.stderr)
        return 2
    data = json.loads(jobs_path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", data if isinstance(data, list) else [])

    touched = 0
    residual: list[tuple[str, str]] = []
    for job in jobs:
        prompt = job.get("prompt") or ""
        new_prompt, changes = rewrite_text(prompt, args.from_repo, args.to_repo)
        for field in ("script", "monitor_script", "workdir"):
            val = job.get(field)
            if val:
                nv, ch = rewrite_text(val, args.from_repo, args.to_repo)
                if ch:
                    job[field] = nv
                    changes += [f"{field}:{c}" for c in ch]
        if changes:
            job["prompt"] = new_prompt
            touched += 1
            print(f"[rewrite] {job.get('name','?')}: {', '.join(sorted(set(changes)))}")
        for m in re.finditer(r"/Users/[^\s\"']*", job.get("prompt") or ""):
            residual.append((job.get("name", "?"), m.group(0)))

    print(f"\njobs total: {len(jobs)} | rewritten: {touched}")
    if residual:
        print("\nRESIDUAL /Users/ references (inspect these):")
        for name, p in residual:
            print(f"  - {name}: {p}")
        if not args.allow_residual:
            print("\nRun again with --allow-residual only if you have reviewed them.")
            return 1

    if args.apply:
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        backup = jobs_path.with_suffix(f".json.pre-migrate-{stamp}")
        backup.write_text(jobs_path.read_text(encoding="utf-8"), encoding="utf-8")
        jobs_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        print(f"applied. backup at {backup}")
    else:
        print("dry-run only — re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
