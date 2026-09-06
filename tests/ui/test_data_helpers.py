"""Tests for the Task 3.1 UI data helpers (queue views, filters, details)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    (root / "tracking" / "jobs").mkdir(parents=True)
    (root / "tracking" / "applications").mkdir(parents=True)
    (root / "tracking" / "contacts").mkdir(parents=True)
    (root / "tracking" / "companies").mkdir(parents=True)
    (root / "execution_results" / "reviews").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import importlib

    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


JOBS_CSV = (
    "job_id,company,title,status,fit_score,fit_tier,application_priority\n"
    "j1,Acme,ML Eng,open,92,A,tier_1_now\n"
    "j2,Beta,Data Eng,open,70,B,\n"
    "j3,Gamma,ML Eng,closed,80,A,tier_1_now\n"
    "j4,Delta,MLOps,open,55,,tier_2_next\n"
)


# --- filter_jobs ------------------------------------------------------------


def test_filter_jobs_search_and_columns(data_root):
    from ui import data as d

    jobs = pd.read_csv(pd.io.common.StringIO(JOBS_CSV))
    assert len(d.filter_jobs(jobs)) == 4
    assert list(d.filter_jobs(jobs, search="acme")["job_id"]) == ["j1"]
    # Case-insensitive match across any column (title here).
    assert list(d.filter_jobs(jobs, search="ml eng")["job_id"]) == ["j1", "j3"]
    assert list(d.filter_jobs(jobs, fit_tier="a")["job_id"]) == ["j1", "j3"]
    assert list(d.filter_jobs(jobs, priority="TIER_2_NEXT")["job_id"]) == ["j4"]
    # Filter column missing -> empty result rather than a crash.
    no_tier = jobs.drop(columns=["fit_tier"])
    assert d.filter_jobs(no_tier, fit_tier="A").empty
    assert d.filter_jobs(jobs.iloc[0:0], search="x").empty


# --- tier_counts ------------------------------------------------------------


def test_tier_counts_open_only_and_sorted(data_root):
    from ui import data as d

    jobs = pd.read_csv(pd.io.common.StringIO(JOBS_CSV))
    counts = d.tier_counts(jobs)
    assert counts == [("A", 1), ("B", 1), ("", 1)]
    assert d.tier_counts(jobs.iloc[0:0]) == []
    assert d.tier_counts(jobs.drop(columns=["fit_tier"])) == []


# --- connections_pending ----------------------------------------------------


def test_connections_pending(data_root):
    from ui import data as d

    contacts = pd.DataFrame(
        {"outreach_status": ["contacted", "", "pending", None, "queued"]}
    )
    assert d.connections_pending(contacts) == 4
    assert d.connections_pending(contacts.drop(columns=["outreach_status"])) == 0
    assert d.connections_pending(pd.DataFrame()) == 0


# --- job_detail -------------------------------------------------------------


def test_job_detail_orders_known_fields_then_extras(data_root):
    from ui import data as d

    record = {
        "job_url": "https://example.com/1",
        "title": "ML Eng",
        "company": "Acme",
        "notes": "",  # empty -> dropped
        "mystery_extra": "kept",
        "fit_tier": None,  # NaN-like -> dropped
    }
    pairs = d.job_detail(record)
    fields = [f for f, _ in pairs]
    # Known fields first in canonical order...
    assert fields[:2] == ["company", "title"] or fields[0] in d.JOB_DETAIL_FIELDS
    assert "notes" not in fields and "fit_tier" not in fields
    # ...unknown extras appended at the end.
    assert fields[-1] == "mystery_extra"
    assert dict(pairs)["job_url"] == "https://example.com/1"


# --- load_queue_views / get_followups ---------------------------------------


def test_load_queue_views_reads_today_queue_outputs(data_root):
    from ui import data as d

    reviews = data_root / "execution_results" / "reviews"
    (reviews / "top_queue.csv").write_text("job_id,company\nq1,Acme\n")
    (reviews / "needing_attention.csv").write_text("job_id,attention_reasons\nn1,stale_flagged\n")
    (reviews / "fresh_jobs_2099-01-01.csv").write_text("job_id,company\nf1,Beta\n")

    views = d.load_queue_views()
    assert list(views["top_queue"]["job_id"]) == ["q1"]
    assert list(views["needing_attention"]["job_id"]) == ["n1"]
    # No snapshot for today -> falls back to the latest dated one.
    assert list(views["fresh_jobs"]["job_id"]) == ["f1"]

    # Mutually exclusive buckets: a job in top_queue/needing_attention is
    # removed from the other sections.
    (reviews / "fresh_jobs_2099-01-01.csv").write_text(
        "job_id,company\nf1,Beta\nq1,Acme\nn1,Gamma\nf2,Delta\n")
    (reviews / "needing_attention.csv").write_text(
        "job_id,attention_reasons\nn1,stale_flagged\nq1,thin_jd\n")
    views = d.load_queue_views()
    assert list(views["top_queue"]["job_id"]) == ["q1"]
    # Fresh wins over needing attention; q1 was already in top queue.
    assert sorted(views["fresh_jobs"]["job_id"]) == ["f1", "f2", "n1"]
    assert list(views["needing_attention"]["job_id"]) == []

    # Missing everything -> graceful empties.
    for path in reviews.glob("*.csv"):
        path.unlink()
    views = d.load_queue_views()
    assert all(df.empty for df in views.values())


def test_get_followups_delegates_to_followups_lib(data_root):
    from ui import data as d

    (data_root / "tracking" / "applications" / "applications.csv").write_text(
        "application_id,job_id,company,status,date_submitted\n"
        "a1,j1,Acme,submitted,2020-01-01\n"
    )
    followups = d.get_followups()
    assert len(followups) == 1
    assert followups[0]["action"] == "nudge_recruiter"


def test_get_followups_graceful_on_missing_columns(data_root):
    from ui import data as d

    (data_root / "tracking" / "applications" / "applications.csv").write_text(
        "application_id,status\na1,queued\n"
    )
    assert d.get_followups() == []
