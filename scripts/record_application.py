#!/usr/bin/env python3
"""record_application — post-submission tracking write-back (Task 5).

Called ONLY after a human-approved submission (see form_filler --submit gate).
Transforms:
  1. applications.csv: status=submitted, date_submitted=<today>,
     current_stage=submitted, date_last_status_change=<today>
  2. jobs.csv: append a "[<date>] submitted" note (idempotent by tag)
  3. execution_results/apply_runs/<job_id>_confirmation.txt: confirmation text
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

APPLICATIONS_CSV = ROOT / "tracking" / "applications" / "applications.csv"
JOBS_CSV = ROOT / "tracking" / "jobs" / "jobs.csv"
RUN_DIR = ROOT / "execution_results" / "apply_runs"


class JobNotFound(Exception):
    pass


def today() -> str:
    return datetime.date.today().isoformat()


def mark_submitted(applications_csv, job_id: str) -> int:
    """Set status/date_submitted/current_stage on the application row."""
    applications_csv = Path(applications_csv)
    with applications_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    for row in rows:
        if row.get("job_id") == job_id:
            if "date_submitted" not in fieldnames:
                fieldnames.append("date_submitted")
            row["status"] = "submitted"
            row["date_submitted"] = today()
            if "current_stage" in fieldnames:
                row["current_stage"] = "submitted"
            if "date_last_status_change" in fieldnames:
                row["date_last_status_change"] = today()
            with applications_csv.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(rows)
            return 1
    raise JobNotFound(f"job_id {job_id} not found in {applications_csv}")


def append_jobs_note(jobs_csv, job_id: str, note: str) -> int:
    """Append `note` to the jobs.csv notes cell; idempotent per exact tag."""
    jobs_csv = Path(jobs_csv)
    with jobs_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    changed = 0
    for row in rows:
        if row.get("job_id") == job_id:
            existing = (row.get("notes") or "").strip()
            if note in existing:
                return 0
            parts = [p.strip() for p in existing.split("|") if p.strip()]
            parts.append(note)
            row["notes"] = " | ".join(parts)
            changed = 1
            break
    if not changed:
        raise JobNotFound(f"job_id {job_id} not found in {jobs_csv}")
    with jobs_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return 1


def write_confirmation(run_dir, job_id: str, text: str) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / f"{job_id}_confirmation.txt"
    p.write_text(text.rstrip() + "\n", encoding="utf-8")
    return p


def record(applications_csv=APPLICATIONS_CSV, jobs_csv=JOBS_CSV,
           run_dir=RUN_DIR, job_id: str = "", company: str = "",
           role: str = "", confirmation: str = "") -> dict:
    d = today()
    note = f"[{d}] submitted{f' - {company}' if company else ''}"
    mark_submitted(applications_csv, job_id)
    append_jobs_note(jobs_csv, job_id, note)
    text = confirmation or (
        f"Application {job_id} ({company} - {role}) recorded as "
        f"SUBMITTED on {d}. Human approval on file.")
    path = write_confirmation(run_dir, job_id, text)
    return {"job_id": job_id, "date": d, "confirmation_path": str(path)}


if __name__ == "__main__":
    ap = __import__("argparse").ArgumentParser(
        description="record an approved submission in tracking CSVs + confirmation file")
    ap.add_argument("job_id")
    ap.add_argument("--company", default="")
    ap.add_argument("--role", default="")
    ap.add_argument("--note", default="", help="extra confirmation text")
    ap.add_argument("--applications-csv", default=str(APPLICATIONS_CSV))
    ap.add_argument("--jobs-csv", default=str(JOBS_CSV))
    ap.add_argument("--run-dir", default=str(RUN_DIR))
    ap.add_argument("--approved-by", required=True,
                    help="recording requires a named human approver")
    args = ap.parse_args()
    out = record(
        applications_csv=args.applications_csv, jobs_csv=args.jobs_csv,
        run_dir=args.run_dir, job_id=args.job_id, company=args.company,
        role=args.role,
        confirmation=(args.note or "") +
        f"\nApproved by: {args.approved_by}")
    print(f"recorded {out['job_id']} submitted on {out['date']}; "
          f"confirmation at {out['confirmation_path']}")
