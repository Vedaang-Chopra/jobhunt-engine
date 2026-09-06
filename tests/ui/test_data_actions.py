"""Tests for job-state mutations + role_family filtering (ui/data.py).

Covers set_job_status, set_job_review_flag, delete_job, _mutate_jobs and the
filter_jobs role_family branch, all against an isolated JOBHUNT_HOME root.
"""

from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ui import data as data_layer


JOBS_CSV = (
    "job_id,company,title,status,date_updated,last_checked,notes,role_family\n"
    'J1,Acme,ML Eng,open,2026-01-01,,base note,agentic_ai\n'
    "J2,Beta,Data Eng,open,,,,\n"
    "J3,Gamma,MLOps,expired,2026-02-02,2026-02-03,stale,applied_ml\n"
)


@pytest.fixture()
def isolated_root(tmp_path, monkeypatch):
    """Isolate the data root per test (mirrors test_data_states pattern)."""
    root = tmp_path / "data_root"
    jobs_dir = root / "tracking" / "jobs"
    jobs_dir.mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    yield root


def seed_jobs(root: Path, content: str = JOBS_CSV) -> Path:
    path = root / "tracking" / "jobs" / "jobs.csv"
    path.write_text(content)
    return path


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --- set_job_status -----------------------------------------------------------


def test_set_job_status_happy_path(isolated_root):
    path = seed_jobs(isolated_root)
    data_layer.set_job_status("J1", "archived")
    rows = {r["job_id"]: r for r in read_rows(path)}
    assert rows["J1"]["status"] == "archived"
    assert rows["J1"]["date_updated"] == datetime.date.today().isoformat()
    # Untouched row verbatim.
    assert rows["J2"]["status"] == "open"


def test_set_job_status_rejects_unknown_status(isolated_root):
    path = seed_jobs(isolated_root)
    before = path.read_text()
    with pytest.raises(ValueError):
        data_layer.set_job_status("J1", "hired")
    assert path.read_text() == before  # no partial write
    assert data_layer.JOB_STATUSES == (
        "open", "expired", "filled", "withdrawn", "archived")


# --- set_job_review_flag --------------------------------------------------------


def test_set_and_clear_review_flag_creates_column(isolated_root):
    path = seed_jobs(isolated_root)
    data_layer.set_job_review_flag("J2", "for_later")

    rows = {r["job_id"]: r for r in read_rows(path)}
    assert rows["J2"]["review_flag"] == "for_later"
    assert rows["J2"]["date_updated"] == datetime.date.today().isoformat()
    assert "review_flag" in path.read_text().splitlines()[0]

    # Clearing stores empty string but keeps the column in the header.
    data_layer.set_job_review_flag("J2", "")
    rows = {r["job_id"]: r for r in read_rows(path)}
    assert rows["J2"]["review_flag"] == ""
    assert "review_flag" in path.read_text().splitlines()[0]


def test_set_job_review_flag_rejects_unknown_flag(isolated_root):
    path = seed_jobs(isolated_root)
    with pytest.raises(ValueError):
        data_layer.set_job_review_flag("J2", "urgent")


# --- delete_job ------------------------------------------------------------------


def test_delete_job_removes_row_and_preserves_others(isolated_root):
    path = seed_jobs(isolated_root)
    assert data_layer.delete_job("J2") is True
    rows = read_rows(path)
    assert [r["job_id"] for r in rows] == ["J1", "J3"]
    # Other rows keep every column value.
    by_id = {r["job_id"]: r for r in rows}
    assert by_id["J1"]["notes"] == "base note"
    assert by_id["J3"]["last_checked"] == "2026-02-03"


def test_delete_and_mutate_on_missing_id_raise(isolated_root):
    path = seed_jobs(isolated_root)
    with pytest.raises(ValueError):
        data_layer.delete_job("NOPE")
    with pytest.raises(ValueError):
        data_layer.set_job_status("NOPE", "open")
    with pytest.raises(ValueError):
        data_layer.set_job_review_flag("NOPE", "completed")
    assert len(read_rows(path)) == 3  # untouched


# --- _mutate_jobs internals ------------------------------------------------------


def test_mutate_jobs_missing_file_raises_file_not_found(isolated_root):
    with pytest.raises(FileNotFoundError):
        data_layer._mutate_jobs(["J1"], lambda row: True)
    with pytest.raises(FileNotFoundError):
        data_layer._mutate_jobs("J1", lambda row: True)


def test_mutate_jobs_returns_changed_ids_and_skips_noop(isolated_root):
    path = seed_jobs(isolated_root)

    def touch_j1(row):
        if row["job_id"] != "J1":
            return False
        row["status"] = "filled"
        return True

    changed = data_layer._mutate_jobs(["J1", "J2", "J3"], touch_j1)
    assert changed == ["J1"]
    rows = {r["job_id"]: r for r in read_rows(path)}
    assert rows["J1"]["status"] == "filled"
    assert rows["J2"]["status"] == "open"  # mutator returned False -> untouched


# --- column preservation ---------------------------------------------------------


EXOTIC_CSV = (
    "job_id,status,frobnicator_level,zalgo\n"
    'J1,open,"weird, comma","tabs\tand ""quotes"""\n'
    "J2,open,preserved-untouched,keep-me\n"
)


def test_round_trip_preserves_exotic_columns_byte_wise(isolated_root):
    path = seed_jobs(isolated_root, EXOTIC_CSV)
    original = path.read_text()

    data_layer.set_job_status("J1", "filled")

    rows = {r["job_id"]: r for r in read_rows(path)}
    assert rows["J2"] == {
        "job_id": "J2",
        "status": "open",
        "frobnicator_level": "preserved-untouched",
        "zalgo": "keep-me",
    }
    # The untouched row's raw line survives verbatim.
    assert "J2,open,preserved-untouched,keep-me\n" in path.read_text()
    # And the mutated row keeps its exotic value too.
    assert rows["J1"]["zalgo"] == 'tabs\tand "quotes"'
    del original


# --- filter_jobs role_family -----------------------------------------------------


def test_filter_jobs_role_family_case_insensitive():
    df = pd.DataFrame([
        {"job_id": "J1", "role_family": "agentic_ai"},
        {"job_id": "J2", "role_family": "Applied_ML"},
        {"job_id": "J3", "role_family": ""},
    ])
    out = data_layer.filter_jobs(df, role_family="AGENTIC_AI")
    assert list(out["job_id"]) == ["J1"]
    out = data_layer.filter_jobs(df, role_family="applied_ml")
    assert list(out["job_id"]) == ["J2"]
    # Empty value = no filtering.
    assert len(data_layer.filter_jobs(df)) == 3


def test_filter_jobs_role_family_missing_column_returns_empty():
    df = pd.DataFrame([{"job_id": "J1", "status": "open"}])
    assert data_layer.filter_jobs(df, role_family="agentic_ai").empty
