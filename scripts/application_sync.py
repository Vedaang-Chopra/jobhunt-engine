#!/usr/bin/env python3
"""Task 6: post-submission application sync loop.

Subcommands (mutually exclusive):

  --mark <job_id> <status> [reason]
      Manually mark an application row in
      tracking/applications/applications.csv. Allowed statuses:
      submitted / acknowledged / rejected / interview / withdrawn.
      Sets date_last_status_change=today; rejection also records
      rejection_reason; interview sets follow_up_date=+7d;
      acknowledgment fills date_acknowledged when empty.
      Human-in-the-loop: this command only ever runs on explicit request.

  --check-portals
      For every application with status=submitted, cheap-GET the canonical
      URL (status code only). 404 or a redirect that lands off the posting
      -> flagged possibly_closed; login-walled responses (401/403 or a
      known login-host redirect) -> flagged needs_manual. Flags are written
      to the notes column only -- the status is NEVER changed automatically.

  --suggest-followups
      Print suggested follow-up drafts for submitted applications with no
      acknowledgment for >=14 days. NEVER sends anything.

Lock: .hermes/ops.lock prevents concurrent runs from double-writing.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import sys
import typing
import urllib.error
import urllib.request
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib
REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_CSV = config_lib.data_root() / "tracking" / "applications" / "applications.csv"
LOCK_FILE = REPO_ROOT / ".hermes" / "ops.lock"

VALID_STATUSES = ("submitted", "acknowledged", "rejected", "interview", "withdrawn")
FOLLOWUP_AFTER_DAYS = 14
LOGIN_WALL_CODES = {401, 403}
# Hosts that signal a login wall rather than a public job page.
LOGIN_HOST_MARKERS = ("login", "signin", "auth", "myworkdayjobs.com/login")


def parse_date(value: str | None) -> datetime.date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        return None


def read_apps(path: Path = APPS_CSV) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_apps(rows: list[dict], path: Path = APPS_CSV) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def add_note(row: dict, note: str) -> None:
    """Append a dated flag to the notes column without touching status."""
    stamp = datetime.date.today().isoformat()
    tag = f"[portal-check:{stamp}] {note}"
    existing = (row.get("notes") or "").strip()
    row["notes"] = f"{existing} | {tag}" if existing else tag


# ---------------------------------------------------------------- transitions
def mark_status(row: dict, status: str, today: datetime.date,
                reason: str | None = None) -> list[str]:
    """Apply a manual status transition to one application row.

    Returns a list of human-readable change descriptions. Raises ValueError
    for unknown statuses or invalid transitions (e.g. marking withdrawn on
    a row still queued).
    """
    status = (status or "").strip().lower()
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; must be one of {', '.join(VALID_STATUSES)}")

    current = (row.get("status") or "").strip().lower()
    changes: list[str] = []
    jid = row.get("job_id") or row.get("application_id") or "?"

    # Guard: lifecycle statuses only make sense from queued/ready_to_apply onward
    # for submitted, and from an active pipeline for the rest.
    if status == "submitted":
        if current in ("rejected", "withdrawn"):
            raise ValueError(f"{jid}: cannot re-submit from status {current!r}")
    elif current in ("queued", "ready_to_apply", ""):
        raise ValueError(
            f"{jid}: cannot move {current or 'empty'!r} directly to "
            f"{status!r}; mark it submitted first")

    row["status"] = status
    row["date_last_status_change"] = today.isoformat()
    changes.append(f"status {current or '(empty)'} -> {status}")

    if status == "submitted":
        if not (row.get("date_submitted") or "").strip():
            row["date_submitted"] = today.isoformat()
            changes.append(f"date_submitted={row['date_submitted']}")
    elif status == "acknowledged":
        if not (row.get("date_acknowledged") or "").strip():
            row["date_acknowledged"] = today.isoformat()
            changes.append(f"date_acknowledged={row['date_acknowledged']}")
    elif status == "rejected":
        if not reason:
            raise ValueError(f"{jid}: rejection requires a reason argument")
        row["rejection_reason"] = reason
        changes.append(f"rejection_reason={reason}")
    elif status == "interview":
        followup = today + datetime.timedelta(days=7)
        row["follow_up_date"] = followup.isoformat()
        changes.append(f"follow_up_date={followup.isoformat()} (+7d)")
    elif status == "withdrawn":
        if reason:
            row["notes"] = ((row.get("notes") or "").rstrip(" |")
                            + (" | " if row.get("notes") else "")
                            + f"withdrawn: {reason}").lstrip(" |")
            changes.append(f"note: withdrawn reason recorded")

    row["current_stage"] = status
    return changes


# ---------------------------------------------------------------- portal check
def check_url(url: str, timeout: float = 15.0) -> dict:
    """Cheap GET returning {'code', 'final_url'}; network errors are captured."""
    result: dict = {"code": None, "final_url": url}
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "Mozilla/5.0 (portal-check)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["code"] = resp.status
            result["final_url"] = resp.geturl()
    except urllib.error.HTTPError as exc:
        result["code"] = exc.code
        result["final_url"] = exc.geturl() or url
    except (urllib.error.URLError, OSError, ValueError) as exc:
        result["code"] = f"error:{type(exc).__name__}"
    return result


def classify_portal_check(url: str, res: dict) -> str:
    """Map a check result to a flag: ok | possibly_closed | needs_manual.

    Never returns a directive to change status -- ambiguity always resolves
    to needs_manual.
    """
    code = res.get("code")
    if code is None or isinstance(code, str):
        return "needs_manual"
    final_url = (res.get("final_url") or "").lower()
    if code in LOGIN_WALL_CODES:
        return "needs_manual"
    if any(marker in final_url for marker in LOGIN_HOST_MARKERS):
        return "needs_manual"
    if code == 404:
        return "possibly_closed"
    if code in (301, 302, 303, 307, 308):
        # Redirected somewhere else: if it left the original posting path,
        # treat as possibly_closed only when it landed on a listing root;
        # otherwise ambiguous -> needs_manual.
        orig_path = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        if orig_path and orig_path not in final_url.split("?")[0]:
            return "possibly_closed"
        return "needs_manual"
    if 200 <= code < 300:
        return "ok"
    return "needs_manual"


# --------------------------------------------------------------- follow-ups
def followup_candidates(rows: list[dict], today: datetime.date) -> list[dict]:
    """Submitted rows with no acknowledgment for >= FOLLOWUP_AFTER_DAYS days."""
    out = []
    for r in rows:
        if (r.get("status") or "").strip().lower() != "submitted":
            continue
        if (r.get("date_acknowledged") or "").strip():
            continue
        d = parse_date(r.get("date_submitted"))
        if d is None or (today - d).days < FOLLOWUP_AFTER_DAYS:
            continue
        r = dict(r)
        r["_days_waiting"] = (today - d).days
        out.append(r)
    out.sort(key=lambda r: -r["_days_waiting"])
    return out


def draft_followup(row: dict) -> str:
    role = row.get("role") or "the role"
    company = row.get("company") or "your team"
    name = (row.get("referral_contact") or "").strip() or "Hiring Team"
    return (
        f"Subject: Following up — {role} application\n\n"
        f"Hi {name},\n\n"
        f"I wanted to follow up on my application for the {role} position at "
        f"{company}, submitted on {row.get('date_submitted')}. I remain very "
        f"interested in the role and would be glad to provide any additional "
        f"material.\n\nThank you for your time,\n"
    )


# ------------------------------------------------------------------ locking
class OpsLock:
    def __init__(self, path: Path = LOCK_FILE):
        self.path = path
        self._fh: "typing.TextIO" = open("/dev/null")

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")
        import fcntl
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._fh.close()
            raise RuntimeError("another ops run holds .hermes/ops.lock")
        return self

    def __exit__(self, *exc):
        import fcntl
        try:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
        except Exception:
            pass
        self._fh.close()
        return False


# ---------------------------------------------------------------------- CLI
def cmd_mark(args) -> int:
    rows = read_apps()
    idx = next((i for i, r in enumerate(rows)
                if (r.get("job_id") or "").strip() == args.job_id.strip()), None)
    if idx is None:
        print(f"ERROR: no application row for job_id {args.job_id}", file=sys.stderr)
        return 2
    today = datetime.date.today()
    try:
        with OpsLock():
            changes = mark_status(rows[idx], args.status, today, args.reason)
            write_apps(rows)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"marked {args.job_id}:")
    for c in changes:
        print(f"  - {c}")
    return 0


def cmd_check_portals(args) -> int:
    rows = read_apps()
    submitted = [r for r in rows
                 if (r.get("status") or "").strip().lower() == "submitted"]
    if not submitted:
        print("no submitted applications to check")
        return 0
    dirty = False
    counts = {"ok": 0, "possibly_closed": 0, "needs_manual": 0}
    for row in submitted:
        url = (row.get("job_url") or "").strip()
        if not url:
            counts["needs_manual"] += 1
            print(f"- {row.get('job_id')}: NO URL -> needs_manual")
            continue
        res = check_url(url)
        flag = classify_portal_check(url, res)
        counts[flag] += 1
        line = f"- {row.get('job_id')}: HTTP {res.get('code')} -> {flag}"
        if flag == "possibly_closed":
            add_note(row, f"possibly_closed (HTTP {res.get('code')}, "
                          f"landed: {res.get('final_url')})")
            dirty = True
            line += " (NOTED; status NOT changed)"
        elif flag == "needs_manual":
            add_note(row, f"needs_manual (HTTP {res.get('code')}; "
                          "login wall or ambiguous response)")
            dirty = True
            line += " (NOTED; verify manually)"
        print(line)
    if dirty and not args.dry_run:
        with OpsLock():
            write_apps(rows)
    print(f"\nsummary: {counts['ok']} ok | {counts['possibly_closed']} "
          f"possibly_closed | {counts['needs_manual']} needs_manual "
          "(statuses never auto-changed)")
    return 0


def cmd_suggest_followups(args) -> int:
    today = datetime.date.today()
    cands = followup_candidates(read_apps(), today)
    if not cands:
        print(f"no follow-ups due (no submitted application waiting "
              f">= {FOLLOWUP_AFTER_DAYS} days without acknowledgment)")
        return 0
    print(f"{len(cands)} follow-up(s) suggested (DRAFTS ONLY — nothing is sent):\n")
    for r in cands:
        print(f"=== {r.get('job_id')} ({r['_days_waiting']}d waiting) ===")
        print(draft_followup(r))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--mark", nargs="+", metavar=("JOB_ID", "STATUS_REASON"),
                   help="<job_id> <status> [reason]")
    g.add_argument("--check-portals", action="store_true")
    g.add_argument("--suggest-followups", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="(with --check-portals) do not persist notes")
    args = p.parse_args(argv)

    if args.mark is not None:
        if len(args.mark) < 2:
            p.error("--mark requires <job_id> <status> [reason]")
        args.job_id = args.mark[0]
        args.status = args.mark[1]
        args.reason = args.mark[2] if len(args.mark) > 2 else None
        return cmd_mark(args)
    if args.check_portals:
        return cmd_check_portals(args)
    return cmd_suggest_followups(args)


if __name__ == "__main__":
    sys.exit(main())
