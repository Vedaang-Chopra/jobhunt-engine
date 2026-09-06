"""Tests for linkedin_guest_sweep planned-query intake (Task 7).

Pure-function tests only: no network, no LinkedIn calls.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import linkedin_guest_sweep as sweep


class TestResolveQueryRows(unittest.TestCase):
    def test_no_flag_returns_static_queries_unchanged(self):
        args = sweep.build_arg_parser().parse_args([])
        rows = sweep.resolve_query_rows(args)
        self.assertEqual(rows, list(sweep.QUERIES))

    def test_planned_json_selects_planned_rows(self):
        planned = [
            {"query": "Planned Query A", "family": "domain_plus_role",
             "intent": "variation",
             "filters": {"recency": "week", "geo": "us_remote"},
             "rationale": "r", "notes": ""},
            {"query": "Planned Query B", "family": "post_training",
             "intent": "proven", "filters": {}, "rationale": "", "notes": ""},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "planned.json"
            p.write_text(json.dumps({"queries": planned}))
            args = sweep.build_arg_parser().parse_args(["--planned-json", str(p)])
            rows = sweep.resolve_query_rows(args)
        self.assertEqual([r["query"] for r in rows],
                         ["Planned Query A", "Planned Query B"])
        self.assertNotIn(rows[0]["query"], sweep.QUERIES)

    def test_filter_mapping_known_and_unknown_keys(self):
        filters = {"geo": "us_remote", "recency": "week",
                   "experience": "2,3", "bogus_key": "x"}
        params = sweep.filters_to_params(filters)
        self.assertIn("location", params)
        self.assertIn("f_TPR", params)
        self.assertIn("f_E", params)
        self.assertNotIn("bogus_key", params)


if __name__ == "__main__":
    unittest.main()
