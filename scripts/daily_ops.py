#!/usr/bin/env python3
"""Unattended morning ops cycle (master-plan Task 8).

Runs, in order, each step try/except-isolated with status recorded:
  1. career-ops scan + import (live)
  2. discovery sweeps due (discovery_run.py --sources career_ops,freshness;
     l1/l2 self-skip headless — fine)
  3. hiring-post ingestion note (the existing 4x/day cron does ingestion;
     here we only verify tracking/hiring_posts/hiring_posts.csv is readable
     and count recent rows)
  4. scoring of unscored rows (score_jobs_v2.py)
  5. rebuild today_queue review CSVs (today_queue.py)
  6. compile the morning digest -> execution_results/digests/digest_<date>.md
     and print it
  7. STOP. Nothing consequential (approvals, outreach sends, applications)
     runs without explicit user input.

Uses the same .hermes/ops.lock as discovery_run so it never double-runs
against discovery crons.

CLI:
    python scripts/daily_ops.py            # full morning cycle
    python scripts/daily_ops.py --dry-run  # print planned steps only
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from discovery_run import OpsLock, load_health, run_cmd  # noqa: E402
import config_lib

PY = sys.executable
DIGEST_DIR = config_lib.path("digests_dir")
JOBS_CSV = config_lib.path("jobs_csv")
APPS_CSV = config_lib.path("applications_csv")
REQ_CSV = config_lib.path("connection_requests")
POSTS_CSV = config_lib.path("hiring_posts_csv")
TOP_QUEUE_CSV = config_lib.path("reviews_dir") / "top_queue.csv"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Steps (each returns a short human note; raise on failure)
# ---------------------------------------------------------------------------

def step_career_ops() -> str:
    """Live career-ops portal scan + import into jobs.csv."""
    code, out = run_cmd([PY, "scripts/career_ops_sweep.py"], REPO)
    if code != 0:
        raise RuntimeError(f"career_ops_sweep exit={code}: {out[-300:]}")
    tail = " ".join(out.split()[-25:])
    return f"live scan+import ok :: {tail}"


def step_discovery() -> str:
    """Run discovery_run for career_ops + freshness sources."""
    code, out = run_cmd(
        [PY, "scripts/discovery_run.py", "--sources", "career_ops,freshness"],
        REPO,
        # we already hold .hermes/ops.lock — don't self-deadlock
        extra_env={"HERMES_OPS_LOCK_HELD": "1"})
    if code != 0:
        # l1/l2-style skips are fine; discovery_run returns 1 only on real fail
        raise RuntimeError(f"discovery_run exit={code}: {out[-300:]}")
    summary = [ln for ln in out.splitlines() if ln.startswith("discovery_")]
    return summary[-1] if summary else "ok"


def step_hiring_posts_note() -> str:
    """Verify hiring_posts.csv readability; count recent rows."""
    if not POSTS_CSV.exists():
        return "no hiring_posts.csv yet (cron will create it)"
    rows = _read_csv(POSTS_CSV)
    cutoff = (date.today() - timedelta(days=1)).isoformat()
    recent = sum(1 for r in rows
                 if (r.get("discovered_date") or "") >= cutoff)
    return f"hiring_posts.csv readable: {len(rows)} total, {recent} since {cutoff} " \
           f"(ingestion itself runs via the existing 4x/day cron)"


def step_score() -> str:
    """Score unscored/open job rows via canonical scorer."""
    code, out = run_cmd([PY, "scripts/score_jobs_v2.py"], REPO)
    if code != 0:
        raise RuntimeError(f"score_jobs_v2 exit={code}: {out[-300:]}")
    tail = " ".join(out.strip().splitlines()[-1:] or ["ok"])
    return f"scoring ok :: {tail}"


def step_today_queue() -> str:
    """Rebuild execution_results/reviews review CSVs."""
    code, out = run_cmd([PY, "scripts/today_queue.py"], REPO)
    if code != 0:
        raise RuntimeError(f"today_queue exit={code}: {out[-300:]}")
    return f"review CSVs rebuilt in execution_results/reviews/"


# ---------------------------------------------------------------------------
# Digest compilation (step 6)
# ---------------------------------------------------------------------------

def _job_age_days(row: dict) -> str:
    for key in ("date_posted", "date_discovered"):
        raw = (row.get(key) or "").strip()[:10]
        if not raw:
            continue
        try:
            posted = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        return f"{(date.today() - posted).days}d old"
    return "age unknown"


def digest_new_jobs(limit: int = 10) -> list[str]:
    """Digest contract (docs/workflows/DAILY_RHYTHM.md): each line shows
    fit tier + why (explanation) + age + action + score, ranked by
    priority_v2."""
    rows = _read_csv(TOP_QUEUE_CSV)
    scored = {}
    sj = config_lib.path("scored_jobs_json")
    if sj.exists():
        try:
            scored = {s["job_id"]: s for s in json.loads(sj.read_text())}
        except (ValueError, KeyError):
            scored = {}
    lines = []
    for r in rows[:limit]:
        s = scored.get(r.get("job_id", ""), {})
        tier = r.get("fit_tier") or s.get("level") or "?"
        why = s.get("explanation") or r.get("matching_strengths") or "no explanation"
        why = why.replace("\n", " ")[:160]
        lines.append(
            f"- **{tier}** [{r.get('priority_v2', '?')}] "
            f"{r.get('company', '?')} — {r.get('title', '?')} "
            f"({r.get('recommended_action') or s.get('action') or ''}, "
            f"{_job_age_days(r)}) — why: {why} — "
            f"{r.get('canonical_application_url') or r.get('job_url') or ''}".rstrip())
    return lines


def digest_people() -> list[str]:
    lines = []
    reqs = _read_csv(REQ_CSV)
    STATUS_KEY = ("send_status(pending|approved|sent_no_note|"
                  "sent_with_note|connected|declined|failed)")
    counts = Counter((r.get(STATUS_KEY) or r.get("send_status") or "?").strip()
                     for r in reqs)
    lines.append(
        "- connection_requests: pending={pending} approved={approved} "
        "sent={sent} connected={connected}".format(
            pending=counts.get("pending", 0), approved=counts.get("approved", 0),
            sent=counts.get("sent_no_note", 0) + counts.get("sent_with_note", 0),
            connected=counts.get("connected", 0)))
    # Detailed queue with LinkedIn note + email draft per person.
    lines += digest_people_detailed(reqs, STATUS_KEY)
    # Poster sweep dry-run summary (default mode is dry: queue build only).
    p = subprocess.run([PY, "scripts/poster_connect_sweep.py"],
                       cwd=str(REPO), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    tail = " ".join(out.strip().splitlines()[-3:]) if out.strip() \
        else "(no output)"
    if p.returncode != 0:
        tail = f"poster sweep failed exit={p.returncode}: {tail[:200]}"
    lines.append(f"- poster sweep dry-run: {tail}")
    return lines


def _email_for(name: str, company: str) -> str:
    """Look up an email in contacts.csv by name (+ company when available)."""
    for c in _read_csv(config_lib.path("contacts_csv")):
        if (c.get("name") or "").strip().lower() == name.strip().lower():
            if not company or \
                    (c.get("company") or "").strip().lower() == company.strip().lower():
                return (c.get("email") or "").strip()
    return ""


def _email_draft(row: dict, note: str) -> str:
    """Build a short referral-outreach email from the LinkedIn note draft."""
    ident = config_lib.identity()
    name = (row.get("person_name") or "there").split()[0]
    company = row.get("company") or "your company"
    jobs = (row.get("related_job_ids") or "").replace(";", ", ") or "(role TBD)"
    sig = ident.get("signature_name") or ident.get("full_name") or ""
    school = ident.get("school") or ""
    background = ident.get("headline_background") or \
        "a machine learning engineer"
    return (
        f"Subject: {school} student interested in {company} roles\n\n"
        f"Hi {name},\n\n"
        f"I'm {background}. I noticed openings at {company} ({jobs}) and it "
        f"would be great to connect — if you're open to it, I'd value your "
        f"advice or a referral.\n\n"
        f"Resume on request. Thank you!\n\n"
        f"{sig}\n"
        f"{school} | {ident.get('email', '')}\n\n"
        f"(adapted from LinkedIn note: {note[:140]})")


def digest_people_detailed(reqs: list[dict], status_key: str) -> list[str]:
    """Per-person block for every non-sent request: LinkedIn note + email
    draft (email address resolved from contacts.csv when known)."""
    lines = []
    for r in reqs:
        st = (r.get(status_key) or r.get("send_status") or "?").strip()
        if st in ("sent_no_note", "sent_with_note", "connected", "declined"):
            continue
        name = r.get("person_name") or "?"
        company = r.get("company") or "?"
        ptype = r.get("person_type") or ""
        url = r.get("linkedin_url") or r.get("source_post_url") or ""
        note = (r.get("note_draft") or "").strip()
        email = (r.get("email") or "").strip() or _email_for(name, company)
        lines.append(f"- **{name}** — {ptype} @ {company} [{st}]")
        if url:
            lines.append(f"  - profile/post: {url}")
        if note:
            lines.append(f"  - LinkedIn note: \"{note}\"")
        if email:
            lines.append(f"  - email: {email}")
            lines.append("  - email draft:")
            lines += [f"    > {ln}".rstrip()
                      for ln in _email_draft(r, note).splitlines()]
        else:
            lines.append("  - email: (not found — LinkedIn note above is the "
                         "primary channel)")
    return lines


def digest_applications() -> list[str]:
    lines = []
    apps = _read_csv(APPS_CSV)
    ready = [a for a in apps
             if (a.get("status") or "").strip() == "ready_to_apply"]
    lines.append(f"- awaiting GO / fill-plan approval: {len(ready)}")
    for a in ready[:10]:
        lines.append(f"  - {a.get('company', '?')} — {a.get('role', '?')} "
                     f"(job_id={a.get('job_id', '?')})")
    return lines


def digest_status_changes(since: date) -> list[str]:
    lines = []
    iso = since.isoformat()
    new_jobs = [j for j in _read_csv(JOBS_CSV)
                if (j.get("date_discovered") or "") >= iso]
    lines.append(f"- new jobs discovered since {iso}: {len(new_jobs)}")
    for j in new_jobs[:5]:
        lines.append(f"  - {j.get('company')} — {j.get('title')}")
    apps_changed = [a for a in _read_csv(APPS_CSV)
                    if (a.get("date_last_status_change") or "") >= iso]
    lines.append(f"- application rows with status change since {iso}: "
                 f"{len(apps_changed)}")
    for a in apps_changed[:5]:
        lines.append(f"  - {a.get('company')} — {a.get('role')} -> "
                     f"{a.get('status')} ({a.get('current_stage', '')})")
    return lines


def digest_health() -> list[str]:
    lines = []
    health = load_health()
    paused = [(s, e) for s, e in sorted(health.items())
              if isinstance(e, dict) and e.get("status") == "self-paused"]
    streaky = [(s, e) for s, e in sorted(health.items())
               if isinstance(e, dict) and int(e.get("failure_streak") or 0) > 0
               and e.get("status") != "self-paused"]
    if paused:
        lines += [f"- PAUSED: {s} (failure_streak={e.get('failure_streak')})"
                  for s, e in paused]
    else:
        lines.append("- no sources paused")
    lines += [f"- watch: {s} failure_streak={e.get('failure_streak')}"
              for s, e in streaky]
    alerts_log = config_lib.path("ops_dir") / "alerts.log"
    if alerts_log.exists():
        tail = alerts_log.read_text().splitlines()[-5:]
        lines += [f"- alert log: {ln}" for ln in tail]
    return lines


def build_digest(statuses: list[tuple[str, str, str]], today: date) -> str:
    """statuses: list of (step, status(ok/fail/skip), note)."""
    yesterday = today - timedelta(days=1)
    dts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"# Morning Digest — {today.isoformat()}",
         f"_generated {dts} by scripts/daily_ops.py_", "",
         "## Cycle steps", ""]
    L += [f"- {name}: **{st}** — {note}" for name, st, note in statuses]

    L += ["", "## New jobs worth eyes", ""]
    nj = digest_new_jobs()
    L += nj or ["- none"]

    L += ["", "## People to connect", ""]
    L += digest_people()

    L += ["", "## Applications needing action (awaiting your GO)", ""]
    L += digest_applications()

    L += ["", f"## Status changes since {yesterday.isoformat()}", ""]
    L += digest_status_changes(yesterday)

    L += ["", "## System health", ""]
    L += digest_health()

    L += ["", "---",
          "**STOP: nothing consequential ran.** Approvals, connection sends, "
          "and application submissions wait for explicit user input "
          "(see docs/workflows/DAILY_OPS_WORKFLOW.md).", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------

STEPS = [
    ("career_ops_scan_import", step_career_ops),
    ("discovery_sweeps", step_discovery),
    ("hiring_posts_note", step_hiring_posts_note),
    ("score_unscored", step_score),
    ("rebuild_today_queue", step_today_queue),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the planned steps and exit")
    args = ap.parse_args(argv)

    if args.dry_run:
        print("daily_ops plan (DRY-RUN):")
        for i, (name, fn) in enumerate(STEPS, 1):
            print(f"  {i}. {name}: would run -> {fn.__doc__ or name}")
        print(f"  6. compile_morning_digest: would write "
              f"execution_results/digests/digest_{date.today().isoformat()}.md "
              f"and print it")
        print("  7. STOP — waits for user input.")
        print("dry-run: nothing executed.")
        return 0

    today = date.today()
    statuses: list[tuple[str, str, str]] = []
    with OpsLock():
        for name, fn in STEPS:
            print(f"\n=== daily_ops: {name} ===")
            try:
                note = fn()
                statuses.append((name, "ok", str(note)))
                print(f"[{name}] ok :: {note}")
            except Exception as exc:  # noqa: BLE001 — per-step isolation
                statuses.append((name, "fail", f"{type(exc).__name__}: {exc}"))
                print(f"[{name}] FAIL :: {type(exc).__name__}: {exc}")

        print("\n=== daily_ops: compile_morning_digest ===")
        try:
            digest = build_digest(statuses, today)
            DIGEST_DIR.mkdir(parents=True, exist_ok=True)
            out_path = DIGEST_DIR / f"digest_{today.isoformat()}.md"
            out_path.write_text(digest)
            statuses.append(("compile_morning_digest", "ok", str(out_path)))
            print(digest)
            print(f"\ndigest written: {out_path.relative_to(REPO)}")
        except Exception as exc:  # noqa: BLE001
            statuses.append(("compile_morning_digest", "fail",
                             f"{type(exc).__name__}: {exc}"))
            print(f"[compile_morning_digest] FAIL :: {exc}")

    fails = [s for s in statuses if s[1] == "fail"]
    print(f"\ndaily_ops done: {len(statuses) - len(fails)}/{len(statuses)} "
          f"steps ok. STOPPING — awaiting user input.")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
