"""Deterministic result evaluator + injectable LLM relevance judge (Task 3).

Pure arithmetic scoring of per-query extraction counts against an injectable
policy dict. Semantic relevance judgment is requested from the LLM as a
*service call* (`llm_judge_relevant` with an injected ``judge_fn``); persistence
of verdicts belongs to the memory layer, NOT here.

This module must have no coupling with the persistence (memory) or
ontology layers — no references to them in its imports.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

__all__ = ["ScoreResult", "Evaluator", "NotConfiguredError", "DEFAULT_POLICY"]


DEFAULT_POLICY = {
    "low_yield_threshold": 3,
    "high_yield_threshold": 8,
    "max_duplicate_rate": 0.8,
}


class NotConfiguredError(RuntimeError):
    """Raised when llm_judge_relevant is called without an injected judge_fn."""


@dataclass
class ScoreResult:
    """Deterministic per-query score derived from extraction counts."""

    relevant: int
    new: int
    dups: int
    results_inspected: int
    yield_score: str  # 'low' | 'medium' | 'high'
    novelty_score: str  # 'low' | 'medium' | 'high'
    duplicate_rate: float
    opportunity_count: int  # == new


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y"}
    return bool(value)


class Evaluator:
    """Scores query results deterministically; judges relevance via injection."""

    def __init__(self, policy: Optional[dict] = None):
        self.policy = dict(DEFAULT_POLICY)
        if policy:
            self.policy.update(policy)

    # ------------------------------------------------------------------ score

    def score(
        self,
        results_inspected: int,
        relevant: int,
        new: int,
        dups: int,
    ) -> ScoreResult:
        """Pure arithmetic off the policy thresholds. No I/O, no LLM."""
        duplicate_rate = dups / max(results_inspected, 1)

        low = self.policy["low_yield_threshold"]
        high = self.policy["high_yield_threshold"]
        if relevant < low:
            yield_score = "low"
        elif relevant > high:
            yield_score = "high"
        else:
            yield_score = "medium"

        if new > 0 and duplicate_rate < 0.5:
            novelty_score = "high"
        elif new > 0:
            novelty_score = "medium"
        else:
            novelty_score = "low"

        return ScoreResult(
            relevant=relevant,
            new=new,
            dups=dups,
            results_inspected=results_inspected,
            yield_score=yield_score,
            novelty_score=novelty_score,
            duplicate_rate=duplicate_rate,
            opportunity_count=new,
        )

    # ------------------------------------------------------- relevance judge

    def llm_judge_relevant(
        self,
        items: list,
        planned_query: Any,
        judge_fn: Optional[Callable[[list, Any], list]] = None,
    ) -> list:
        """Ask the injected judge which items are relevant to the planned query.

        Returns one normalized verdict dict per item:
            {item_id, index, relevant: bool, reason: str}

        The *call* may be backed by an LLM; the *persistence* of verdicts stays
        in the memory layer. Production wiring of ``judge_fn`` happens via
        search_strategy.llm (Task 8) — without it this raises NotConfiguredError.
        """
        if judge_fn is None:
            raise NotConfiguredError(
                "llm_judge_relevant requires a judge_fn (production wiring "
                "arrives via search_strategy.llm)"
            )
        if not items:
            return []

        raw = judge_fn(items, planned_query)
        if not isinstance(raw, list):
            raise ValueError(
                f"judge_fn must return a list of dicts, got {type(raw).__name__}"
            )

        verdicts: list = []
        matched: set = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue  # drop malformed non-dict entries
            idx = entry.get("index")
            if idx is None and "item_id" in entry:
                idx = self._index_for_item_id(items, entry["item_id"])
            if idx is None or not isinstance(idx, int) or not (0 <= idx < len(items)):
                idx = len(verdicts)  # positional fallback
            while idx in matched:  # never clobber an already-matched slot
                idx += 1
            if idx >= len(items):
                continue
            matched.add(idx)
            verdicts.append(
                {
                    "item_id": self._item_id(items[idx]),
                    "index": idx,
                    "relevant": _coerce_bool(entry.get("relevant")),
                    "reason": str(entry.get("reason") or ""),
                }
            )

        # Pad unmatched slots with explicit negative verdicts.
        for idx in range(len(items)):
            if idx in matched:
                continue
            verdicts.append(
                {
                    "item_id": self._item_id(items[idx]),
                    "index": idx,
                    "relevant": False,
                    "reason": "no verdict returned",
                }
            )

        verdicts.sort(key=lambda v: v["index"])
        return verdicts

    @staticmethod
    def _item_id(item: Any) -> Any:
        if isinstance(item, dict):
            for key in ("id", "item_id", "url", "urn"):
                if key in item and item[key] is not None:
                    return item[key]
        return None

    @staticmethod
    def _index_for_item_id(items: list, item_id: Any) -> Optional[int]:
        for i, it in enumerate(items):
            if Evaluator._item_id(it) == item_id:
                return i
        return None
