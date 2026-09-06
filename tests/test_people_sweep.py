"""Unit tests for people_sweep.py pure logic (no browser)."""

from __future__ import annotations

import csv
import importlib
import os
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

people_sweep = importlib.import_module("people_sweep")

COLUMNS = [
    "sweep_run_id", "date", "name", "title", "company", "person_type",
    "linkedin_url", "post_url", "why_relevant", "status", "notes",
]


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

def test_build_queries_covers_all_four_families():
    prefs = {
        "role_keywords": {"agentic_ai": ["agentic AI"]},
        "companies": ["Cohere"],
    }
    queries = people_sweep.build_queries(
        prefs, policy={"enable_school_family": True})
    fams = {q["family"] for q in queries}
    assert fams == {"a_hiring_posts", "b_recruiters", "c_company_people", "d_gt_alumni"}


def test_build_queries_rotate_role_families():
    prefs = {
        "role_keywords": {
            "agentic_ai": ["agentic AI"],
            "mle_training": ["distributed training"],
        },
        "companies": ["Cohere", "Together AI"],
    }
    queries = people_sweep.build_queries(prefs)
    # family-a queries should rotate across role families
    a_queries = [q for q in queries if q["family"] == "a_hiring_posts"]
    kws = " OR ".join(q["keywords"].lower() for q in a_queries)
    assert "agentic ai" in kws and "distributed training" in kws
    # each query has a search URL
    assert all(q["url"].startswith("https://www.linkedin.com/search/results/") for q in queries)


def test_cap_queries_round_robin():
    prefs = {
        "role_keywords": {f"f{i}": [f"kw{i}"] for i in range(4)},
        "companies": ["A", "B"],
    }
    queries = people_sweep.build_queries(
        prefs, policy={"enable_school_family": True})
    capped = people_sweep.cap_queries(queries, 4)
    assert len(capped) == 4
    fams = [q["family"] for q in capped]
    # round-robin: first picks come from distinct families
    assert len(set(fams[:4])) == 4


def test_build_queries_school_family_opt_in():
    """Family d_gt_alumni is opt-in via policy['enable_school_family']."""
    prefs = {
        "role_keywords": {"agentic_ai": ["agentic AI"]},
        "companies": ["Cohere"],
    }
    # default (policy=None): no school/alumni family at all
    default_qs = people_sweep.build_queries(prefs)
    assert all(q["family"] != "d_gt_alumni" for q in default_qs)
    assert all("georgia tech" not in q["keywords"].lower() for q in default_qs)

    # explicitly disabled: same
    off_qs = people_sweep.build_queries(prefs, policy={"enable_school_family": False})
    assert all(q["family"] != "d_gt_alumni" for q in off_qs)

    # enabled: one alumni query per company, school from prefs when present
    on_qs = people_sweep.build_queries(
        {**prefs, "school": "Georgia Institute of Technology"},
        policy={"enable_school_family": True},
    )
    gt_qs = [q for q in on_qs if q["family"] == "d_gt_alumni"]
    assert len(gt_qs) == 1
    assert "Georgia Institute of Technology" in gt_qs[0]["keywords"]

    # enabled without prefs["school"]: canonical default applies
    fallback_qs = [q for q in people_sweep.build_queries(
        prefs, policy={"enable_school_family": True})
        if q["family"] == "d_gt_alumni"]
    assert len(fallback_qs) == 1
    assert "Georgia Tech" in fallback_qs[0]["keywords"]


# ---------------------------------------------------------------------------
# Preferences loading
# ---------------------------------------------------------------------------

def test_load_preferences_missing_raises(tmp_path):
    with pytest.raises(people_sweep.PreferencesMissing):
        people_sweep.load_preferences(tmp_path)


def test_load_preferences_empty_target_companies_raises(tmp_path):
    cfg = tmp_path / "job_research" / "config"
    cfg.mkdir(parents=True)
    (cfg / "target-companies.yaml").write_text("companies: []\n")
    with pytest.raises(people_sweep.PreferencesMissing):
        people_sweep.load_preferences(tmp_path)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_normalize_person_defaults_and_columns():
    row = people_sweep.normalize_person(
        {"name": "Jane Doe", "title": "Tech Lead", "company": "Cohere",
         "person_type": "hiring_manager", "linkedin_url":
             "https://www.linkedin.com/in/jane-doe-123/",
         "post_url": "https://www.linkedin.com/posts/x-9", "why_relevant": "kw: agentic"},
        run_id="ps_20260823_0000",
    )
    assert list(row.keys()) == COLUMNS
    assert row["sweep_run_id"] == "ps_20260823_0000"
    assert row["status"] == "pending_review"
    assert row["date"] != ""


def test_normalize_person_requires_name():
    with pytest.raises(ValueError):
        people_sweep.normalize_person({"name": "", "company": "X"}, run_id="r")


def test_linkedin_slug():
    assert people_sweep.linkedin_slug("https://www.linkedin.com/in/jane-doe-123/?x=1") == "jane-doe-123"
    assert people_sweep.linkedin_slug("") == ""
    assert people_sweep.linkedin_slug("https://example.com/foo") == ""


# ---------------------------------------------------------------------------
# Dedup index
# ---------------------------------------------------------------------------

@pytest.fixture()
def contacts_csv(tmp_path):
    p = tmp_path / "contacts.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["contact_id", "name", "company", "role", "relationship",
                    "linkedin_url", "email", "job_id", "reason_to_contact",
                    "shared_context", "outreach_status", "date_identified",
                    "date_contacted", "followup_date", "response", "notes"])
        w.writerow(["c1", "Jane Doe", "Cohere", "", "", 
                    "https://www.linkedin.com/in/jane-doe-123/", "", "", "", "",
                    "requested", "", "", "", "", ""])
        w.writerow(["c2", "Bob Smith", "Together AI", "", "", 
                    "https://www.linkedin.com/in/bob-smith-ai/", "", "", "", "",
                    "not_contacted", "", "", "", "", ""])
    return str(p)


@pytest.fixture()
def prior_sweep_csv(tmp_path):
    p = tmp_path / "people_sweep.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write(",".join(COLUMNS) + "\n")
        fh.write("r1,2026-08-22,Bob Smith,Talent,Cohere,recruiter,"
                 "https://www.linkedin.com/in/bob-smith-ai/,,,why,pending_review,\n")
        fh.write("r1,2026-08-22,Ann Lee,MLE,Anthropic,hiring_manager,"
                 "https://www.linkedin.com/in/ann-lee-ml/,,,why,pending_review,\n")
    return str(p)


def make_index(contacts_csv=None, prior_csv=None):
    idx = people_sweep.PeopleDedupIndex()
    if contacts_csv:
        idx.load_contacts(contacts_csv)
    if prior_csv:
        idx.load_prior_rows(prior_csv)
    return idx


def test_dedup_by_linkedin_slug():
    idx = make_index(prior_csv=None)
    idx.add_seen(slug="jane-doe-123", name="Anything Else", company="")
    assert idx.seen_before("https://www.linkedin.com/in/jane-doe-123/") is True
    assert idx.seen_before("https://www.linkedin.com/in/new-person/") is False


def test_dedup_fuzzy_name_company():
    idx = people_sweep.PeopleDedupIndex()
    idx.add_seen(slug="", name="Bob Smith", company="Together AI")
    hit = idx.fuzzy_seen("Bobby Smith", "Together AI")
    assert hit is True
    assert idx.fuzzy_seen("Totally Different Person", "Other Co") is False


def test_dedup_against_contacts_file(contacts_csv):
    idx = make_index(contacts_csv=contacts_csv)
    # slug hit via contacts.csv regardless of status
    assert idx.seen_before("https://www.linkedin.com/in/jane-doe-123/")
    # fuzzy hit against contacts
    assert idx.fuzzy_seen("Bob Smith", "Together AI")


def test_dedup_against_prior_sweep_rows(prior_sweep_csv):
    idx = make_index(prior_csv=prior_sweep_csv)
    assert idx.seen_before("https://www.linkedin.com/in/bob-smith-ai/")
    assert idx.fuzzy_seen("Ann Lee", "Anthropic")


BLOCKED = ("requested", "connected", "contacted", "responded")


def test_blocked_status_never_resurfaced(tmp_path):
    p = tmp_path / "contacts.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write("contact_id,name,company,outreach_status\n")
        fh.write("c1,Jane Doe,Cohere,responded\n")
    idx = make_index(contacts_csv=str(p))
    verdict = idx.verdict(name="Jane Doe", company="Cohere",
                          linkedin_url="https://www.linkedin.com/in/jane-doe/")
    # fuzzy name+company match AND blocked status -> suppressed outright
    assert verdict == "blocked"


def test_verdict_new_vs_duplicate():
    idx = people_sweep.PeopleDedupIndex()
    idx.add_seen(slug="known-person", name="Known Person", company="Acme")
    v1 = idx.verdict(name="New Person", company="Fresh Co", linkedin_url="https://www.linkedin.com/in/new-person-x/")
    assert v1 == "new"
    v2 = idx.verdict(name="Known Person", company="Acme", linkedin_url="")
    assert v2 == "duplicate"


# ---------------------------------------------------------------------------
# Merge pipeline
# ---------------------------------------------------------------------------

def test_merge_extraction_end_to_end(contacts_csv):
    idx = make_index(contacts_csv=contacts_csv)
    raw = [
        {"name": "Recruiter Rita", "title": "Talent Acquisition", "company": "Cohere",
         "person_type": "recruiter", "linkedin_url": "https://www.linkedin.com/in/recruiter-rita/",
         "post_url": "", "why_relevant": "family:b recruiter posting agentic AI"},
        {"name": "Bob Smith", "title": "Sourcer", "company": "Together AI",
         "person_type": "recruiter", "linkedin_url": "https://www.linkedin.com/in/bob-smith-ai/",
         "post_url": "", "why_relevant": "dup"},
        {"name": "Jane Doe", "title": "EM", "company": "Cohere",
         "person_type": "hiring_manager", "linkedin_url": "https://www.linkedin.com/in/jd-other/",
         "post_url": "", "why_relevant": "fuzzy blocked"},
    ]
    accepted, dups, blocked = people_sweep.merge_extraction(raw, idx, "run_x")
    assert len(accepted) == 1 and accepted[0]["name"] == "Recruiter Rita"
    assert accepted[0]["status"] == "pending_review"
    assert any(d["name"] == "Bob Smith" for d in dups)
    assert any(b["name"] == "Jane Doe" for b in blocked)


def test_append_rows_creates_csv_with_schema(tmp_path):
    out = tmp_path / "people_sweep.csv"
    rows = [people_sweep.normalize_person({"name": "A B", "company": "C"}, run_id="r")]
    n = people_sweep.append_rows(rows, str(out))
    assert n == 1
    with open(out) as fh:
        lines = list(csv.reader(fh))
    assert lines[0] == COLUMNS
    assert lines[1][9] == "pending_review"


# ---------------------------------------------------------------------------
# Preferences parsing
# ---------------------------------------------------------------------------

def test_load_preferences_from_repo():
    prefs = people_sweep.load_preferences()  # resolves via config_lib.data_root()
    assert prefs["role_keywords"], "expected role keyword families"
    assert "agentic_ai" in "".join(prefs["role_keywords"].keys()) or len(prefs["role_keywords"]) >= 3
    assert len(prefs["companies"]) >= 5
    assert any("Cohere" in c for c in prefs["companies"])
