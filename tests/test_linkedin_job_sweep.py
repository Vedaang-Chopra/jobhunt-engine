"""Network-free contract tests for the canonical LinkedIn Jobs runner."""
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from linkedin_job_sweep import (
    _date_posted, _merge_sources, append_jobs, guest_search_url, logged_in_search_path,
    parse_guest_cards,
)
from linkedin_query_planner import plan_queries, load_catalog


def planned_query():
    cfg = load_catalog(REPO / "setup" / "linkedin-job-queries.yaml")
    return plan_queries(cfg, [])[0]


def test_both_retrieval_urls_enforce_us_week_and_experience_filters():
    query = planned_query()
    guest = guest_search_url(query)
    logged = logged_in_search_path(query)
    for url in (guest, logged):
        assert "location=United+States" in url
        assert "geoId=103644278" in url
        assert "f_TPR=r604800" in url
        assert "f_E=2%2C3" in url
        assert "keywords=ML+Research+Engineer" in url


def test_logged_in_relative_age_is_normalized_to_iso_date():
    value = _date_posted({"posted_age": "Posted 3 days ago"})
    assert len(value) == 10
    assert value[4] == "-" and value[7] == "-"


def test_guest_parser_and_dual_path_merge_dedupe_by_source_id():
    fixture = '''<ol><div class="base-card x"><a href="https://www.linkedin.com/jobs/view/ml-role-12345"><h3>ML Engineer LLM</h3><h4>Acme AI</h4><span class="job-search-card__location">Austin, TX</span><time datetime="2026-09-10">1 day ago</time></a></div></ol>'''
    guest = parse_guest_cards(fixture)
    assert len(guest) == 1 and guest[0]["source_id"] == "12345"
    logged = [{**guest[0], "salary": "$180K-$220K", "retrieval_path": "logged_in"}]
    merged = _merge_sources(guest, logged)
    assert len(merged) == 1
    assert merged[0]["salary"] == "$180K-$220K"
    assert merged[0]["retrieval_paths"] == ["guest", "logged_in"]


def test_append_jobs_adds_structured_columns_without_dropping_existing(tmp_path):
    target = tmp_path / "jobs.csv"
    target.write_text("job_id,company,title\nold,Old Co,Old Role\n", encoding="utf-8")
    row = {
        "job_id": "new", "company": "Acme", "title": "AI Engineer",
        "technical_families": "agents", "eligibility_verdict": "eligible",
        "qualification_json": "{}",
    }
    assert append_jobs([row], target) == 1
    with target.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    assert {"technical_families", "eligibility_verdict", "qualification_json"} <= fields
    assert rows[0]["job_id"] == "old"
    assert rows[1]["job_id"] == "new"
