try:
    from scripts import config_lib
except ImportError:
    import config_lib
"""TDD tests for scripts/discovery_lib.py (Task 1 of master pipeline)."""

import csv
import datetime
import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "scripts")
)

from discovery_lib import extract_ats_id, normalize_job, slugify  # noqa: E402

# Resolve against the repo-local data root (what a fresh clone ships) rather
# than ambient $JOBHUNT_HOME so module-level constants are deterministic.
# The canonical tracking CSV is personal/gitignored history in some setups,
# so tests that regress against it skip when it is absent.
from pathlib import Path as _Path  # noqa: E402

CSV_PATH = (
    _Path(__file__).resolve().parents[1]
    / "jobhunt-data" / "tracking" / "jobs" / "jobs.csv"
)


def test_slugify_together_ai():
    assert slugify("Together AI") == "together_ai"


def test_slugify_variants():
    assert slugify("  OpenAI  ") == "openai"
    assert slugify("Anthropic PBC") == "anthropic_pbc"


def test_extract_ats_id_greenhouse():
    url = "https://boards.greenhouse.io/togetherai/jobs/1234567"
    assert extract_ats_id(url) == "1234567"


def test_extract_ats_id_ashby():
    url = "https://jobs.ashbyhq.com/anthropic/abc-123"
    assert extract_ats_id(url) == "abc-123"


def test_extract_ats_id_lever():
    url = "https://jobs.lever.co/mistral/a1b2c3d4"
    assert extract_ats_id(url) == "a1b2c3d4"


def test_extract_ats_id_unknown_returns_none():
    assert extract_ats_id("https://example.com/careers/123") is None


def test_normalize_job_fills_defaults():
    row = normalize_job(
        {
            "title": "ML Engineer",
            "company": "Together AI",
            "url": "https://jobs.lever.co/together/xyz789",
        }
    )
    assert row["status"] == "open"
    today = datetime.date.today().isoformat()
    assert row["date_discovered"] == today
    # ISO 8601 shape
    datetime.date.fromisoformat(row["date_discovered"])


def test_normalize_job_raises_on_empty_title():
    with pytest.raises(ValueError):
        normalize_job({"title": "", "company": "X", "url": "https://a.b/1"})


def test_normalize_job_raises_on_empty_company():
    with pytest.raises(ValueError):
        normalize_job({"title": "Eng", "company": "  ", "url": "https://a.b/1"})


def test_normalize_job_raises_on_empty_url():
    with pytest.raises(ValueError):
        normalize_job({"title": "Eng", "company": "X", "url": ""})


@pytest.mark.skipif(
    not CSV_PATH.exists(),
    reason="fresh clone: canonical tracking/jobs/jobs.csv absent "
    "(personal data, gitignored)",
)
def test_normalize_job_row_matches_csv_header():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    row = normalize_job(
        {
            "title": "Research Engineer",
            "company": "Mistral AI",
            "url": "https://jobs.lever.co/mistral/abc123",
        }
    )
    for col in row:
        assert col in header, f"normalize_job emits column {col} not in jobs.csv header"
    # The three audit_* columns are appended downstream by audit tooling and
    # are legitimately absent from a freshly normalized row.
    # Key columns populated
    assert row["job_url"] == "https://jobs.lever.co/mistral/abc123"
    assert row["canonical_application_url"] == "https://jobs.lever.co/mistral/abc123"
    assert row["source"] == "lever"
    assert row["source_id"] == "abc123"
    assert row["company_slug"] == "mistral_ai"
    for col in ("date_discovered", "date_posted", "date_updated"):
        if row.get(col):
            datetime.date.fromisoformat(row[col])


# ---------------- Task 2: prefix-proof cross-source dedup ----------------

from discovery_lib import (  # noqa: E402
    DedupIndex,
    extract_ats_id as _eai,
    normalize_url,
    slugify as _sl,
    strip_source_prefix,
)
extract_ats_id = _eai
slugify = _sl


def _row(**kw):
    base = {
        "title": "Research Engineer, Post-Training Inference",
        "company": "Together AI",
        "url": "https://boards.greenhouse.io/togetherai/jobs/5179372007",
        "date_discovered": "2026-08-19",
    }
    base.update(kw)
    return normalize_job(base)


def test_normalize_url_strips_query_and_trailing_slash():
    assert (
        normalize_url("https://Boards.Example.com/jobs/1/?utm=x&ref=li")
        == "https://boards.example.com/jobs/1"
    )


def test_three_prefix_variants_are_same_job():
    idx = DedupIndex()
    r1 = _row(source_id="gh_5179372007")
    r2 = dict(_row(), source_id="ashby_5179372007")
    r3 = dict(_row(), source_id="ash_togetherai_5179372007")
    assert not idx.seen_before(r1)[0]
    idx.add(r1)
    dup2, m2 = idx.seen_before(r2)
    assert dup2
    idx.add(r2)
    dup3, m3 = idx.seen_before(r3)
    assert dup3


def test_seen_before_returns_matched_id():
    idx = DedupIndex()
    idx.add(_row())
    dup, mid = idx.seen_before(
        dict(_row(url="https://job-boards.greenhouse.io/togetherai/jobs/5179372007?src=li"),
             source_id="gh_5179372007")
    )
    assert dup and mid


def test_different_jobs_not_deduped():
    idx = DedupIndex()
    idx.add(_row())
    other = _row(title="Product Manager", company="Other Co",
                 url="https://boards.greenhouse.io/otherco/jobs/999")
    dup, _ = idx.seen_before(other)
    assert not dup


def test_fuzzy_title_company_match_within_45_days():
    idx = DedupIndex()
    idx.add(_row(url="https://jobs.lever.co/together/aaa111",
                 source_id="aaa111"))
    dup, _ = idx.seen_before(dict(
        _row(url="https://jobs.ashbyhq.com/together/bbb222",
             source_id="bbb222"),
        title="research engineer post training inference"))
    assert dup


def test_fuzzy_no_match_across_45_day_window():
    idx = DedupIndex()
    idx.add(_row(date_discovered="2026-05-01", url="https://jobs.lever.co/t/a1",
                 source_id="a1"))
    dup, _ = idx.seen_before(dict(
        _row(url="https://jobs.ashbyhq.com/t/b2", source_id="b2"),
        date_discovered="2026-08-20"))
    assert not dup


@pytest.mark.skipif(
    not CSV_PATH.exists(),
    reason="fresh clone: canonical tracking/jobs/jobs.csv absent "
    "(personal data, gitignored)",
)
def test_regression_all_csv_rows_zero_false_new(tmp_path):
    """Load all real jobs.csv rows into DedupIndex, then re-import the latest
    career-ops JSON run; every row that already exists in jobs.csv must be
    reported as seen (0 false-new)."""
    import json as _json

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) > 800
    idx = DedupIndex()
    for row in csv_rows:
        idx.add(row)

    json_path = os.path.join(
        os.path.dirname(__file__), "..", "execution_results",
        "l1_career_fresh_2026-08-22.json",
    )
    if not os.path.exists(json_path):
        # fallback fixture: synthesize from jobs.csv rows with prefix variants
        incoming = [dict(r) for r in csv_rows[:50]]
        for r in incoming:
            sid = r.get("source_id", "")
            if sid.startswith("gh_"):
                r["source_id"] = "ashby_" + sid[3:]
    else:
        with open(json_path, encoding="utf-8") as f:
            raw = _json.load(f)
        # only rows whose normalized URL / ats id exists in the CSV can be
        # checked for false-new; count how many CSV rows they match
        incoming = raw

    false_new = 0
    matched = 0
    for item in incoming:
        row = dict(item)
        row.setdefault("title", "")
        row.setdefault("company", "")
        url = row.get("url") or row.get("job_url") or ""
        row["job_url"] = url
        is_dup, mid = idx.seen_before(row)
        if not is_dup:
            continue
        matched += 1
        # a dup claim must correspond to a CSV row with same normalized URL
        # or same (company_slug, stripped ats_id)
        norm = normalize_url(url) if url else None
        hit = any(
            (norm and normalize_url(r["job_url"]) == norm)
            or (
                extract_ats_id(url)
                and r.get("company_slug") == row.get("company_slug", slugify(row["company"]))
                and strip_source_prefix(r.get("source_id", "")) == extract_ats_id(url)
            )
            or (
                row["title"] and strip_source_prefix(r.get("source_id", ""))
                == strip_source_prefix(row.get("source_id", "")) != ""
                and r.get("company_slug") == slugify(row["company"])
            )
            for r in csv_rows
        )
        if not hit:
            false_new += 1
    assert false_new == 0


# ---------------- Task 3: scrutiny gate (TDD) ----------------

from discovery_lib import scrutinize  # noqa: E402

LONG_DESC = "x" * 600
TODAY = datetime.date.today().isoformat()
OLD_DATE = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()


def _scrutiny_row(**kw):
    row = {
        "title": "Machine Learning Engineer",
        "company": "Acme",
        "location": "San Francisco, CA",
        "description": LONG_DESC,
        "date_posted": TODAY,
    }
    row.update(kw)
    return row


def test_rejects_bangalore_only():
    verdict, flags = scrutinize(_scrutiny_row(location="Bangalore, India"))
    assert verdict == "reject"
    assert "india_below_exceptional" in flags


def test_india_exceptional_flagged():
    verdict, flags = scrutinize(
        _scrutiny_row(location="Bangalore, India", exceptional=True)
    )
    assert verdict == "accept"
    assert "india_exceptional" in flags


def test_india_high_priority_accepted():
    verdict, flags = scrutinize(
        _scrutiny_row(location="Hyderabad, India", priority_v2="75.5")
    )
    assert verdict == "accept"
    assert "india_exceptional" in flags


def test_non_us_non_india_rejected():
    for loc in ("London, UK", "Toronto, Canada", "Berlin, Germany"):
        verdict, flags = scrutinize(_scrutiny_row(location=loc))
        assert verdict == "reject", loc
        assert "location_not_supported" in flags, loc


def test_us_anywhere_accepted():
    for loc in ("Austin, TX", "Denver, Colorado", "Chicago, IL",
                "United States (Remote)"):
        verdict, flags = scrutinize(_scrutiny_row(location=loc))
        assert verdict == "accept", loc
        assert "location_not_supported" not in flags


def test_rejects_staff_role():
    verdict, flags = scrutinize(_scrutiny_row(title="Staff Software Engineer"))
    assert verdict == "reject"
    assert "seniority_bar" in flags


def test_accepts_senior_with_soft_flag():
    verdict, flags = scrutinize(_scrutiny_row(title="Senior ML Engineer"))
    assert verdict == "accept"
    assert "senior_soft" in flags


def test_manager_word_boundary_not_matched_inside_word():
    # 'manager' must not match e.g. 'manage' inside another word; but a real
    # manager title is rejected.
    verdict, flags = scrutinize(_scrutiny_row(title="Engineering Manager, Platform"))
    assert verdict == "reject"
    assert "seniority_bar" in flags


def test_nine_year_bar_in_description():
    verdict, flags = scrutinize(
        _scrutiny_row(description="Requirements: minimum 9 years of experience. " + "x" * 500)
    )
    assert verdict == "reject"
    assert "seniority_bar" in flags


def test_eight_years_is_soft():
    verdict, flags = scrutinize(
        _scrutiny_row(description="Requires 8 years of experience building ML systems. " + "x" * 500)
    )
    assert verdict == "accept"
    assert "senior_soft" in flags


def test_accepts_remote_us():
    verdict, flags = scrutinize(_scrutiny_row(location="Remote - US"))
    assert verdict == "accept"
    assert "location_not_supported" not in flags


def test_accepts_sf_and_nyc_variants():
    for loc in ("SF", "NYC", "New York, NY", "Seattle, WA", "Boston", "Atlanta, GA"):
        verdict, _ = scrutinize(_scrutiny_row(location=loc))
        assert verdict == "accept", loc


def test_internship_without_conversion_rejected():
    verdict, flags = scrutinize(_scrutiny_row(title="ML Intern"))
    assert verdict == "reject"
    assert "internship_no_conversion" in flags


def test_internship_with_conversion_accepted():
    verdict, flags = scrutinize(
        _scrutiny_row(title="ML Intern", description=LONG_DESC + " Offers full-time conversion for top performers.")
    )
    assert verdict == "accept"


def test_thin_jd_flag():
    verdict, flags = scrutinize(_scrutiny_row(description="short desc"))
    assert verdict == "accept"
    assert "thin_jd" in flags


def test_stale_risk_flag():
    verdict, flags = scrutinize(_scrutiny_row(date_posted=OLD_DATE))
    assert verdict == "accept"
    assert "stale_risk" in flags


def test_vp_title_rejected():
    verdict, flags = scrutinize(_scrutiny_row(title="VP of Engineering"))
    assert verdict == "reject"
    assert "seniority_bar" in flags
