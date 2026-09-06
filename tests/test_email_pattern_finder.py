"""Tests for scripts/email_pattern_finder.py (Task 12)."""
import csv
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import email_pattern_finder as epf  # noqa: E402


# ---------------------------------------------------------------------------
# Pattern derivation from observed emails (status=confirmed)
# ---------------------------------------------------------------------------

def _write_contacts(path, rows):
    fields = ["contact_id", "name", "company", "email"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def test_classify_localpart_flast():
    assert epf.classify_localpart("jdoe", "Jane", "Doe") == "flast"


def test_classify_localpart_first_dot_last():
    assert epf.classify_localpart("jane.doe", "Jane", "Doe") == "first.last"


def test_classify_localpart_firstlast():
    assert epf.classify_localpart("janedoe", "Jane", "Doe") == "firstlast"


def test_classify_localpart_first():
    assert epf.classify_localpart("grace", "Grace", "Gao") == "first"


def test_classify_localpart_unclassifiable():
    assert epf.classify_localpart("mmozes", "", "") is None


def test_derive_from_contacts_confirms_pattern(tmp_path):
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "Grace Gao", "company": "Cohere",
         "email": "grace@cohere.com"},
        {"contact_id": "c2", "name": "Mitch Parker", "company": "Cohere",
         "email": "mitch@cohere.com"},
        {"contact_id": "c3", "name": "Bad Row", "company": "Cohere",
         "email": "x@cohere_com"},  # invalid domain ignored
    ])
    result = epf.derive_pattern_from_contacts("Cohere", contacts)
    assert result is not None
    pattern, domain, evidence = result
    assert domain == "cohere.com"
    assert pattern == "first"
    assert evidence  # at least one observed address cited
    assert "grace@cohere.com" in evidence


def test_derive_from_contacts_no_emails_returns_none(tmp_path):
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "A", "company": "X", "email": ""},
    ])
    assert epf.derive_pattern_from_contacts("X", contacts) is None


def test_confirmed_requires_real_observed_address(tmp_path):
    # A guessed pattern must NEVER be marked confirmed even when a contact
    # exists but has no observed email.
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "Jane Doe", "company": "Acme",
         "email": ""},
    ])
    assert epf.derive_pattern_from_contacts("Acme", contacts) is None


# ---------------------------------------------------------------------------
# Guessed patterns: generated but never confirmed
# ---------------------------------------------------------------------------

def test_guess_patterns_common_variants():
    guesses = epf.guess_pattern_candidates("Jane", "Doe", "acme.com")
    locals_ = {g.split("@")[0] for g in guesses}
    assert "jane.doe@acme.com" in guesses
    assert "jdoe@acme.com" in guesses
    assert "janedoe@acme.com" in guesses
    assert "jane@acme.com" in guesses
    assert all("@" in g for g in guesses)


def test_guessed_status_is_never_confirmed():
    for slug, entry in epf.CITED_PATTERNS.items():
        assert entry["status"] in ("unverified",), (
            f"cited entry {slug} must not be confirmed")
    # guessed helper always reports 'guessed'
    assert epf.status_for_method("guess") == "guessed"
    assert epf.status_for_method("cited") == "unverified"
    assert epf.status_for_method("observed") == "confirmed"


def test_cited_patterns_have_source_urls():
    for slug, entry in epf.CITED_PATTERNS.items():
        assert entry.get("source", "").startswith("http"), slug
        assert entry.get("domain"), slug


# ---------------------------------------------------------------------------
# Draft lane: gating on confirmed-only
# ---------------------------------------------------------------------------

def _write_registry(path, rows):
    fields = ["company_slug", "company", "email_pattern",
              "email_pattern_status", "email_pattern_source"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _write_posts(path, rows):
    fields = ["post_id", "poster_name", "poster_headline", "poster_type",
              "company", "post_url", "roles_mentioned", "notes"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def test_draft_blocked_for_unverified_pattern(tmp_path):
    reg = tmp_path / "registry.csv"
    _write_registry(reg, [{
        "company_slug": "acme", "company": "Acme",
        "email_pattern": "first.last@acme.com",
        "email_pattern_status": "guessed", "email_pattern_source": "",
    }])
    with pytest.raises(PermissionError):
        epf.draft_application_emails(
            "acme", registry_path=reg, contacts_path=tmp_path / "c.csv",
            posts_path=tmp_path / "p.csv")


def test_draft_blocked_when_no_confirmed_addresses(tmp_path):
    reg = tmp_path / "registry.csv"
    _write_registry(reg, [{
        "company_slug": "cohere", "company": "Cohere",
        "email_pattern": "first@cohere.com",
        "email_pattern_status": "confirmed",
        "email_pattern_source": "contacts.csv",
    }])
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "Grace Gao", "company": "Cohere",
         "email": ""},  # no observed address -> cannot draft
    ])
    posts = tmp_path / "posts.csv"
    _write_posts(posts, [{
        "post_id": "p1", "poster_name": "Grace Gao", "poster_type":
        "recruiter", "company": "Cohere",
        "post_url": "https://linkedin.com/x", "roles_mentioned":
        "ML Engineer", "notes": ""}])
    drafts = epf.draft_application_emails(
        "cohere", registry_path=reg, contacts_path=contacts,
        posts_path=posts)
    assert drafts == []


def test_draft_generated_only_for_confirmed_addresses(tmp_path):
    reg = tmp_path / "registry.csv"
    _write_registry(reg, [{
        "company_slug": "cohere", "company": "Cohere",
        "email_pattern": "first@cohere.com",
        "email_pattern_status": "confirmed",
        "email_pattern_source": "contacts.csv",
    }])
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "Grace Gao", "company": "Cohere",
         "email": "grace@cohere.com"},
    ])
    posts = tmp_path / "posts.csv"
    _write_posts(posts, [{
        "post_id": "p1", "poster_name": "Grace Gao",
        "poster_headline": "Recruiter at Cohere",
        "poster_type": "recruiter", "company": "Cohere",
        "post_url": "https://linkedin.com/x",
        "roles_mentioned": "ML Engineer", "notes": ""}])
    drafts = epf.draft_application_emails(
        "cohere", registry_path=reg, contacts_path=contacts,
        posts_path=posts)
    assert len(drafts) == 1
    d = drafts[0]
    assert d["email"] == "grace@cohere.com"
    assert d["note_basis"] == "hiring_post"
    body = d["note_draft"]
    assert "grace@cohere.com" in d["email"]
    assert "ML Engineer" in body
    assert epf.CANDIDATE_EMAIL in body
    # banned claims must not appear
    low = body.lower()
    for banned in ("rlhf", "dpo", "sft"):
        assert banned not in low
    assert d["notes"].find("channel=email") >= 0


def test_write_drafts_requires_existing_file_and_skips_gracefully(tmp_path):
    reg = tmp_path / "registry.csv"
    _write_registry(reg, [{
        "company_slug": "cohere", "company": "Cohere",
        "email_pattern": "first@cohere.com",
        "email_pattern_status": "confirmed",
        "email_pattern_source": "contacts.csv",
    }])
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "Grace Gao", "company": "Cohere",
         "email": "grace@cohere.com"},
    ])
    posts = tmp_path / "posts.csv"
    _write_posts(posts, [{
        "post_id": "p1", "poster_name": "Grace Gao",
        "poster_headline": "Recruiter at Cohere",
        "poster_type": "recruiter", "company": "Cohere",
        "post_url": "https://linkedin.com/x",
        "roles_mentioned": "ML Engineer", "notes": ""}])
    missing = tmp_path / "nope.csv"
    n = epf.write_drafts(
        epf.draft_application_emails(
            "cohere", registry_path=reg, contacts_path=contacts,
            posts_path=posts),
        missing)
    assert n == 0  # graceful skip when file does not exist


def test_write_drafts_appends_rows(tmp_path):
    reg = tmp_path / "registry.csv"
    _write_registry(reg, [{
        "company_slug": "cohere", "company": "Cohere",
        "email_pattern": "first@cohere.com",
        "email_pattern_status": "confirmed",
        "email_pattern_source": "contacts.csv",
    }])
    contacts = tmp_path / "contacts.csv"
    _write_contacts(contacts, [
        {"contact_id": "c1", "name": "Grace Gao", "company": "Cohere",
         "email": "grace@cohere.com"},
    ])
    posts = tmp_path / "posts.csv"
    _write_posts(posts, [{
        "post_id": "p1", "poster_name": "Grace Gao",
        "poster_headline": "Recruiter at Cohere",
        "poster_type": "recruiter", "company": "Cohere",
        "post_url": "https://linkedin.com/x",
        "roles_mentioned": "ML Engineer", "notes": ""}])
    out = tmp_path / "connection_requests.csv"
    with open(out, "w", newline="") as f:
        f.write("request_id,person_name,company,person_type,linkedin_url,"
                "email,source_post_url,related_job_ids,score,note_draft,"
                "note_basis,send_status,date_queued,date_sent,"
                "date_connected,response,followup_date,notes\n")
    drafts = epf.draft_application_emails(
        "cohere", registry_path=reg, contacts_path=contacts,
        posts_path=posts)
    n = epf.write_drafts(drafts, out)
    assert n == 1
    rows = list(csv.DictReader(open(out)))
    assert rows[-1]["send_status"] == "pending"
    assert rows[-1]["email"] == "grace@cohere.com"


# ---------------------------------------------------------------------------
# Registry apply path
# ---------------------------------------------------------------------------

def test_apply_pattern_update(tmp_path):
    reg = tmp_path / "registry.csv"
    _write_registry(reg, [{
        "company_slug": "cohere", "company": "Cohere",
        "email_pattern": "", "email_pattern_status": "unknown",
        "email_pattern_source": "",
    }])
    ok = epf.apply_pattern(
        "cohere", pattern="first@cohere.com", status="confirmed",
        source="contacts.csv:grace@cohere.com", registry_path=reg)
    assert ok
    row = list(csv.DictReader(open(reg)))[0]
    assert row["email_pattern_status"] == "confirmed"
    assert row["email_pattern"] == "first@cohere.com"
