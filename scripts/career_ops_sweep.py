#!/usr/bin/env python3
"""One-command career-ops discovery sweep: scan + import + coverage log.

Wraps the two integration commands and records the run in
tracking/search_runs/search_runs.csv per JOB_SEARCH_WORKFLOW.md Phase 8.

Steps:
  1. node scan.mjs --quiet          (career-ops zero-token portal scan)
  2. import_career_ops_scan.py      (dry-run summary, then append new rows)
  3. append search_runs row         (source=career_ops_scan)

Usage:
  python3 scripts/career_ops_sweep.py            # full sweep
  python3 scripts/career_ops_sweep.py --no-scan  # import only (reuse last scan)
"""
import argparse
import csv
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = os.environ.get(
    "JOBHUNT_HOME",
    str(Path(__file__).resolve().parent.parent),
)
CAREER_OPS = os.path.normpath(os.path.join(REPO, "..", "career-ops"))
SCAN_TSV = os.path.join(CAREER_OPS, "data", "scan-history.tsv")
RUNS_CSV = os.path.join(REPO, "tracking", "search_runs", "search_runs.csv")


def run(cmd, cwd):
    print(f"$ {' '.join(cmd)}  (cwd={os.path.basename(cwd)})")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def parse_scan_summary(output):
    def grab(pattern):
        m = re.search(pattern, output)
        return m.group(1) if m else ""
    return {
        "companies": grab(r"Companies scanned:\s*(\d+)"),
        "new_offers": grab(r"New offers added:\s*(\d+)"),
        "duplicates": grab(r"Duplicates:\s*(\d+) skipped"),
        "errors": grab(r"Errors \((\d+)\)"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-scan", action="store_true",
                    help="skip the node scan; import from last scan-history")
    args = ap.parse_args()

    summary = {"companies": "", "new_offers": "", "duplicates": "", "errors": ""}
    failures = []

    if not args.no_scan:
        code, out, err = run(["node", "scan.mjs", "--quiet"], CAREER_OPS)
        output = out + err
        summary.update(parse_scan_summary(output))
        for m in re.finditer(r"✗ ([^\n]+)", output):
            failures.append(m.group(1).strip())
        if code != 0:
            failures.append(f"scan exit={code}")

    # Import: dry-run first to get counts, then apply.
    code, out, _ = run([sys.executable,
                        os.path.join(REPO, "scripts", "import_career_ops_scan.py")], REPO)
    if code != 0:
        sys.exit(f"import dry-run failed: {out}")
    new_match = re.search(r"new\s*:\s*(\d+)", out)
    dup_match = re.search(r"duplicate\s*:\s*(\d+)", out)
    new_count = int(new_match.group(1)) if new_match else 0
    dup_count = int(dup_match.group(1)) if dup_match else 0

    if new_count:
        code, out, err = run([sys.executable,
                              os.path.join(REPO, "scripts", "import_career_ops_scan.py"),
                              "--apply"], REPO)
        if code != 0 or "APPLIED" not in out:
            sys.exit(f"import apply failed:\n{out}\n{err}")

    # Coverage log (Phase 8).
    now = datetime.now()
    run_id = f"coscan_{now.strftime('%Y%m%d_%H%M')}"
    date_str = now.date().isoformat()
    sources = f"career_ops_scan ({summary['companies'] or '?'} companies)"
    queries = "tracked_companies API scans"
    notes = "; ".join(failures) if failures else "clean"
    file_exists = os.path.exists(RUNS_CSV)
    with open(RUNS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists or os.path.getsize(RUNS_CSV) == 0:
            writer.writerow(["run_id", "date", "sources", "queries", "total_scanned",
                             "new_jobs_found", "duplicates_skipped", "strong_fits", "notes"])
        writer.writerow([run_id, date_str, sources, queries,
                         summary["companies"] or "?", new_count, dup_count, "", notes[:200]])

    print(f"\n=== SWEEP COMPLETE {run_id} ===")
    print(f"companies scanned : {summary['companies'] or '(skipped scan)'}")
    print(f"scanner new offers: {summary['new_offers'] or '-'}")
    print(f"rows imported     : {new_count} new, {dup_count} duplicates skipped")
    print(f"failures          : {'; '.join(failures) if failures else 'none'}")
    print("Next: python3 scripts/score_jobs_v2.py to score unscored rows.")


if __name__ == "__main__":
    main()
