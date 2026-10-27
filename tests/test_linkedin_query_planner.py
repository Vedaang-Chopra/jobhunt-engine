"""Pure tests for the deterministic LinkedIn Jobs query planner."""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import config_lib
from linkedin_query_planner import RUN_FIELDS, append_run, load_catalog, plan_queries, read_history


def catalog():
    return load_catalog(REPO / "setup" / "linkedin-job-queries.yaml")


def record(query_id: str, when: datetime, *, eligible=0, duplicates=0, failures=0):
    return {
        "query_id": query_id, "last_run_at": when.isoformat(),
        "eligible_jobs": str(eligible), "duplicates": str(duplicates),
        "failure_count": str(failures),
    }


def test_planner_emits_exactly_eight_with_mandatory_filters():
    plan = plan_queries(catalog(), [])
    assert len(plan) == 8
    assert all(q.location == "United States" for q in plan)
    assert all(q.recency_seconds == 604800 for q in plan)
    assert all(q.geo_id == "103644278" for q in plan)


def test_all_core_and_technical_families_have_bounded_coverage():
    plan = plan_queries(catalog(), [])
    anchors = [q for q in plan if q.slot == "broad_anchor"]
    technical = {q.technical_family for q in plan if q.slot == "recurring_technical"}
    assert [q.query for q in anchors] == [
        "ML Research Engineer", "AI Research Scientist",
        "Applied Scientist AI", "ML Engineer LLM",
    ]
    assert technical == {
        "post_training_alignment", "llm_evaluation_reliability_safety", "agents",
    }
    assert len([q for q in plan if q.slot == "rotating_frontier"]) == 1


def test_rotation_is_deterministic_and_frontier_round_robins_by_coverage():
    cfg = catalog()
    first = plan_queries(cfg, [])
    assert [q.query_id for q in first] == [q.query_id for q in plan_queries(cfg, [])]
    frontier = next(q for q in first if q.slot == "rotating_frontier")
    now = datetime.now(timezone.utc)
    second = plan_queries(cfg, [record(frontier.query_id, now)])
    next_frontier = next(q for q in second if q.slot == "rotating_frontier")
    assert next_frontier.technical_family != frontier.technical_family


def test_all_frontier_families_are_covered_within_five_sweeps():
    cfg = catalog()
    history = []
    covered = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for sweep_number in range(5):
        plan = plan_queries(cfg, history)
        frontier = next(q for q in plan if q.slot == "rotating_frontier")
        covered.append(frontier.technical_family)
        history.append(record(frontier.query_id, start + timedelta(hours=sweep_number)))
    assert set(covered) == set(cfg["frontier"])


def test_low_yield_duplicate_query_deprioritized_without_starving_family():
    cfg = catalog()
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=30)
    history = [
        record("ai_agents_tool_use", now, eligible=0, duplicates=100),
        record("agentic_tool_calling", old, eligible=5, duplicates=0),
    ]
    plan = plan_queries(cfg, history)
    agents = [q for q in plan if q.technical_family == "agents"]
    assert len(agents) == 1
    assert agents[0].query_id != "ai_agents_tool_use"


def test_query_state_uses_canonical_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path))
    target = config_lib.path("linkedin_query_runs_csv")
    assert str(target).startswith(str(tmp_path))
    row = {field: "" for field in RUN_FIELDS}
    row.update({"run_id": "r1", "query_id": "q1", "query": "AI agents",
                "last_run_at": datetime.now(timezone.utc).isoformat(),
                "raw_results": 10, "eligible_jobs": 2})
    append_run([row])
    assert target.is_file()
    loaded = read_history()
    assert loaded[0]["query_id"] == "q1"
    assert loaded[0]["eligible_jobs"] == "2"


def test_append_run_additively_migrates_old_header(tmp_path):
    target = tmp_path / "old.csv"
    target.write_text("query_id,query\nold,Legacy\n", encoding="utf-8")
    row = {field: "" for field in RUN_FIELDS}
    row.update({"query_id": "new", "query": "New", "last_run_at": "2026-01-01T00:00:00+00:00"})
    append_run([row], target)
    with target.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        assert set(RUN_FIELDS).issubset(reader.fieldnames)
    assert [r["query_id"] for r in rows] == ["old", "new"]


def test_catalog_keeps_clip_based_loss_exploration_only():
    cfg = catalog()
    serialized_queries = " ".join(
        q["query"] for family in cfg["frontier"].values() for q in family["queries"])
    assert "CLIP-based loss" not in serialized_queries
    assert cfg["frontier"]["contrastive_representation_learning"]["exploration_signals"] == ["CLIP-based loss"]
