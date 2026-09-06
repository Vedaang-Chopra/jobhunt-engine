"""TDD tests for scripts/right_people_lib.py — target resolver (right-people Task 1).

Seeds a temp repo layout so the real jobhunt-data is never touched:
    <tmp>/jobhunt-data/tracking/jobs/jobs.csv
    <tmp>/jobhunt-data/tracking/companies/companies_registry.csv
"""

import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from right_people_lib import TargetNotFound, resolve_target  # noqa: E402

JOBS_HEADER = [
    "job_id", "company", "title", "location", "job_url",
    "canonical_application_url", "source", "date_discovered", "date_posted",
    "date_updated", "status", "fit_score", "fit_tier", "role_family",
    "seniority", "key_requirements", "matching_strengths", "main_gaps",
    "resume_variant", "networking_priority", "application_priority",
    "last_checked", "notes", "full_description_hash", "description_file",
    "is_medical_false_positive", "company_slug", "source_id", "stale_flag",
    "last_verified", "merged_from", "opportunity_level", "recommended_action",
    "priority_v2", "score_explanation", "score_confidence", "missing_info",
    "override_reason", "last_scored", "ats_score", "keyword_match_score",
    "keyword_matched", "keyword_missing", "ats_issues", "last_ats_check",
    "review_flag", "application_status", "audit_verdict", "audit_reasons",
    "audit_date",
]

REGISTRY_HEADER = [
    "company_slug", "company", "careers_url", "ats_platform",
    "email_pattern", "email_pattern_status", "email_pattern_source",
    "jobs_open_count", "top_job_ids", "contacts_count", "contacts_by_type",
    "referral_coverage", "status", "last_updated", "notes",
]


def _write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _job_row(**overrides):
    row = {col: "" for col in JOBS_HEADER}
    row.update({
        "job_id": "scale_ai_research_engineer_post_training_abc",
        "company": "Scale AI",
        "title": "Research Engineer, Post-Training",
        "location": "San Francisco",
        "job_url": "https://jobs.eu.lever.co/scale/abc",
        "canonical_application_url": "https://jobs.eu.lever.co/scale/abc",
        "source": "lever",
        "status": "open",
        "role_family": "post_training",
        "company_slug": "scale_ai",
        "description_file": "tracking/job_descriptions/active/scale_ai__x.md",
    })
    row.update(overrides)
    return row


def _seed_jobs_csv(repo, rows):
    _write_csv(repo / "jobhunt-data" / "tracking" / "jobs" / "jobs.csv",
               JOBS_HEADER, rows)


def _seed_registry(repo, rows):
    _write_csv(repo / "jobhunt-data" / "tracking" / "companies"
               / "companies_registry.csv", REGISTRY_HEADER, rows)


# ---------------------------------------------------------------------------
# Company mode
# ---------------------------------------------------------------------------

def test_resolve_company(tmp_path):
    _seed_registry(tmp_path, [
        {"company_slug": "scale_ai", "company": "Scale AI"},
    ])
    t = resolve_target("--company", "Scale AI", repo=tmp_path)
    assert t["kind"] == "company"
    assert t["company"] == "Scale AI"
    assert t["company_slug"] == "scale_ai"
    assert t["job"] is None and t["jd_path"] is None and t["hints"] is None


def test_resolve_company_by_slug(tmp_path):
    _seed_registry(tmp_path, [
        {"company_slug": "scale_ai", "company": "Scale AI"},
    ])
    t = resolve_target("--company", "scale_ai", repo=tmp_path)
    assert t["company_slug"] == "scale_ai"


def test_resolve_company_unknown_raises(tmp_path):
    _seed_registry(tmp_path, [
        {"company_slug": "scale_ai", "company": "Scale AI"},
    ])
    with pytest.raises(TargetNotFound):
        resolve_target("--company", "Nonexistent Corp", repo=tmp_path)


def test_resolve_company_missing_registry_raises(tmp_path):
    with pytest.raises(TargetNotFound):
        resolve_target("--company", "Scale AI", repo=tmp_path)


# ---------------------------------------------------------------------------
# Job mode
# ---------------------------------------------------------------------------

def test_resolve_job_from_jobs_csv(tmp_path):
    _seed_jobs_csv(tmp_path, [_job_row()])
    url = "https://jobs.eu.lever.co/scale/abc"
    t = resolve_target("--job-url", url, repo=tmp_path)
    assert t["kind"] == "job"
    assert t["company"] == "Scale AI"
    assert t["company_slug"] == "scale_ai"
    assert t["job"]["role_family"] == "post_training"
    assert t["job"]["job_url"] == url
    assert t["job"]["title"] == "Research Engineer, Post-Training"
    assert t["hints"] is None


def test_resolve_job_matches_canonical_url(tmp_path):
    _seed_jobs_csv(tmp_path, [_job_row(
        canonical_application_url="https://jobs.eu.lever.co/scale/abc?ref=li")])
    t = resolve_target("--job-url", "https://jobs.eu.lever.co/scale/abc?ref=li",
                       repo=tmp_path)
    assert t["kind"] == "job"
    assert t["job"]["job_id"] == "scale_ai_research_engineer_post_training_abc"


def test_resolve_job_fuzzy_fallback(tmp_path):
    _seed_jobs_csv(tmp_path, [_job_row(
        job_url="https://jobs.lever.co/scaleai/xyz123",
        canonical_application_url="https://jobs.lever.co/scaleai/xyz123")])
    t = resolve_target(
        "--job-url",
        "https://jobs.eu.lever.co/scale/research-engineer-post-training",
        repo=tmp_path)
    assert t["kind"] == "job"
    assert t["company_slug"] == "scale_ai"
    assert t["job"]["title"] == "Research Engineer, Post-Training"


def test_resolve_job_jd_path_resolved_when_file_exists(tmp_path):
    jd_rel = "tracking/job_descriptions/active/scale_ai__x.md"
    _seed_jobs_csv(tmp_path, [_job_row(description_file=jd_rel)])
    jd_file = tmp_path / "jobhunt-data" / jd_rel
    jd_file.parent.mkdir(parents=True, exist_ok=True)
    jd_file.write_text("# JD\n", encoding="utf-8")
    t = resolve_target("--job-url", "https://jobs.eu.lever.co/scale/abc",
                       repo=tmp_path)
    assert t["jd_path"] == str(jd_file)


def test_resolve_job_jd_path_none_when_file_missing(tmp_path):
    _seed_jobs_csv(tmp_path, [_job_row()])
    t = resolve_target("--job-url", "https://jobs.eu.lever.co/scale/abc",
                       repo=tmp_path)
    assert t["jd_path"] is None


def test_resolve_job_unknown_url_raises(tmp_path):
    _seed_jobs_csv(tmp_path, [_job_row()])
    with pytest.raises(TargetNotFound):
        resolve_target("--job-url", "https://x.example/nope", repo=tmp_path)


def test_resolve_job_missing_jobs_csv_raises(tmp_path):
    with pytest.raises(TargetNotFound):
        resolve_target("--job-url", "https://jobs.eu.lever.co/scale/abc",
                       repo=tmp_path)


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def test_invalid_flag_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        resolve_target("--url", "https://jobs.eu.lever.co/scale/abc",
                       repo=tmp_path)


def test_empty_value_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        resolve_target("--company", "", repo=tmp_path)
    with pytest.raises(ValueError):
        resolve_target("--job-url", "   ", repo=tmp_path)
