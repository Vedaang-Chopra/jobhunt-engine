"""Tests for Task 5: submit-mode approval gate + record_application write-back."""
import csv
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import form_filler  # noqa: E402
import record_application  # noqa: E402


class TestSubmitGate:
    """Submit mode must refuse to run without an explicit --approved-by user."""

    def _args(self, approved_by=None):
        return SimpleNamespace(approved_by=approved_by)

    def test_gate_refuses_without_approver(self):
        with pytest.raises(form_filler.ApprovalRequired):
            form_filler.check_submit_approval(self._args())

    def test_gate_refuses_on_blank_or_placeholder(self):
        for bad in ("", "   ", "true", "yes", "auto"):
            with pytest.raises(form_filler.ApprovalRequired):
                form_filler.check_submit_approval(self._args(bad))

    def test_gate_accepts_named_user(self):
        assert form_filler.check_submit_approval(
            self._args("testuser")) == "testuser"

    def test_parser_requires_approved_by_for_submit(self, capsys):
        parser = form_filler.build_parser()
        args = parser.parse_args(["4720573005", "--submit"])
        assert args.submit is True
        assert args.approved_by is None  # caller must still pass the gate fn


class TestRecordApplication:
    APP_HEADER = ["application_id", "job_id", "company", "role", "status",
                  "date_queued", "date_submitted", "current_stage", "notes"]
    JOBS_HEADER = ["job_id", "company", "title", "status", "notes"]

    def _apps(self, path, rows=None):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.APP_HEADER)
            w.writeheader()
            w.writerows(rows or [])

    def _jobs(self, path, rows=None):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.JOBS_HEADER)
            w.writeheader()
            w.writerows(rows or [])

    def _read(self, path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_marks_application_submitted(self, tmp_path):
        apps = tmp_path / "applications.csv"
        self._apps(apps, [{"application_id": "j1", "job_id": "j1",
                           "company": "Scale", "role": "Eng",
                           "status": "ready_to_apply",
                           "date_queued": "2026-08-19"}])
        n = record_application.mark_submitted(apps, "j1")
        row = self._read(apps)[0]
        assert n == 1
        assert row["status"] == "submitted"
        assert row["current_stage"] == "submitted"
        assert row["date_submitted"] == record_application.today()
        assert len(row["date_submitted"]) == 10  # ISO date

    def test_missing_job_raises(self, tmp_path):
        apps = tmp_path / "applications.csv"
        self._apps(apps)
        with pytest.raises(record_application.JobNotFound):
            record_application.mark_submitted(apps, "nope")

    def test_appends_note_to_jobs_row_once(self, tmp_path):
        jobs = tmp_path / "jobs.csv"
        self._jobs(jobs, [{"job_id": "j1", "company": "scaleai",
                           "title": "Eng", "status": "open",
                           "notes": "existing note"}])
        n = record_application.append_jobs_note(
            jobs, "j1", "[2026-08-23] submitted")
        rows = self._read(jobs)
        assert n == 1 and len(rows) == 1
        assert rows[0]["notes"] == "existing note | [2026-08-23] submitted"
        # idempotent: same tag not appended twice
        n2 = record_application.append_jobs_note(
            jobs, "j1", "[2026-08-23] submitted")
        assert n2 == 0
        assert self._read(jobs)[0]["notes"].count("[2026-08-23] submitted") == 1

    def test_writes_confirmation_file(self, tmp_path):
        run_dir = tmp_path / "apply_runs"
        p = record_application.write_confirmation(
            run_dir, "4720573005",
            "Application for 4720573005 recorded on 2026-08-23.")
        assert p.exists() and p.name == "4720573005_confirmation.txt"
        assert "recorded on 2026-08-23" in p.read_text(encoding="utf-8")

    def test_full_record_run_end_to_end(self, tmp_path):
        apps = tmp_path / "applications.csv"
        jobs = tmp_path / "jobs.csv"
        run_dir = tmp_path / "apply_runs"
        self._apps(apps, [{"application_id": "s1", "job_id": "s1",
                           "company": "scaleai", "role": "AI Eng",
                           "status": "ready_to_apply"}])
        self._jobs(jobs, [{"job_id": "s1", "company": "scaleai",
                           "title": "AI Eng", "status": "open", "notes": ""}])
        record_application.record(
            applications_csv=apps, jobs_csv=jobs, run_dir=run_dir,
            job_id="s1", company="scaleai", role="AI Eng",
            confirmation="Confirmed submission of s1.")
        app_rows = self._read(apps)
        assert app_rows[0]["status"] == "submitted"
        job_rows = self._read(jobs)
        assert "submitted" in job_rows[0]["notes"]
        assert (run_dir / "s1_confirmation.txt").exists()
