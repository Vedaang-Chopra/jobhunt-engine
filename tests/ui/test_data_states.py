"""Tests for data-layer states, truthful labels & provenance (spec 003 §6.1/§6.2).

Covers: load_csv error channel (thread-local), data_health/source_freshness,
explicit outcome vocabulary + stage_outcome_split, and score_provenance.
"""

from __future__ import annotations

import datetime
import os
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui import data as data_layer


@pytest.fixture()
def isolated_root(tmp_path, monkeypatch):
    """Isolate the data root per test (mirrors test_llm_editor pattern)."""
    root = tmp_path / "data_root"
    root.mkdir(exist_ok=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    yield root


@pytest.fixture(autouse=True)
def _clean_issues():
    data_layer.clear_load_issues()
    yield
    data_layer.clear_load_issues()


# --- load_csv error channel --------------------------------------------------


def test_load_csv_missing_file_returns_empty_and_records_issue(isolated_root):
    df = data_layer.load_csv("tracking/jobs/jobs.csv", columns=["job_id"])
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == ["job_id"]
    issues = data_layer.get_load_issues()
    assert len(issues) == 1
    assert issues[0]["reason"] == "missing"
    assert issues[0]["path"] == str(isolated_root / "tracking/jobs/jobs.csv")


def test_load_csv_unreadable_file_records_read_error(isolated_root, monkeypatch):
    path = isolated_root / "tracking"
    path.mkdir(exist_ok=True)
    (path / "jobs").mkdir(exist_ok=True)
    csv = path / "jobs" / "jobs.csv"
    csv.write_text("job_id\nA1\n")

    def boom(*args, **kwargs):
        raise ValueError("bad csv")

    monkeypatch.setattr(data_layer.pd, "read_csv", boom)
    df = data_layer.load_csv("tracking/jobs/jobs.csv")
    assert df.empty
    issues = data_layer.get_load_issues()
    assert len(issues) == 1
    assert issues[0]["reason"].startswith("read-error")
    assert "bad csv" in issues[0]["reason"]


def test_clear_and_get_load_issues_roundtrip_and_thread_locality():
    data_layer.clear_load_issues()
    data_layer.load_csv("does/not/exist.csv")  # records 'missing' on this thread
    assert len(data_layer.get_load_issues()) == 1

    seen_in_thread: dict[str, list] = {}

    def worker():
        seen_in_thread["before"] = data_layer.get_load_issues()
        data_layer.load_csv("other/missing.csv")
        seen_in_thread["after"] = data_layer.get_load_issues()

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    # Other thread started with zero issues (isolation)...
    assert seen_in_thread["before"] == []
    # ...recorded only its own issue...
    assert [i["path"] for i in seen_in_thread["after"]] == [
        str(data_layer._data_root() / "other/missing.csv")]
    # ...and this thread's issue is untouched.
    assert len(data_layer.get_load_issues()) == 1

    data_layer.clear_load_issues()
    assert data_layer.get_load_issues() == []


# --- data_health / source_freshness ------------------------------------------


def test_data_health_on_empty_root(isolated_root):
    report = {entry["path"]: entry for entry in data_layer.data_health()}
    assert set(report) == set(data_layer.CANONICAL_SOURCES)
    for rel, entry in report.items():
        assert entry["exists"] is False
        assert entry["rows"] is None
        assert entry["mtime"] is None
        assert entry["readable"] is False


def test_data_health_with_seeded_csvs(isolated_root):
    jobs = isolated_root / "tracking" / "jobs"
    jobs.mkdir(parents=True)
    pd.DataFrame([
        {"job_id": "J1", "status": "open"},
        {"job_id": "J2", "status": "open"},
    ]).to_csv(jobs / "jobs.csv", index=False)

    contacts = isolated_root / "tracking" / "contacts"
    contacts.mkdir(parents=True)
    # Unterminated quote -> pandas ParserError (a NUL byte alone still parses).
    (contacts / "contacts.csv").write_text('a,b\n"unterminated\n')

    report = {entry["path"]: entry for entry in data_layer.data_health()}
    jobs_entry = report["tracking/jobs/jobs.csv"]
    assert jobs_entry["exists"] is True
    assert jobs_entry["rows"] == 2
    assert jobs_entry["readable"] is True
    mtime = datetime.datetime.fromisoformat(jobs_entry["mtime"])
    assert mtime.tzinfo is not None  # ISO 8601 with timezone

    bad = report["tracking/contacts/contacts.csv"]
    assert bad["exists"] is True
    assert bad["readable"] is False
    assert bad["rows"] is None


def test_source_freshness_stale_boundary(isolated_root):
    rel = "tracking/jobs/jobs.csv"
    jobs_dir = isolated_root / "tracking" / "jobs"
    jobs_dir.mkdir(parents=True)
    csv = jobs_dir / "jobs.csv"
    csv.write_text("job_id\nJ1\n")

    now = datetime.datetime.now(datetime.timezone.utc).timestamp()

    fresh = data_layer.source_freshness(rel, stale_days=7)
    assert fresh["exists"] is True
    assert fresh["stale"] is False
    assert 0 <= fresh["age_days"] < 7
    datetime.datetime.fromisoformat(fresh["mtime"])

    ten_days_ago = now - 10 * 86400
    seven_days_ago = now - 7 * 86400
    six_days_ago = now - 6 * 86400

    os.utime(csv, (ten_days_ago, ten_days_ago))
    old = data_layer.source_freshness(rel, stale_days=7)
    assert old["stale"] is True
    assert 9.9 < old["age_days"] < 10.1

    # Just under the boundary (1h margin avoids clock-skew flakiness).
    just_under = now - (7 * 86400 - 3600)
    os.utime(csv, (just_under, just_under))
    exact = data_layer.source_freshness(rel, stale_days=7)
    assert exact["stale"] is False

    # Just over the boundary.
    just_over = now - (7 * 86400 + 3600)
    os.utime(csv, (just_over, just_over))
    over = data_layer.source_freshness(rel, stale_days=7)
    assert over["stale"] is True

    os.utime(csv, (six_days_ago, six_days_ago))
    recent = data_layer.source_freshness(rel, stale_days=7)
    assert recent["stale"] is False

    missing = data_layer.source_freshness("nope/missing.csv", stale_days=7)
    assert missing == {
        "path": "nope/missing.csv",
        "exists": False,
        "mtime": None,
        "age_days": None,
        "stale": False,
    }


# --- Truthful labels / outcomes ------------------------------------------------


def test_outcomes_vocabulary_complete():
    expected = (
        "rejected", "withdrawn", "role_closed",
        "no_response", "offer_declined", "other",
    )
    assert data_layer.OUTCOMES == expected
    # Totality: every outcome maps onto a legacy engine status and has a note.
    for outcome in data_layer.OUTCOMES:
        assert outcome in data_layer.OUTCOME_TO_LEGACY_STATUS
        legacy = data_layer.OUTCOME_TO_LEGACY_STATUS[outcome]
        assert isinstance(legacy, str) and legacy
        assert outcome in data_layer.APPLICATION_OUTCOME_NOTES


def test_outcome_to_legacy_status_values():
    assert data_layer.OUTCOME_TO_LEGACY_STATUS == {
        "rejected": "rejected",
        "withdrawn": "withdrawn",
        "role_closed": "closed",
        "no_response": "withdrawn",
        "offer_declined": "declined",
        "other": "closed",
    }


def test_label_renames_constant():
    assert data_layer.LABEL_RENAMES == {
        "Applications Sent": "Submitted (local status)",
        "Connections Pending": "Awaiting outreach (ledger)",
        "Closed": "Completed",
    }


def test_stage_outcome_split_known_terminal_statuses():
    assert data_layer.stage_outcome_split("rejected") == ("Closed", "rejected")
    assert data_layer.stage_outcome_split("withdrawn") == ("Closed", "withdrawn")
    assert data_layer.stage_outcome_split("role_closed") == ("Closed", "role_closed")
    # Legacy engine statuses resolve through the inverse map too.
    assert data_layer.stage_outcome_split("closed") == ("Closed", "role_closed")
    assert data_layer.stage_outcome_split("declined") == ("Closed", "offer_declined")


def test_stage_outcome_split_non_terminal_and_unknown():
    assert data_layer.stage_outcome_split("submitted") == ("Applied", "")
    assert data_layer.stage_outcome_split("interview") == ("Interviewing", "")
    assert data_layer.stage_outcome_split("ready_to_apply") == ("Preparing", "")
    assert data_layer.stage_outcome_split("") == ("Saved", "")
    assert data_layer.stage_outcome_split(None) == ("Saved", "")
    stage, outcome = data_layer.stage_outcome_split("totally-unknown-status")
    assert outcome == ""
    assert isinstance(stage, str) and stage


def test_score_provenance_thin_jd_branches():
    thin = data_layer.score_provenance({
        "scored_at": "2026-08-20",
        "description": "short",
    })
    by_key_thin = dict(thin)
    assert by_key_thin["Scale"] == "priority_v2 0–100"
    assert by_key_thin["Computed"] == "2026-08-20"
    assert by_key_thin["Inputs"] == "12-dimension scorer (scripts/score_jobs_v2.py)"
    assert "thin JD" in by_key_thin["Quality"]

    thin_via_jd_chars = data_layer.score_provenance({"jd_chars": 120})
    assert "thin JD" in dict(thin_via_jd_chars)["Quality"]

    full = data_layer.score_provenance({"description": "x" * 900})
    assert "thin" not in dict(full)["Quality"].lower()


def test_score_provenance_unknown_computed_date():
    lines = dict(data_layer.score_provenance({"description": "y" * 600}))
    assert lines["Computed"] == "unknown date"
