"""Thin deterministic adapter between planned queries and Jobs-mode execution.

Consumes PlannedQuery-shaped dicts (keys: query/family/intent/filters/rationale/
notes) — never imports the planner (parallel ownership). Calls an injectable
sweep_run_fn per row, persists SearchMemory QueryRecord rows, aggregates a
summary. No browser, no LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from scripts.search_strategy.memory import QueryRecord, SearchMemory
    from scripts import config_lib
except ImportError:
    try:
        from search_strategy.memory import QueryRecord, SearchMemory  # type: ignore
        import config_lib  # type: ignore
    except ImportError:
        from ..memory import QueryRecord, SearchMemory  # type: ignore
        import config_lib  # type: ignore


def parse_planned_json(path) -> list[dict]:
    """Load a --planned-json file.

    Accepts {"queries": [ {...}, ... ]} or a bare list of PlannedQuery dicts.
    Every row must carry the required 'query' key; raises ValueError otherwise.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("queries", [])
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not str(row.get("query", "")).strip():
            raise ValueError(
                f"planned query row {i} missing required key 'query': {row!r}")
        out.append(row)
    return out


def run_planned(rows: list[dict], sweep_run_fn=None, mem=None) -> dict:
    """Execute each planned row via sweep_run_fn, persist memory rows, aggregate.

    sweep_run_fn(row) -> counts dict with any of results_inspected / relevant /
    new / duplicates (missing keys default to 0). When sweep_run_fn is None no
    execution happens and zero counts are recorded (dry/wiring mode).
    """
    if mem is None:
        mem = SearchMemory(root=config_lib.data_root())

    per_query = []
    total_new = 0
    for row in rows:
        counts = {
            "results_inspected": 0,
            "relevant": 0,
            "new": 0,
            "duplicates": 0,
        }
        error = None
        if sweep_run_fn is not None:
            try:
                returned = sweep_run_fn(row) or {}
                for k in counts:
                    counts[k] = int(returned.get(k, 0) or 0)
            except Exception as exc:  # never let one query kill the run
                error = f"{type(exc).__name__}: {exc}"

        record = QueryRecord(
            mode="jobs",
            query=row.get("query", ""),
            family=str(row.get("family", "")),
            filters_json=json.dumps(row.get("filters") or {}, sort_keys=True),
            results_inspected=counts["results_inspected"],
            relevant_results=counts["relevant"],
            new_results=counts["new"],
            duplicate_results=counts["duplicates"],
        )
        if error:
            print(f"  !! sweep failed q={row.get('query')!r}: {error}")
        try:
            mem.append(record)
        except Exception as exc:  # logging failures must not break the sweep
            print(f"  !! search-memory append failed q={row.get('query')!r}: {exc}")

        total_new += counts["new"]
        per_query.append({
            "query": row.get("query", ""),
            "family": row.get("family", ""),
            "results_inspected": counts["results_inspected"],
            "relevant": counts["relevant"],
            "new": counts["new"],
            "duplicates": counts["duplicates"],
            **({"error": error} if error else {}),
        })

    return {"per_query": per_query, "total_new": total_new}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: exec_jobs.py <planned.json>")
        raise SystemExit(2)
    summary = run_planned(parse_planned_json(sys.argv[1]))
    print(json.dumps(summary, indent=2))
