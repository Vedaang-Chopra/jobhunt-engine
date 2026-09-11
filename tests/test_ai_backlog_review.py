"""Safety tests for per-record LLM backlog qualification."""
from __future__ import annotations


def test_ai_review_archives_only_explicit_valid_decisions():
    from scripts import ai_backlog_review as review

    rows = [
        {"job_id": "keep", "status": "open"},
        {"job_id": "archive", "status": "open"},
    ]
    decisions = {
        "keep": {"decision": "KEEP", "reason": "Relevant role"},
        "archive": {"decision": "ARCHIVE", "reason": "New-grad program"},
    }
    changed = review.apply_job_decisions(rows, decisions, "2026-09-11")

    assert [row["status"] for row in rows] == ["open", "archived"]
    assert changed == ["archive"]
    assert rows[0]["ai_review_verdict"] == "KEEP"
    assert rows[1]["ai_review_reason"] == "New-grad program"


def test_ai_review_rejects_unrecognized_decisions_without_changing_status():
    from scripts import ai_backlog_review as review

    rows = [{"post_id": "p1", "status": "new"}]
    changed = review.apply_post_decisions(
        rows, {"p1": {"decision": "maybe", "reason": "uncertain"}},
        "2026-09-11")

    assert changed == []
    assert rows[0]["status"] == "new"
    assert "ai_review_verdict" not in rows[0]


def test_ai_review_invokes_hermes_with_the_codex_profile(monkeypatch):
    from scripts import ai_backlog_review as review

    seen = {}
    def fake_run(command, **kwargs):
        seen["command"] = command
        return type("Result", (), {"returncode": 0, "stdout": '{"decision":"KEEP","reason":"fit"}', "stderr": ""})()

    monkeypatch.setattr(review.subprocess, "run", fake_run)
    assert review.codex_chat("return JSON") == '{"decision":"KEEP","reason":"fit"}'
    assert seen["command"][:4] == ["hermes", "--profile", "job-hunt-fresh", "chat"]


def test_ai_review_loads_canonical_profile_context(tmp_path, monkeypatch):
    from scripts import ai_backlog_review as review

    profile = tmp_path / "profile.md"
    profile.write_text("Target: applied AI/ML roles", encoding="utf-8")
    monkeypatch.setattr(review, "PROFILE_PATH", profile)
    assert review.profile_context() == "Target: applied AI/ML roles"
