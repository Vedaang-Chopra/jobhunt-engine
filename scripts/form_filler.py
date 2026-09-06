#!/usr/bin/env python3
"""form_filler — fill-plan execution helpers + application record write-through.

Pure-logic parts (tested):
  resolve_field(plan_entry, store)      — decide the value/status for one field
  update_applications_csv(...)          — write-through to tracking/applications
  page_summary(page_no, results)        — human-readable per-page summary

Browser interaction (Playwright MCP / agent-driven) lives in the agent layer;
this module supplies the decisions, the CSV write-through, and summaries so the
browser driver only executes mechanical steps.
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from answers_lib import is_gated  # noqa: E402

ASK_USER = "ask_user"
FILLED = "filled"
SKIPPED = "skipped"

APPLICATIONS_CSV = ROOT / "tracking" / "applications" / "applications.csv"


def resolve_field(entry: dict, store: dict) -> dict:
    """Resolve a single fill-plan entry against the answers store.

    Returns {label, status, resolved}:
      filled   — a concrete string value to type/select/upload.
      ask_user — gated label (salary/EEO/legal), planned ASK_USER, or no value.
    Gated labels are ALWAYS ask_user even if the plan carries a value.
    """
    label = entry.get("label", "")
    out = {"label": label, "status": ASK_USER, "resolved": None}
    if entry.get("action") == "ASK_USER":
        return out
    if is_gated(label):
        return out
    value = entry.get("value")
    if entry.get("action") == "USE_SAVED_ANSWER" and not value:
        key = entry.get("key")
        from answers_lib import get_answer
        value = get_answer(store, key) if key else None
    if isinstance(value, str) and value.strip():
        out["status"], out["resolved"] = FILLED, value
    return out


def update_applications_csv(csv_path, job_id: str,
                            company: str = "", role: str = "",
                            job_url: str = "", **updates) -> int:
    """Write-through application state for job_id. Appends a row when absent;
    never deletes rows. Returns number of rows written (1)."""
    csv_path = Path(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    target = None
    for row in rows:
        if row.get("job_id") == job_id:
            target = row
            break

    if target is None:
        target = {k: "" for k in fieldnames}
        target.update({"application_id": job_id, "job_id": job_id})
        if company:
            target["company"] = company
        if role:
            target["role"] = role
        if job_url:
            target["job_url"] = job_url
        target.setdefault("date_queued", datetime.date.today().isoformat())
        rows.append(target)

    for k, v in updates.items():
        if k in fieldnames:
            target[k] = v

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return 1


def page_summary(page_no: int, results: list[dict]) -> str:
    """Human-readable summary of one filled page."""
    filled = [r for r in results if r["status"] == FILLED]
    asked = [r for r in results if r["status"] == ASK_USER]
    lines = [f"Page {page_no}: {len(filled)} filled, "
             f"{len(asked)} ask_user"]
    for r in results:
        mark = "✓" if r["status"] == FILLED else "?"
        line = f"  [{mark}] {r['label']}"
        if r["status"] == FILLED:
            line += f" -> {r['resolved'][:80]}"
        lines.append(line)
    return "\n".join(lines)


class ApprovalRequired(Exception):
    """Raised when submit mode runs without a named human approver."""


_PLACEHOLDER_APPROVERS = {"", "true", "yes", "auto", "user", "admin"}


def check_submit_approval(args) -> str:
    """Gate for submit mode: requires args.approved_by naming a real user.

    Returns the approver name; raises ApprovalRequired otherwise.
    """
    approver = (getattr(args, "approved_by", None) or "").strip()
    if not approver or approver.lower() in _PLACEHOLDER_APPROVERS:
        raise ApprovalRequired(
            "submit mode refused: pass --approved-by <your-name> to record "
            "explicit human approval before submitting")
    return approver


def build_parser():
    ap = __import__("argparse").ArgumentParser(
        description="write application record through to applications.csv")
    ap.add_argument("job_id")
    ap.add_argument("--csv", default=str(APPLICATIONS_CSV))
    ap.add_argument("--company", default="")
    ap.add_argument("--role", default="")
    ap.add_argument("--url", dest="job_url", default="")
    ap.add_argument("--submit", action="store_true",
                    help="submit mode: REQUIRES --approved-by <your-name>")
    ap.add_argument("--approved-by", default=None,
                    help="name of the human approving submission (gate)")
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if getattr(args, "submit", False):
        try:
            approver = check_submit_approval(args)
        except ApprovalRequired as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
        from record_application import record
        out = record(job_id=args.job_id, company=args.company,
                     role=args.role,
                     confirmation=f"Submitted via form_filler; "
                                  f"approved by {approver}.")
        print(f"SUBMITTED {out['job_id']} on {out['date']} "
              f"(approved by {approver}); confirmation at "
              f"{out['confirmation_path']}")
        return 0
    n = update_applications_csv(
        args.csv, args.job_id, company=args.company, role=args.role,
        job_url=args.job_url, status="ready_to_apply",
        date_resume_ready=datetime.date.today().isoformat(),
        date_last_status_change=datetime.date.today().isoformat(),
        current_stage="ready_to_apply")
    print(f"updated {n} row(s) for {args.job_id} in {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
