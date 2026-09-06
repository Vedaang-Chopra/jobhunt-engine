"""Tests for search_strategy.exec_jobs — thin deterministic adapter for Jobs mode."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from search_strategy.exec_jobs import parse_planned_json, run_planned
from search_strategy.memory import SearchMemory


ROWS = [
    {"query": "Research Engineer Agents",
     "family": "domain_plus_role",
     "intent": "variation",
     "filters": {"recency": "week", "geo": "us_remote"},
     "rationale": "variation of proven query",
     "notes": ""},
    {"query": "LLM Fine-Tuning Engineer",
     "family": "post_training",
     "intent": "proven",
     "filters": {},
     "rationale": "",
     "notes": ""},
]


class TestParsePlannedJson(unittest.TestCase):
    def test_roundtrip_bare_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "planned.json"
            p.write_text(json.dumps(ROWS))
            out = parse_planned_json(p)
        self.assertEqual(out, ROWS)

    def test_roundtrip_wrapped_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "planned.json"
            p.write_text(json.dumps({"queries": ROWS}))
            out = parse_planned_json(str(p))
        self.assertEqual([r["query"] for r in out], [r["query"] for r in ROWS])

    def test_missing_query_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text(json.dumps([{"family": "x"}, {"query": "ok"}]))
            with self.assertRaises(ValueError):
                parse_planned_json(p)


class TestRunPlanned(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = SearchMemory(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_fake_sweep_appends_and_aggregates(self):
        def fake_sweep(row):
            return {"results_inspected": 10, "relevant": 4,
                    "new": 3, "duplicates": 1}

        summary = run_planned(ROWS, sweep_run_fn=fake_sweep, mem=self.mem)
        self.assertEqual(summary["total_new"], 6)
        self.assertEqual(len(summary["per_query"]), 2)
        self.assertEqual(summary["per_query"][0]["query"], ROWS[0]["query"])
        self.assertEqual(summary["per_query"][0]["new"], 3)
        self.assertEqual(summary["per_query"][1]["new"], 3)
        rows = self.mem.recent(limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].mode, "jobs")
        self.assertEqual({r.query for r in rows},
                         {ROWS[0]["query"], ROWS[1]["query"]})
        rec = [r for r in rows if r.query == ROWS[0]["query"]][0]
        self.assertEqual(rec.new_results, 3)
        self.assertEqual(rec.relevant_results, 4)
        self.assertEqual(rec.results_inspected, 10)
        self.assertEqual(rec.duplicate_results, 1)
        self.assertIn("recency", rec.filters_json)

    def test_default_sweep_none_records_zero_counts(self):
        summary = run_planned(ROWS[:1], mem=self.mem)
        self.assertEqual(summary["total_new"], 0)
        row = self.mem.recent(limit=5)[0]
        self.assertEqual(row.new_results, 0)
        self.assertEqual(row.yield_score, "low")

    def test_sweep_exception_does_not_break_run(self):
        def bad_sweep(row):
            raise RuntimeError("network down")

        summary = run_planned(ROWS, sweep_run_fn=bad_sweep, mem=self.mem)
        self.assertEqual(summary["total_new"], 0)
        self.assertEqual(len(summary["per_query"]), 2)


if __name__ == "__main__":
    unittest.main()
