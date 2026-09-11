"""Regression coverage for bulk qualification cleanup and post-table navigation."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_post_cleanup_uses_canonical_discovered_date_and_persists(tmp_path, monkeypatch):
    """Stale canonical posts must become dismissed when an apply run is requested."""
    from scripts import qualify_sweep as qs

    jobs = tmp_path / "jobs.csv"
    posts = tmp_path / "hiring_posts.csv"
    report_dir = tmp_path / "reports"
    _write_csv(jobs, ["job_id", "status", "title", "priority_v2"], [])
    _write_csv(posts,
               ["post_id", "status", "discovered_date", "posted_date"],
               [{"post_id": "old", "status": "new",
                 "discovered_date": "2020-01-01", "posted_date": ""},
                {"post_id": "fresh", "status": "new",
                 "discovered_date": "2999-01-01", "posted_date": ""},
                {"post_id": "reviewed", "status": "reviewed",
                 "discovered_date": "2020-01-01", "posted_date": ""}])
    monkeypatch.setattr(qs, "JOBS_CSV", jobs)
    monkeypatch.setattr(qs, "POSTS_CSV", posts)
    monkeypatch.setattr(qs, "REPORT_DIR", report_dir)

    assert qs.main(["--posts", "--post-age-days", "14", "--apply"]) == 0

    rows = list(csv.DictReader(posts.open(newline="", encoding="utf-8")))
    assert {r["post_id"]: r["status"] for r in rows} == {
        "old": "dismissed", "fresh": "new", "reviewed": "reviewed"}


def test_posts_default_to_newest_sort_with_discovered_date_fallback():
    """Posts without a source posting date remain navigable by discovery date."""
    from ui import data

    posts = pd.DataFrame([
        {"post_id": "old", "posted_date": "2026-01-01", "discovered_date": "2026-01-02"},
        {"post_id": "fallback", "posted_date": "", "discovered_date": "2026-09-10"},
        {"post_id": "latest", "posted_date": "2026-09-11", "discovered_date": "2026-09-11"},
    ])
    sorted_posts = data.sort_hiring_posts(posts)
    assert list(sorted_posts["post_id"]) == ["latest", "fallback", "old"]


def test_posts_can_filter_to_high_priority():
    from ui import data

    posts = pd.DataFrame([
        {"post_id": "high", "priority": "high"},
        {"post_id": "normal", "priority": "normal"},
    ])
    assert list(data.filter_hiring_posts(posts, priority="high")["post_id"]) == ["high"]


def test_cleanup_command_is_available_to_the_ui_trigger_registry():
    from ui import triggers

    assert triggers.qualify_sweep_cmd()[-3:] == ["--posts", "--post-age-days", "14"]
    assert triggers.ai_backlog_review_cmd()[-1] == "--apply"
