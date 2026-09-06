"""TDD tests for scripts/right_people_ingest.py — right-people Tasks 7-9.

Covers run_ingest (normalize/score/dedup/cap), render_report, queue_drafts
(human-gated P0/P1 staging), and log_search_run — all pure, tmp-path backed,
never touching real jobhunt-data.
"""
import csv
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import connection_queue  # noqa: E402
import people_sweep  # noqa: E402
import right_people_ingest as rpi  # noqa: E402
from upsert_lib import CONNECTIONS_HEADER, CONTACTS_HEADER  # noqa: E402

TODAY = date(2026, 8, 28)

TARGET = {
    "kind": "company",
    "company": "Cohere",
    "company_slug": "cohere",
    "job": None,
    "jd_path": None,
}

ROWS = [
    {
        "name": "Ada Active",
        "title": "ML Lead",
        "company": "Cohere",
        "location": "San Francisco, CA, United States",
        "linkedin_url": "https://www.linkedin.com/in/ada-active",
        "degree": "1st",
        "school": "Georgia Tech",
        "hiring_post_urls": ["https://www.linkedin.com/posts/ada-1"],
    },
    {
        "name": "Bob Recruiter",
        "title": "Technical Recruiter",
        "company": "Cohere",
        "location": "Remote - US",
        "linkedin_url": "https://www.linkedin.com/in/bob-recruiter",
        "relationship": "2nd",
    },
]


def _paths(tmp_path):
    return (
        tmp_path / "contacts.csv",
        tmp_path / "people_sweep.csv",
        tmp_path / "companies" / "cohere",
    )


def _ingest(tmp_path, rows=None, cap=12, target=None):
    contacts, sweep, company_dir = _paths(tmp_path)
    return rpi.run_ingest(
        target or TARGET,
        ROWS if rows is None else rows,
        cap=cap,
        today=TODAY,
        contacts_path=contacts,
        sweep_path=sweep,
        company_dir=company_dir,
    )


# ------------------------------------------------------------------ run_ingest


def test_run_ingest_scores_ranks_and_upserts(tmp_path):
    out = _ingest(tmp_path)

    # summary shape
    assert out["summary"]["added"] == 2
    assert out["summary"]["updated"] == 0
    assert out["summary"]["skipped_dup"] == 0
    assert out["summary"]["inspected"] == 2

    # ranked: Ada (1st + GT + US + active poster) outranks Bob (2nd, recruiter)
    names = [r["name"] for r in out["results"]]
    assert names == ["Ada Active", "Bob Recruiter"]

    ada = out["results"][0]
    assert ada["priority"] == "P0"
    # 1st(10) + GT(8) + US(5) + activity(6) + HM(15) — "ML Lead" hits the
    # manager/lead/director/head title heuristic per the ingest contract.
    assert ada["score"] == 10 + 8 + 5 + 6 + 15
    assert ada["degree"] == "1st"
    assert ada["activity_level"] == "active_poster"
    assert ada["skipped"] is False
    assert ada["inspected"] is True
    assert ada["ask"]

    bob = out["results"][1]
    assert bob["degree"] == "2nd"
    assert bob["us_based"] is True
    assert bob["is_recruiter"] is True
    assert bob["priority"] in ("P2", "P3")  # recruiter cap: never above P2

    # canonical CSVs were written
    conn = tmp_path / "companies" / "cohere" / "connections.csv"
    with conn.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == CONNECTIONS_HEADER
        assert len(list(reader)) == 2
    contacts = tmp_path / "contacts.csv"
    with contacts.open(newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 2
    sweep = tmp_path / "people_sweep.csv"
    with sweep.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
        assert rows[0]["sweep_run_id"].startswith("rp_20260828_cohere")


def test_run_ingest_heuristics_from_raw_fields(tmp_path):
    row = {
        "name": "Carol Manager",
        "title": "Engineering Manager",
        "company": "Cohere",
        "location": "Austin, TX, United States",
        "linkedin_url": "https://www.linkedin.com/in/carol",
        "relationship": "3rd",
        "school": "MS CS, Georgia Tech",
        "snippet": "previously Fortinet SD-WAN team",
        "source_pass": "gt_alumni",
        "mutuals": ["Dan Peer"],
    }
    out = _ingest(tmp_path, rows=[row])
    r = out["results"][0]
    assert r["degree"] == "3rd"
    assert r["gt_alumni"] is True
    assert r["fortinet_overlap"] is True
    assert r["us_based"] is True
    assert r["is_hiring_manager"] is True
    assert r["is_recruiter"] is False
    # 3rd(3) + GT(8) + Fortinet(6) + HM(15) + US(5) + 1 mutual(5)
    assert r["score"] == 3 + 8 + 6 + 15 + 5 + 5
    assert "Georgia Tech" in r["reason_to_contact"] or "GT" in r["reason_to_contact"]


def test_run_ingest_skips_blocked_dup_before_inspection(tmp_path):
    contacts, sweep, company_dir = _paths(tmp_path)
    contacts.parent.mkdir(parents=True, exist_ok=True)
    with contacts.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CONTACTS_HEADER)
        w.writeheader()
        row = {c: "" for c in CONTACTS_HEADER}
        row.update({
            "contact_id": "cohere_001",
            "name": "Ada Active",
            "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/ada-active",
            "outreach_status": "requested",
        })
        w.writerow(row)

    out = rpi.run_ingest(
        TARGET, ROWS, cap=12, today=TODAY,
        contacts_path=contacts, sweep_path=sweep, company_dir=company_dir)

    assert out["summary"]["skipped_dup"] == 1
    assert out["summary"]["added"] == 1
    ada = next(r for r in out["results"] if r["name"] == "Ada Active")
    assert ada["skipped"] is True
    assert "requested" in ada["dup_reason"]
    # dups are not inspected and don't consume cap
    assert ada.get("inspected") in (False, None)
    bob = next(r for r in out["results"] if r["name"] == "Bob Recruiter")
    assert bob["skipped"] is False
    with contacts.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2  # Ada (pre-existing) + Bob; NO duplicate Ada row
    assert sum(1 for r in rows if r["name"] == "Ada Active") == 1


def test_run_ingest_cap_limits_inspection_not_ingestion(tmp_path):
    out = _ingest(tmp_path, cap=1)
    assert out["summary"]["added"] == 2       # both still ingested
    assert out["summary"]["inspected"] == 1   # only top-scored inspected
    ada = out["results"][0]
    bob = out["results"][1]
    assert ada["inspected"] is True and ada["inspect_pending"] is False
    assert bob["inspected"] is False and bob["inspect_pending"] is True
    assert bob["priority"]  # score/priority still assigned


# --------------------------------------------------------------- render_report


def _fixture_results():
    return [
        {
            "name": "Ada Active", "title": "ML Lead", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/ada-active",
            "degree": "1st", "score": 29, "priority": "P0",
            "ask": "Introduction to hiring manager/team",
            "reason_to_contact": "1st-degree connection; Georgia Tech alumni",
            "activity_level": "active_poster",
            "hiring_post_urls": ["https://www.linkedin.com/posts/ada-1"],
            "skipped": False, "dup_reason": "",
            "inspected": True, "inspect_pending": False,
        },
        {
            "name": "Eve Peer", "title": "MLE", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/eve",
            "degree": "2nd", "score": 11, "priority": "P1",
            "ask": "Connection request + informational chat ask",
            "reason_to_contact": "2nd-degree; mutual: Dan Peer",
            "activity_level": "unknown", "hiring_post_urls": [],
            "skipped": False, "dup_reason": "",
            "inspected": True, "inspect_pending": False,
        },
        {
            "name": "Old Contact", "title": "MLE", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/old",
            "degree": "2nd", "score": 6, "priority": "P2",
            "ask": "", "reason_to_contact": "", "activity_level": "unknown",
            "hiring_post_urls": [],
            "skipped": True, "dup_reason": "contacts: requested",
            "inspected": False, "inspect_pending": False,
        },
    ]


def test_render_report_ranked_sections_and_bullets():
    report = rpi.render_report(TARGET, _fixture_results(), today=TODAY)
    p0 = report.index("## P0")
    p1 = report.index("## P1")
    skipped = report.index("Skipped")
    assert p0 < p1 < skipped
    # header carries company/slug/date
    assert "Cohere" in report.splitlines()[0]
    assert "cohere" in report.splitlines()[0]
    assert "2026-08-28" in report
    # bullet contract
    assert "**Ada Active**" in report
    assert "ML Lead @ Cohere" in report
    assert "29" in report
    assert "https://www.linkedin.com/in/ada-active" in report
    assert "Introduction to hiring manager/team" in report
    # activity signal surfaces when present
    assert "active_poster" in report
    # empty sections omitted (no P2/P3 non-skipped in fixture)
    assert not report.startswith("## P2")
    # skipped dups compact, at the end
    assert "Old Contact" in report[skipped:]
    assert "requested" in report[skipped:]


def test_render_report_omits_empty_priority_sections():
    results = [r for r in _fixture_results() if r["priority"] in ("P0", "P2")]
    report = rpi.render_report(TARGET, results, today=TODAY)
    assert "## P0" in report
    assert "## P1" not in report
    assert "## P3" not in report


# ---------------------------------------------------------------- queue_drafts


def _draft_fixture():
    return [
        {   # P0 with hiring post -> basis hiring_post
            "name": "Ada Active", "title": "ML Lead", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/ada-active",
            "score": 29, "priority": "P0", "skipped": False,
            "gt_alumni": True, "hiring_post_urls":
                ["https://www.linkedin.com/posts/ada-1"],
        },
        {   # P1 GT+mutual, no posts -> basis shared_ctx
            "name": "Eve Peer", "title": "MLE", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/eve",
            "score": 16, "priority": "P1", "skipped": False,
            "gt_alumni": True,
            "mutuals": ["Dan Peer"],
            "hiring_post_urls": [],
        },
        {   # P2 -> never staged
            "name": "Bob Recruiter", "title": "Recruiter", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/bob-recruiter",
            "score": 11, "priority": "P2", "skipped": False,
            "hiring_post_urls": [],
        },
        {   # skipped dup -> never staged even if P0
            "name": "Old Contact", "title": "MLE", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/old",
            "score": 25, "priority": "P0", "skipped": True,
            "dup_reason": "contacts: requested", "hiring_post_urls": [],
        },
    ]


def test_queue_drafts_stages_p0_p1_pending_only(tmp_path):
    ledger = tmp_path / "connection_requests.csv"
    staged = rpi.queue_drafts(_draft_fixture(), ledger, today=TODAY)

    assert [s["person_name"] for s in staged] == ["Ada Active", "Eve Peer"]
    with ledger.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == connection_queue.HEADER
        rows = list(reader)
    assert len(rows) == 2
    assert all(r["send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)"]
               == "pending" for r in rows)
    basis_col = connection_queue.HEADER[10]
    by_name = {r["person_name"]: r for r in rows}
    assert by_name["Ada Active"][basis_col] == "hiring_post"
    assert by_name["Eve Peer"][basis_col] == "shared_ctx"
    assert by_name["Ada Active"]["source_post_url"] == \
        "https://www.linkedin.com/posts/ada-1"
    # honest identity tokens in every draft note
    for r in rows:
        assert "Georgia Tech" in r["note_draft"] or "GT" in r["note_draft"]
        assert "Fortinet" in r["note_draft"]


def test_queue_drafts_is_idempotent(tmp_path):
    ledger = tmp_path / "connection_requests.csv"
    rpi.queue_drafts(_draft_fixture(), ledger, today=TODAY)
    rpi.queue_drafts(_draft_fixture(), ledger, today=TODAY)
    with ledger.open(newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 2


# -------------------------------------------------------------- log_search_run


def test_log_search_run_appends_one_row_keeping_header(tmp_path):
    run_csv = tmp_path / "search_runs.csv"
    header = ["run_id", "date", "sources", "queries", "total_scanned",
              "new_jobs_found", "duplicates_skipped", "strong_fits", "notes"]
    with run_csv.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(header)

    results = [
        {"name": "A", "priority": "P0", "skipped": False},
        {"name": "B", "priority": "P1", "skipped": False},
        {"name": "C", "priority": "P2", "skipped": True, "dup_reason": "x"},
    ]
    summary = {"added": 2, "updated": 0, "skipped_dup": 1, "inspected": 2}
    row = rpi.log_search_run(TARGET, results, summary=summary, path=run_csv,
                             today=TODAY)
    assert row["run_id"] == "rp_20260828_cohere"
    assert row["date"] == "2026-08-28"
    with run_csv.open(newline="", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.splitlines()
    assert lines[0] == ",".join(header)  # header preserved verbatim
    rows = list(csv.DictReader(text.splitlines()))
    assert len(rows) == 1  # exactly ONE run row appended
    assert rows[0]["new_jobs_found"] == "2"
    assert rows[0]["duplicates_skipped"] == "1"
    assert rows[0]["strong_fits"] == "2"  # P0 + P1
    assert rows[0]["total_scanned"] == "3"


def test_log_search_run_creates_file_with_canonical_header(tmp_path):
    run_csv = tmp_path / "fresh" / "search_runs.csv"
    rpi.log_search_run(TARGET, [], path=run_csv, today=TODAY)
    with run_csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == rpi.SEARCH_RUNS_HEADER
        rows = list(reader)
    assert len(rows) == 1  # one coverage row even for zero rows extracted
    assert rows[0]["total_scanned"] == "0"
