"""Cycle runner + stopping rules for the adaptive LinkedIn search strategy.

Implements Task 10 of the adaptive-search plan. ``run_cycle`` is deliberately
decoupled from the concrete planner (Task 5) and sweep executors (Task 7):
both are injected as callables.

    planner_fn(mode, state, remaining_budget) -> list[dict]
        PlannedQuery-shaped dicts: {"mode", "query", "family", "filters": {...}}.
    executor_fn(mode, row) -> dict with keys results_inspected, relevant_results,
        new_results, duplicate_results, companies_found, roles_found.

Adaptive budget reallocation
----------------------------
Each mode starts with an equal share of ``total_budget``:
``share_m = total_budget / len(modes)``.  When a mode stops early with
``leftover = share_m - queries_executed``, the leftover is redistributed to the
remaining modes proportionally to their mean new-per-query so far::

    w_i = mean_new_i / sum(mean_new_j for remaining j)
    extra_i = floor(leftover * w_i)

Modes with no recorded queries yet get a default mean_new of 1.0 so starved
modes still receive share; any unallocated remainder from flooring goes to the
last remaining mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from search_strategy.memory import QueryRecord, SearchMemory
except ImportError:
    try:
        from .memory import QueryRecord, SearchMemory  # type: ignore
    except ImportError:
        from memory import QueryRecord, SearchMemory  # type: ignore


class AuthWallError(Exception):
    """Raised by executors when LinkedIn auth-walls or CAPTCHAs a sweep."""


# --------------------------------------------------------------------- policy

_FALLBACK_POLICY = {
    "batch_size": 5,
    "max_batches_per_mode": 3,
    "mix_policy": {"proven": 0.30, "variation": 0.40,
                   "exploratory": 0.20, "entity_targeted": 0.10},
    "stop_rules": {"min_new_per_query": 1, "max_duplicate_rate": 0.8,
                   "authwall_or_captcha": "stop"},
    "low_yield_threshold": 3,
    "high_yield_threshold": 8,
    "broaden_after_low_yield": True,
}


def load_policy(path=None) -> dict:
    """Load search_policy.yaml via config_lib.data_root(); fall back to seed."""
    policy_path: Path | None = None
    if path is not None:
        policy_path = Path(path)
    else:
        try:
            from config_lib import data_root
        except ImportError:
            try:
                from scripts.config_lib import data_root  # type: ignore
            except ImportError:
                return dict(_FALLBACK_POLICY)
        policy_path = data_root() / "job_research" / "config" / "search_policy.yaml"
    try:
        import yaml
        data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return dict(_FALLBACK_POLICY)
    if not isinstance(data, dict) or not data:
        return dict(_FALLBACK_POLICY)
    merged = dict(_FALLBACK_POLICY)
    merged.update(data)
    return merged


def _stop_rules(policy: dict) -> dict:
    rules = dict(_FALLBACK_POLICY["stop_rules"])
    rules.update(policy.get("stop_rules") or {})
    return rules


# ------------------------------------------------------------------ run_cycle

def run_cycle(modes: list[str], total_budget: int, planner_fn, executor_fn,
              mem=None, onto=None, dry_run: bool = False, policy: dict | None = None) -> dict:
    """Run one adaptive discovery cycle across ``modes`` under ``total_budget``.

    See module docstring for the planner/executor interface and the
    reallocation formula. Returns a JSON-serializable summary dict:

        {modes: {mode: {batches, queries_executed, total_new, total_relevant,
                        stopped_reason}},
         budget_used, status, plan?}
    """
    policy = policy or load_policy()
    batch_size = int(policy.get("batch_size") or 5)
    max_batches = int(policy.get("max_batches_per_mode") or 3)
    rules = _stop_rules(policy)
    max_dup_rate = float(rules.get("max_duplicate_rate") or 0.8)
    min_new = int(rules.get("min_new_per_query") or 1)

    mem = mem if mem is not None else SearchMemory()
    modes = [m for m in modes if m]

    shares = {m: total_budget / len(modes) for m in modes} if modes else {}
    budgets = {m: shares.get(m, 0.0) for m in modes}
    stats = {m: {"queries_executed": 0, "total_new": 0, "total_relevant": 0,
                 "mean_new": 0.0, "batches": []} for m in modes}

    summary: dict = {
        "modes": {m: {"batches": [], "queries_executed": 0, "total_new": 0,
                      "total_relevant": 0, "stopped_reason": ""} for m in modes},
        "budget_used": 0,
        "status": "completed",
    }
    if dry_run:
        summary["plan"] = {}

    pending_modes = list(modes)
    while pending_modes:
        mode = pending_modes[0]
        pending_modes = pending_modes[1:]
        mstats = stats[mode]

        if not dry_run and budgets[mode] < 1:
            summary["modes"][mode]["stopped_reason"] = "budget_exhausted"
            continue

        stopped_reason = ""
        consecutive_zero_new = 0

        for _batch in range(max_batches):
            if not dry_run and budgets[mode] < 1:
                stopped_reason = "budget_exhausted"
                break
            remaining_for_mode = (
                max_batches * batch_size if dry_run else max(0, int(budgets[mode])))
            state = mem.build_state(onto=onto, budget_remaining=remaining_for_mode)
            rows = planner_fn(mode, state, remaining_for_mode) or []
            if not isinstance(rows, list):
                rows = [rows]

            if dry_run:
                summary.setdefault("plan", {})[mode] = [
                    r if isinstance(r, dict) else {"query": str(r)} for r in rows]
                break  # one planned batch per mode in dry-run

            batch_record = {"queries": [], "new": 0, "relevant": 0,
                            "duplicate_rate": 0.0, "zero_new_all": False}
            zero_new_all = True
            inspected_total = dupes_total = 0
            executed_this_batch = 0

            try:
                for row in rows[:max(1, int(budgets[mode]))]:
                    result = executor_fn(mode, row) or {}
                    record = QueryRecord(
                        mode=mode,
                        query=str(row.get("query") or ""),
                        family=str(row.get("family") or ""),
                        filters_json=_dumps_filters(row.get("filters")),
                        results_inspected=int(result.get("results_inspected") or 0),
                        relevant_results=int(result.get("relevant_results") or 0),
                        new_results=int(result.get("new_results") or 0),
                        duplicate_results=int(result.get("duplicate_results") or 0),
                        companies_found=list(result.get("companies_found") or []),
                        roles_found=list(result.get("roles_found") or []),
                    )
                    mem.append(record)
                    executed_this_batch += 1
                    mstats["queries_executed"] += 1
                    mstats["total_new"] += record.new_results
                    mstats["total_relevant"] += record.relevant_results
                    mstats["mean_new"] = (mstats["total_new"] / mstats["queries_executed"])
                    inspected_total += record.results_inspected
                    dupes_total += record.duplicate_results
                    if record.new_results >= max(1, min_new):
                        zero_new_all = False
                    batch_record["queries"].append({
                        "query": record.query, "family": record.family,
                        "new": record.new_results,
                        "relevant": record.relevant_results})
            except AuthWallError as exc:
                summary["budget_used"] = sum(s["queries_executed"] for s in stats.values())
                summary["status"] = "stopped_authwall"
                summary["authwall_error"] = str(exc)
                summary["modes"][mode]["batches"].append(batch_record)
                summary["modes"][mode]["stopped_reason"] = "authwall"
                return summary

            batch_record["new"] = mstats["total_new"]
            batch_record["relevant"] = mstats["total_relevant"]
            rate = dupes_total / inspected_total if inspected_total > 0 else 0.0
            batch_record["duplicate_rate"] = round(rate, 3)
            batch_record["zero_new_all"] = zero_new_all
            mstats["batches"].append(batch_record)
            summary["modes"][mode]["batches"].append(batch_record)
            budgets[mode] -= executed_this_batch

            consecutive_zero_new = consecutive_zero_new + 1 if zero_new_all else 0

            if inspected_total > 0 and rate >= max_dup_rate:
                stopped_reason = "duplicate_saturation"
            elif consecutive_zero_new >= 2:
                stopped_reason = "zero_new_two_batches"

            if stopped_reason:
                break
        else:
            if not dry_run and not stopped_reason:
                stopped_reason = "max_batches"

        if dry_run:
            summary["budget_used"] = 0
            summary["modes"][mode]["stopped_reason"] = stopped_reason or "dry_run"
            continue

        # ------------------------------------------------- reallocation step
        leftover = budgets[mode]
        if leftover > 0 and pending_modes:
            weights = []
            for m in pending_modes:
                s = stats[m]
                mean_new = s["mean_new"] if s["queries_executed"] > 0 else 1.0
                weights.append(max(0.05, mean_new))
            total_w = sum(weights)
            allocated = 0.0
            extras = {}
            for i, m in enumerate(pending_modes[:-1]):
                extra = int(leftover * weights[i] / total_w)
                extras[m] = extra
                allocated += extra
            extras[pending_modes[-1]] = int(leftover) - int(allocated)
            for m, extra in extras.items():
                budgets[m] += max(0, extra)

        summary["modes"][mode]["stopped_reason"] = stopped_reason or "completed"

    if not dry_run:
        summary["budget_used"] = sum(s["queries_executed"] for s in stats.values())

    for mode in modes:
        ms = stats[mode]
        out = summary["modes"][mode]
        out["queries_executed"] = ms["queries_executed"]
        out["total_new"] = ms["total_new"]
        out["total_relevant"] = ms["total_relevant"]

    return summary


def _dumps_filters(filters) -> str:
    import json
    if not filters:
        return ""
    try:
        return json.dumps(filters, sort_keys=True)
    except (TypeError, ValueError):
        return str(filters)


# ------------------------------------------------------- production wiring

def _default_planner(mode: str, state: dict, remaining_budget: int):
    """Real planner hook (Task 5). Returns None until planner.py lands."""
    try:
        from search_strategy.planner import plan_queries
    except ImportError:
        return None
    return plan_queries(mode, state, remaining_budget)


def _default_executor_factory():
    """Real sweep-executor hook (Task 7). Returns None until it lands."""
    try:
        from scripts.search_strategy.sweeps import make_executor  # type: ignore
    except ImportError:
        try:
            from search_strategy.sweeps import make_executor  # type: ignore
        except ImportError:
            return None
    return make_executor()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(2)
