"""Tests for scripts/upsert_lib.py — dedup + canonical CSV upserts.

Task 5 of the right-people plan (.hermes/plans/2026-08-27_232352-right-people-feature.md).
Seeds tmp contacts.csv / people_sweep.csv with the REAL repo headers and
verifies the never-twice interlock, update-in-place semantics, contact_id
sequencing, and per-company connections.csv upserts.
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import upsert_lib  # noqa: E402
from people_sweep import COLUMNS as SWEEP_COLUMNS  # noqa: E402

TODAY = datetime.date(2026, 8, 28)
LATER = datetime.date(2026, 8, 29)

CONTACTS_HEADER = (
    "contact_id,name,company,role,relationship,linkedin_url,email,job_id,"
    "reason_to_contact,shared_context,outreach_status,date_identified,"
    "date_contacted,followup_date,response,notes,email_status,repair_note,"
    "domain_relevance,referral_likelihood,outreach_priority,"
    "last_verified_date,email_source"
).split(",")


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _seed(tmp_path: Path, contact_rows=None, sweep_rows=None):
    contacts = tmp_path / "contacts.csv"
    sweep = tmp_path / "people_sweep.csv"
    _write_csv(contacts, CONTACTS_HEADER, contact_rows or [])
    _write_csv(sweep, SWEEP_COLUMNS, sweep_rows or [])
    return contacts, sweep


def _finding(**over):
    f = {
        "name": "Dana Fox",
        "linkedin_url": "https://www.linkedin.com/in/dana-fox/",
        "company": "Cohere",
        "title": "Staff ML Engineer",
        "reason_to_contact": "Search & embeddings team, works on RAG",
        "degree": "2nd",
        "hiring_post_urls": "https://www.linkedin.com/posts/dana-fox-hiring",
        "person_type": "company_people",
    }
    f.update(over)
    return f


# ---------------------------------------------------------------- find_existing

def test_find_existing_blocked_contacts_row(tmp_path):
    contacts, sweep = _seed(tmp_path, contact_rows=[{
        "contact_id": "cohere_001", "name": "Dana Fox", "company": "Cohere",
        "linkedin_url": "https://www.linkedin.com/in/dana-fox",
        "outreach_status": "requested",
    }])
    row = upsert_lib.find_existing(
        "https://www.linkedin.com/in/dana-fox/", "Dana Fox", "Cohere",
        contacts_path=contacts, sweep_path=sweep)
    assert row is not None
    assert row["source_file"] == "contacts"
    assert row["outreach_status"] == "requested"


def test_find_existing_non_blocked_returns_none(tmp_path):
    contacts, sweep = _seed(tmp_path, contact_rows=[{
        "contact_id": "cohere_001", "name": "Dana Fox", "company": "Cohere",
        "linkedin_url": "https://www.linkedin.com/in/dana-fox",
        "outreach_status": "not_contacted",
    }])
    assert upsert_lib.find_existing(
        "https://www.linkedin.com/in/dana-fox/", "Dana Fox", "Cohere",
        contacts_path=contacts, sweep_path=sweep) is None


def test_find_existing_blocked_sweep_row(tmp_path):
    contacts, sweep = _seed(tmp_path, sweep_rows=[{
        "sweep_run_id": "lhp_1", "date": "2026-08-01", "name": "Dana Fox",
        "title": "Staff ML Engineer", "company": "Cohere",
        "person_type": "company_people",
        "linkedin_url": "https://www.linkedin.com/in/dana-fox",
        "status": "connected", "notes": "",
    }])
    row = upsert_lib.find_existing(
        "https://www.linkedin.com/in/dana-fox/", "Dana Fox", "Cohere",
        contacts_path=contacts, sweep_path=sweep)
    assert row is not None and row["source_file"] == "people_sweep"


# ---------------------------------------------------------------- upsert_contacts

def test_new_person_added_with_contact_id_and_header(tmp_path):
    contacts, sweep = _seed(tmp_path)
    res = upsert_lib.upsert_contacts([_finding()], contacts_path=contacts,
                                     sweep_path=sweep,
                                     company_dir=tmp_path, today=TODAY)
    assert res == {"added": 1, "updated": 0, "skipped_dup": 0}
    rows = _read_rows(contacts)
    assert len(rows) == 1
    assert rows[0]["contact_id"] == "cohere_001"
    assert rows[0]["name"] == "Dana Fox"
    assert rows[0]["role"] == "Staff ML Engineer"
    assert rows[0]["outreach_status"] == "not_contacted"
    assert rows[0]["last_verified_date"] == "2026-08-28"
    # exact real header preserved
    with contacts.open(newline="", encoding="utf-8") as fh:
        assert next(csv.reader(fh)) == CONTACTS_HEADER
    # sweep run row appended
    srows = _read_rows(sweep)
    assert len(srows) == 1
    assert srows[0]["sweep_run_id"] == f"rp_20260828_cohere"
    assert srows[0]["status"] == "new"
    assert srows[0]["notes"] == "right_people"
    assert srows[0]["post_url"] == _finding()["hiring_post_urls"]
    assert srows[0]["why_relevant"] == _finding()["reason_to_contact"]


def test_same_person_again_updates_not_duplicates(tmp_path):
    contacts, sweep = _seed(tmp_path)
    upsert_lib.upsert_contacts([_finding()], contacts_path=contacts,
                               sweep_path=sweep, company_dir=tmp_path,
                               today=TODAY)
    res = upsert_lib.upsert_contacts(
        [_finding(reason_to_contact="updated reason")],
        contacts_path=contacts, sweep_path=sweep, company_dir=tmp_path,
        today=LATER)
    assert res == {"added": 0, "updated": 1, "skipped_dup": 0}
    rows = _read_rows(contacts)
    assert len(rows) == 1
    assert rows[0]["last_verified_date"] == "2026-08-29"
    assert rows[0]["contact_id"] == "cohere_001"
    # non-empty fields never overwritten
    assert rows[0]["name"] == "Dana Fox"


def test_blocked_contacts_status_skipped_file_unchanged(tmp_path):
    contacts, sweep = _seed(tmp_path, contact_rows=[{
        "contact_id": "cohere_001", "name": "Dana Fox", "company": "Cohere",
        "linkedin_url": "https://www.linkedin.com/in/dana-fox",
        "role": "Staff ML Engineer", "outreach_status": "requested",
    }])
    before = contacts.read_bytes(), sweep.read_bytes()
    res = upsert_lib.upsert_contacts([_finding()], contacts_path=contacts,
                                     sweep_path=sweep,
                                     company_dir=tmp_path, today=TODAY)
    assert res["skipped_dup"] == 1 and res["added"] == 0 and res["updated"] == 0
    assert (contacts.read_bytes(), sweep.read_bytes()) == before


def test_blocked_sweep_status_skipped(tmp_path):
    contacts, sweep = _seed(tmp_path, sweep_rows=[{
        "sweep_run_id": "lhp_1", "date": "2026-08-01", "name": "Dana Fox",
        "title": "Staff ML Engineer", "company": "Cohere",
        "person_type": "company_people",
        "linkedin_url": "https://www.linkedin.com/in/dana-fox",
        "status": "responded", "notes": "",
    }])
    res = upsert_lib.upsert_contacts([_finding()], contacts_path=contacts,
                                     sweep_path=sweep,
                                     company_dir=tmp_path, today=TODAY)
    assert res["skipped_dup"] == 1
    assert _read_rows(contacts) == []
    assert len(_read_rows(sweep)) == 1  # only the seeded row


def test_fuzzy_name_company_match_skips(tmp_path):
    # old row has NO linkedin_url — fuzzy name+company must still match
    contacts, sweep = _seed(tmp_path, contact_rows=[{
        "contact_id": "cohere_001", "name": "Dana  Fox", "company": "Cohere",
        "linkedin_url": "", "outreach_status": "contacted",
    }])
    res = upsert_lib.upsert_contacts([_finding()], contacts_path=contacts,
                                     sweep_path=sweep,
                                     company_dir=tmp_path, today=TODAY)
    assert res["skipped_dup"] == 1
    assert len(_read_rows(contacts)) == 1


def test_contact_id_seq_across_both_files(tmp_path):
    contacts, sweep = _seed(tmp_path, contact_rows=[{
        "contact_id": "cohere_003", "name": "Old Row", "company": "Cohere",
        "outreach_status": "not_contacted",
    }])
    comp = tmp_path / "connections.csv"
    upsert_lib.connections_upsert(
        [_finding(name="Seq Seed", linkedin_url="https://www.linkedin.com/in/seq-seed/")],
        comp, today=TODAY)
    rows = _read_rows(comp)
    assert rows[0]["contact_id"] == "cohere_001"
    res = upsert_lib.upsert_contacts([_finding()], contacts_path=contacts,
                                     sweep_path=sweep,
                                     company_dir=tmp_path, today=TODAY)
    assert res["added"] == 1
    new = [r for r in _read_rows(contacts) if r["name"] == "Dana Fox"]
    assert new[0]["contact_id"] == "cohere_004"


# ---------------------------------------------------------------- connections_upsert

def test_connections_csv_created_with_exact_header_and_deduped(tmp_path):
    comp = tmp_path / "connections.csv"
    res1 = upsert_lib.connections_upsert([_finding()], comp, today=TODAY)
    assert res1["added"] == 1
    with comp.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == upsert_lib.CONNECTIONS_HEADER
    assert ",".join(header) == (
        "contact_id,name,linkedin_url,company,title,location,degree,"
        "relevant_team,alumni_shared_affiliation,mutuals,shared_context,"
        "activity_level,hiring_post_urls,target_job_ids,reason_to_contact,"
        "recommended_ask,referral_likelihood,outreach_priority,email,"
        "email_status,source,outreach_status,last_verified")
    rows = _read_rows(comp)
    assert rows[0]["contact_id"] == "cohere_001"
    assert rows[0]["last_verified"] == "2026-08-28"

    res2 = upsert_lib.connections_upsert(
        [_finding(shared_context="GT alum")], comp, today=LATER)
    assert res2 == {"added": 0, "updated": 1, "skipped_dup": 0}
    rows = _read_rows(comp)
    assert len(rows) == 1
    assert rows[0]["last_verified"] == "2026-08-29"
    assert rows[0]["shared_context"] == "GT alum"


def test_connections_company_scoped_seq_and_blocked_skip(tmp_path):
    comp = tmp_path / "connections.csv"
    upsert_lib.connections_upsert([_finding()], comp, today=TODAY)
    res = upsert_lib.connections_upsert(
        [_finding(name="Ravi Patel",
                  linkedin_url="https://www.linkedin.com/in/ravi-patel/",
                  outreach_status="requested")],
        comp, today=TODAY)
    assert res["added"] == 1
    rows = _read_rows(comp)
    assert sorted(r["contact_id"] for r in rows) == [
        "cohere_001", "cohere_002"]

    # blocked row is never re-added — fuzzy name match (dot-normalized), no URL
    res2 = upsert_lib.connections_upsert(
        [_finding(name="ravi.patel", linkedin_url="",
                  title="Anything Else")], comp, today=TODAY)
    assert res2["skipped_dup"] == 1
    assert len(_read_rows(comp)) == 2
