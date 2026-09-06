#!/usr/bin/env python3
"""Connection-request queue with customized notes (Task 10).

CLI:
    connection_queue.py list
    connection_queue.py draft [--company NAME] [--limit N]
    connection_queue.py approve REQUEST_ID
    connection_queue.py record-sent REQUEST_ID {sent_no_note,sent_with_note}
    connection_queue.py record-connected REQUEST_ID
    connection_queue.py record-replied REQUEST_ID --response TEXT

Ledger semantics: rows are never deleted; statuses move forward only
(pending -> approved -> sent_* -> connected/declined/failed); dates are
immutable once stamped. Interlocks:
  * draft refuses to run while any queued request is still `approved`
    (the previous batch must be record-sent first);
  * record-sent requires status `approved`.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib  # noqa: E402
except ImportError:
    import config_lib  # noqa: E402

# Canonical CSVs live under the data root (JOBHUNT_HOME / config.yaml pointer),
# NOT inside the repo tree (data-isolation rule).
DATA_ROOT = config_lib.data_root()
REQ_PATH = DATA_ROOT / "tracking" / "messages" / "connection_requests.csv"
CONTACTS_PATH = DATA_ROOT / "tracking" / "contacts" / "contacts.csv"
POSTS_PATH = DATA_ROOT / "tracking" / "hiring_posts" / "hiring_posts.csv"

HEADER = [
    "request_id", "person_name", "company", "person_type", "linkedin_url",
    "email", "source_post_url", "related_job_ids", "score", "note_draft",
    "note_basis(hiring_post|shared_ctx|job_specific|generic)",
    "send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)",
    "date_queued", "date_sent", "date_connected", "response", "followup_date",
    "notes",
]

BASIS_VALUES = ["hiring_post", "shared_ctx", "job_specific", "generic"]
STATUS_VALUES = ["pending", "approved", "sent_no_note", "sent_with_note",
                 "connected", "declined", "failed"]

MAX_NOTE_LEN = 300
BANNED_CLAIMS = re.compile(r"\b(RLHF|DPO|SFT)\b", re.IGNORECASE)
IDENTITY_TOKENS = {
    "school": ["Georgia Tech", "GT"],
    "experience": ["Fortinet"],
}
# contacts.csv outreach_status values meaning the person was already touched.
TOUCHED_STATUSES = {"requested", "connected", "contacted", "responded"}

CANDIDATE_FACTS = (
    "MS CS student at Georgia Tech with ~4.5 years of production ML "
    "experience at Fortinet"
)

# One note style per person_type bucket.
STYLE_BY_TYPE = {
    "recruiter": "recruiter",
    "talent": "recruiter",
    "hr": "recruiter",
    "engineer_researcher": "engineer",
    "engineer": "engineer",
    "researcher": "engineer",
    "founder": "founder",
    "director": "leader",
    "leader": "leader",
    "engineering leadership": "leader",
    "peer": "peer",
    "intern": "peer",
}


def today_iso() -> str:
    return date.today().isoformat()


def _norm(value) -> str:
    return str(value or "").strip().lower()


STYLE_PRIORITY = [
    ("recruiter", "recruiter"), ("talent", "recruiter"), ("hr", "recruiter"),
    ("founder", "founder"), ("director", "leader"),
    ("engineering leadership", "leader"), ("leader", "leader"),
    ("intern", "peer"), ("peer", "peer"),
    ("engineer_researcher", "engineer"), ("researcher", "engineer"),
    ("engineer", "engineer"),
]


def style_for(person_type: str) -> str:
    pt = _norm(person_type)
    for key, style in STYLE_PRIORITY:
        if key in pt:
            return style
    return "generic"


def compose_note(person: dict, basis: str) -> str:
    """Draft a note honoring one-variant-style-per-person_type."""
    name = person["person_name"].split()[0]
    company = person["company"]
    role = person.get("_role_hint") or "your open ML roles"
    style = style_for(person["person_type"])
    if style == "recruiter":
        note = (f"Hi {name} - I'm a {CANDIDATE_FACTS}, interested in "
                f"{role} at {company}. Would love to connect.")
    elif style == "engineer":
        note = (f"Hi {name} - {CANDIDATE_FACTS}. Interested in {role} on "
                f"your team at {company}; would value connecting.")
    elif style == "leader":
        note = (f"Hi {name} - {CANDIDATE_FACTS}. Very interested in {role} "
                f"at {company}; would appreciate connecting.")
    elif style == "founder":
        note = (f"Hi {name} - {CANDIDATE_FACTS}. Building in AI/security and "
                f"interested in {role}-type work at {company}. Connecting!")
    elif style == "peer":
        note = (f"Hi {name} - fellow Georgia Tech student here ({CANDIDATE_FACTS}"
                f"). Interested in {role} at {company}. Great to connect!")
    else:
        note = (f"Hi {name} - {CANDIDATE_FACTS}. Interested in {role} at "
                f"{company}; would love to connect.")
    if basis == "hiring_post":
        post_hint = person.get("_post_hint") or "your recent hiring post"
        note += f" Re: {post_hint}."
    return note


def validate_note(note: str, basis: str, person: dict) -> list[str]:
    """Return a list of rule violations; empty means valid."""
    errors = []
    if len(note) > MAX_NOTE_LEN:
        errors.append(f"note exceeds {MAX_NOTE_LEN} chars ({len(note)})")
    if BANNED_CLAIMS.search(note):
        errors.append("banned claim present (RLHF/DPO/SFT)")
    if not any(t in note for t in IDENTITY_TOKENS["school"]):
        errors.append("missing honest identity token (Georgia Tech/GT)")
    if not any(t in note for t in IDENTITY_TOKENS["experience"]):
        errors.append("missing experience token (Fortinet)")
    if not re.search(r"\b(interested|value connecting|Connecting|connect)\b",
                     note, re.IGNORECASE):
        errors.append("missing role-interest expression")
    if basis == "hiring_post":
        post_url = person.get("source_post_url") or ""
        hint = person.get("_post_hint") or ""
        tokens = [w for w in re.findall(r"[A-Za-z]{5,}", hint)][:3]
        referenced = ("post" in note.lower()
                      or any(t.lower() in note.lower() for t in tokens))
        if not referenced:
            errors.append("hiring_post basis but their specific post not referenced")
        if not post_url:
            errors.append("hiring_post basis without source_post_url")
    return errors


def read_requests(path=None) -> list[dict]:
    path = path or REQ_PATH
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_requests(rows: list[dict], path=None) -> None:
    path = path or REQ_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


STATUS_COL = HEADER[11]


def _status(row: dict) -> str:
    return row[STATUS_COL]


def _set_status(row: dict, new_status: str) -> None:
    order = STATUS_VALUES
    assert order.index(new_status) >= order.index(_status(row)), \
        "append-only ledger: status may only move forward"
    row[STATUS_COL] = new_status


def load_contacts(path=None) -> list[dict]:
    path = path or CONTACTS_PATH
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_posts(path=None) -> list[dict]:
    path = path or POSTS_PATH
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _score_contact(row: dict) -> int:
    score = 50
    rel = _norm(row.get("outreach_priority") or "")
    score += 30 if rel == "p1" else 10 if rel == "p2" else 0
    ctx = _norm(row.get("shared_context"))
    if "georgia tech" in ctx or "gt" in ctx.split():
        score += 15
    if "1st" == _norm(row.get("relationship")):
        score += 20
    elif "2nd" == _norm(row.get("relationship")):
        score += 10
    return score


def _job_titles(jobs_path=None) -> dict:
    path = jobs_path or (config_lib.path("jobs_csv"))
    titles = {}
    if not path.exists():
        return titles
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            jid = r.get("job_id") or ""
            title = r.get("title") or r.get("job_title") or ""
            if jid and title:
                titles[jid] = title
    return titles


def candidate_pool(company=None, contacts_path=None, posts_path=None, requests_path=None) -> list[dict]:
    contacts_path = contacts_path or CONTACTS_PATH
    posts_path = posts_path or POSTS_PATH
    requests_path = requests_path or REQ_PATH
    """Untouched contacts + hiring-post posters not already queued/touched."""
    pool: dict[tuple[str, str], dict] = {}
    existing = read_requests(requests_path)
    queued_keys = {_norm(r["person_name"]) for r in existing}
    job_titles = _job_titles()

    for c in load_contacts(contacts_path):
        status = _norm(c.get("outreach_status"))
        name_key = _norm(c.get("name"))
        if status in TOUCHED_STATUSES or name_key in queued_keys:
            continue
        if company and _norm(company) not in _norm(c.get("company")):
            continue
        person = {
            "person_name": c.get("name", ""),
            "company": c.get("company", ""),
            "person_type": c.get("role", ""),
            "linkedin_url": c.get("linkedin_url", ""),
            "email": c.get("email", ""),
            "source_post_url": "",
            "related_job_ids": c.get("job_id", ""),
            "_role_hint": job_titles.get(_norm(c.get("job_id")))
                          or c.get("reason_to_contact", "")[:60].split(";")[0]
                          or "your open ML roles",
            "_score": _score_contact(c),
            "_basis": "shared_ctx" if _norm(c.get("shared_context")) else "job_specific"
                      if c.get("job_id") else "generic",
        }
        pool[(name_key, _norm(person["company"]))] = person

    for p in load_posts(posts_path):
        name_key = _norm(p.get("poster_name"))
        if name_key in queued_keys or name_key in {_norm(x["person_name"])
                                                   for x in pool.values()}:
            continue
        if company and _norm(company) not in _norm(p.get("company")):
            continue
        roles = p.get("roles_mentioned", "") or "your open ML roles"
        person = {
            "person_name": p.get("poster_name", ""),
            "company": p.get("company", ""),
            "person_type": p.get("poster_type", ""),
            "linkedin_url": "",
            "email": "",
            "source_post_url": p.get("post_url", ""),
            "related_job_ids": "",
            "_role_hint": roles.split(",")[0][:80] or "your open ML roles",
            "_post_hint": ("your hiring post" + (
                f" about {roles.split(',')[0][:40]}" if roles else "")),
            "_score": 40 + (20 if _norm(p.get("priority")) == "high" else 0),
            "_basis": "hiring_post",
        }
        pool.setdefault((name_key, _norm(person["company"])), person)

    ranked = sorted(pool.values(), key=lambda x: -x["_score"])
    return ranked


def cmd_draft(args) -> int:
    existing = read_requests()
    unbatched_approved = [r for r in existing if _status(r) == "approved"]
    if unbatched_approved:
        print("INTERLOCK: %d approved request(s) not yet record-sent. Run "
              "`record-sent` before drafting the next batch:" % len(unbatched_approved))
        for r in unbatched_approved:
            print(f"  {r['request_id']} {r['person_name']}")
        return 2

    pool = candidate_pool(args.company)
    limit = args.limit
    batch = pool[:limit]
    if not batch:
        print("No eligible candidates to draft.")
        return 1

    rows = list(existing)
    queued = []
    today = today_iso()
    for i, person in enumerate(batch):
        note = compose_note(person, person["_basis"])
        errs = validate_note(note, person["_basis"], person)
        if errs:
            print(f"SKIP {person['person_name']}: {'; '.join(errs)}")
            continue
        rid = f"cr_{today.replace('-', '')}_{uuid.uuid4().hex[:6]}"
        row = {k: "" for k in HEADER}
        row.update({
            "request_id": rid,
            "person_name": person["person_name"],
            "company": person["company"],
            "person_type": person["person_type"],
            "linkedin_url": person["linkedin_url"],
            "email": person["email"],
            "source_post_url": person["source_post_url"],
            "related_job_ids": person["related_job_ids"],
            "score": person["_score"],
            "note_draft": note,
            HEADER[10]: person["_basis"],
            STATUS_COL: "pending",
            "date_queued": today,
        })
        rows.append(row)
        queued.append((rid, person, note))

    write_requests(rows)
    print(f"Queued {len(queued)} of {len(batch)} candidates.\n")
    for rid, person, note in queued:
        print(f"{rid} | {person['person_name']} ({person['company']}, "
              f"{person['person_type']}, basis={person['_basis']}, "
              f"score={person['_score']})")
        print(f"  note ({len(note)} chars): {note}\n")
    return 0


def _find(rows: list[dict], rid: str) -> dict:
    for r in rows:
        if r["request_id"] == rid:
            return r
    raise SystemExit(f"request_id not found: {rid}")


def cmd_approve(args) -> int:
    rows = read_requests()
    row = _find(rows, args.request_id)
    if _status(row) != "pending":
        raise SystemExit(f"approve requires pending status, got {_status(row)}")
    _set_status(row, "approved")
    row["notes"] = (row["notes"] + "; " if row["notes"] else "") + \
                   f"approved {today_iso()}"
    write_requests(rows)
    print(f"approved {row['request_id']} ({row['person_name']})")
    return 0


def cmd_record_sent(args) -> int:
    rows = read_requests()
    row = _find(rows, args.request_id)
    if _status(row) != "approved":
        print("INTERLOCK: record-sent requires prior approval "
              f"(got '{_status(row)}') — run `approve` first")
        return 3
    if args.state not in ("sent_no_note", "sent_with_note"):
        print("--state must be sent_no_note or sent_with_note")
        return 2
    if args.state == "sent_with_note" and not row["note_draft"]:
        print("sent_with_note requires a note_draft")
        return 2
    _set_status(row, args.state)
    row["date_sent"] = today_iso()
    followup = datetime.strptime(today_iso(), "%Y-%m-%d").replace(day=1)
    row["followup_date"] = args.followup_date or ""
    write_requests(rows)
    print(f"{args.state} {row['request_id']} on {row['date_sent']}")
    return 0


def cmd_record_connected(args) -> int:
    rows = read_requests()
    row = _find(rows, args.request_id)
    if not row["date_sent"]:
        print("record-connected requires a recorded send (date_sent)")
        return 3
    _set_status(row, "connected")
    row["date_connected"] = today_iso()
    write_requests(rows)
    print(f"connected {row['request_id']} on {row['date_connected']}")
    return 0


def cmd_record_replied(args) -> int:
    rows = read_requests()
    row = _find(rows, args.request_id)
    if not row["date_sent"]:
        print("record-replied requires a recorded send (date_sent)")
        return 3
    row["response"] = args.response
    if _status(row) in ("pending", "approved"):
        _set_status(row, "sent_with_note" if row["note_draft"] else "sent_no_note")
    write_requests(rows)
    print(f"replied {row['request_id']}: {args.response}")
    return 0


def cmd_list(args) -> int:
    rows = read_requests()
    if not rows:
        print("(empty queue)")
        return 0
    for r in rows:
        print(f"{r['request_id']} | {r['person_name']:28s} | "
              f"{r['company']:12s} | {_status(r):14s} | q={r['date_queued']} "
              f"s={r['date_sent']} c={r['date_connected']} | "
              f"{r[HEADER[10]]} | jobs={r['related_job_ids']} "
              f"post={r['source_post_url']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    d = sub.add_parser("draft")
    d.add_argument("--company")
    d.add_argument("--limit", type=int, default=5)
    d.set_defaults(fn=cmd_draft)
    a = sub.add_parser("approve"); a.add_argument("request_id")
    a.set_defaults(fn=cmd_approve)
    s = sub.add_parser("record-sent"); s.add_argument("request_id")
    s.add_argument("--state", default="sent_no_note")
    s.add_argument("--followup-date", default="")
    s.set_defaults(fn=cmd_record_sent)
    c = sub.add_parser("record-connected"); c.add_argument("request_id")
    c.set_defaults(fn=cmd_record_connected)
    rp = sub.add_parser("record-replied"); rp.add_argument("request_id")
    rp.add_argument("--response", required=True)
    rp.set_defaults(fn=cmd_record_replied)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
