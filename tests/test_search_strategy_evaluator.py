"""Tests for scripts/search_strategy/evaluator.py (Task 3).

Deterministic per-query scoring + injectable LLM relevance judge.
Evaluator must NOT import memory or ontology.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Ensure the shared package marker exists (create-if-missing ONLY; never overwrite).
_INIT = REPO_ROOT / "scripts" / "search_strategy" / "__init__.py"
if not _INIT.exists():
    _INIT.parent.mkdir(parents=True, exist_ok=True)
    _INIT.write_text('"""Search strategy package."""\n', encoding="utf-8")

from search_strategy.evaluator import (  # noqa: E402
    Evaluator,
    NotConfiguredError,
    ScoreResult,
)


def default_policy():
    return {
        "low_yield_threshold": 3,
        "high_yield_threshold": 8,
        "max_duplicate_rate": 0.8,
    }


class TestScoreSpecExample(unittest.TestCase):
    def test_scores_example_from_spec(self):
        ev = Evaluator(policy=default_policy())
        s = ev.score(results_inspected=38, relevant=12, new=9, dups=3)
        self.assertIsInstance(s, ScoreResult)
        self.assertEqual((s.yield_score, s.novelty_score), ("high", "high"))
        self.assertAlmostEqual(s.duplicate_rate, 3 / 38)
        self.assertEqual(s.opportunity_count, 9)
        self.assertEqual(
            (s.results_inspected, s.relevant, s.new, s.dups), (38, 12, 9, 3)
        )


class TestYieldThresholdBoundaries(unittest.TestCase):
    def setUp(self):
        self.ev = Evaluator(policy=default_policy())

    def _yield(self, relevant):
        return self.ev.score(
            results_inspected=max(relevant, 1), relevant=relevant, new=0, dups=0
        ).yield_score

    def test_below_low_threshold_is_low(self):
        self.assertEqual(self._yield(0), "low")
        self.assertEqual(self._yield(2), "low")

    def test_at_low_threshold_is_medium(self):
        self.assertEqual(self._yield(3), "medium")

    def test_between_thresholds_is_medium(self):
        self.assertEqual(self._yield(5), "medium")
        self.assertEqual(self._yield(8), "medium")  # > high_yield_threshold required

    def test_above_high_threshold_is_high(self):
        self.assertEqual(self._yield(9), "high")

    def test_injected_policy_overrides_thresholds(self):
        ev = Evaluator(policy={"low_yield_threshold": 10, "high_yield_threshold": 20})
        s = ev.score(results_inspected=10, relevant=5, new=1, dups=0)
        self.assertEqual(s.yield_score, "low")


class TestNoveltyAndDuplicateRate(unittest.TestCase):
    def setUp(self):
        self.ev = Evaluator(policy=default_policy())

    def test_zero_results_scores_low_everything(self):
        s = self.ev.score(results_inspected=0, relevant=0, new=0, dups=0)
        self.assertEqual(s.yield_score, "low")
        self.assertEqual(s.novelty_score, "low")
        self.assertEqual(s.duplicate_rate, 0.0)  # dups/max(inspected, 1)

    def test_new_with_low_dup_rate_is_high_novelty(self):
        s = self.ev.score(results_inspected=10, relevant=4, new=4, dups=1)
        self.assertEqual(s.novelty_score, "high")

    def test_new_with_high_dup_rate_is_medium_novelty(self):
        # dup rate >= 0.5 with new > 0 -> medium
        s = self.ev.score(results_inspected=10, relevant=6, new=2, dups=7)
        self.assertGreaterEqual(s.duplicate_rate, 0.5)
        self.assertEqual(s.novelty_score, "medium")

    def test_no_new_results_is_low_novelty_even_when_relevant(self):
        s = self.ev.score(results_inspected=10, relevant=6, new=0, dups=2)
        self.assertEqual(s.yield_score, "medium")
        self.assertEqual(s.novelty_score, "low")

    def test_duplicate_rate_guard_against_division_by_zero(self):
        s = self.ev.score(results_inspected=0, relevant=0, new=0, dups=5)
        self.assertEqual(s.duplicate_rate, 5.0)


class TestLlmJudgeRelevant(unittest.TestCase):
    ITEMS = [
        {"id": "job-1", "title": "Research Engineer"},
        {"id": "job-2", "title": "Recruiter spam"},
        {"id": "job-3", "title": "LLM Post-Training Engineer"},
    ]

    def test_no_judge_fn_raises_not_configured(self):
        ev = Evaluator()
        with self.assertRaises(NotConfiguredError):
            ev.llm_judge_relevant(self.ITEMS, "research engineer reasoning")

    def test_judge_fn_called_with_items_and_query(self):
        seen = {}

        def judge(items, query):
            seen["items"], seen["query"] = items, query
            return [{"index": i, "relevant": True, "reason": "ok"} for i in range(len(items))]

        ev = Evaluator()
        out = ev.llm_judge_relevant(self.ITEMS, {"query": "q", "filters": {}}, judge_fn=judge)
        self.assertEqual(seen["items"], self.ITEMS)
        self.assertEqual(seen["query"], {"query": "q", "filters": {}})
        self.assertEqual(len(out), 3)
        self.assertTrue(all(v["relevant"] for v in out))

    def test_verdict_shape_normalized(self):
        def judge(items, query):
            return [{"item_id": "job-1", "relevant": True, "reason": "role match"},
                    {"index": 1, "relevant": False, "reason": "not hiring"},
                    {"item_id": "job-3", "relevant": True}]  # missing reason

        out = Evaluator().llm_judge_relevant(self.ITEMS, "q", judge_fn=judge)
        self.assertEqual(out[0]["item_id"], "job-1")
        self.assertFalse(out[1]["relevant"])
        self.assertEqual(out[2]["reason"], "")  # normalized default

    def test_malformed_judge_output_normalized(self):
        # non-bool relevant coerced; non-dict entries skipped; missing entries padded False
        def judge(items, query):
            return [
                "garbage-string-entry",
                {"index": 0, "relevant": "yes", "reason": "coerced"},
            ]

        out = Evaluator().llm_judge_relevant(self.ITEMS, "q", judge_fn=judge)
        self.assertEqual(len(out), 3)
        self.assertTrue(out[0]["relevant"])          # "yes" -> True
        self.assertFalse(out[1]["relevant"])         # unpadded -> False
        self.assertEqual(out[1]["reason"], "no verdict returned")
        self.assertFalse(out[2]["relevant"])

    def test_non_list_judge_output_raises_value_error(self):
        def judge(items, query):
            return {"unexpected": "shape"}

        with self.assertRaises(ValueError):
            Evaluator().llm_judge_relevant(self.ITEMS, "q", judge_fn=judge)

    def test_empty_items_short_circuits_without_calling_judge(self):
        calls = []

        def judge(items, query):
            calls.append(1)
            return []

        out = Evaluator().llm_judge_relevant([], "q", judge_fn=judge)
        self.assertEqual(out, [])
        self.assertEqual(calls, [])


class TestNoForbiddenImports(unittest.TestCase):
    def test_evaluator_does_not_import_memory_or_ontology(self):
        import search_strategy.evaluator as mod

        src = open(mod.__file__, encoding="utf-8").read()
        self.assertNotIn("import memory", src)
        self.assertNotIn("from search_strategy.memory", src)
        self.assertNotIn("import ontology", src)
        self.assertNotIn("from search_strategy.ontology", src)


if __name__ == "__main__":
    unittest.main()
