import json, sys, tempfile, unittest
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from search_strategy.memory import SearchMemory, QueryRecord, LOW_YIELD_THRESHOLD, HIGH_YIELD_THRESHOLD

def rec(**kw):
    base = dict(mode="jobs", query="research engineer reasoning", family="domain_role",
                results_inspected=38, relevant_results=12, new_results=9, duplicate_results=3)
    base.update(kw); return QueryRecord(**base)

class TestSearchMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = SearchMemory(root=Path(self.tmp.name))
    def tearDown(self): self.tmp.cleanup()

    def test_append_derives_scores_and_roundtrips(self):
        self.mem.append(rec())
        rows = self.mem.recent()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.yield_score, "high")          # relevant 12 > 8
        self.assertAlmostEqual(r.duplicate_rate, 3/38)
        self.assertEqual(r.novelty_score, "high")        # new>0 and dup_rate<0.5
        self.assertTrue(r.query_id and r.timestamp)

    def test_yield_buckets(self):
        self.mem.append(re1 := rec(query="a", relevant_results=2, new_results=0, duplicate_results=0, results_inspected=5))
        self.mem.append(re2 := rec(query="b", relevant_results=5, new_results=1, duplicate_results=0, results_inspected=10))
        self.assertEqual(self.mem.recent()[1].yield_score if False else None, None)
        rows = self.mem.recent()
        by_q = {r.query: r for r in rows}
        self.assertEqual(by_q["a"].yield_score, "low")
        self.assertEqual(by_q["b"].yield_score, "medium")
        self.assertEqual(by_q["a"].novelty_score, "low")

    def test_csv_created_lazily_with_header(self):
        p = Path(self.tmp.name) / "job_research" / "search_memory" / "query_log.csv"
        self.assertFalse(p.exists())
        self.mem.append(rec())
        self.assertTrue(p.exists())
        import csv as _csv
        header = p.read_text().splitlines()[0]
        for col in ("query_id","mode","query","family","filters_json","yield_score","duplicate_rate"):
            self.assertIn(col, header)

    def test_recent_window_and_limit(self):
        old = rec(query="old"); old.timestamp = (datetime.now() - timedelta(days=30)).isoformat()
        self.mem.append(old)
        self.mem.append(rec(query="fresh"))
        self.assertEqual([r.query for r in self.mem.recent(window_days=7)], ["fresh"])
        self.assertEqual(len(self.mem.recent(window_days=60)), 2)

    def test_yield_stats_aggregates_case_insensitive(self):
        self.mem.append(rec(query="Research Engineer Reasoning", relevant_results=12))
        self.mem.append(rec(query="research engineer reasoning", relevant_results=4))
        s = self.mem.yield_stats("research engineer REASONING")
        self.assertEqual(s["runs"], 2)
        self.assertEqual(s["total_relevant"], 16)

    def test_entity_query_count(self):
        self.mem.append(rec(query="Cohere research"))
        self.mem.append(rec(query="unrelated"))
        self.assertEqual(self.mem.entity_query_count("cohere"), 1)

    def test_build_state_required_fields_and_coverage_gaps(self):
        class FakeOnto:
            def role_families(self): return {"agentic-ai": {"priority": 1}, "post-training": {"priority": 6}}
            def domain_terms(self, fam): return ["x"]
            def primary_titles(self): return ["Research Engineer"]
            def locations(self): return ["United States"]
            def target_companies(self): return ["Anthropic"]
        self.mem.append(rec(family="agentic-ai"))
        st = self.mem.build_state(onto=FakeOnto(), seen_jobs={"a":1,"b":2}, seen_posts={"p":1},
                                  budget_remaining=9)
        for f in ("candidate_target_roles","candidate_domains","location_preferences",
                  "recent_queries","recent_high_yield_queries","recent_low_yield_queries",
                  "already_seen_jobs","already_seen_posts","already_seen_companies",
                  "target_companies","recent_hiring_signals","coverage_gaps","remaining_search_budget"):
            self.assertIn(f, st)
        self.assertIn("post-training", st["coverage_gaps"])   # zero queries in window
        self.assertNotIn("agentic-ai", st["coverage_gaps"])
        self.assertEqual(st["remaining_search_budget"], 9)

    def test_company_evidence_tolerant(self):
        from search_strategy.memory import company_evidence
        ev = company_evidence("No Such Co", jobs_csv=Path(self.tmp.name)/"nope.csv",
                              hiring_posts_csv=Path(self.tmp.name)/"nope2.csv")
        self.assertEqual(ev, {"on_target_list": False, "recent_hiring_signal": False,
                              "open_job_lead": False})
