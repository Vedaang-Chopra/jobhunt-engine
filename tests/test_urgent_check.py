"""Tests for scripts/urgent_check.py — urgent-job alert fast path (Task 3)."""

import csv
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import urgent_check  # noqa: E402

NOW = datetime(2026, 8, 23, 12, 0, 0)

JOBS_HEADER = [
    "job_id", "company", "title", "job_url", "canonical_application_url",
    "source", "date_discovered", "date_posted", "status",
    "is_medical_false_positive", "priority_v2",
]

CONTACTS_HEADER = ["contact_id", "name", "company", "linkedin_url"]


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def job_row(job_id="c_x", company="Acme", title="ML Engineer", **kw):
    row = {
        "job_id": job_id,
        "company": company,
        "title": title,
        "job_url": f"https://jobs.example/{job_id}",
        "canonical_application_url": f"https://apply.example/{job_id}",
        "source": "greenhouse",
        "date_discovered": "2026-08-23",
        "date_posted": "2026-08-23T06:00:00",
        "status": "open",
        "is_medical_false_positive": "false",
        "priority_v2": "75",
    }
    row.update(kw)
    return row


@pytest.fixture
def env(tmp_path):
    jobs = tmp_path / "jobs.csv"
    contacts = tmp_path / "contacts.csv"
    write_csv(jobs, JOBS_HEADER, [job_row()])
    write_csv(contacts, CONTACTS_HEADER, [])
    return {"jobs": jobs, "contacts": contacts}


def run_main(env, extra=None):
    argv = ["--jobs", str(env["jobs"]), "--contacts", str(env["contacts"]),
            "--now", NOW.isoformat()] + (extra or [])
    return urgent_check.main(argv)


def test_qualifying_row_alerts(env, capsys):
    code = run_main(env)
    out = capsys.readouterr().out
    assert code == 0
    assert "🔥 HOT JOB:" in out
    assert "ML Engineer @ Acme" in out
    assert "APPLY tier" in out
    assert "https://apply.example/c_x" in out


def test_threshold_gating_below_68_excluded(env, capsys):
    write_csv(env["jobs"], JOBS_HEADER, [job_row(priority_v2="67.9")])
    run_main(env)
    assert "🔥 HOT JOB:" not in capsys.readouterr().out


def test_threshold_boundary_68_included(env, capsys):
    write_csv(env["jobs"], JOBS_HEADER, [job_row(priority_v2="68")])
    run_main(env)
    assert "🔥 HOT JOB:" in capsys.readouterr().out


def test_age_older_than_24h_excluded(env, capsys):
    write_csv(
        env["jobs"], JOBS_HEADER,
        [job_row(date_posted=(NOW - timedelta(hours=25)).isoformat())],
    )
    run_main(env)
    assert "🔥 HOT JOB:" not in capsys.readouterr().out


def test_age_exactly_24h_included(env, capsys):
    write_csv(
        env["jobs"], JOBS_HEADER,
        [job_row(date_posted=(NOW - timedelta(hours=24)).isoformat())],
    )
    run_main(env)
    out = capsys.readouterr().out
    assert "🔥 HOT JOB:" in out
    assert "24h old" in out


def test_cap_at_three_alerts(env, capsys):
    rows = [job_row(job_id=f"c_{i}", title=f"Role {i}") for i in range(5)]
    write_csv(env["jobs"], JOBS_HEADER, rows)
    code = run_main(env)
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("🔥 HOT JOB:") == 3


def test_no_contact_handling(env, capsys):
    run_main(env)
    out = capsys.readouterr().out
    assert "no referral contact on file" in out


def test_top_referral_contact_included(tmp_path, capsys):
    jobs = tmp_path / "jobs.csv"
    contacts = tmp_path / "contacts.csv"
    write_csv(jobs, JOBS_HEADER, [job_row()])
    write_csv(
        contacts, CONTACTS_HEADER,
        [
            {"contact_id": "1", "name": "Jane Doe", "company": "Other Co",
             "linkedin_url": "https://linkedin.com/in/jane"},
            {"contact_id": "2", "name": "Bob Roe", "company": "acme",
             "linkedin_url": "https://linkedin.com/in/bob"},
        ],
    )
    urgent_check.main(["--jobs", str(jobs), "--contacts", str(contacts),
                       "--now", NOW.isoformat()])
    out = capsys.readouterr().out
    assert "Bob Roe" in out
    assert "https://linkedin.com/in/bob" in out


def test_exit_zero_even_on_missing_jobs_file(tmp_path, capsys):
    code = urgent_check.main([
        "--jobs", str(tmp_path / "missing.csv"),
        "--contacts", str(tmp_path / "contacts.csv"),
    ])
    assert code == 0


def test_cli_script_end_to_end(env, capsys):
    """Script runs as subprocess and exits 0."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "urgent_check.py"),
         "--jobs", str(env["jobs"]), "--contacts", str(env["contacts"]),
         "--now", NOW.isoformat(), "--dry-run"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "🔥 HOT JOB:" in proc.stdout
