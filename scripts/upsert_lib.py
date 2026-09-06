#!/usr/bin/env python3
"""upsert_lib — dedup + canonical CSV upserts for the right-people feature.

Task 5 of .hermes/plans/2026-08-27_232352-right-people-feature.md.

Enforces the people_sweep never-twice interlock (BLOCKED_STATUSES =
requested/connected/contacted/responded — a person already touched is NEVER
re-added), matches by normalized linkedin_url with a fuzzy name+company
fallback (reusing referral_lib._fuzzy_same), updates existing non-blocked
rows in place (refresh last_verified, fill-empty-only), and appends new rows
with ``<company_slug>_<seq>`` contact ids sequenced across contacts.csv and
the per-company connections.csv.

CSV conventions mirror the existing repo scripts (connection_queue.py /
people_sweep.py): csv.DictReader/DictWriter opened with newline="" and the
csv-module default \\r\\n line terminator, which matches the real tracking
files. Unknown columns are preserved on update because fieldnames are read
from the file itself.
"""
from __future__ import annotations

import csv
import datetime
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import config_lib
import people_sweep
from people_sweep import BLOCKED_STATUSES
from referral_lib import _fuzzy_same, _slug

REPO = Path(__file__).resolve().parents[1]

# Per-company connections.csv schema (plan §4, exact).
CONNECTIONS_HEADER = [
    "contact_id", "name", "linkedin_url", "company", "title", "location",
    "degree", "relevant_team", "alumni_shared_affiliation", "mutuals",
    "shared_context", "activity_level", "hiring_post_urls", "target_job_ids",
    "reason_to_contact", "recommended_ask", "referral_likelihood",
    "outreach_priority", "email", "email_status", "source", "outreach_status",
    "last_verified",
]

# Real tracking/contacts/contacts.csv header (23 cols, verified from the file).
CONTACTS_HEADER = [
    "contact_id", "name", "company", "role", "relationship", "linkedin_url",
    "email", "job_id", "reason_to_contact", "shared_context",
    "outreach_status", "date_identified", "date_contacted", "followup_date",
    "response", "notes", "email_status", "repair_note", "domain_relevance",
    "referral_likelihood", "outreach_priority", "last_verified_date",
    "email_source",
]

DEFAULT_SOURCE = "right_people"


# ---------------------------------------------------------------- helpers

def _today(value=None) -> datetime.date:
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    return datetime.date.today()


def _norm_url(url: str) -> str:
    """Normalize a profile URL: lowercase scheme/host, strip trailing '/'."""
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path.rstrip("/"), parts.query, parts.fragment))


def _urls_same(a: str, b: str) -> bool:
    from referral_lib import linkedin_slug

    na, nb = _norm_url(a), _norm_url(b)
    if na and na == nb:
        return True
    sa, sb = linkedin_slug(a), linkedin_slug(b)
    return bool(sa) and sa == sb


def _status_of(row: dict, col: str) -> str:
    return (row.get(col) or "").strip().lower()


def _is_blocked(status: str) -> bool:
    return status in BLOCKED_STATUSES


def _load(path, default_header: list[str]) -> tuple[list[str], list[dict]]:
    """Read a CSV -> (fieldnames, rows). Missing/empty file -> default header."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return list(default_header), []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or default_header)
        rows = [dict(r) for r in reader]
    return fieldnames, rows


def _write(path, fieldnames: list[str], rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def _match_row(linkedin_url: str, name: str, company: str,
               rows: list[dict]) -> dict | None:
    """First row matching by normalized URL, else fuzzy name+company."""
    for row in rows:
        if linkedin_url and _urls_same(linkedin_url,
                                       row.get("linkedin_url", "") or ""):
            return row
    for row in rows:
        if name and _fuzzy_same(name, company, row.get("name", "") or "",
                                row.get("company", "") or ""):
            return row
    return None


def _next_seq(slug: str, contact_id_lists) -> int:
    """Next 1-based sequence for ``<slug>_NNN`` across all given id lists."""
    pat = re.compile(rf"^{re.escape(slug)}_(\d+)$")
    mx = 0
    for ids in contact_id_lists:
        for cid in ids:
            m = pat.match(cid or "")
            if m:
                mx = max(mx, int(m.group(1)))
    return mx + 1


def _first_post_url(finding: dict) -> str:
    posts = finding.get("hiring_post_urls") or ""
    if isinstance(posts, (list, tuple)):
        posts = next((p for p in posts if p), "")
    return str(posts or "")


# ---------------------------------------------------------------- public API

def find_existing(linkedin_url: str, name: str, company: str,
                  contacts_path=None, sweep_path=None) -> dict | None:
    """Never-twice lookup: return the blocking existing row, else None.

    Matches by normalized linkedin_url (strip trailing '/', lowercase host)
    with a fuzzy name+company fallback, against contacts.csv and prior
    people_sweep.csv rows. Returns the matched row (plus ``source_file``)
    only when its status is in BLOCKED_STATUSES (contacts rows use
    ``outreach_status``; sweep rows use ``status``) — i.e. the person must
    never be re-added. Non-blocked matches return None here; the upsert
    update-in-place path resolves those internally.
    """
    contacts_path = Path(contacts_path or config_lib.path("contacts_csv"))
    sweep_path = Path(sweep_path or config_lib.path("people_sweep_csv"))
    checks = [
        (contacts_path, "contacts", _load(contacts_path, CONTACTS_HEADER)[1],
         "outreach_status"),
        (sweep_path, "people_sweep",
         _load(sweep_path, people_sweep.COLUMNS)[1], "status"),
    ]
    for path, source, rows, status_col in checks:
        row = _match_row(linkedin_url, name, company, rows)
        if row is not None and _is_blocked(_status_of(row, status_col)):
            out = dict(row)
            out["source_file"] = source
            return out
    return None


def connections_upsert(findings: list[dict], connections_path,
                       today=None) -> dict:
    """Upsert findings into one per-company connections.csv.

    Creates the file with CONNECTIONS_HEADER when absent; dedups by
    linkedin_url with fuzzy name+company fallback; updates non-blocked
    matches in place (refresh ``last_verified``, fill-empty-only); appends
    new rows with company-scoped ``<slug>_<seq>`` contact ids. Never touches
    rows whose outreach_status is blocked.
    """
    today = _today(today)
    iso = today.isoformat()
    path = Path(connections_path)
    fieldnames, rows = _load(path, CONNECTIONS_HEADER)
    counts = {"added": 0, "updated": 0, "skipped_dup": 0}
    for f in findings:
        name = (f.get("name") or "").strip()
        if not name:
            raise ValueError("upsert finding requires a non-empty name")
        company = (f.get("company") or "").strip()
        slug = _slug(company)
        existing = _match_row(f.get("linkedin_url", "") or "", name,
                              company, rows)
        if existing is not None:
            status = _status_of(existing, "outreach_status")
            if _is_blocked(status):
                counts["skipped_dup"] += 1
                continue
            for col in fieldnames:
                if col == "last_verified":
                    existing[col] = iso
                    continue
                val = (f.get(col) or "").strip()
                if val and not (existing.get(col) or "").strip():
                    existing[col] = val
            counts["updated"] += 1
            continue
        seq = _next_seq(slug, [[r.get("contact_id", "") for r in rows]])
        row = {col: "" for col in fieldnames}
        row.update({k: str(f[k]) for k in fieldnames
                    if f.get(k) not in (None, "") and k != "hiring_post_urls"})
        posts = f.get("hiring_post_urls")
        if isinstance(posts, (list, tuple)):
            posts = "; ".join(str(p) for p in posts if p)
        elif posts:
            posts = str(posts)
        if "hiring_post_urls" in fieldnames and posts:
            row["hiring_post_urls"] = posts
        row["contact_id"] = f"{slug}_{seq:03d}"
        row["name"] = name
        row["company"] = company or row.get("company", "")
        row["source"] = (f.get("source") or DEFAULT_SOURCE)
        row["outreach_status"] = (f.get("outreach_status") or "not_contacted")
        row["last_verified"] = iso
        rows.append(row)
        counts["added"] += 1
    if counts["added"] or counts["updated"]:
        _write(path, fieldnames, rows)
    return counts


def upsert_contacts(findings: list[dict], contacts_path=None, sweep_path=None,
                    company_dir=None, today=None) -> dict:
    """Dedup + upsert findings into contacts.csv (+ per-company upserts).

    Returns {"added", "updated", "skipped_dup"}:
    - blocked-status match (contacts ``outreach_status`` or sweep ``status``)
      → skipped entirely: never re-added anywhere → ``skipped_dup``;
    - non-blocked existing contacts row → update in place (refresh
      ``last_verified_date``, fill empty fields only) → ``updated``;
    - otherwise append a new row with ``<company_slug>_<seq:03d>`` contact id
      sequenced across contacts.csv AND the company connections.csv →
      ``added``.

    Every non-skipped finding also (a) upserts the per-company
    ``<company_dir>/connections.csv`` (creating it with CONNECTIONS_HEADER
    when absent) and (b) appends one run row to people_sweep.csv with
    ``sweep_run_id=rp_<YYYYMMDD>_<slug>``, status="new",
    notes="right_people".
    """
    today = _today(today)
    iso = today.isoformat()
    contacts_path = Path(contacts_path or config_lib.path("contacts_csv"))
    sweep_path = Path(sweep_path or config_lib.path("people_sweep_csv"))

    c_fieldnames, c_rows = _load(contacts_path, CONTACTS_HEADER)
    _, s_rows = _load(sweep_path, people_sweep.COLUMNS)
    conn_path = Path(company_dir) / "connections.csv" if company_dir else None
    conn_ids: list[str] = []
    if conn_path is not None and conn_path.exists():
        _, conn_rows = _load(conn_path, CONNECTIONS_HEADER)
        conn_ids = [r.get("contact_id", "") for r in conn_rows]

    counts = {"added": 0, "updated": 0, "skipped_dup": 0}
    sweep_new: list[dict] = []
    passed: list[dict] = []

    for f in findings:
        name = (f.get("name") or "").strip()
        if not name:
            raise ValueError("upsert finding requires a non-empty name")
        company = (f.get("company") or "").strip()
        slug = _slug(company)

        # never-twice interlock against contacts.csv then prior sweep rows
        c_match = _match_row(f.get("linkedin_url", "") or "", name, company,
                             c_rows)
        if c_match is not None:
            status = _status_of(c_match, "outreach_status")
            if _is_blocked(status):
                counts["skipped_dup"] += 1
                continue
            for col in c_fieldnames:
                if col == "last_verified_date":
                    c_match[col] = iso
                    continue
                val = _contacts_value(f, col)
                if val and not (c_match.get(col) or "").strip():
                    c_match[col] = val
            counts["updated"] += 1
        else:
            s_match = _match_row(f.get("linkedin_url", "") or "", name,
                                 company, s_rows)
            if s_match is not None and _is_blocked(
                    _status_of(s_match, "status")):
                counts["skipped_dup"] += 1
                continue
            seq = _next_seq(slug, [
                [r.get("contact_id", "") for r in c_rows], conn_ids])
            row = {col: "" for col in c_fieldnames}
            for col in c_fieldnames:
                val = _contacts_value(f, col)
                if val:
                    row[col] = val
            row["contact_id"] = f"{slug}_{seq:03d}"
            row["name"] = name
            row["company"] = company
            row["outreach_status"] = (f.get("outreach_status")
                                      or "not_contacted")
            row["date_identified"] = iso
            row["last_verified_date"] = iso
            c_rows.append(row)
            counts["added"] += 1

        passed.append(f)
        sweep_new.append({
            "sweep_run_id": f"rp_{today:%Y%m%d}_{slug}",
            "date": iso,
            "name": name,
            "title": f.get("title", ""),
            "company": company,
            "person_type": f.get("person_type", "company_people"),
            "linkedin_url": f.get("linkedin_url", ""),
            "post_url": _first_post_url(f),
            "why_relevant": f.get("reason_to_contact", ""),
            "status": "new",
            "notes": DEFAULT_SOURCE,
        })

    if counts["added"] or counts["updated"]:
        _write(contacts_path, c_fieldnames, c_rows)
    if sweep_new:
        people_sweep.append_rows(sweep_new, sweep_path)
    if conn_path is not None and passed:
        connections_upsert(passed, conn_path, today=today)
    return counts


def _contacts_value(finding: dict, col: str) -> str:
    """Map a finding key onto a contacts.csv column (empty when unmapped)."""
    aliases = {
        "role": "title",
        "relationship": "degree",
    }
    key = aliases.get(col, col)
    val = finding.get(key)
    if val in (None, ""):
        return ""
    if isinstance(val, (list, tuple)):
        val = "; ".join(str(v) for v in val if v)
    return str(val).strip()


if __name__ == "__main__":
    raise SystemExit("upsert_lib is a library; import it from right_people.py")
