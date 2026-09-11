#!/usr/bin/env python3
"""LLM-backed, per-record qualification of open jobs and new hiring posts.

Every candidate receives an explicit KEEP/ARCHIVE or KEEP/DISMISS verdict from
an OpenAI-compatible configured provider. No malformed, missing, or uncertain
verdict changes lifecycle state. Dry-run is the default; --apply persists only
explicit archive/dismiss verdicts plus the auditable AI review fields.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib  # type: ignore[no-redef]

DATA_ROOT = Path(config_lib.data_root())
JOBS_CSV = DATA_ROOT / "tracking/jobs/jobs.csv"
POSTS_CSV = DATA_ROOT / "tracking/hiring_posts/hiring_posts.csv"
PROFILE_PATH = DATA_ROOT / "profile_info/profile.md"
REPORT_DIR = DATA_ROOT / "execution_results/cleanup_reports"
REVIEW_FIELDS = ["ai_reviewed_at", "ai_review_verdict", "ai_review_reason"]


def load_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.is_file():
        return [], []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def _review_fields(fields: list[str]) -> list[str]:
    return fields + [field for field in REVIEW_FIELDS if field not in fields]


def _json_decision(response: str, allowed: set[str]) -> dict | None:
    """Accept only a compact decision object with a permitted exact verdict."""
    try:
        value = json.loads(response.strip())
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    decision = str(value.get("decision") or "").strip().upper()
    reason = str(value.get("reason") or "").strip()
    if decision not in allowed or not reason:
        return None
    return {"decision": decision, "reason": reason[:500]}


def profile_context() -> str:
    """Load the canonical candidate facts without failing an otherwise safe review."""
    try:
        return PROFILE_PATH.read_text(encoding="utf-8")[:12000].strip()
    except OSError:
        return ""


def codex_chat(prompt: str) -> str:
    """Use Hermes's OpenAI Codex OAuth route, never the engine API-key chain."""
    result = subprocess.run(
        ["hermes", "--profile", "job-hunt-fresh", "chat", "-q", prompt],
        text=True, capture_output=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Hermes Codex call failed")
    return result.stdout.strip()


def _judge(kind: str, row: dict) -> dict | None:
    if kind == "job":
        allowed = {"KEEP", "ARCHIVE"}
        record = {key: row.get(key, "") for key in (
            "job_id", "company", "title", "location", "source", "priority_v2",
            "recommended_action", "fit_class", "disqualify_reason", "date_posted",
            "date_discovered")}
        instruction = (
            "Review one job against the candidate's established AI/ML job-search "
            "profile. Archive only when it is clearly unsuitable (e.g., internship, "
            "new-grad program, non-IC/sales/annotation role, ineligible location, or "
            "very poor fit). Keep any plausible target or useful stretch role. "
            "Return exactly JSON: {\"decision\":\"KEEP|ARCHIVE\",\"reason\":\"...\"}.")
    else:
        allowed = {"KEEP", "DISMISS"}
        record = {key: row.get(key, "") for key in (
            "post_id", "poster_name", "poster_headline", "poster_type", "company",
            "posted_date", "discovered_date", "roles_mentioned", "priority",
            "role_family", "notes")}
        instruction = (
            "Review one LinkedIn hiring post against the candidate's established "
            "AI/ML job-search profile. Dismiss only when it is clearly stale, not an "
            "actual hiring lead, irrelevant, or unusable. Keep plausible recruiting, "
            "team-hiring, referral, or direct-application signals. Return exactly JSON: "
            "{\"decision\":\"KEEP|DISMISS\",\"reason\":\"...\"}.")
    prompt = ("You are a conservative job-search reviewer. " + instruction
              + "\n\nCanonical candidate profile:\n" + profile_context()
              + "\n\nRecord to review:\n" + json.dumps(record, ensure_ascii=False))
    return _json_decision(codex_chat(prompt), allowed)


def apply_job_decisions(rows: list[dict], decisions: dict[str, dict], today: str) -> list[str]:
    changed = []
    for row in rows:
        if row.get("status") != "open":
            continue
        decision = decisions.get(row.get("job_id") or "")
        if not decision or decision.get("decision") not in {"KEEP", "ARCHIVE"}:
            continue
        row["ai_reviewed_at"] = today
        row["ai_review_verdict"] = decision["decision"]
        row["ai_review_reason"] = decision["reason"]
        if decision["decision"] == "ARCHIVE":
            row["status"] = "archived"
            row["date_updated"] = today
            changed.append(row.get("job_id") or "")
    return changed


def apply_post_decisions(rows: list[dict], decisions: dict[str, dict], today: str) -> list[str]:
    changed = []
    for row in rows:
        if row.get("status") != "new":
            continue
        decision = decisions.get(row.get("post_id") or "")
        if not decision or decision.get("decision") not in {"KEEP", "DISMISS"}:
            continue
        row["ai_reviewed_at"] = today
        row["ai_review_verdict"] = decision["decision"]
        row["ai_review_reason"] = decision["reason"]
        if decision["decision"] == "DISMISS":
            row["status"] = "dismissed"
            changed.append(row.get("post_id") or "")
    return changed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="persist explicit AI verdicts")
    parser.add_argument("--limit", type=int, default=250, help="maximum records per type")
    parser.add_argument("--jobs-only", action="store_true")
    parser.add_argument("--posts-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.jobs_only and args.posts_only:
        raise SystemExit("--jobs-only and --posts-only cannot be combined")
    today = date.today().isoformat()
    job_fields, jobs = load_csv(JOBS_CSV)
    post_fields, posts = load_csv(POSTS_CSV)
    job_targets = [] if args.posts_only else [r for r in jobs if r.get("status") == "open"][:args.limit]
    post_targets = [] if args.jobs_only else [r for r in posts if r.get("status") == "new"][:args.limit]
    job_decisions: dict[str, dict] = {}
    post_decisions: dict[str, dict] = {}
    failures: list[str] = []
    for row in job_targets:
        try:
            decision = _judge("job", row)
            if decision:
                job_decisions[row.get("job_id") or ""] = decision
            else:
                failures.append(f"job {row.get('job_id')}: invalid verdict")
        except Exception as exc:  # provider failures must leave data untouched
            failures.append(f"job {row.get('job_id')}: {type(exc).__name__}: {exc}")
    for row in post_targets:
        try:
            decision = _judge("post", row)
            if decision:
                post_decisions[row.get("post_id") or ""] = decision
            else:
                failures.append(f"post {row.get('post_id')}: invalid verdict")
        except Exception as exc:
            failures.append(f"post {row.get('post_id')}: {type(exc).__name__}: {exc}")
    archived = apply_job_decisions(jobs, job_decisions, today)
    dismissed = apply_post_decisions(posts, post_decisions, today)
    report = {"date": today, "applied": bool(args.apply), "jobs_reviewed": len(job_decisions),
              "posts_reviewed": len(post_decisions), "jobs_archived": archived,
              "posts_dismissed": dismissed, "failures": failures}
    print(json.dumps(report, indent=2))
    if args.apply:
        if job_decisions:
            write_csv(JOBS_CSV, _review_fields(job_fields), jobs)
        if post_decisions:
            write_csv(POSTS_CSV, _review_fields(post_fields), posts)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"ai_backlog_review_{today}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
