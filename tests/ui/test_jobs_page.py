"""Tests for the overhauled Jobs page data layer (filters + saved views)."""

from __future__ import annotations

import importlib
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
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


JOBS_CSV = (
    "job_id,company,title,status,source,fit_tier,application_priority,priority_v2,recommended_action\n"
    "j1,Acme,ML Eng,open,linkedin,A,tier_1_now,92,apply_now\n"
    "j2,Beta,Data Eng,open,indeed,B,,70,tailored_resume\n"
    "j3,Gamma,ML Eng,closed,linkedin,A,tier_1_now,80,\n"
    "j4,Delta,MLOps,expired,referral,,tier_2_next,55,network_first\n"
)


def _jobs() -> pd.DataFrame:
    return pd.read_csv(pd.io.common.StringIO(JOBS_CSV))


# --- filter_jobs: new dimensions --------------------------------------------


def test_filter_jobs_source_case_insensitive(data_root):
    from ui import data as d

    jobs = _jobs()
    assert list(d.filter_jobs(jobs, source="LINKEDIN")["job_id"]) == ["j1", "j3"]
    assert list(d.filter_jobs(jobs, source="indeed")["job_id"]) == ["j2"]
    # Empty source -> no filtering.
    assert len(d.filter_jobs(jobs)) == 4
    # Missing source column -> empty result rather than a crash.
    assert d.filter_jobs(jobs.drop(columns=["source"]), source="linkedin").empty


def test_filter_jobs_status(data_root):
    from ui import data as d

    jobs = _jobs()
    assert list(d.filter_jobs(jobs, status="OPEN")["job_id"]) == ["j1", "j2"]
    assert list(d.filter_jobs(jobs, status="expired")["job_id"]) == ["j4"]
    assert d.filter_jobs(jobs.iloc[0:0], status="open").empty
    assert d.filter_jobs(jobs.drop(columns=["status"]), status="open").empty


def test_filter_jobs_min_priority(data_root):
    from ui import data as d

    jobs = _jobs()
    assert list(d.filter_jobs(jobs, min_priority=80)["job_id"]) == ["j1", "j3"]
    assert list(d.filter_jobs(jobs, min_priority=55.5)["job_id"]) == [
        "j1", "j2", "j3"]
    # None / 0 -> no filtering.
    assert len(d.filter_jobs(jobs, min_priority=None)) == 4
    assert len(d.filter_jobs(jobs, min_priority=0)) == 4
    # Non-numeric scores are dropped when the filter is active.
    dirty = pd.DataFrame({"priority_v2": ["92", "not-a-number", None]})
    assert list(d.filter_jobs(dirty, min_priority=10)["priority_v2"]) == ["92"]
    # Missing column -> empty rather than a crash.
    assert d.filter_jobs(jobs.drop(columns=["priority_v2"]),
                         min_priority=10).empty


def test_filter_jobs_combined_dimensions_and_backward_compat(data_root):
    from ui import data as d

    jobs = _jobs()
    out = d.filter_jobs(
        jobs,
        search="ml eng",
        fit_tier="a",
        priority="tier_1_now",
        source="LinkedIn",
        status="open",
        min_priority=90,
    )
    assert list(out["job_id"]) == ["j1"]
    # Positional call style of existing callers still works.
    legacy = d.filter_jobs(jobs, "acme", "", "")
    assert list(legacy["job_id"]) == ["j1"]


# --- saved views -------------------------------------------------------------


def test_saved_views_missing_file_returns_empty(data_root):
    from ui import data as d

    assert d.list_saved_views() == []
    assert not (data_root / "tracking" / "jobs" / "saved_views.csv").exists()


def test_saved_view_roundtrip_upsert_and_delete(data_root):
    from ui import data as d

    saved = d.save_view("Top Open Jobs", search="ml", fit_tier="A",
                        priority="tier_1_now", source="linkedin",
                        status="open", min_priority=80,
                        sort_by="priority_v2", sort_dir="desc")
    assert saved["view_id"] == "top-open-jobs"
    assert saved["name"] == "Top Open Jobs"

    views = d.list_saved_views()
    assert [v["view_id"] for v in views] == ["top-open-jobs"]
    row = views[0]
    for key in ("search", "fit_tier", "priority", "source", "status"):
        assert row[key]
    assert float(row["min_priority"]) == 80.0
    assert row["sort_by"] == "priority_v2" and row["sort_dir"] == "desc"
    assert row["created_at"]

    # Upsert by name: same name replaces, no duplicate rows.
    updated = d.save_view("Top Open Jobs", search="", fit_tier="B",
                          sort_by="company", sort_dir="asc")
    views = d.list_saved_views()
    assert len(views) == 1
    assert views[0]["fit_tier"] == "B"
    assert views[0]["search"] == ""
    assert views[0]["sort_by"] == "company"
    assert updated["view_id"] == "top-open-jobs"

    # Second view coexists; slugified ids stay unique.
    d.save_view("Expired Only", status="expired")
    names = {v["name"] for v in d.list_saved_views()}
    assert names == {"Top Open Jobs", "Expired Only"}

    assert d.delete_view("expired-only") is True
    assert [v["view_id"] for v in d.list_saved_views()] == ["top-open-jobs"]
    # Deleting an unknown id is a no-op returning False.
    assert d.delete_view("expired-only") is False
    assert len(d.list_saved_views()) == 1

    # save_view without a name is rejected.
    with pytest.raises(ValueError):
        d.save_view("   ")
