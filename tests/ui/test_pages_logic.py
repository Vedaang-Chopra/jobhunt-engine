"""Tests for Task 3.2 wrapper logic: pipeline stage changes + outreach ledger."""

from __future__ import annotations

import csv
import datetime
import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

APP_HEADER = [
    "application_id", "job_id", "company", "role", "job_url", "status",
    "resume_variant", "referral_contact", "date_queued", "date_resume_ready",
    "date_submitted", "date_acknowledged", "date_last_status_change",
    "current_stage", "rejection_reason", "follow_up_date", "notes",
]

REQ_HEADER = [
    "request_id", "person_name", "company", "person_type", "linkedin_url",
    "email", "source_post_url", "related_job_ids", "score", "note_draft",
    "note_basis(hiring_post|shared_ctx|job_specific|generic)",
    "send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)",
    "date_queued", "date_sent", "date_connected", "response", "followup_date",
    "notes",
]


@pytest.fixture
def apps_csv(tmp_path):
    path = tmp_path / "applications.csv"

    def _row(**overrides):
        row = {k: "" for k in APP_HEADER}
        row.update({
            "application_id": "app1",
            "job_id": "job1",
            "company": "Acme",
            "role": "ML Engineer",
            "status": "queued",
            "current_stage": "queued",
            "date_queued": "2026-08-01",
        })
        row.update(overrides)
        return row

    rows = {"row_factory": _row}

    def write(*application_rows):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=APP_HEADER)
            writer.writeheader()
            writer.writerows(application_rows)
        return path

    rows["write"] = write
    rows["path"] = path
    return rows


@pytest.fixture
def requests_csv(tmp_path):
    path = tmp_path / "connection_requests.csv"

    def _write(*rows):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=REQ_HEADER)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _row(**overrides):
        row = {k: "" for k in REQ_HEADER}
        row.update({
            "request_id": "cr_1",
            "person_name": "Jane Doe",
            "company": "Acme",
            "note_draft": "Hi Jane",
            "send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)": "pending",
            "date_queued": "2026-08-23",
        })
        row.update(overrides)
        return row

    return {"path": path, "write": _write, "row": _row}


# ------------------------------------------------------------------ pipeline
def test_full_stage_progression_writes_through_engine(apps_csv):
    from ui import data as d

    today = datetime.date(2026, 8, 23)
    path = apps_csv["write"](apps_csv["row_factory"]())

    # Saved -> Preparing (pre-submission stage)
    changes = d.update_application_stage("app1", "Preparing", path, today=today)
    assert changes == ["status queued -> ready_to_apply"]
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["status"] == "ready_to_apply"
    assert rows[0]["date_last_status_change"] == "2026-08-23"

    # Preparing -> Applied (engine mark_status: submitted)
    d.update_application_stage("app1", "Applied", path, today=today)
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["status"] == "submitted"
    assert rows[0]["date_submitted"] == "2026-08-23"
    assert rows[0]["current_stage"] == "submitted"

    # Applied -> Interviewing (interview; sets +7d follow-up)
    d.update_application_stage("app1", "Interviewing", path, today=today)
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["status"] == "interview"
    assert rows[0]["follow_up_date"] == "2026-08-30"

    # Interviewing -> Closed (withdrawn)
    d.update_application_stage("app1", "Closed", path, today=today)
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["status"] == "withdrawn"


def test_invalid_stage_and_unknown_id_raise(apps_csv):
    from ui import data as d

    path = apps_csv["write"](apps_csv["row_factory"]())
    with pytest.raises(ValueError, match="unknown pipeline stage"):
        d.update_application_stage("app1", "Bogus", path)
    with pytest.raises(ValueError, match="not found"):
        d.update_application_stage("missing_id", "Saved", path)


def test_invalid_engine_transition_surfaces_error(apps_csv):
    from ui import data as d

    # Engine forbids jumping from queued straight to interview.
    path = apps_csv["write"](apps_csv["row_factory"]())
    with pytest.raises(ValueError, match="mark it submitted first"):
        d.update_application_stage("app1", "Interviewing", path)


def test_status_to_stage_mapping():
    from ui import data as d

    assert d.status_to_stage("queued") == "Saved"
    assert d.status_to_stage("") == "Saved"
    assert d.status_to_stage("ready_to_apply") == "Preparing"
    assert d.status_to_stage("submitted") == "Applied"
    assert d.status_to_stage("acknowledged") == "Applied"
    assert d.status_to_stage("interview") == "Interviewing"
    assert d.status_to_stage("rejected") == "Closed"
    assert d.status_to_stage("withdrawn") == "Closed"


# ------------------------------------------------------------- manual adds
def test_add_application_appends_row_with_canonical_header(apps_csv):
    from ui import data as d

    path = apps_csv["path"]
    today = datetime.date(2026, 8, 24)
    row = d.add_application(
        "Anthropic", "Applied AI Engineer",
        job_url="https://example.com/1", notes="manual", apps_path=path,
        today=today,
    )
    assert row["application_id"] == "anthropic_applied_ai_engineer_20260824"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == APP_HEADER
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["company"] == "Anthropic"
    assert rows[0]["status"] == "queued"
    assert rows[0]["current_stage"] == "queued"
    assert rows[0]["date_queued"] == "2026-08-24"


def test_add_application_creates_schema_complete_file(tmp_path):
    """Missing file is created header-complete (empty-board cold start)."""
    from ui import data as d

    path = tmp_path / "fresh" / "applications.csv"
    d.add_application("Acme", "ML Engineer", apps_path=path,
                      today=datetime.date(2026, 8, 24))
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == APP_HEADER
        assert len(list(reader)) == 1


def test_add_application_rejects_blank_and_unknown_status(apps_csv):
    from ui import data as d

    path = apps_csv["path"]
    with pytest.raises(ValueError, match="required"):
        d.add_application("", "Role", apps_path=path)
    with pytest.raises(ValueError, match="unknown status"):
        d.add_application("Acme", "Role", status="bogus", apps_path=path)


def test_add_application_duplicate_same_day_raises(apps_csv):
    from ui import data as d

    path = apps_csv["path"]
    day = datetime.date(2026, 8, 24)
    d.add_application("Acme", "ML Engineer", apps_path=path, today=day)
    with pytest.raises(ValueError, match="already tracked"):
        d.add_application("Acme", "ML Engineer", apps_path=path, today=day)


def test_application_id_for_slugifies_company_and_role():
    from ui import data as d

    day = datetime.date(2026, 8, 24)
    assert d.application_id_for(
        "Data Scientist!", "SWE III, ML", day) == \
        "data_scientist_swe_iii_ml_20260824"


# ------------------------------------------------------------------ outreach
def test_approve_request_happy_path(requests_csv):
    from ui import data as d

    path = requests_csv["write"](requests_csv["row"]())
    updated = d.approve_request(
        "cr_1", path, today=datetime.date(2026, 8, 23))
    assert updated["send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)"].startswith("approved")
    assert "approved 2026-08-23" in updated["notes"]
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1  # append-only ledger: row count unchanged
    assert rows[0]["request_id"] == "cr_1"


def test_approve_requires_pending(requests_csv):
    from ui import data as d

    status_col = ("send_status(pending|approved|sent_no_note|"
                  "sent_with_note|connected|declined|failed)")
    path = requests_csv["write"](
        requests_csv["row"](**{status_col: "approved"}))
    with pytest.raises(ValueError, match="pending"):
        d.approve_request("cr_1", path)


def test_approve_unknown_request_raises(requests_csv):
    from ui import data as d

    path = requests_csv["write"](requests_csv["row"]())
    with pytest.raises(ValueError, match="not found"):
        d.approve_request("cr_missing", path)


def test_send_cap_progress_counts_only_todays_sends(requests_csv):
    from ui import data as d

    status_col = ("send_status(pending|approved|sent_no_note|"
                  "sent_with_note|connected|declined|failed)")
    path = requests_csv["write"](
        requests_csv["row"](request_id="cr_1", **{status_col: "sent_no_note"},
                            date_sent="2026-08-23"),
        requests_csv["row"](request_id="cr_2", **{status_col: "sent_with_note"},
                            date_sent="2026-08-23"),
        requests_csv["row"](request_id="cr_3", **{status_col: "sent_no_note"},
                            date_sent="2026-08-20"),  # older day
        requests_csv["row"](request_id="cr_4", **{status_col: "pending"}),
    )
    progress = d.send_cap_progress(path, today=datetime.date(2026, 8, 23))
    assert progress == {"sent_today": 2, "cap": 25, "remaining": 23}


def test_load_connection_requests_graceful_on_missing(tmp_path):
    from ui import data as d

    assert d.load_connection_requests(tmp_path / "nope.csv") == []
    df = d.load_requests_df(tmp_path / "nope.csv")
    assert df.empty


# ------------------------------------------------- jobs ↔ applications sync
JOBS_MIN_HEADER = [
    "job_id", "company", "title", "job_url", "status",
]


@pytest.fixture
def jobs_root(tmp_path, monkeypatch):
    """Isolated JOBHUNT_HOME with a minimal jobs.csv."""
    root = tmp_path / "data_root"
    jobs_dir = root / "tracking" / "jobs"
    jobs_dir.mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    path = jobs_dir / "jobs.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=JOBS_MIN_HEADER)
        writer.writeheader()
        writer.writerow({
            "job_id": "acme_ml_eng_123",
            "company": "Acme",
            "title": "ML Engineer",
            "job_url": "https://jobs.acme.com/123",
            "status": "open",
        })
    return root


def test_sync_job_application_status_adds_column(jobs_root):
    from ui import data as d

    assert d.sync_job_application_status("acme_ml_eng_123", "submitted")
    path = jobs_root / "tracking" / "jobs" / "jobs.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["application_status"] == "submitted"
    # Job lifecycle status untouched.
    assert rows[0]["status"] == "open"


def test_sync_job_application_status_tolerates_unknown_id(jobs_root):
    from ui import data as d

    # Manual applications carry their application_id as job_id; no canonical
    # row exists and the mirror must be a silent no-op, not an error.
    assert d.sync_job_application_status("not_a_real_job", "queued") is False
    assert d.application_status_for_job("acme_ml_eng_123") is None


def test_track_job_as_application_links_canonical_job_id(jobs_root):
    from ui import data as d

    row = d.track_job_as_application("acme_ml_eng_123")
    assert row["job_id"] == "acme_ml_eng_123"
    assert row["company"] == "Acme"
    assert row["role"] == "ML Engineer"
    assert row["job_url"] == "https://jobs.acme.com/123"
    assert row["status"] == "queued"

    apps = d.applications_csv_path()
    with apps.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["job_id"] == "acme_ml_eng_123"
    # Status mirrored onto the canonical job row.
    assert d.application_status_for_job("acme_ml_eng_123") == "queued"


def test_track_job_as_application_rejects_double_tracking(jobs_root):
    from ui import data as d

    d.track_job_as_application("acme_ml_eng_123")
    with pytest.raises(ValueError, match="already tracked"):
        d.track_job_as_application("acme_ml_eng_123")


def test_stage_change_mirrors_onto_linked_job(jobs_root, apps_csv):
    from ui import data as d

    path = apps_csv["write"](apps_csv["row_factory"](
        job_id="acme_ml_eng_123", application_id="app1"))
    d.update_application_stage("app1", "Applied", apps_path=path)
    assert d.application_status_for_job("acme_ml_eng_123") == "submitted"

