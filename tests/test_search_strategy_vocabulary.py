"""Tests for search_strategy.vocabulary — candidate-vocabulary learning with promotion gate.

Task 6 of the LinkedIn adaptive search strategy plan. All tests use temp dirs.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from search_strategy.vocabulary import (  # noqa: E402
    VocabHit,
    VocabularyTracker,
    NotPromotable,
    extract_candidate_terms,
)

HEADER = (
    "term,source_query,first_seen,last_seen,frequency,"
    "relevance_hits,successful_searches,confidence,status"
)


class VocabularyTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.vt = VocabularyTracker(self.root)

    # -- helpers ---------------------------------------------------------
    def observe_term(self, term, queries, relevant=True):
        """Observe one term across a list of source queries."""
        self.vt.observe(
            [VocabHit(term=term, source_query=q, relevant=relevant) for q in queries]
        )


class TestPersistenceAndUpsert(VocabularyTestBase):
    def test_csv_created_with_exact_header(self):
        self.observe_term("agent infrastructure", ["q1"])
        csv_path = self.root / "job_research" / "search_memory" / "candidate_vocabulary.csv"
        self.assertTrue(csv_path.exists())
        with open(csv_path) as fh:
            self.assertEqual(fh.readline().strip(), HEADER)

    def test_observe_upserts_case_insensitive(self):
        self.vt.observe([VocabHit(term="Agent Infrastructure", source_query="q1", relevant=False)])
        self.vt.observe([VocabHit(term="agent infrastructure", source_query="q1", relevant=False)])
        rows = self.vt.lookup("AGENT INFRASTRUCTURE")
        self.assertEqual(rows["term"], "agent infrastructure")  # canonical lowercase
        self.assertEqual(rows["frequency"], 2)
        # only one row on disk
        with open(self.root / "job_research" / "search_memory" / "candidate_vocabulary.csv") as fh:
            self.assertEqual(len(fh.readlines()), 2)  # header + 1 row

    def test_observe_increments_frequency_and_relevance(self):
        self.observe_term("agent infrastructure", ["q1"])
        self.observe_term("agent infrastructure", ["q2", "q3"])
        row = self.vt.lookup("agent infrastructure")
        self.assertEqual(row["frequency"], 3)
        self.assertEqual(row["relevance_hits"], 3)

    def test_irrelevant_hits_do_not_count_relevance(self):
        self.observe_term("junk term", ["q1", "q2", "q3"], relevant=False)
        row = self.vt.lookup("junk term")
        self.assertEqual(row["frequency"], 3)
        self.assertEqual(row["relevance_hits"], 0)

    def test_first_seen_stable_last_seen_updates(self):
        self.observe_term("agent infra", ["q1"])
        first = self.vt.lookup("agent infra")
        self.vt.observe([VocabHit(term="agent infra", source_query="q1", relevant=True)])
        second = self.vt.lookup("agent infra")
        self.assertTrue(first["first_seen"])          # ISO timestamp present
        self.assertEqual(first["first_seen"], second["first_seen"])
        self.assertGreaterEqual(second["last_seen"], first["first_seen"])

    def test_roundtrip_across_tracker_instances(self):
        self.observe_term("post training evals", ["q1"])
        vt2 = VocabularyTracker(self.root)
        self.assertEqual(vt2.lookup("post training evals")["frequency"], 1)


class TestConfidenceRuleTable(VocabularyTestBase):
    """confidence = min(1.0, (relevance_hits>=2 ? 0.8 : 0.4)
                           + (distinct_source_queries>=2 ? 0.2 : 0))
    Four cells: 0.4 / 0.6 / 0.8 / 1.0."""

    def confidence_for(self, n_relevant_queries):
        term = "conf term"
        self.observe_term(term, [f"q{i}" for i in range(n_relevant_queries)])
        return float(self.vt.lookup(term)["confidence"])

    def test_one_hit_one_source_is_040(self):
        self.assertAlmostEqual(self.confidence_for(1), 0.4)

    def test_low_relevance_many_sources_is_060(self):
        # relevance_hits=1 (<2 => 0.4 base) but >=2 distinct sources (+0.2)
        self.vt.observe([
            VocabHit(term="weak term", source_query="q1", relevant=True),
            VocabHit(term="weak term", source_query="q2", relevant=False),
        ])
        self.assertAlmostEqual(float(self.vt.lookup("weak term")["confidence"]), 0.6)

    def test_two_relevant_hits_two_sources_is_100(self):
        self.assertAlmostEqual(self.confidence_for(2), 1.0)

    def test_confidence_capped_at_10(self):
        self.observe_term("hot term", [f"q{i}" for i in range(7)])
        self.assertAlmostEqual(float(self.vt.lookup("hot term")["confidence"]), 1.0)


class TestPromotionGate(VocabularyTestBase):
    def test_default_status_observed(self):
        self.observe_term("new term", ["q1"])
        self.assertEqual(self.vt.lookup("new term")["status"], "observed")

    def test_promote_raises_below_gate(self):
        # 1 relevance hit, 1 source: conf 0.4, rel 1 → both conditions fail
        self.observe_term("weak term", ["q1"])
        with self.assertRaises(NotPromotable):
            self.vt.promote("weak term")
        self.assertEqual(self.vt.lookup("weak term")["status"], "observed")

    def test_promote_raises_with_high_confidence_but_one_relevance_hit(self):
        # conf 0.6 < 0.7 anyway; force-check gate needs BOTH conditions:
        # single relevant hit can't reach conf >= 0.7, so also test via direct
        # CSV seeding that confidence alone is insufficient.
        self.vt._upsert_row({  # noqa: SLF001 - seed edge case directly
            "term": "edge term", "source_query": "q1",
            "frequency": "5", "relevance_hits": "1",
            "successful_searches": "0", "confidence": "0.9", "status": "observed",
        })
        with self.assertRaises(NotPromotable):
            self.vt.promote("edge term")

    def test_promote_succeeds_at_gate(self):
        self.observe_term("strong term", ["q1", "q2"])  # conf 1.0, rel 2
        self.vt.promote("strong term")
        self.assertEqual(self.vt.lookup("strong term")["status"], "promoted")

    def test_promote_case_insensitive_lookup(self):
        self.observe_term("Strong Term", ["q1", "q2"])
        self.vt.promote("STRONG TERM")
        self.assertEqual(self.vt.lookup("strong term")["status"], "promoted")

    def test_unknown_term_raises(self):
        with self.assertRaises(KeyError):
            self.vt.promote("never seen")


class TestRejectAndPool(VocabularyTestBase):
    def test_pool_only_contains_promoted(self):
        self.observe_term("pool term a", ["q1", "q2"])
        self.observe_term("observed only", ["q1"])
        self.vt.promote("pool term a")
        pool = self.vt.pool()
        self.assertIn("pool term a", pool)
        self.assertNotIn("observed only", pool)

    def test_rejected_is_terminal_and_excluded_from_pool(self):
        self.observe_term("doomed term", ["q1", "q2"])
        self.vt.reject("doomed term")
        self.assertEqual(self.vt.lookup("doomed term")["status"], "rejected")
        # even though it would pass the promotion gate
        with self.assertRaises(NotPromotable):
            self.vt.promote("doomed term")
        # further observation does not resurrect it
        self.observe_term("doomed term", ["q3", "q4"])
        self.assertNotIn("doomed term", self.vt.pool())
        self.assertNotIn("doomed term", self.vt.promoted())

    def test_promoted_listing_matches_pool(self):
        self.observe_term("listed term", ["q1", "q2"])
        self.vt.promote("listed term")
        self.assertEqual(self.vt.promoted(), ["listed term"])


class TestExtractCandidateTerms(unittest.TestCase):
    def test_drops_stopwords_and_generic_tokens(self):
        out = extract_candidate_terms(["Senior Research Engineer at a company"])
        for t in out:
            tokens = t.split()
            self.assertFalse(all(tok in extract_candidate_terms.GENERIC_TOKENS
                                 or tok in extract_candidate_terms.STOPWORDS
                                 for tok in tokens))

    def test_unigram_non_generic_kept(self):
        out = extract_candidate_terms(["Post-Training RL Engineer"])
        self.assertIn("post-training", out)
        self.assertIn("rl", out)  # non-generic unigram survives

    def test_bigram_requires_non_generic_token(self):
        out = extract_candidate_terms(["machine learning engineer"])
        self.assertIn("machine learning", out)
        self.assertNotIn("learning engineer", out)  # hmm: contains 'machine'? no.
        # 'engineer' is generic; 'learning' generic too -> bigram dropped

    def test_dedupe_and_ordering_freq_desc_then_alpha(self):
        texts = [
            "agentic workflows engineer",
            "agentic workflows engineer",
            "compiler kernels role",
            "agentic workflows engineer",
        ]
        out = extract_candidate_terms(texts)
        # freq-3 candidates first, alphabetical within equal frequency;
        # then freq-1 candidates in alphabetical order
        expected = [
            'agentic', 'agentic workflows', 'workflows', 'workflows engineer',
            'compiler', 'compiler kernels', 'kernels'
        ]
        self.assertEqual(out, expected)

    def test_deterministic(self):
        texts = ["inference optimization lead", "gpu kernel specialist"]
        self.assertEqual(extract_candidate_terms(texts),
                         extract_candidate_terms(texts))

    def test_empty_input(self):
        self.assertEqual(extract_candidate_terms([]), [])
        self.assertEqual(extract_candidate_terms(["", "   ", "!!!"]), [])

    def test_custom_stopword_path_extends_builtin(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("kernel\n")
            path = fh.name
        try:
            out = extract_candidate_terms(["gpu kernel specialist"],
                                          stopword_path=Path(path))
            self.assertNotIn("kernel", out)
            self.assertIn("gpu", out)
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
