#!/usr/bin/env python3
"""Deterministic, configuration-driven planner for LinkedIn Jobs sweeps.

The catalog is code-owned at setup/linkedin-job-queries.yaml. A runtime may
copy and edit it at <data_root>/job_research/config/linkedin-job-queries.yaml;
that canonical data-root override wins. Query execution history is append-only
CSV under config_lib.path("linkedin_query_runs_csv"). No LLM is involved.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts import config_lib
except ImportError:  # pragma: no cover - direct script execution
    import config_lib

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "setup" / "linkedin-job-queries.yaml"
MAX_QUERIES = 8

RUN_FIELDS = [
    "run_id", "query_id", "query", "slot", "role_family",
    "technical_family", "last_run_at", "raw_results", "unique_results",
    "duplicates", "hard_rejections", "eligible_jobs", "apply_outcomes",
    "optimistic_outcomes", "failure_count", "error",
]


@dataclass(frozen=True)
class PlannedLinkedInQuery:
    query_id: str
    query: str
    slot: str
    role_family: str
    technical_family: str
    location: str
    geo_id: str
    recency_seconds: int
    experience_levels: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def config_path() -> Path:
    override = config_lib.path("linkedin_query_config")
    return override if override.is_file() else DEFAULT_CONFIG


def load_catalog(path: Path | str | None = None) -> dict:
    source = Path(path) if path else config_path()
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    policy = data.get("policy") or {}
    if int(policy.get("max_queries", MAX_QUERIES)) > MAX_QUERIES:
        raise ValueError("LinkedIn query policy may not exceed 8 searches")
    if int(policy.get("recency_seconds", 0)) != 604800:
        raise ValueError("LinkedIn query policy must use the past-week filter (604800s)")
    if int(policy.get("coverage_window_days", 0)) <= 0:
        raise ValueError("LinkedIn query policy requires a positive coverage window")
    if str(policy.get("location", "")).strip().lower() != "united states":
        raise ValueError("LinkedIn query policy must be US-only")
    return data


def read_history(path: Path | str | None = None) -> list[dict]:
    source = Path(path) if path else config_lib.path("linkedin_query_runs_csv")
    if not source.is_file():
        return []
    with source.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _parse_ts(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _stats(history: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in history:
        qid = str(row.get("query_id") or "")
        if not qid:
            continue
        item = out.setdefault(qid, {
            "last_run_at": datetime.min.replace(tzinfo=timezone.utc),
            "runs": 0, "eligible": 0, "duplicates": 0, "failures": 0,
        })
        item["runs"] += 1
        item["last_run_at"] = max(item["last_run_at"], _parse_ts(row.get("last_run_at", "")))
        for source, dest in (("eligible_jobs", "eligible"),
                             ("duplicates", "duplicates"),
                             ("failure_count", "failures")):
            try:
                item[dest] += int(float(row.get(source) or 0))
            except (TypeError, ValueError):
                pass
    return out


def _query_rank(entry: dict, stats: dict[str, dict]) -> tuple:
    """Oldest coverage first; then higher eligible yield, fewer dupes/failures, ID."""
    qid = str(entry["id"])
    s = stats.get(qid, {})
    runs = int(s.get("runs", 0))
    eligible = int(s.get("eligible", 0))
    dupes = int(s.get("duplicates", 0))
    failures = int(s.get("failures", 0))
    yield_rate = eligible / runs if runs else 0.0
    duplicate_rate = dupes / runs if runs else 0.0
    return (
        s.get("last_run_at", datetime.min.replace(tzinfo=timezone.utc)),
        -yield_rate,
        duplicate_rate,
        failures,
        qid,
    )


def _family_rank(name: str, entries: list[dict], stats: dict[str, dict]) -> tuple:
    latest = max(
        (stats.get(str(e["id"]), {}).get("last_run_at", datetime.min.replace(tzinfo=timezone.utc))
         for e in entries),
        default=datetime.min.replace(tzinfo=timezone.utc),
    )
    runs = sum(int(stats.get(str(e["id"]), {}).get("runs", 0)) for e in entries)
    eligible = sum(int(stats.get(str(e["id"]), {}).get("eligible", 0)) for e in entries)
    return (latest, -(eligible / runs if runs else 0.0), name)


def _planned(entry: dict, slot: str, technical_family: str,
             role_family: str, policy: dict, rationale: str) -> PlannedLinkedInQuery:
    return PlannedLinkedInQuery(
        query_id=str(entry["id"]),
        query=str(entry["query"]).strip(),
        slot=slot,
        role_family=str(role_family),
        technical_family=technical_family,
        location=str(policy["location"]),
        geo_id=str(policy["geo_id"]),
        recency_seconds=int(policy["recency_seconds"]),
        experience_levels=str(policy.get("experience_levels") or ""),
        rationale=rationale,
    )


def plan_queries(catalog: dict | None = None, history: list[dict] | None = None) -> list[PlannedLinkedInQuery]:
    """Return exactly 4 anchors + 3 technical families + 1 frontier query."""
    catalog = catalog or load_catalog()
    history = history if history is not None else read_history()
    policy = catalog["policy"]
    stats = _stats(history)
    selected: list[PlannedLinkedInQuery] = []

    for entry in catalog.get("broad_anchors", []):
        selected.append(_planned(
            entry, "broad_anchor", "", entry["role_family"], policy,
            "fixed broad-role anchor",
        ))

    for family_name in sorted((catalog.get("recurring_technical") or {}).keys()):
        family = catalog["recurring_technical"][family_name]
        entry = min(family["queries"], key=lambda q: _query_rank(q, stats))
        selected.append(_planned(
            entry, "recurring_technical", family_name, family["role_family"],
            policy, "oldest-covered variant, then yield/duplicate/error tie-break",
        ))

    frontier = catalog.get("frontier") or {}
    frontier_name = min(
        frontier,
        key=lambda name: _family_rank(name, frontier[name]["queries"], stats),
    )
    frontier_family = frontier[frontier_name]
    frontier_entry = min(frontier_family["queries"], key=lambda q: _query_rank(q, stats))
    selected.append(_planned(
        frontier_entry, "rotating_frontier", frontier_name,
        frontier_family["role_family"], policy,
        "oldest-covered frontier family; yield is a stable secondary signal",
    ))

    cap = min(int(policy.get("max_queries", MAX_QUERIES)), MAX_QUERIES)
    if len(selected) != cap or len(selected) > MAX_QUERIES:
        raise ValueError(f"catalog must produce exactly {cap} queries; produced {len(selected)}")
    if len({q.query_id for q in selected}) != len(selected):
        raise ValueError("catalog produced duplicate query IDs")
    return selected


def append_run(records: list[dict], path: Path | str | None = None) -> None:
    """Append metrics, additively migrating an older header when necessary."""
    if not records:
        return
    target = Path(path) if path else config_lib.path("linkedin_query_runs_csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = read_history(target)
    if target.exists():
        with target.open(newline="", encoding="utf-8") as fh:
            old_fields = list(csv.DictReader(fh).fieldnames or [])
    else:
        old_fields = []
    fields = old_fields + [field for field in RUN_FIELDS if field not in old_fields]
    if fields != old_fields and existing:
        with target.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(existing)
    write_header = not target.exists() or target.stat().st_size == 0
    with target.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields or RUN_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in records:
            writer.writerow({field: row.get(field, "") for field in (fields or RUN_FIELDS)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    plan = plan_queries(load_catalog(args.config), read_history(args.history) if args.history else None)
    payload = {"config": str(args.config or config_path()), "queries": [q.to_dict() for q in plan]}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for idx, query in enumerate(plan, 1):
            print(f"{idx}. [{query.query_id}] {query.query} ({query.slot}/{query.technical_family or query.role_family})")
        print("plan-only: no LinkedIn request and no state write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
