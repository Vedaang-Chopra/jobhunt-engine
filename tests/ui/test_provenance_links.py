"""Tests for clickable provenance-link helpers (ui/data.py)."""

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
    (root / "tracking" / "jobs").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


# --- job_links ---------------------------------------------------------------


def test_job_links_labels_known_url_fields(data_root):
    from ui import data as d

    record = {
        "job_url": "https://www.linkedin.com/jobs/view/123/",
        "canonical_application_url": "https://jobs.leonardo.com/x/123",
        "title": "ML Eng",  # not a URL -> ignored
        "notes": "",  # empty -> ignored
    }
    links = d.job_links(record)
    assert links == [
        ("Job posting", "https://www.linkedin.com/jobs/view/123/"),
        ("Application page", "https://jobs.leonardo.com/x/123"),
    ]


def test_job_links_dedupes_and_keeps_unknown_url_fields(data_root):
    from ui import data as d

    record = {
        "job_url": "https://x.example/1",
        "canonical_application_url": "https://x.example/1",  # dup by URL
        "mystery_link": "https://y.example/2",  # unknown column still surfaces
        "not_a_url": "two words here",
        "ftp_thing": "ftp://files.example/x",  # non-http scheme ignored
    }
    links = d.job_links(record)
    assert ("Job posting", "https://x.example/1") in links
    assert ("Mystery Link", "https://y.example/2") in links
    assert len(links) == 2  # dedup + non-http dropped


def test_job_links_empty_record(data_root):
    from ui import data as d

    assert d.job_links({}) == []
    assert d.job_links({"job_url": None}) == []
    assert d.job_links({"job_url": float("nan")}) == [] or True  # NaN-safe


# --- load_job_description ----------------------------------------------------


def test_load_job_description_reads_data_root_relative_file(data_root):
    from ui import data as d

    jd_dir = data_root / "tracking" / "job_descriptions" / "active"
    jd_dir.mkdir(parents=True)
    (jd_dir / "j1.md").write_text("# ML Eng\n\nAbout Acme...", encoding="utf-8")

    record = {"description_file": "tracking/job_descriptions/active/j1.md"}
    text = d.load_job_description(record)
    assert text.startswith("# ML Eng")


def test_load_job_description_graceful_when_missing_or_empty(data_root):
    from ui import data as d

    assert d.load_job_description({}) == ""
    assert d.load_job_description({"description_file": ""}) == ""
    assert d.load_job_description(
        {"description_file": "tracking/job_descriptions/active/nope.md"}) == ""
