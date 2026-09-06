"""TDD tests for source-provenance enforcement (discovery_lib.normalize_source)."""

try:
    from scripts import config_lib
except ImportError:
    import config_lib

import csv
import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "scripts")
)

from discovery_lib import normalize_source, normalize_job  # noqa: E402

CONTROLLED_VOCABULARY = {
    "greenhouse", "lever", "ashby", "workday", "oracle_hcm",
    "wellfound", "linkedin", "company_page", "referral", "other",
}


# ---------------- URL shapes taken from live jobs.csv rows ----------------

def test_normalize_source_greenhouse_boards():
    assert normalize_source(
        "https://boards.greenhouse.io/togetherai/jobs/1234567") == "greenhouse"


def test_normalize_source_greenhouse_job_boards():
    assert normalize_source(
        "https://job-boards.greenhouse.io/togetherai/jobs/5179372007"
    ) == "greenhouse"


def test_normalize_source_greenhouse_gh_jid_query():
    # Legacy career-ops scan-history shape.
    assert normalize_source(
        "https://job-boards.greenhouse.io/acme/jobs/4001?gh_jid=4001"
    ) == "greenhouse"


def test_normalize_source_ashby():
    assert normalize_source(
        "https://jobs.ashbyhq.com/cohere/"
        "443368a3-6276-4b90-9671-27fed40fd6d2") == "ashby"


def test_normalize_source_lever():
    assert normalize_source(
        "https://jobs.lever.co/superannotate/"
        "26b7799a-b68a-47d2-bde1-891fbd7e2e68") == "lever"


def test_normalize_source_workday():
    assert normalize_source(
        "https://paloaltonetworks.wd5.myworkdayjobs.com/en-US/"
        "panwexternalcareers/job/Charlotte/Uni") == "workday"


def test_normalize_source_workday_site_variant():
    assert normalize_source(
        "https://acme.wd3.myworkdaysite.com/recruiting/acme/Jobs/1") == "workday"


def test_normalize_source_oracle_hcm():
    assert normalize_source(
        "https://edel.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/"
        "en/sites/CX_2001/job/23069") == "oracle_hcm"


def test_normalize_source_wellfound():
    assert normalize_source("https://wellfound.com/jobs/4574038-ai-engineer") \
        == "wellfound"


def test_normalize_source_linkedin_jobs_view():
    assert normalize_source(
        "https://www.linkedin.com/jobs/view/3813454490/") == "linkedin"


def test_normalize_source_linkedin_country_subdomain():
    assert normalize_source(
        "https://uk.linkedin.com/jobs/view/1234567/") == "linkedin"


def test_normalize_source_is_case_insensitive():
    assert normalize_source(
        "https://JOBS.Lever.CO/mistral/a1b2c3d4") == "lever"


def test_normalize_source_lookalike_host_not_matched():
    # "clever.company" contains "lever.co" as a substring — must NOT match.
    assert normalize_source("https://clever.company/jobs/1") == ""


# ---------------- fallback semantics ----------------

def test_normalize_source_company_career_page_fallback():
    assert normalize_source(
        "https://www.anthropic.com/careers/roles", fallback="company_page"
    ) == "company_page"


def test_normalize_source_unknown_returns_default_empty():
    assert normalize_source("https://example.com/careers/123") == ""


def test_normalize_source_empty_url_returns_fallback():
    assert normalize_source("", fallback="other") == "other"
    assert normalize_source(None, fallback="referral") == "referral"


def test_normalize_source_output_always_in_vocabulary():
    urls = [
        "https://boards.greenhouse.io/x/jobs/1",
        "https://jobs.ashbyhq.com/y/abc",
        "https://jobs.lever.co/z/xyz",
        "https://a.wd5.myworkdayjobs.com/en-US/b/job/c",
        "https://d.fa.us2.oraclecloud.com/hcmUI/job/1",
        "https://wellfound.com/jobs/1-x",
        "https://www.linkedin.com/jobs/view/99/",
        "not a url at all",
    ]
    for u in urls:
        val = normalize_source(u, fallback="other")
        assert val in CONTROLLED_VOCABULARY


# ---------------- writer-path enforcement ----------------

def _extraction(url):
    return [{
        "title": "ML Engineer",
        "company": "Together AI",
        "url": url,
        "location": "San Francisco",
    }]


def test_merge_extraction_never_writes_blank_source(tmp_path):
    """Synthetic row-writer path: merge_extraction -> append_jobs must never
    produce a row with a blank source, even when the caller passes source=''.
    """
    import linkedin_portal_sweep as sweep

    accepted, _, _ = sweep.merge_extraction(
        _extraction("https://www.linkedin.com/jobs/view/424242/"),
        sweep.DedupIndex(),
        search_id="test_search",
        source="",  # simulate unknown sweep-level source
    )
    assert accepted and all(r["source"] for r in accepted)
    assert all(r["source"] in CONTROLLED_VOCABULARY for r in accepted)

    out = tmp_path / "jobs.csv"
    sweep.append_jobs(accepted, str(out))
    with open(out, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["source"] == "linkedin"  # derived from the job URL


def test_explicit_source_still_wins_in_merge_extraction():
    import linkedin_portal_sweep as sweep

    accepted, _, _ = sweep.merge_extraction(
        _extraction("https://www.linkedin.com/jobs/view/424242/"),
        sweep.DedupIndex(),
        search_id="test_search",
        source="linkedin",
    )
    assert accepted[0]["source"] == "linkedin"


def test_normalize_job_row_enforcement_produces_non_blank_source():
    """The discovery_run.ingest enforcement chain applied to a raw row."""
    raw = {
        "title": "Platform Engineer",
        "company": "Anthropic",
        "url": "https://www.anthropic.com/careers/platform-engineer",
    }
    row = normalize_job(raw)
    url = raw["url"]
    row["source"] = row.get("source") or normalize_source(
        url, fallback="company_page") or "other"
    assert row["source"] == "company_page"
    assert row["source"] in CONTROLLED_VOCABULARY


# ---------------- career-ops import gate (extract_source refactor) --------

def test_import_career_ops_extract_source_via_normalize_source():
    import import_career_ops_scan as imp

    source, sid = imp.extract_source(
        "https://job-boards.greenhouse.io/togetherai/jobs/5179372007")
    assert source == "greenhouse"
    assert sid == "gh_5179372007"

    source, sid = imp.extract_source(
        "https://jobs.ashbyhq.com/cohere/"
        "443368a3-6276-4b90-9671-27fed40fd6d2")
    assert source == "ashby"
    assert sid == "443368a3"

    source, _sid = imp.extract_source(
        "https://www.linkedin.com/jobs/view/3813454490/")
    assert source is None  # non-direct-ATS URLs stay gated out

    source, _sid = imp.extract_source("https://example.com/careers/1")
    assert source is None


# ---------------- data-root resolution (hardcoded-path bug class) ----------

def test_writer_scripts_resolve_jobs_csv_through_data_root(monkeypatch):
    """No jobs.csv writer may hardcode <repo>/tracking/jobs/jobs.csv; the
    path must resolve through config_lib.data_root() ($JOBHUNT_HOME aware).
    """
    import importlib

    fake_root = "/tmp/fake-jobhunt-home"
    monkeypatch.setenv("JOBHUNT_HOME", fake_root)
    expected_tail = os.path.join("tracking", "jobs", "jobs.csv")

    for mod_name in ("linkedin_portal_sweep", "linkedin_recommended_sweep"):
        monkeypatch.delitem(sys.modules, mod_name, raising=False)
        sys.modules.pop(mod_name, None)
        mod = importlib.import_module(mod_name)
        assert str(mod.JOBS_CSV).endswith(expected_tail)
        assert fake_root in str(mod.JOBS_CSV)
        sys.modules.pop(mod_name, None)


@pytest.mark.parametrize("mod_name", [
    "linkedin_portal_sweep",
    "linkedin_recommended_sweep",
])
def test_writer_jobs_csv_matches_config_lib(mod_name):
    import importlib

    # Earlier tests may leave a stale copy of this module cached with
    # module-level paths resolved against a different data root; force a
    # fresh import so JOBS_CSV matches config_lib under the pinned env.
    sys.modules.pop(mod_name, None)
    mod = importlib.import_module(mod_name)
    expected = str(config_lib.data_root() / "tracking" / "jobs" / "jobs.csv")
    assert str(mod.JOBS_CSV) == expected
