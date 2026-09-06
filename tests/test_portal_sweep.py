try:
    from scripts import config_lib
except ImportError:
    import config_lib
"""Unit tests for linkedin_portal_sweep merge logic (extraction fixture ->
normalized -> deduped -> scrutinized output). No browser, no live calls."""

import csv
import json
import os
import sys
import tempfile

import yaml

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import linkedin_portal_sweep as sweep  # noqa: E402

# The saved-searches registry resolves through data_root() at sweep-module
# import time, which is polluted by ambient $JOBHUNT_HOME during collection.
# Point it at the repo-local shipped registry instead, and skip this module
# entirely on a fresh clone where the registry has not been created yet.
REGISTRY = os.path.join(
    REPO, "jobhunt-data", "job_research", "config", "linkedin_saved_searches.yaml"
)
if os.path.exists(REGISTRY):
    sweep.REGISTRY_PATH = REGISTRY


def _require_registry():
    if not os.path.exists(REGISTRY):
        pytest.skip(
            f"fresh clone: LinkedIn registry not found at {REGISTRY} "
            "(personal config, gitignored)"
        )


def _fixture():
    path = os.path.join(REPO, "tests", "fixtures", "linkedin_extraction_fixture.json")
    with open(path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_counts_base_plus_c2():
    _require_registry()
    searches = sweep.build_registry(REGISTRY)
    base = [s for s in searches if s["tier"] == "base"]
    c2 = [s for s in searches if s["tier"] == "c2"]
    assert len(base) >= 8
    assert len(c2) == 23  # target companies without career-ops ATS coverage
    assert all(s["company"] for s in c2)
    ids = [s["id"] for s in searches]
    assert len(ids) == len(set(ids))


def test_build_search_url_has_freshness_and_experience_params():
    _require_registry()
    cfg = yaml.safe_load(open(sweep.REGISTRY_PATH))
    entry = sweep.build_registry(REGISTRY)[0]
    url = sweep.build_search_url(entry, cfg["geos"], cfg["defaults"])
    assert url.startswith("https://www.linkedin.com/jobs/search")
    assert "f_TPR=r604800" in url          # <=7 days freshness
    assert "f_E=2%2C3" in url              # Associate + Mid-Senior
    assert "geoId=103644278" in url        # US remote geo


def test_cap_searches_round_robins_tiers():
    _require_registry()
    searches = sweep.build_registry(REGISTRY)
    picked = sweep.cap_searches(searches, 8)
    assert len(picked) == 8
    tiers = {s["tier"] for s in picked}
    assert tiers == {"base", "c2"}


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def _merge_with_tmp_jobs(extraction):
    """Merge against an empty temp jobs.csv so results are deterministic."""
    with tempfile.TemporaryDirectory() as tmp:
        jobs_csv = os.path.join(tmp, "jobs.csv")
        accepted, duplicates, rejected = sweep.merge_extraction(
            extraction, sweep.load_dedup_index(jobs_csv), "test_search"
        )
    return accepted, duplicates, rejected


def test_merge_normalizes_dedups_scrutinizes():
    extraction = _fixture()
    accepted, duplicates, rejected = _merge_with_tmp_jobs(extraction)
    seen_urls = {r["job_url"] for r in accepted} | {r["job_url"] for r in duplicates}
    # every row that passes scrutiny lands exactly once across accepted+duplicates
    assert seen_urls == {
        "https://www.linkedin.com/jobs/view/4100000001",
        "https://www.linkedin.com/jobs/view/4100000002",
    }
    # duplicate of the same URL within the batch is deduped, not double-added
    dup_urls = [d["job_url"] for d in duplicates]
    assert dup_urls  # fixture contains at least one in-batch/existing dup
    for row in accepted:
        assert row["status"] == "open"
        assert row["source"] == "linkedin"
        assert row["date_discovered"]
        verdict, _ = __import__("discovery_lib").scrutinize(row)
        assert verdict == "accept"
    for row in rejected:
        assert row["flags"]


def test_merge_rejects_unsupported_location_and_missing_fields():
    extraction = [
        {"title": "ML Engineer", "company": "Acme", "url": "https://x.example/1",
         "location": "Bangalore, India", "posted_age": "3 days ago"},
        {"title": "", "company": "Acme", "url": "https://x.example/2"},
    ]
    accepted, duplicates, rejected = _merge_with_tmp_jobs(extraction)
    assert accepted == [] and duplicates == []
    flags = {r["flags"][0] for r in rejected}
    assert flags == {"india_below_exceptional", "missing_required_field"}


def test_append_jobs_then_dedup_prevents_second_insert(tmp_path):
    jobs_csv = str(tmp_path / "jobs.csv")
    extraction = [e for e in _fixture() if e.get("url")][:3]
    dedup = sweep.load_dedup_index(jobs_csv)  # missing file -> empty index
    accepted, _, _ = sweep.merge_extraction(extraction, dedup, "run1")
    n1 = sweep.append_jobs(accepted, jobs_csv)
    # second pass against the now-populated csv must yield zero new rows
    dedup2 = sweep.load_dedup_index(jobs_csv)
    accepted2, dups2, _ = sweep.merge_extraction(extraction, dedup2, "run2")
    assert n1 == len(accepted) > 0
    assert accepted2 == [] and len(dups2) == 3  # url rows all seen now (incl. in-batch dup)
    with open(jobs_csv) as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == n1


def test_log_search_run_creates_csv_with_header(tmp_path):
    runs_csv = str(tmp_path / "search_runs.csv")
    sweep.log_search_run("s1", 10, 2, 1, "ok", runs_csv=runs_csv)
    sweep.log_search_run("s2", 5, 0, 0, "no_results", runs_csv=runs_csv)
    with open(runs_csv) as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == sweep.SEARCH_RUNS_HEADER
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# parse_search_results_html — fetch-based extractor for the current
# hash-classed LinkedIn DOM (structure captured live 2026-08-24)
# ---------------------------------------------------------------------------

def _card_html(job_id, title, company, location, salary="", alumni="", posted=""):
    """Minimal card region mimicking the double componentkey layout."""
    inner = f"<p>{title}</p><p>{company}</p><p>{location}</p>"
    if salary:
        inner += f"<p>{salary}</p>"
    if alumni:
        inner += f"<p>{alumni}</p>"
    if posted:
        inner += f"<p>Posted {posted}</p>"
    return (
        f'<button class="a9768087 hashed" componentkey="job-card-component-ref-{job_id}">'
        f'<div class="cc5d114c" componentkey="job-card-component-ref-{job_id}">{inner}</div>'
        f"</button>"
    )


def test_parse_search_results_html_extracts_card_fields():
    html = (
        "<html><style>.x{color:red}</style><body>"
        + _card_html("4418852774", "Applied AI Engineer", "OpenAI",
                     "Seattle, WA (On-site)", salary="$230K/yr - $385K/yr",
                     alumni="64 company alumni work here", posted="1 day ago")
        + _card_html("4437084478", "Advisory AI Prototyping Engineer", "Lenovo",
                     "North Carolina, United States", posted="3 days ago")
        + "</body></html>"
    )
    rows = sweep.parse_search_results_html(html)
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["title"] == "Applied AI Engineer"
    assert r0["company"] == "OpenAI"
    assert r0["location"] == "Seattle, WA (On-site)"
    assert r0["salary"] == "$230K/yr - $385K/yr"
    assert r0["alumni"] == "64 company alumni work here"
    assert r0["posted_age"] == "Posted 1 day ago"
    assert r0["source_id"] == "4418852774"
    assert r0["url"].endswith("/jobs/view/4418852774/")
    # second row has no salary/alumni tokens -> empty strings
    assert rows[1]["salary"] == "" and rows[1]["alumni"] == ""


def test_parse_dedupes_double_componentkey_and_html_entities():
    html = (
        _card_html("4456844850", "AI Engineer ($170k-$220k) at Withshepherd",
                   "Jack &amp; Jill", "San Francisco, CA (On-site)", posted="34 minutes ago")
    )
    rows = sweep.parse_search_results_html(html)
    assert len(rows) == 1  # id appears twice; emitted once
    assert rows[0]["company"] == "Jack & Jill"  # entity unescaped


def test_parse_returns_empty_for_legacy_or_empty_dom():
    assert sweep.parse_search_results_html("<html><body>No cards</body></html>") == []
    assert sweep.parse_search_results_html("") == []
