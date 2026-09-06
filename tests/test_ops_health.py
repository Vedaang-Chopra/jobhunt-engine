"""Unit tests for scripts/ops_health.py (Task 9), including the health drill.

The drill simulates a fake failing source by writing health.json directly,
then verifies detection, self-pause, alert emission, and non-zero exit.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ops_health", REPO / "scripts" / "ops_health.py")
assert spec and spec.loader
ops_health = importlib.util.module_from_spec(spec)
sys.modules.setdefault("ops_health", ops_health)
spec.loader.exec_module(ops_health)


@pytest.fixture()
def env(tmp_path):
    health = tmp_path / "health.json"
    log = tmp_path / "alerts.log"
    runs = tmp_path / "search_runs.csv"
    return {"health": health, "log": log, "runs": runs}


def _write_health(path, data):
    path.write_text(json.dumps(data))


def _write_runs(path, rows):
    lines = ["run_id,date,sources,notes"]
    for i, (date, src) in enumerate(rows):
        lines.append(f"r{i},{date},{src},")
    path.write_text("\n".join(lines) + "\n")


def test_healthy_source_no_alert(env):
    _write_health(env["health"], {
        "career_ops": {"failure_streak": 0, "status": "active",
                       "last_result": "ok"}})
    res = ops_health.evaluate(env["health"], env["runs"], env["log"])
    assert res["alerts"] == []
    assert not env["log"].exists()
    row = next(r for r in res["rows"] if r["source"] == "career_ops")
    assert row["status"] == "active"


def test_drill_fake_failing_source_detected_paused_alerted(env):
    """Health drill: fake failing source -> detected + paused + alert."""
    _write_health(env["health"], {
        "freshness": {"failure_streak": 2, "status": "active",
                      "last_result": "fail"}})
    res = ops_health.evaluate(env["health"], env["runs"], env["log"],
                              persist=True)
    # Detection: alert raised this evaluation.
    assert len(res["alerts"]) == 1
    assert "freshness" in res["alerts"][0]
    # Pause: written back into health.json.
    data = json.loads(env["health"].read_text())
    assert data["freshness"]["status"] == "self-paused"
    assert data["freshness"]["alerted_at_streak"] == 2
    # Alert emitted to alerts.log.
    content = env["log"].read_text()
    assert "ALERT freshness:" in content


def test_alert_not_duplicated_on_recheck(env):
    _write_health(env["health"], {
        "freshness": {"failure_streak": 2, "status": "active",
                      "last_result": "fail"}})
    ops_health.evaluate(env["health"], env["runs"], env["log"])
    res = ops_health.evaluate(env["health"], env["runs"], env["log"])
    assert res["alerts"] == []          # same streak -> no re-alert
    assert env["log"].read_text().count("ALERT") == 1
    # Escalating streak re-alerts.
    data = json.loads(env["health"].read_text())
    data["freshness"]["failure_streak"] = 3
    _write_health(env["health"], data)
    res = ops_health.evaluate(env["health"], env["runs"], env["log"])
    assert len(res["alerts"]) == 1


def test_check_exit_nonzero_via_main(env, capsys):
    _write_health(env["health"], {
        "l1": {"failure_streak": 4, "status": "active",
               "last_result": "fail"}})
    rc = ops_health.main(["--check"], health_path=env["health"],
                         runs_path=env["runs"], log_path=env["log"])
    assert rc != 0
    out = capsys.readouterr().out
    assert "CHECK FAILED" in out and "l1" in out


def test_report_lists_recency_and_untracked(env, capsys):
    from datetime import date, timedelta
    old = (date.today() - timedelta(days=9)).isoformat()
    _write_runs(env["runs"], [(old, "linkedin_posts"),
                              (date.today().isoformat(), "career_ops")])
    _write_health(env["health"], {
        "career_ops": {"failure_streak": 0, "status": "active"}})
    rc = ops_health.main(["--report"], health_path=env["health"],
                         runs_path=env["runs"], log_path=env["log"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "linkedin_posts" in out and "untracked" in out
    assert "stale" in out            # 9 days > STALE_DAYS
