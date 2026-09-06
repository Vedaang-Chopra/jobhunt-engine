"""Tests for the ui.data CSV wrappers (Task 2.1)."""

from __future__ import annotations

import sys
from pathlib import Path

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
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    # Reload so module-level state picks up the patched env var.
    import importlib

    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


def test_load_missing_files_returns_empty(data_root):
    from ui import data as d

    df = d.load_jobs()
    assert df.empty
    assert list(df.columns) == ["job_id", "company", "title", "status", "fit_score"]
    assert d.load_applications().empty
    assert d.load_contacts().empty
    assert d.load_companies().empty


def test_load_csv_graceful_on_bad_file(data_root):
    from ui import data as d

    bad = data_root / "tracking" / "jobs" / "broken.csv"
    bad.write_bytes(b"a,b\n\x00\xff\xfe garbage,binary\n")
    df = d.load_csv("tracking/jobs/broken.csv", columns=["a", "b"])
    assert df.empty
    assert list(df.columns) == ["a", "b"]


def test_load_real_csv_fixtures(data_root):
    from ui import data as d

    (data_root / "tracking" / "jobs" / "jobs.csv").write_text(
        "job_id,company,title,status,fit_score\nj1,Acme,ML Eng,open,90\nj2,Beta,ML Eng,closed,70\n"
    )
    (data_root / "tracking" / "applications" / "applications.csv").write_text(
        "application_id,job_id,status,date_submitted\na1,j1,submitted,2026-08-01\na2,j2,queued,\n"
    )
    (data_root / "tracking" / "contacts" / "contacts.csv").write_text("contact_id,name\n")
    (data_root / "tracking" / "companies" / "companies.csv").write_text("company_slug\nacme\n")

    jobs = d.load_jobs()
    apps = d.load_applications()
    assert len(jobs) == 2
    assert len(apps) == 2

    counts = d.kpi_counts()
    assert counts == {
        "jobs": 2,
        "open_jobs": 1,
        "applications": 2,
        "submitted": 1,
        "contacts": 0,
        "companies": 1,
    }


def test_kpi_counts_empty_state(data_root):
    from ui import data as d

    counts = d.kpi_counts()
    assert set(counts) == {"jobs", "open_jobs", "applications", "submitted", "contacts", "companies"}
    assert all(v == 0 for v in counts.values())
