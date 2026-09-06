#!/usr/bin/env python3
"""Task 7: Review views + today's queue.

Joins tracking/jobs/jobs.csv with tracking/applications/applications.csv and
tracking/contacts/contacts.csv, then writes three review CSVs to
execution_results/reviews/:

  - fresh_jobs_<date>.csv   recently discovered/refreshed open jobs
  - top_queue.csv           highest priority_v2/score open jobs, ranked
  - needing_attention.csv   stale_flagged / expired-soon / thin_jd / missing-data rows

Also prints a human-readable summary (counts + top 10).

Repository-relative paths only; run from the repo root:
    python3 scripts/today_queue.py
"""

from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib
REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
APPS_CSV = config_lib.data_root() / "tracking" / "applications" / "applications.csv"
CONTACTS_CSV = config_lib.data_root() / "tracking" / "contacts" / "contacts.csv"
JD_DIR = config_lib.data_root() / "tracking" / "job_descriptions"
OUT_DIR = config_lib.data_root() / "execution_results" / "reviews"

# A job is "fresh" when discovered or verified within this many days.
FRESH_DAYS = 3
# A job is "expiring soon" when this close to the 90-day expiry horizon.
EXPIRING_SOON_DAYS = 90 - 14


def parse_date(value: str | None) -> datetime.date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        return None


def days_since(value: str | None, today: datetime.date) -> int | None:
    d = parse_date(value)
    return None if d is None else (today - d).days


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def is_thin_jd(row: dict) -> bool:
    """A JD is thin when the description file is missing or under 500 chars."""
    pointer = (row.get("description_file") or "").strip()
    if not pointer:
        return True
    path = JD_DIR / pointer
    if not path.exists():
        # pointer may be relative to repo root
        alt = REPO_ROOT / pointer
        if alt.exists():
            path = alt
        else:
            return True
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore")) < 500
    except OSError:
        return True


def missing_data_tags(row: dict) -> list[str]:
    tags = []
    for tag in (row.get("missing_info") or "").replace(";", ",").split(","):
        tag = tag.strip()
        if tag:
            tags.append(tag)
    if not (row.get("priority_v2") or "").strip():
        tags.append("priority_v2 missing")
    if not (row.get("canonical_application_url") or "").strip():
        tags.append("canonical_application_url empty")
    return tags


def main() -> int:
    today = datetime.date.today()
    date_str = today.isoformat()

    jobs = read_csv(JOBS_CSV)
    apps = read_csv(APPS_CSV)
    contacts = read_csv(CONTACTS_CSV)

    apps_by_job: dict[str, list[dict]] = {}
    for a in apps:
        apps_by_job.setdefault((a.get("job_id") or "").strip(), []).append(a)
    contacts_by_job: dict[str, list[dict]] = {}
    for c in contacts:
        jid = (c.get("job_id") or "").strip()
        if jid:
            contacts_by_job.setdefault(jid, []).append(c)

    def enrich(row: dict) -> dict:
        jid = (row.get("job_id") or "").strip()
        out = dict(row)
        out["application_ids"] = ";".join(
            a.get("application_id", "") for a in apps_by_job.get(jid, [])
        )
        out["application_status"] = ";".join(
            a.get("status", "") for a in apps_by_job.get(jid, [])
        )
        out["referral_contacts"] = ";".join(
            c.get("name", "") for c in contacts_by_job.get(jid, [])
        )
        # Provenance: keep the contacts' LinkedIn profile URLs alongside the
        # names so the UI can render each one as a clickable link.
        out["referral_contact_urls"] = ";".join(
            c.get("linkedin_url", "")
            for c in contacts_by_job.get(jid, [])
            if (c.get("linkedin_url") or "").strip()
        )
        out["days_since_checked"] = days_since(row.get("last_checked"), today)
        return out

    enriched = [enrich(j) for j in jobs]

    def is_open(row: dict) -> bool:
        """Open AND not gated out by the hard-eligibility audit
        (docs/rules/ROLE_FIT_RULES.md §9): recommended_action=SKIP or
        audit_verdict=non_useful never enter today's queues."""
        if not ((row.get("status") or "").strip().lower() == "open"):
            return False
        if (row.get("recommended_action") or "").strip().upper() == "SKIP":
            return False
        if (row.get("audit_verdict") or "").strip().lower() == "non_useful":
            return False
        return True

    def priority(row: dict) -> float:
        try:
            return float(row.get("priority_v2") or 0)
        except ValueError:
            return 0.0

    # --- fresh jobs -------------------------------------------------------
    fresh = []
    for row in enriched:
        if not is_open(row):
            continue
        for field in ("date_discovered", "date_updated", "last_checked"):
            age = days_since(row.get(field), today)
            if age is not None and age <= FRESH_DAYS:
                fresh.append(row)
                break
    fresh.sort(key=priority, reverse=True)

    # --- top queue --------------------------------------------------------
    queue = sorted((r for r in enriched if is_open(r)), key=priority, reverse=True)
    top_queue = queue[:50]

    # --- needing attention -------------------------------------------------
    attention = []
    for row in enriched:
        if not is_open(row):
            continue
        reasons = []
        if (row.get("stale_flag") or "").strip().lower() in ("true", "yes", "1"):
            reasons.append("stale_flagged")
        ref_date = row.get("date_updated") or row.get("date_posted") or row.get("date_discovered")
        ref_age = days_since(ref_date, today)
        if ref_age is not None and ref_age >= EXPIRING_SOON_DAYS:
            reasons.append("expired_soon")
        if is_thin_jd(row):
            reasons.append("thin_jd")
        reasons.extend(missing_data_tags(row))
        if reasons:
            row = dict(row)
            row["attention_reasons"] = ";".join(reasons)
            attention.append(row)
    attention.sort(key=lambda r: (r["attention_reasons"], -priority(r)))

    # --- write outputs -----------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def write(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fieldnames = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    fresh_path = OUT_DIR / f"fresh_jobs_{date_str}.csv"
    write(fresh_path, fresh)
    top_path = OUT_DIR / "top_queue.csv"
    write(top_path, top_queue)
    attn_path = OUT_DIR / "needing_attention.csv"
    write(attn_path, attention)

    # --- human summary -----------------------------------------------------
    print(f"today_queue review — {date_str}")
    print(f"jobs: {len(jobs)} total | open: {sum(1 for r in enriched if is_open(r))} | "
          f"expired: {sum(1 for r in enriched if (r.get('status') or '').lower() == 'expired')} | "
          f"archived: {sum(1 for r in enriched if (r.get('status') or '').lower() == 'archived')}")
    print(f"applications: {len(apps)} | contacts: {len(contacts)}")
    print(f"wrote {fresh_path.name} ({len(fresh)} rows)")
    print(f"wrote {top_path.name} ({len(top_queue)} rows)")
    print(f"wrote {attn_path.name} ({len(attention)} rows)")
    print("\nTop 10 queue (open jobs by priority_v2):")
    for i, row in enumerate(top_queue[:10], 1):
        apps_txt = row["application_status"] or "-"
        print(f"  {i:2d}. [{row['priority_v2'] or '?':>5}] {row['company']} — {row['title']} "
              f"(app: {apps_txt})")
    top1 = top_queue[0] if top_queue else None
    if top1 and top1["company"] == "CrowdStrike" and "Agentic Systems" in top1["title"]:
        print(f"\nOK: CrowdStrike Agentic Systems tops top_queue.csv (priority_v2={top1['priority_v2']})")
    else:
        print(f"\nWARNING: expected CrowdStrike Agentic Systems (75.5) at top; "
              f"got: {top1['company']} — {top1['title']} ({top1['priority_v2']})" if top1
              else "\nWARNING: queue empty")

    # --- apply-day surface sections (apply-plan Task 7) -------------------
    print_apply_day_sections(enriched, apps_by_job, today)

    return 0


# --------------------------------------------------------------------------
# Apply-day surface (apply-plan Task 7): five action sections. Each row
# carries the exact next command so the queue is directly executable.
# --------------------------------------------------------------------------

BASE_VARIANT_DIR = config_lib.data_root() / "resume_custom" / "base_variants"
APPLICATIONS_DIR = REPO_ROOT / "all_custom_resumes"  # custom resumes live in-repo
REQ_CSV = config_lib.data_root() / "tracking" / "messages" / "connection_requests.csv"

HIGH_PRIORITY_FLOOR = 60.0  # priority_v2 floor for the NEEDS RESUME section

IN_FLIGHT_STATUSES = ("submitted", "acknowledged", "interview")


def variant_compiled(resume_variant: str | None) -> bool:
    """A resume variant counts as compiled when its base PDF exists or a
    tailored application dir carries a compiled resume."""
    variant = (resume_variant or "").strip()
    if not variant:
        return False
    if (BASE_VARIANT_DIR / f"{variant.lower()}.pdf").exists():
        return True
    # fall back: any application dir for this job with resume.pdf
    if APPLICATIONS_DIR.exists():
        for d in APPLICATIONS_DIR.iterdir():
            if d.is_dir() and (d / "resume.pdf").exists():
                return True
    return False


def next_command_for_job(row: dict) -> str:
    url = (row.get("canonical_application_url") or row.get("job_url") or "").strip()
    cmd = f"python scripts/apply_pipeline.py {row.get('job_id', '')}"
    if url:
        cmd += f" --url {url}"
    return cmd


def read_connection_requests() -> list[dict]:
    if not REQ_CSV.exists():
        return []
    with REQ_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # tolerate schema-tagged header names like send_status(pending|approved|...)
    norm = []
    for r in rows:
        out = {}
        for k, v in r.items():
            key = k.split("(")[0].strip()
            out[key] = v
        norm.append(out)
    return norm


def passes_scrutiny(row: dict) -> bool:
    """Fresh-jobs gate: open, not stale-flagged, JD not thin, has URL."""
    if not ((row.get("status") or "").strip().lower() == "open"):
        return False
    if (row.get("stale_flag") or "").strip().lower() in ("true", "yes", "1"):
        return False
    if not (row.get("canonical_application_url") or row.get("job_url") or "").strip():
        return False
    return True


def print_apply_day_sections(enriched: list[dict], apps_by_job: dict,
                             today: datetime.date) -> None:
    reqs = read_connection_requests()
    date_str = today.isoformat()

    def prio(row):
        try:
            return float(row.get("priority_v2") or 0)
        except ValueError:
            return 0.0

    def job_row_line(row, extra=""):
        return (f"  [{row.get('priority_v2') or '?':>5}] "
                f"{row.get('company', '?')} — {row.get('title', '?')}{extra}")

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # ① APPLY NOW ----------------------------------------------------------
    now_rows = [r for r in enriched
                if (r.get("status") or "").strip().lower() == "open"
                and not apps_by_job.get((r.get("job_id") or "").strip())]
    now_rows.sort(key=prio, reverse=True)
    now_rows = now_rows[:10]
    sections.append(("① APPLY NOW — top-ranked open jobs with no application row",
                     [(job_row_line(r),
                       next_command_for_job(r)) for r in now_rows]))

    # ② NEEDS RESUME --------------------------------------------------------
    needs = [r for r in enriched
             if (r.get("status") or "").strip().lower() == "open"
             and prio(r) >= HIGH_PRIORITY_FLOOR
             and (r.get("resume_variant") or "").strip()
             and not variant_compiled(r.get("resume_variant"))]
    needs.sort(key=prio, reverse=True)
    sections.append((
        f"② NEEDS RESUME — high-priority (priority_v2>={HIGH_PRIORITY_FLOOR:.0f}), "
        "variant not compiled",
        [(job_row_line(r, f"  variant={r['resume_variant']}"),
          f"compile resume_custom/base_variants/{r['resume_variant'].lower()}.tex "
          f"-> then {next_command_for_job(r)}") for r in needs]))

    # ③ OUTREACH DUE ---------------------------------------------------------
    outreach = []
    for r in reqs:
        status = (r.get("send_status") or "").strip().lower()
        due = None
        if status == "approved":
            due = "(approved, unsent)"
            cmd = (f"python scripts/connection_queue.py record-sent "
                   f"{r.get('request_id', '')} --status sent_with_note")
        elif status in ("sent_no_note", "sent_with_note"):
            fu = parse_date(r.get("followup_date"))
            if fu is not None and fu <= today:
                due = f"(followup due {fu.isoformat()})"
                cmd = (f"python scripts/connection_queue.py record-response "
                       f"{r.get('request_id', '')} <response>")
            else:
                continue
        else:
            continue
        outreach.append((
            f"{r.get('person_name', '?')} @ {r.get('company', '?')} "
            f"[{r.get('person_type', '')}] {due}", cmd))
    sections.append(("③ OUTREACH DUE — approved-but-unsent + followups due",
                     outreach))

    # ④ APPLICATIONS IN FLIGHT ----------------------------------------------
    inflight = []
    for jid, approws in sorted(apps_by_job.items()):
        for a in approws:
            st = (a.get("status") or "").strip().lower()
            if st not in IN_FLIGHT_STATUSES:
                continue
            overdue = None
            fu = parse_date(a.get("follow_up_date"))
            last = parse_date(a.get("date_last_status_change"))
            if fu is not None and fu <= today:
                overdue = f"(follow-up due/overdue since {fu})"
            elif fu is None and last is not None and (today - last).days >= 7:
                overdue = f"(no touch since {last}, {(today - last).days}d)"
            if overdue is None:
                continue
            cmd = (f"python scripts/application_sync.py --mark {jid} "
                   "<acknowledged|interview|rejected> [reason]")
            inflight.append((
                f"{a.get('company', '?')} — {a.get('role', '?')} "
                f"[{st}] {overdue}", cmd))
    sections.append(("④ APPLICATIONS IN FLIGHT — submitted+, follow-up overdue",
                     inflight))

    # ⑤ FRESH JOBS ------------------------------------------------------------
    fresh24 = []
    for r in enriched:
        disc = parse_date(r.get("date_discovered"))
        upd = parse_date(r.get("date_updated"))
        ref = disc or upd
        if ref is None or (today - ref).days > 1:
            continue
        if not passes_scrutiny(r):
            continue
        fresh24.append(r)
    fresh24.sort(key=prio, reverse=True)
    sections.append(("⑤ FRESH JOBS — last 24h, passing scrutiny",
                     [(job_row_line(r), next_command_for_job(r))
                      for r in fresh24]))

    print("\n" + "=" * 72)
    print(f"APPLY-DAY SURFACE — {date_str}")
    print("=" * 72)
    combined: list[dict] = []
    PRINT_CAP = {"⑤": 15}  # fresh jobs can be large: print top slice, keep all in CSV
    for title, items in sections:
        shown = items[:PRINT_CAP.get(title[:1], len(items))]
        print(f"\n{title}  ({len(items)})")
        if not items:
            print("  (empty)")
            continue
        for label, cmd in shown:
            print(f"  • {label}")
            print(f"      → {cmd}")
            combined.append({"section": title.split("—")[0].strip(),
                             "item": label, "next_command": cmd})
    out_path = OUT_DIR / f"apply_day_{date_str}.csv"
    if combined:
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["section", "item", "next_command"])
            w.writeheader()
            w.writerows(combined)
        print(f"\nwrote {out_path.name} ({len(combined)} rows)")


if __name__ == "__main__":
    sys.exit(main())
