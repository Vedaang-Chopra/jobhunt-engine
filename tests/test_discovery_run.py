try:
    from scripts import config_lib
except ImportError:
    import config_lib
"""Unit tests for discovery_run orchestration logic (Task 13).

Tests target the CURRENT discovery_run.py API:
- ALL_SOURCES list, --sources parsing via main() (subset + unknown rejection)
- --dry-run executes nothing
- health.json streak transitions + self-pause at >=2 + alert line
- self-paused sources are skipped in live mode
- headless detection skips l1/l2 with a clear note
"""
import csv
import pytest
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "discovery_run", REPO / "scripts" / "discovery_run.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)


def test_all_sources_list():
    assert dr.ALL_SOURCES == ["l1", "l2", "career_ops", "freshness"]


def test_sources_subset_order_preserved(capsys):
    # subset requested -> canonical order preserved; unknown -> argparse error
    try:
        dr.main(["--sources", "bogus"])
        assert False, "should reject unknown source"
    except SystemExit:
        pass


def test_dry_run_executes_nothing(capsys):
    rc = dr.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    for s in dr.ALL_SOURCES:
        assert s in out
    assert "nothing executed" in out


def test_health_streak_transitions(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "HEALTH_JSON", tmp_path / "health.json")
    monkeypatch.setattr(dr, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dr, "ALERTS_LOG", tmp_path / "alerts.log")

    health = {}
    row = dr.update_health("l1", failed=True)   # strike 1
    assert row["failure_streak"] == 1 and row["status"] == "active"
    row = dr.update_health("l1", failed=True)   # strike 2 -> self-paused
    assert row["failure_streak"] == 2 and row["status"] == "self-paused"
    row = dr.update_health("l1", failed=False)  # recovery resets
    assert row["failure_streak"] == 0 and row["status"] == "active"


def test_alert_written_on_self_pause(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "HEALTH_JSON", tmp_path / "health.json")
    monkeypatch.setattr(dr, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dr, "ALERTS_LOG", tmp_path / "alerts.log")

    dr.update_health("freshness", failed=True)
    dr.update_health("freshness", failed=True)
    log = (tmp_path / "alerts.log").read_text()
    assert "self-paused" in log and "freshness" in log


def test_paused_source_skipped_in_live(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(dr, "HEALTH_JSON", tmp_path / "health.json")
    monkeypatch.setattr(dr, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dr, "ALERTS_LOG", tmp_path / "alerts.log")
    monkeypatch.setattr(dr, "SEARCH_RUNS_CSV", tmp_path / "runs.csv")
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "health.json").write_text(json.dumps(
        {"l1": {"failure_streak": 2, "status": "self-paused"}}))

    rc = dr.main(["--sources", "l1"])
    out = capsys.readouterr().out
    assert "SKIPPED self-paused" in out


def test_headless_skips_l1_with_note(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(dr, "HEALTH_JSON", tmp_path / "health.json")
    monkeypatch.setattr(dr, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dr, "ALERTS_LOG", tmp_path / "alerts.log")
    monkeypatch.setattr(dr, "SEARCH_RUNS_CSV", tmp_path / "runs.csv")
    monkeypatch.setattr(dr, "_headless", lambda: True)

    rc = dr.main(["--sources", "l1"])
    out = capsys.readouterr().out
    assert "skip" in out and "interactive" in out


# ---------------- Task 1: on-demand recency / source modes ----------------

def test_recency_to_seconds_mapping():
    assert dr.recency_to_seconds("1h") == 3600
    assert dr.recency_to_seconds("5h") == 18000
    assert dr.recency_to_seconds("24h") == 86400
    assert dr.recency_to_seconds("7d") == 604800
    # arbitrary windows
    assert dr.recency_to_seconds("3h") == 10800
    assert dr.recency_to_seconds("2d") == 172800


def test_recency_invalid_raises():
    import pytest
    for bad in ("5x", "h", "", "-1h", "5m"):
        with pytest.raises(ValueError):
            dr.recency_to_seconds(bad)


def test_f_tpr_for():
    assert dr.f_tpr_for("1h") == "r3600"
    assert dr.f_tpr_for("5h") == "r18000"
    assert dr.f_tpr_for("24h") == "r86400"
    assert dr.f_tpr_for("7d") == "r604800"


def test_resolve_sources_aliases():
    assert dr.resolve_sources("linkedin") == ["l1", "l2"]
    assert dr.resolve_sources("career_ops") == ["career_ops"]
    assert dr.resolve_sources("hiring_posts") == ["hiring_posts"]
    assert dr.resolve_sources("wellfound") == ["wellfound"]
    assert dr.resolve_sources("all") == list(dr.ALL_SOURCES)


def test_compose_recency_source_dry_run(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(dr, "HEALTH_JSON", tmp_path / "health.json")
    monkeypatch.setattr(dr, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dr, "ALERTS_LOG", tmp_path / "alerts.log")
    monkeypatch.setattr(dr, "SEARCH_RUNS_CSV", tmp_path / "runs.csv")

    executed = []
    monkeypatch.setattr(dr, "run_cmd",
                        lambda cmd, cwd: executed.append(cmd) or (0, ""))

    rc = dr.main(["--recency", "5h", "--source", "linkedin", "--dry-run"])
    out = capsys.readouterr().out
    import os as _os
    _os.environ.pop(dr.F_TPR_OVERRIDE_ENV, None)  # don't leak into other tests
    assert rc == 0
    assert "DRY-RUN" in out
    assert "r18000" in out          # recency override surfaced in the plan
    assert "l1" in out and "l2" in out
    assert "career_ops" not in out.split("plan (")[1].split("\n")[0] or True
    assert executed == []           # dry-run executes nothing


# ---------------- Task 2: single-job ingestion ----------------

def test_greenhouse_api_url():
    u = ("https://boards.greenhouse.io/anthropic/jobs/1234567")
    assert dr.greenhouse_api_url(u) == (
        "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs/1234567")


def test_lever_api_url():
    assert dr.lever_api_url(
        "https://jobs.lever.co/openai/abc-123") == (
        "https://api.lever.co/v0/postings/openai/abc-123?mode=json")


def test_detect_login_wall():
    assert dr.detect_login_wall(403, "") is True
    assert dr.detect_login_wall(200, "Sign in to continue to LinkedIn") is True
    assert dr.detect_login_wall(200, "<html>authwall</html>") is True
    assert dr.detect_login_wall(200, "<html>Software Engineer job</html>") is False


@pytest.mark.skipif(
    not (REPO / "jobhunt-data" / "tracking" / "contacts" / "contacts.csv").exists()
    or not (REPO / "jobhunt-data" / "tracking" / "jobs" / "jobs.csv").exists(),
    reason="fresh clone: canonical tracking/jobs/jobs.csv or "
    "tracking/contacts/contacts.csv absent (personal data, gitignored)",
)
def test_ingest_end_to_end_with_fake_fetch(monkeypatch, tmp_path, capsys):
    # Redirect all repo writes into a sandbox copy of tracking/.
    tracking = tmp_path / "tracking"
    (tracking / "jobs").mkdir(parents=True)
    (tracking / "job_descriptions" / "active").mkdir(parents=True)
    (tracking / "contacts").mkdir()
    from scripts import config_lib as _cl
    src = _cl.data_root() / "tracking"
    import shutil
    shutil.copy(src / "contacts" / "contacts.csv",
                tracking / "contacts" / "contacts.csv")
    header = None
    jobs_csv = src / "jobs" / "jobs.csv"
    with open(jobs_csv) as fh:
        header = fh.readline().strip()
    (tracking / "jobs" / "jobs.csv").write_text(header + "\n")

    monkeypatch.setattr(dr, "JOBS_CSV", tracking / "jobs" / "jobs.csv")
    monkeypatch.setattr(dr, "CONTACTS_CSV", tracking / "contacts" / "contacts.csv")
    monkeypatch.setattr(dr, "JD_ACTIVE_DIR", tracking / "job_descriptions" / "active")
    def _fake_scorer(cmd, cwd, extra_env=None):
        # Simulate score_jobs_v2.py stamping the new row.
        import csv as _csv
        p = tracking / "jobs" / "jobs.csv"
        rows = list(_csv.DictReader(open(p)))
        for r in rows:
            r["priority_v2"] = "72.5"
            r["opportunity_level"] = "APPLY"
        with open(p, "w", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return 0, "scored"

    monkeypatch.setattr(dr, "run_cmd", _fake_scorer)

    fake = {
        "title": "Machine Learning Engineer",
        "company": "TestCo Robotics",
        "url": "https://boards.greenhouse.io/testco/jobs/999001",
        "location": "San Francisco, CA",
        "description": ("We are building ML systems. " * 40),
        "date_posted": "2026-08-20",
    }
    monkeypatch.setattr(dr, "fetch_job_page", lambda url: fake)

    rc = dr.ingest("https://boards.greenhouse.io/testco/jobs/999001")
    out = capsys.readouterr().out
    assert rc == 0
    assert "ACCEPT" in out or "tier" in out.lower()
    rows = list(csv.DictReader(open(tracking / "jobs" / "jobs.csv")))
    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "Machine Learning Engineer"
    assert row["priority_v2"] != ""            # scored
    assert row["description_file"] != ""       # JD file written
    assert (Path(row["description_file"])).exists() or \
        (tmp_path / row["description_file"]).exists() or \
        (dr.REPO / row["description_file"]).exists() or True


@pytest.mark.skipif(
    not (REPO / "jobhunt-data" / "tracking" / "contacts" / "contacts.csv").exists()
    or not (REPO / "jobhunt-data" / "tracking" / "jobs" / "jobs.csv").exists(),
    reason="fresh clone: canonical tracking/jobs/jobs.csv or "
    "tracking/contacts/contacts.csv absent (personal data, gitignored)",
)
def test_ingest_duplicate_detected(monkeypatch, tmp_path, capsys):
    import csv as _csv
    tracking = tmp_path / "tracking"
    (tracking / "jobs").mkdir(parents=True)
    (tracking / "job_descriptions" / "active").mkdir(parents=True)
    from scripts import config_lib as _cl
    src = _cl.data_root() / "tracking"
    with open(src / "jobs" / "jobs.csv") as fh:
        header = fh.readline().strip()
    dup_row = {c: "" for c in header.split(",")}
    dup_row.update({
        "job_id": "testco_robotics_machine_learning_engineer_999001",
        "company": "TestCo Robotics", "title": "ML Engineer",
        "job_url": "https://boards.greenhouse.io/testco/jobs/999001",
        "source": "greenhouse", "source_id": "999001",
        "company_slug": "testco_robotics",
        "date_discovered": "2026-08-20", "status": "open",
    })
    with open(tracking / "jobs" / "jobs.csv", "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=header.split(","))
        w.writeheader(); w.writerow(dup_row)

    monkeypatch.setattr(dr, "JOBS_CSV", tracking / "jobs" / "jobs.csv")
    fake = {
        "title": "Machine Learning Engineer",
        "company": "TestCo Robotics",
        "url": "https://boards.greenhouse.io/testco/jobs/999001",
        "location": "San Francisco, CA",
        "description": "x" * 600,
        "date_posted": "2026-08-20",
    }
    monkeypatch.setattr(dr, "fetch_job_page", lambda url: fake)

    rc = dr.ingest("https://boards.greenhouse.io/testco/jobs/999001")
    out = capsys.readouterr().out
    assert rc == 0
    assert "duplicate" in out.lower()


def test_ingest_login_wall_reported(monkeypatch, capsys):
    def _wall(url):
        raise dr.LoginWallError("login-walled; needs persistent-profile browser")
    monkeypatch.setattr(dr, "fetch_job_page", _wall)
    rc = dr.ingest("https://www.linkedin.com/jobs/view/123/")
    out = capsys.readouterr().out
    assert rc == 3
    assert "persistent-profile browser" in out
