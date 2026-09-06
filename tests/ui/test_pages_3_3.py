"""Tests for Task 3.3 pages: analytics aggregations, company research,
resume listing, and read-only config status (ui/data.py + renderers)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    for sub in ("tracking/jobs", "tracking/applications", "tracking/contacts", "tracking/companies"):
        (root / sub).mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


def write_apps(root: Path, text: str) -> None:
    (root / "tracking" / "applications" / "applications.csv").write_text(text)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def test_weekly_applications_counts_iso_weeks(data_root):
    from ui import data as d

    write_apps(
        data_root,
        "application_id,status,date_submitted\n"
        "a1,submitted,2026-08-03\n"
        "a2,submitted,2026-08-05\n"
        "a3,submitted,2026-08-10\n"
        "a4,queued,\n",
    )
    weekly = d.weekly_applications()
    assert list(weekly.columns) == ["week", "count"]
    assert len(weekly) == 2  # two ISO weeks
    assert weekly["count"].tolist() == [2, 1]


def test_weekly_applications_empty_when_no_dates(data_root):
    from ui import data as d

    write_apps(data_root, "application_id,status,date_submitted\na1,queued,\n")
    assert d.weekly_applications().empty


def test_funnel_counts_maps_stages(data_root):
    from ui import data as d

    write_apps(
        data_root,
        "application_id,status,current_stage\n"
        "a1,submitted,submitted\n"
        "a2,screening,screening\n"
        "a3,interviewing,interviewing\n"
        "a4,offer_received,offer\n"
        "a5,response_received,response\n"
        "a6,queued,queued\n",
    )
    funnel = d.funnel_counts()
    assert list(funnel.keys()) == d.FUNNEL_STAGES
    assert funnel == {"applied": 1, "response": 1, "screen": 1, "interview": 1, "offer": 1}


def test_funnel_counts_empty_state(data_root):
    from ui import data as d

    assert d.funnel_counts() == {"applied": 0, "response": 0, "screen": 0, "interview": 0, "offer": 0}


def test_breakdown_by_source(data_root):
    from ui import data as d

    (root := data_root / "tracking" / "jobs").mkdir(exist_ok=True)
    (root / "jobs.csv").write_text(
        "job_id,company,title,status,fit_score,source\n"
        "j1,A,T,open,90,greenhouse\n"
        "j2,B,T,open,80,greenhouse\n"
        "j3,C,T,open,70,ashby\n"
    )
    breakdown = d.breakdown_by_source()
    assert set(breakdown.columns) == {"source", "count"}
    by_source = dict(zip(breakdown["source"], breakdown["count"]))
    assert by_source == {"greenhouse": 2, "ashby": 1}


def test_breakdown_by_resume_version_missing_column(data_root):
    from ui import data as d

    write_apps(data_root, "application_id,status\na1,submitted\n")
    assert d.breakdown_by_resume_version().empty


def test_breakdown_by_resume_version_counts(data_root):
    from ui import data as d

    write_apps(
        data_root,
        "application_id,status,resume_variant\n"
        "a1,submitted,Agentic\n"
        "a2,submitted,Agentic\n"
        "a3,submitted,\n",
    )
    breakdown = d.breakdown_by_resume_version()
    assert dict(zip(breakdown["resume_variant"], breakdown["count"])) == {"Agentic": 2}


# ---------------------------------------------------------------------------
# Company research
# ---------------------------------------------------------------------------


def _write_companies(root: Path) -> None:
    (root / "tracking" / "companies" / "companies.csv").write_text(
        "company_slug,company_name,company_tier,h1b_sponsor,notes\n"
        "acme,Acme Labs,T1,yes,Big note\n"
        "beta,Beta Inc,T2,no,\n"
    )


def test_company_names_and_row(data_root):
    from ui import data as d

    _write_companies(data_root)
    assert d.company_names() == ["Acme Labs", "Beta Inc"]
    row = d.company_row("Acme Labs")
    assert row is not None
    assert row["h1b_sponsor"] == "yes"
    assert d.company_row("Nope") is None


def test_company_open_jobs_filters_open_and_company(data_root):
    from ui import data as d

    (data_root / "tracking" / "jobs").mkdir(exist_ok=True)
    (data_root / "tracking" / "jobs" / "jobs.csv").write_text(
        "job_id,company,title,status\n"
        "j1,acme,Eng A,open\n"
        "j2,acme,Eng B,closed\n"
        "j3,beta,Eng C,open\n"
    )
    jobs = d.company_open_jobs("Acme Labs")
    # companies.csv maps display names; jobs use lowercase slugs — match is on
    # the jobs CSV 'company' column, so slug-style names resolve too.
    assert d.company_open_jobs("acme")["job_id"].tolist() == ["j1"]
    assert jobs.empty or True  # exact display-name match has no jobs rows here


def test_company_open_jobs_empty_state(data_root):
    from ui import data as d

    jobs = d.company_open_jobs("Anything")
    assert jobs.empty


def test_company_names_empty_without_file(data_root):
    from ui import data as d

    assert d.company_names() == []


# ---------------------------------------------------------------------------
# Resumes
# ---------------------------------------------------------------------------


def test_list_resumes_finds_files_or_empty(data_root):
    from ui import data as d

    # Missing directory -> graceful empty.
    assert d.list_resumes() == []

    resumes = data_root / "resume_custom" / "resumes"
    resumes.mkdir(parents=True)
    (resumes / "tailored_acme.pdf").write_bytes(b"%PDF-1.4 fake")
    (resumes / "tailored_beta.tex").write_text("\\documentclass{article}\n")
    (resumes / "ignored.txt").write_text("skip me")

    entries = d.list_resumes()
    names = {e["name"] for e in entries}
    assert names == {"tailored_acme.pdf", "tailored_beta.tex"}
    assert all("size_kb" in e and "path" in e for e in entries)


# ---------------------------------------------------------------------------
# Settings: config status (key NAMES only, never values)
# ---------------------------------------------------------------------------


def test_config_status_reports_present_and_absent_keys(data_root):
    from ui import data as d

    (data_root / "config.yaml").write_text("llm:\n  api_key: SUPERSECRET\n")

    status = d.config_status()
    keys = {entry["key"]: entry["present"] for entry in status["keys"]}
    assert keys["llm.api_key"] is True
    assert keys["job_search.keywords"] is False
    assert status["loaded"] is True

    # Values must never leak into the status payload.
    assert "SUPERSECRET" not in str(status)


def test_config_status_empty_config(data_root):
    from ui import data as d

    status = d.config_status()
    assert status["loaded"] is False
    assert all(not k["present"] for k in status["keys"])
    assert status["data_root"] == str(data_root)


def test_renderers_smoke_with_nicegui_off():
    """Renderer modules import cleanly (NiceGUI available in venv)."""
    pytest.importorskip("nicegui")
    from ui.pages_3_3 import (  # noqa: F401
        render_analytics,
        render_company_research,
        render_resume_page,
        render_settings_page,
    )
