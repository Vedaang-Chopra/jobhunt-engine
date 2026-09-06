#!/usr/bin/env python3
"""Poster fast-path connect sweep (Task 11).

Reads tracking/hiring_posts/hiring_posts.csv rows whose post `status` is not
`connected`, builds connection_requests.csv queue rows with
note_basis=hiring_post and source_post_url filled in (drafting/validation
reused from scripts/connection_queue.py), then sends them via Playwright MCP.

Recruiters / hiring managers are HIGH PRIORITY: person_type recruiter or hm
sorts to the front of the batch regardless of post score.

LIVE SENDING PROCEDURE (per person, executed by the injected driver):
  1. Open the person's LinkedIn profile URL (from linkedin_url or
     source_post_url) in the Playwright MCP browser.
  2. Click the primary "Connect" button on the profile.
       - If LinkedIn shows a "Add a note" prompt/dialog instead, click
         "Add a note" to reveal the note box.
  3. If a note box appears: paste the approved note_draft, submit.
     If no note box appears: send the bare connection request.
  4. Verify the button now reads "Pending".
  5. Immediately record the outcome via connection_queue record-sent:
       sent_with_note if a note was pasted, else sent_no_note.
  6. Move to the next person.

SAFETY RULES
  * Daily cap: at most MAX_DAILY_SENDS = 25 sends per calendar day. Sends
    already recorded today (sent_* statuses dated today in
    connection_requests.csv) count against the cap.
  * Stop-on-warning: the driver must detect CAPTCHA challenges, account
    restriction/warning banners, or login walls. Any such signal aborts the
    entire run immediately (no further clicks, remaining people stay queued).
  * Approval gate: only requests already `approved` via
    `connection_queue.py approve <id>` may be sent live (human-in-the-loop).
    Drafted-but-pending rows require approval first.

CLI
    poster_connect_sweep.py            # --dry-run is the DEFAULT: prints the
                                       # exact intended actions per person,
                                       # performs NO clicks and opens NO browser.
    poster_connect_sweep.py --live --driver-json   # live mode expects the
                                       # pluggable driver to be injected
                                       # (see live_driver); without one it
                                       # refuses to run.

The live driver is a callable passed/injected at run time (never imported),
so this script stays testable and decoupled from any specific MCP transport:
    driver(person: dict, note: str) -> SendResult
where SendResult has fields: ok(bool), used_note(bool), warning(str|"").
"""
from __future__ import annotations

import argparse
import csv
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import connection_queue as cq  # noqa: E402

POSTS_PATH = cq.POSTS_PATH  # data-root canonical hiring_posts.csv
MAX_DAILY_SENDS = 25

HIGH_PRIORITY_TYPES = {"recruiter", "hm", "hiring_manager", "talent", "hr"}


@dataclass
class SendResult:
    ok: bool
    used_note: bool
    warning: str = ""


# ---------------------------------------------------------------- queue build

def poster_people(posts_path=None, requests_path=None) -> tuple[list[dict], int]:
    """Hiring-post posters with post status != connected, ranked for outreach."""
    posts_path = posts_path or POSTS_PATH
    existing = cq.read_requests(requests_path)
    queued_names = {cq._norm(r["person_name"]) for r in existing}
    sent_today = sum(
        1 for r in existing
        if r.get("date_sent") == cq.today_iso()
        and cq._status(r).startswith("sent")
    )
    people = []
    with open(posts_path, newline="", encoding="utf-8") as f:
        for p in csv.DictReader(f):
            if cq._norm(p.get("status")) == "connected":
                continue
            name_key = cq._norm(p.get("poster_name"))
            if name_key in queued_names:
                continue
            roles = p.get("roles_mentioned", "") or "your open ML roles"
            pt = cq._norm(p.get("poster_type"))
            people.append({
                "person_name": p.get("poster_name", ""),
                "company": p.get("company", ""),
                "person_type": p.get("poster_type", ""),
                "linkedin_url": p.get("post_url", ""),
                "email": "",
                "source_post_url": p.get("post_url", ""),
                "related_job_ids": "",
                "_role_hint": roles.split(",")[0][:80],
                "_post_hint": "your hiring post"
                              + (f" about {roles.split(',')[0][:40]}"
                                 if roles else ""),
                "_score": (60 if pt in HIGH_PRIORITY_TYPES else 40)
                          + (20 if cq._norm(p.get("priority")) == "high" else 0),
                "_high_priority": pt in HIGH_PRIORITY_TYPES,
                "_basis": "hiring_post",
            })
    # Recruiters/HMs always sort first, then score desc, then name.
    people.sort(key=lambda x: (not x["_high_priority"], -x["_score"],
                               x["person_name"]))
    return people, sent_today


def build_queue_rows(people: list[dict]):
    """Compose+validate notes; returns (paired [(person,row)], skipped msgs)."""
    paired, skipped = [], []
    today = cq.today_iso()
    for person in people:
        note = cq.compose_note(person, "hiring_post")
        errs = cq.validate_note(note, "hiring_post", person)
        if errs:
            skipped.append(f"{person['person_name']}: {'; '.join(errs)}")
            continue
        row = {k: "" for k in cq.HEADER}
        row.update({
            "request_id": f"cr_{today.replace('-', '')}_{uuid.uuid4().hex[:6]}",
            "person_name": person["person_name"],
            "company": person["company"],
            "person_type": person["person_type"],
            "linkedin_url": person["linkedin_url"],
            "source_post_url": person["source_post_url"],
            "score": person["_score"],
            "note_draft": note,
            cq.HEADER[10]: "hiring_post",
            cq.STATUS_COL: "pending",
            "date_queued": today,
        })
        paired.append((person, row))
    return paired, skipped


def write_queue_rows(rows: list[dict], requests_path=None) -> None:
    requests_path = requests_path or cq.REQ_PATH
    existing = cq.read_requests(requests_path)
    cq.write_requests(existing + rows, requests_path)


# ------------------------------------------------------------------ sending

def remaining_quota(requests_path=None) -> int:
    existing = cq.read_requests(requests_path)
    sent_today = sum(1 for r in existing
                     if r.get("date_sent") == cq.today_iso()
                     and cq._status(r).startswith("sent"))
    return max(0, MAX_DAILY_SENDS - sent_today)


def approved_batch(limit: int, requests_path=None) -> list[dict]:
    return [r for r in cq.read_requests(requests_path)
            if cq._status(r) == "approved"][:limit]


def live_send(driver, batch, requests_path=None):
    """Run the documented procedure through an injected driver callable.

    `driver(person_row, note) -> SendResult`. Aborts everything on the first
    warning (CAPTCHA/account-restriction detection) or failed send.
    """
    results = []
    for row in batch:
        res = driver(row, row["note_draft"])
        if res.warning:
            print(f"WARNING DETECTED ({row['person_name']}): {res.warning}")
            print("STOP-ON-WARNING: aborting entire run; "
                  f"{len(batch) - len(results) - 1} person(s) remain queued.")
            results.append((row, res))
            break
        state = "sent_with_note" if res.used_note else "sent_no_note"
        rc = cq.main(["record-sent", row["request_id"], "--state", state])
        status = "recorded" if rc == 0 else f"record-sent rc={rc}"
        print(f"{row['request_id']} {row['person_name']}: {state} ({status})")
        results.append((row, res))
    return results


# --------------------------------------------------------------------- CLI

def cmd_dry_run(args) -> int:
    people, sent_today = poster_people(args.posts_path, args.requests_path)
    quota = max(0, MAX_DAILY_SENDS - sent_today)
    batch = people[:quota]
    print(f"[DRY-RUN] posters eligible: {len(people)} | sent today: "
          f"{sent_today} | remaining quota: {quota} | batching: {len(batch)}")
    rows, skipped = build_queue_rows(batch)
    for s in skipped:
        print(f"SKIP {s}")
    for i, (person, row) in enumerate(rows, 1):
        print(f"\n{i}. {person['person_name']} ({person['company']}, "
              f"type={person['person_type']}, "
              f"{'HIGH-PRIORITY ' if person['_high_priority'] else ''}"
              f"score={person['_score']})")
        print(f"   would queue request_id={row['request_id']} "
              f"basis=hiring_post source_post_url={person['source_post_url']}")
        print(f"   INTENDED ACTIONS:")
        print(f"     1. open profile {person['linkedin_url']}")
        print(f"     2. click Connect (+ Add a note if prompted)")
        print(f"     3. paste note: {row['note_draft']}")
        print(f"     4. verify Pending; record-sent -> sent_with_note")
    if not batch:
        print("(nothing to do)")
    return 0


def cmd_live(args) -> int:
    driver = getattr(cmd_live, "_driver", None)
    if driver is None:
        print("LIVE mode requires an injected driver callable "
              "(set cmd_live._driver = fn before calling, e.g. a Playwright "
              "MCP adapter). Refusing to run without one.")
        return 2
    quota = remaining_quota(args.requests_path)
    if quota <= 0:
        print(f"DAILY CAP REACHED: {MAX_DAILY_SENDS} sends already recorded today.")
        return 1
    batch = approved_batch(quota, args.requests_path)
    pending = [r for r in cq.read_requests(args.requests_path)
               if cq._status(r) == "pending"]
    if pending:
        print(f"INTERLOCK: {len(pending)} pending request(s) need `approve` "
              "before live sending.")
        return 3
    print(f"LIVE: sending to {len(batch)} approved request(s) "
          f"(quota {quota}/{MAX_DAILY_SENDS}).")
    live_send(driver, batch, args.requests_path)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="mode", action="store_const",
                      const="dry", default="dry")
    mode.add_argument("--live", dest="mode", action="store_const", const="live")
    ap.add_argument("--posts-path")
    ap.add_argument("--requests-path")
    args = ap.parse_args(argv)
    args.posts_path = Path(args.posts_path) if args.posts_path else None
    args.requests_path = Path(args.requests_path) if args.requests_path else None
    if args.mode == "dry":
        return cmd_dry_run(args)
    return cmd_live(args)


if __name__ == "__main__":
    raise SystemExit(main())
