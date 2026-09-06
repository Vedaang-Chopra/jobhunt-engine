"""Tests for form_filler: plan resolution + applications.csv write-through."""
import csv
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import form_filler  # noqa: E402


@pytest.fixture
def store(tmp_path):
    """Minimal answers store dict like answers_lib.load_answers returns."""
    return {
        "_path": str(tmp_path / "answers.yaml"),
        "identity": {"email": {"value": "test.candidate@example.edu",
                               "verified_by": "profile.md"}},
    }


def _entry(label, action="AUTO_FILL", key=None, field_type="text", value=None):
    return {"label": label, "key": key, "action": action,
            "field_type": field_type, "required": False, "value": value}


class TestResolveFieldValue:
    def test_auto_fill_keeps_planned_value(self, store):
        e = _entry("Email Address", key="identity.email", value="test.candidate@example.edu")
        assert form_filler.resolve_field(e, store)["resolved"] == "test.candidate@example.edu"
        assert form_filler.resolve_field(e, store)["status"] == "filled"

    def test_gated_label_always_ask_user_even_if_planned(self, store):
        e = _entry("Expected Salary", key="identity.email",
                   value="test.candidate@example.edu")
        r = form_filler.resolve_field(e, store)
        assert r["status"] == "ask_user"
        assert r["resolved"] is None

    def test_use_saved_answer_resolves_from_store(self, store):
        e = _entry("Email Address", action="USE_SAVED_ANSWER", key="identity.email")
        r = form_filler.resolve_field(e, store)
        assert r["status"] == "filled"
        assert r["resolved"] == "test.candidate@example.edu"

    def test_ask_user_stays_unresolved(self, store):
        e = _entry("Yes, I understand and acknowledge the terms and conditions.",
                   action="ASK_USER")
        r = form_filler.resolve_field(e, store)
        assert r["status"] == "ask_user"
        assert r["resolved"] is None

    def test_missing_key_is_ask_user(self, store):
        e = _entry("Something Unknown", key="nope.nada", value=None)
        r = form_filler.resolve_field(e, store)
        assert r["status"] == "ask_user"


class TestUpdateApplicationsCsv:
    CSV_HEADER = ["application_id", "job_id", "company", "role", "job_url",
                  "status", "date_queued", "date_resume_ready"]

    def _write(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.CSV_HEADER)
            w.writeheader()
            w.writerows(rows)

    def _read(self, path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_updates_existing_row(self, tmp_path):
        p = tmp_path / "applications.csv"
        self._write(p, [{"application_id": "j1", "job_id": "j1",
                         "company": "Acme", "role": "Eng",
                         "job_url": "https://x/j1", "status": "queued",
                         "date_queued": "2026-08-19", "date_resume_ready": ""}])
        n = form_filler.update_applications_csv(
            p, "j1", status="ready_to_apply", date_resume_ready="2026-08-23")
        rows = self._read(p)
        assert n == 1
        assert len(rows) == 1
        assert rows[0]["status"] == "ready_to_apply"
        assert rows[0]["date_resume_ready"] == "2026-08-23"

    def test_appends_row_when_absent_never_deletes(self, tmp_path):
        p = tmp_path / "applications.csv"
        self._write(p, [{"application_id": "j1", "job_id": "j1",
                         "company": "Acme", "role": "Eng",
                         "job_url": "https://x/j1", "status": "queued",
                         "date_queued": "2026-08-19", "date_resume_ready": ""}])
        n = form_filler.update_applications_csv(
            p, "newjob_42", company="CrowdStrike", role="Data Scientist",
            job_url="https://wd5/myworkday", status="ready_to_apply",
            date_resume_ready="2026-08-23")
        rows = self._read(p)
        assert n == 1
        assert len(rows) == 2  # original row preserved
        assert rows[0]["job_id"] == "j1"
        added = [r for r in rows if r["job_id"] == "newjob_42"][0]
        assert added["status"] == "ready_to_apply"
        assert added["date_resume_ready"] == "2026-08-23"
        assert added["application_id"] == "newjob_42"


class TestPageSummary:
    def test_summary_counts_filled_vs_ask_user(self):
        results = [
            {"label": "Email Address", "status": "filled",
             "resolved": "test.candidate@example.edu"},
            {"label": "Terms attestation", "status": "ask_user", "resolved": None},
        ]
        s = form_filler.page_summary(1, results)
        assert "Page 1" in s
        assert "1 filled" in s
        assert "1 ask_user" in s
        assert "Email Address" in s
        assert "test.candidate@example.edu" in s
