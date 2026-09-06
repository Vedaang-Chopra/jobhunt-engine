"""right_people_ingest — ingest pipeline, ranking report, draft staging.

Right-people plan Tasks 7-9 (.hermes/plans/2026-08-27_232352-right-people-feature.md).

Architecture (canonical repo pattern from people_sweep.py): browser
extraction is AGENT-DRIVEN — the orchestrating agent extracts raw person rows
from LinkedIn (keys: name, title, company, location, linkedin_url,
degree/relationship like "1st"/"2nd", post_url/hiring_post_urls, snippet,
school, mutuals) and hands them to ``run_ingest``. This module owns every
decision: never-twice dedup BEFORE inspection, weighted scoring, the
inspection cap, canonical CSV upserts, the ranked Markdown report, the
human-gated P0/P1 draft queue, and the single search_runs.csv run row.

Nothing here sends a message: ``queue_drafts`` only ever appends
``send_status=pending`` rows to the connection_requests ledger.

Public surface::

    run_ingest(target, rows, cap=12, today=None, contacts_path=None,
               sweep_path=None, company_dir=None) -> dict
    render_report(target, results, today=None) -> str
    queue_drafts(results, ledger_path, today=None, job_ids="") -> list[dict]
    log_search_run(target, results, summary=None, path=None, run_id=None,
                   today=None) -> dict
"""
from __future__ import annotations

import csv
import re
import uuid
from datetime import date as _date
from pathlib import Path

import config_lib
import scoring_lib
import upsert_lib
from upsert_lib import find_existing, upsert_contacts

try:  # connection_queue imports cleanly (module-level code only sets paths)
    import connection_queue
except ImportError:  # pragma: no cover - repo layout guarantees import
    connection_queue = None

REPO = Path(__file__).resolve().parents[1]

# tracking/search_runs/search_runs.csv header (read from the real file).
SEARCH_RUNS_HEADER = [
    "run_id", "date", "sources", "queries", "total_scanned",
    "new_jobs_found", "duplicates_skipped", "strong_fits", "notes",
]

SOURCE_NAME = "right_people_ingest"

# Heuristic keyword tables (rule 05 / REFERRAL_RESEARCH_WORKFLOW shared ctx).
_GT_TOKENS = ("georgia tech", "georgia-tech", " gatech", "gt alumni")
_FORTINET_TOKENS = ("fortinet",)
_US_TOKENS = ("united states", "remote-us", "remote - us", "remote us", "usa")
_RECRUITER_TOKENS = ("recruiter", "talent", "sourcer")
_MANAGER_TOKENS = ("manager", "lead", "director", "head ")


def _today(value=None) -> _date:
    if isinstance(value, _date):
        return value
    if isinstance(value, str):
        return _date.fromisoformat(value)
    return _date.today()


# ------------------------------------------------------------- normalization

def _norm_degree(raw: dict) -> str:
    for key in ("degree", "relationship", "connection_degree"):
        val = (raw.get(key) or "").strip().lower()
        if not val:
            continue
        if val.startswith("1") or "first" in val:
            return "1st"
        if val.startswith("2") or "second" in val:
            return "2nd"
        if val.startswith("3") or "third" in val:
            return "3rd"
    return "unknown"


def _posts_list(raw) -> list:
    posts = raw.get("hiring_post_urls") or raw.get("post_url") or ""
    if isinstance(posts, (list, tuple)):
        return [str(p).strip() for p in posts if str(p).strip()]
    posts = str(posts).strip()
    return [posts] if posts else []


def _mutuals_list(raw) -> list:
    val = raw.get("mutuals")
    if val in (None, "", []):
        return []
    if isinstance(val, (list, tuple)):
        return [str(v).strip() for v in val if str(v).strip()]
    text = str(val)
    m = re.search(r"(\d+)", text)
    if m:
        return [""] * int(m.group(1))
    return [p.strip() for p in text.split(",") if p.strip()]


def _haystack(raw) -> str:
    parts = [raw.get(k) or "" for k in
             ("snippet", "school", "education", "history", "why_relevant",
              "notes")]
    return " ".join(str(p) for p in parts).lower()


def _gt_alumni(raw, haystack: str) -> bool:
    for key in ("source_pass", "pass_family", "family", "pass_id"):
        if "gt_alumni" in str(raw.get(key) or "").lower():
            return True
    return any(tok in haystack for tok in _GT_TOKENS)


def _us_based(location: str) -> bool:
    loc = (location or "").lower()
    if not loc:
        return False
    if any(tok in loc for tok in _US_TOKENS):
        return True
    # bare country token: ", US" / "US" as its own word
    return re.search(r"\bus\b", loc) is not None


def normalize_row(raw: dict, target: dict, today=None) -> dict:
    """Map one agent-extracted raw row onto the scoring/person contract.

    Extends the people_sweep.normalize_person contract (name/title/company/
    linkedin_url/post_url/notes) with the scoring fields: degree, mutuals,
    hiring_post_urls, activity_level, and the boolean signal inputs.
    """
    today = _today(today)
    name = (raw.get("name") or "").strip()
    if not name:
        raise ValueError("ingest row requires a non-empty name")
    title = (raw.get("title") or "").strip()
    location = (raw.get("location") or "").strip()
    posts = _posts_list(raw)
    haystack = _haystack(raw)
    title_l = title.lower()
    return {
        "name": name,
        "title": title,
        "company": (raw.get("company") or target.get("company") or "").strip(),
        "location": location,
        "linkedin_url": (raw.get("linkedin_url") or "").strip(),
        "degree": _norm_degree(raw),
        "mutuals": _mutuals_list(raw),
        "hiring_post_urls": posts,
        "activity_level": ("active_poster" if posts
                           else (raw.get("activity_level") or "unknown")),
        "gt_alumni": _gt_alumni(raw, haystack),
        "fortinet_overlap": any(tok in haystack for tok in _FORTINET_TOKENS),
        "us_based": _us_based(location),
        "is_recruiter": any(tok in title_l for tok in _RECRUITER_TOKENS),
        "is_hiring_manager": any(tok in title_l for tok in _MANAGER_TOKENS),
        "job_id": ((target.get("job") or {}).get("job_id") or ""),
        "date": today.isoformat(),
    }


# ------------------------------------------------------------------- scoring

def _reason_to_contact(p: dict) -> str:
    parts = []
    if p["degree"] != "unknown":
        parts.append(f"{p['degree']}-degree connection")
    if p["gt_alumni"]:
        parts.append("Georgia Tech alumni")
    if p["fortinet_overlap"]:
        parts.append("Fortinet overlap")
    named = [m for m in p["mutuals"] if m]
    if named:
        parts.append("mutuals: " + ", ".join(named[:3]))
    if p["is_hiring_manager"]:
        parts.append("hiring manager / team lead")
    if p["is_recruiter"]:
        parts.append("recruiter")
    if p["hiring_post_urls"]:
        parts.append("active hiring poster")
    if p["us_based"]:
        parts.append("US-based")
    return "; ".join(parts) if parts else "works at target company"


def _shared_context(p: dict) -> str:
    parts = []
    if p["gt_alumni"]:
        parts.append("Georgia Tech alumni")
    if p["fortinet_overlap"]:
        parts.append("Fortinet overlap")
    named = [m for m in p["mutuals"] if m]
    if named:
        parts.append("mutuals: " + ", ".join(named[:3]))
    return "; ".join(parts)


def _likelihood(score: int) -> str:
    if score >= 20:
        return "high"
    if score >= 12:
        return "medium"
    return "low"


# --------------------------------------------------------------- run_ingest

def run_ingest(target, rows, cap=12, today=None, contacts_path=None,
               sweep_path=None, company_dir=None) -> dict:
    """Full ingest pipeline for agent-extracted rows (pure, tmp-path testable).

    Per row: normalize -> never-twice dedup check BEFORE inspection ->
    weighted scoring -> cap-gated inspection flag -> canonical upserts.
    Returns {"results": [...], "summary": {...}}; results are ranked
    (non-skipped by score desc, then skipped dups in input order).
    """
    today = _today(today)
    people = [normalize_row(raw, target, today=today) for raw in rows]

    results = []
    qualified = []
    for p in people:
        blocked = find_existing(
            p["linkedin_url"], p["name"], p["company"],
            contacts_path=contacts_path, sweep_path=sweep_path)
        scored = scoring_lib.score_person(p)
        if blocked is not None:
            status = (blocked.get("outreach_status")
                      or blocked.get("status") or "unknown").strip()
            source = blocked.get("source_file", "")
            results.append({
                **p, **scored,
                "skipped": True,
                "dup_reason": f"{source}: {status}".strip(": "),
                "inspected": False,
                "inspect_pending": False,
                "reason_to_contact": "",
            })
            continue
        reason = _reason_to_contact(p)
        qualified.append({
            **p, **scored,
            "skipped": False,
            "dup_reason": "",
            "reason_to_contact": reason,
            "shared_context": _shared_context(p),
            "referral_likelihood": _likelihood(scored["score"]),
        })
        results.append(None)  # placeholder, replaced after ranking

    # Cap gates inspection only — everyone is still ingested and scored.
    ranked = sorted(qualified, key=lambda r: -r["score"])
    inspected_names = set()
    for r in ranked[:max(int(cap), 0)]:
        r["inspected"] = True
        r["inspect_pending"] = False
        inspected_names.add(r["name"])
    for r in ranked[max(int(cap), 0):]:
        r["inspected"] = False
        r["inspect_pending"] = True

    results = [r if r is not None else qualified.pop(0) for r in results]
    results = sorted(
        results,
        key=lambda r: (r["skipped"], -r["score"]))  # dups sink to the end

    findings = []
    for r in results:
        if r["skipped"]:
            continue
        findings.append({
            "name": r["name"],
            "company": r["company"],
            "title": r["title"],
            "location": r["location"],
            "linkedin_url": r["linkedin_url"],
            "degree": r["degree"],
            "shared_context": r["shared_context"],
            "activity_level": r["activity_level"],
            "hiring_post_urls": r["hiring_post_urls"],
            "reason_to_contact": r["reason_to_contact"],
            "recommended_ask": r["ask"],
            "outreach_priority": r["priority"],
            "referral_likelihood": r["referral_likelihood"],
            "job_id": r["job_id"],
            "source": SOURCE_NAME,
        })
    counts = upsert_contacts(
        findings, contacts_path=contacts_path, sweep_path=sweep_path,
        company_dir=company_dir, today=today)

    summary = {
        "added": counts["added"],
        "updated": counts["updated"],
        # dups are filtered BEFORE upsert, so count them from our own results
        "skipped_dup": sum(1 for r in results if r["skipped"]),
        "inspected": sum(1 for r in results
                         if not r["skipped"] and r["inspected"]),
    }
    return {"results": results, "summary": summary}


# ------------------------------------------------------------- render_report

def _bullet(r: dict) -> str:
    bits = [f"**{r['name']}**",
            f"{r['title'] or '?'} @ {r['company'] or '?'}",
            f"score {r['score']}"]
    if r.get("degree") and r["degree"] != "unknown":
        bits.append(r["degree"])
    if r.get("ask"):
        bits.append(r["ask"])
    if r.get("reason_to_contact"):
        bits.append(r["reason_to_contact"])
    if r.get("activity_level") == "active_poster" or r.get("hiring_post_urls"):
        bits.append("active_poster")
    if r.get("linkedin_url"):
        bits.append(r["linkedin_url"])
    if r.get("inspect_pending"):
        bits.append("(inspection pending — over cap)")
    return "- " + " | ".join(bits)


def render_report(target, results, today=None) -> str:
    """Ranked Markdown report: header, P0→P3 sections, skipped dups at end."""
    today = _today(today)
    company = target.get("company") or "?"
    slug = target.get("company_slug") or "?"
    lines = [f"# Right people — {company} (slug: {slug}) — {today.isoformat()}",
             ""]
    live = [r for r in results if not r.get("skipped")]
    for band in ("P0", "P1", "P2", "P3"):
        section = [r for r in live if r.get("priority") == band]
        if not section:
            continue
        lines.append(f"## {band}")
        lines.append("")
        lines.extend(_bullet(r) for r in section)
        lines.append("")
    dups = [r for r in results if r.get("skipped")]
    if dups:
        lines.append("## Skipped (never-twice duplicates)")
        lines.append("")
        for r in dups:
            lines.append(f"- {r['name']} ({r['company'] or '?'}) — "
                         f"dup: {r.get('dup_reason') or 'already touched'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# -------------------------------------------------------------- queue_drafts

def _note_basis(r: dict) -> str:
    """note_basis precedence: hiring_post > shared_ctx > job_specific > generic."""
    if r.get("hiring_post_urls"):
        return "hiring_post"
    if r.get("gt_alumni") or r.get("fortinet_overlap") or r.get("mutuals"):
        return "shared_ctx"
    if r.get("job_id"):
        return "job_specific"
    return "generic"


def queue_drafts(results, ledger_path, today=None, job_ids="") -> list:
    """Stage P0/P1 non-skipped results as PENDING connection requests.

    Human-gated: rows are appended with send_status=pending and a validated
    note_draft (honest Georgia Tech / Fortinet identity tokens via
    connection_queue.compose_note). NOTHING is ever sent here. Idempotent:
    people already in the ledger are not re-staged.
    """
    today = _today(today)
    if connection_queue is None:  # pragma: no cover
        raise RuntimeError("connection_queue is not importable")
    existing = connection_queue.read_requests(ledger_path)
    known = {(connection_queue._norm(r["person_name"]),
              connection_queue._norm(r["linkedin_url"])) for r in existing}
    status_col = connection_queue.STATUS_COL
    basis_col = connection_queue.HEADER[10]
    rows = list(existing)
    staged = []
    for r in results:
        if r.get("skipped") or r.get("priority") not in ("P0", "P1"):
            continue
        key = (connection_queue._norm(r["name"]),
               connection_queue._norm(r.get("linkedin_url") or ""))
        if key in known:
            continue
        basis = _note_basis(r)
        source_post = next(iter(r.get("hiring_post_urls") or []), "")
        person = {
            "person_name": r["name"],
            "company": r.get("company", ""),
            "person_type": r.get("title") or "engineer",
            "_role_hint": r.get("title") or "your open ML roles",
        }
        if basis == "hiring_post":
            person["_post_hint"] = "your recent hiring post"
        note = connection_queue.compose_note(person, basis)
        row = {k: "" for k in connection_queue.HEADER}
        row.update({
            "request_id": f"cr_{today:%Y%m%d}_{uuid.uuid4().hex[:6]}",
            "person_name": r["name"],
            "company": r.get("company", ""),
            "person_type": r.get("title") or "",
            "linkedin_url": r.get("linkedin_url") or "",
            "source_post_url": source_post,
            "related_job_ids": str(job_ids or ""),
            "score": r.get("score", ""),
            "note_draft": note,
            basis_col: basis,
            status_col: "pending",
            "date_queued": today.isoformat(),
            "notes": f"right_people {r.get('priority', '')}".strip(),
        })
        rows.append(row)
        known.add(key)
        staged.append(row)
    if staged:
        connection_queue.write_requests(rows, ledger_path)
    return staged


# ------------------------------------------------------------ log_search_run

def log_search_run(target, results, summary=None, path=None, run_id=None,
                   today=None) -> dict:
    """Append exactly ONE coverage row to tracking/search_runs/search_runs.csv.

    Preserves the file's existing header; creates the file with the canonical
    header when absent. Returns the appended row.
    """
    today = _today(today)
    path = Path(path or config_lib.path("search_runs_csv"))
    summary = summary or {}
    slug = target.get("company_slug") or "unknown"
    live = [r for r in results if not r.get("skipped")]
    strong = sum(1 for r in live if r.get("priority") in ("P0", "P1"))
    fieldnames = list(SEARCH_RUNS_HEADER)
    if path.exists() and path.stat().st_size > 0:
        with path.open(newline="", encoding="utf-8") as fh:
            fieldnames = list(csv.DictReader(fh).fieldnames or fieldnames)
    row = {c: "" for c in fieldnames}
    row.update({
        "run_id": run_id or f"rp_{today:%Y%m%d}_{slug}",
        "date": today.isoformat(),
        "sources": "linkedin_people_search",
        "queries": "agent-driven filter-first passes (rule 05)",
        "total_scanned": str(len(results)),
        "new_jobs_found": str(summary.get("added", 0)),
        "duplicates_skipped": str(summary.get("skipped_dup", 0)),
        "strong_fits": str(strong),
        "notes": (f"{SOURCE_NAME}: {summary.get('added', 0)} added, "
                  f"{summary.get('updated', 0)} updated, "
                  f"{summary.get('inspected', 0)} inspected"),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        w.writerow(row)
    return row


if __name__ == "__main__":
    raise SystemExit("right_people_ingest is a library; use right_people.py ingest")
