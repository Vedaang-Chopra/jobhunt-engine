import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from search_strategy.planner import Planner, PlannedQuery, PlannerError
from search_strategy.memory import SearchMemory, QueryRecord
from search_strategy.ontology import Ontology
from search_strategy.vocabulary import VocabularyTracker, VocabHit


class FakeLLM:
    """Mock LLM that returns a fixed response."""
    def __init__(self, response_json):
        self.response_json = response_json
        self.call_count = 0
        self.last_messages = None

    def chat(self, messages, temperature=0.4, max_tokens=4000, clients=None):
        self.call_count += 1
        self.last_messages = messages
        return self.response_json

    def __call__(self, messages, temperature=0.4, max_tokens=4000, clients=None):
        return self.chat(messages, temperature, max_tokens, clients)


class TestPlanner(unittest.TestCase):
    def setUp(self):
        # Set up a temporary JOBHUNT_HOME for isolation
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        # Create the directory structure for job_research/config
        config_src = Path(__file__).resolve().parents[2] / "jobhunt-data" / "job_research" / "config"
        config_dst = self.tmp_path / "job_research" / "config"
        config_dst.mkdir(parents=True)
        # We'll copy the actual config files from the repo to ensure the ontology loads correctly.
        # However, for simplicity and to avoid depending on the exact repo state, we'll create minimal configs.
        # But note: the planner uses the ontology to get domain terms, etc.
        # Let's create minimal configs that are enough for the tests.
        self._create_minimal_config(config_dst)
        # Set environment variable
        self.env_patch = patch.dict('os.environ', {'JOBHUNT_HOME': str(self.tmp_path)})
        self.env_patch.start()

        # Create memory and ontology instances
        self.mem = SearchMemory(root=self.tmp_path / "job_research" / "search_memory")
        self.ontology = Ontology.load(data_root=self.tmp_path)
        self.vocab = VocabularyTracker(root=self.tmp_path / "job_research" / "search_memory")

        # Seed memory with some past queries to show fixation and yield
        self._seed_memory()

        # Seed vocabulary with some terms
        self._seed_vocabulary()

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    def _create_minimal_config(self, config_dst):
        # Create minimal YAML files for the ontology to load
        import yaml
        # role-keywords.yaml
        role_data = {
            "role_families": {
                "agentic-ai": {
                    "name": "Agentic AI",
                    "priority": 1,
                    "primary_keywords": ["agentic", "multi-agent", "langgraph", "langchain", "tool use"],
                    "secondary_keywords": ["autonomous", "reasoning"],
                    "exclude_keywords": ["internship"],
                    "seniority": ["Engineer", "Scientist"],
                    "locations": ["United States", "San Francisco"],
                    "target_companies": ["Anthropic", "Mistral AI"]
                },
                "domain_role": {
                    "name": "Domain Role",
                    "priority": 5,
                    "primary_keywords": ["Software Engineer", "Research Engineer"],
                    "secondary_keywords": ["Developer"],
                    "exclude_keywords": [],
                    "seniority": ["Engineer"],
                    "locations": ["United States"],
                    "target_companies": []
                }
            }
        }
        with (config_dst / "role-keywords.yaml").open("w") as f:
            yaml.dump(role_data, f)

        # target-companies.yaml
        with (config_dst / "target-companies.yaml").open("w") as f:
            yaml.dump({"companies": ["Anthropic", "Mistral AI", "Liquid AI"]}, f)

        # location-preferences.yaml
        with (config_dst / "location-preferences.yaml").open("w") as f:
            yaml.dump({
                "location_tiers": {
                    "Tier 1": {"name": "United States", "cities": ["San Francisco", "New York City", "Seattle"]},
                    "Tier 2": {"name": "Canada", "cities": ["Toronto", "Vancouver"]}
                }
            }, f)

    def _seed_memory(self):
        # Add a few past queries to memory
        now = datetime.now()
        # High yield query for agentic-ai
        self.mem.append(QueryRecord(
            mode="jobs",
            query="Software Engineer agentic",
            family="agentic-ai",
            results_inspected=20,
            relevant_results=15,
            new_results=10,
            duplicate_results=0,
            timestamp=now.isoformat(),
            companies_found=["Anthropic"],
            roles_found=["Software Engineer"]
        ))
        # Medium yield query
        self.mem.append(QueryRecord(
            mode="jobs",
            query="Research Engineer multi-agent",
            family="agentic-ai",
            results_inspected=15,
            relevant_results=8,
            new_results=4,
            duplicate_results=0,
            timestamp=(now - timedelta(days=1)).isoformat(),
            companies_found=["Mistral AI"],
            roles_found=["Research Engineer"]
        ))
        # Low yield query (to trigger broadening)
        self.mem.append(QueryRecord(
            mode="jobs",
            query="Software Engineer at Cohere",
            family="domain_role",
            results_inspected=10,
            relevant_results=2,
            new_results=1,
            duplicate_results=0,
            timestamp=(now - timedelta(days=2)).isoformat(),
            companies_found=["Cohere"],
            roles_found=["Software Engineer"]
        ))

    def _seed_vocabulary(self):
        # Observe some vocabulary terms
        self.vocab.observe([
            VocabHit(term="agent infrastructure", source_query="q1", relevant=True),
            VocabHit(term="agent infrastructure", source_query="q2", relevant=True),
            VocabHit(term="alignment science", source_query="q3", relevant=True),
        ])

    def test_planner_prompt_contains_state(self):
        # Arrange
        fake_llm_response = json.dumps({
            "queries": [
                {
                    "query": "Software Engineer agentic",
                    "family": "agentic-ai",
                    "intent": "Find agentic AI roles",
                    "expected_signals": ["hiring", "open role"],
                    "reject": ["ads", "internship"],
                    "filters": {"geo": "US", "recency": "month"},
                    "rationale": "From ontology",
                    "justification": "on_target_company_list"
                }
            ]
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={})

        # Act
        _ = planner.plan_batch(mode="jobs", state={}, budget=5)

        # Assert
        self.assertEqual(fake_llm.call_count, 1)
        # Check that the prompt contains the state information
        prompt = fake_llm.last_messages[0]["content"]  # assuming the first message is system
        self.assertIn("Recent high yield queries", prompt)
        self.assertIn("Software Engineer agentic", prompt)
        self.assertIn("mode: jobs", prompt.lower())

    def test_diversity_guardrail_drops_near_duplicates(self):
        # Arrange: LLM returns two near-duplicate queries
        fake_llm_response = json.dumps({
            "queries": [
                {
                    "query": "Software Engineer agentic",
                    "family": "agentic-ai",
                    "intent": "Find agentic AI roles",
                    "expected_signals": ["hiring", "open role"],
                    "reject": ["ads", "internship"],
                    "filters": {},
                    "rationale": "test",
                    "justification": ""
                },
                {
                    "query": "Software Engineer agentic systems",
                    "family": "agentic-ai",
                    "intent": "Find agentic AI roles",
                    "expected_signals": ["hiring", "open role"],
                    "reject": ["ads", "internship"],
                    "filters": {},
                    "rationale": "test",
                    "justification": ""
                }
            ]
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={})

        # Act
        queries = planner.plan_batch(mode="jobs", state={}, budget=10)

        # Assert: only one query should remain due to diversity guardrail
        self.assertLessEqual(len(queries), 2)
        # Actually, we expect the diversity guardrail to drop near duplicates, so we expect 1 or 2?
        # The guardrail drops if Jaccard similarity > 0.7. These two queries are very similar.
        # Let's assert that at least one is dropped (so we have less than 2).
        self.assertLess(len(queries), 2, f"Expected near-duplicates to be dropped, got {len(queries)} queries: {[q.query for q in queries]}")

    def test_mix_backfill_from_ontology(self):
        # Arrange: LLM returns only proven-style queries (we'll simulate by returning the same high-yield query)
        fake_llm_response = json.dumps({
            "queries": [
                {
                    "query": "Software Engineer agentic",
                    "family": "agentic-ai",
                    "intent": "Find agentic AI roles",
                    "expected_signals": ["hiring", "open role"],
                    "reject": ["ads", "internship"],
                    "filters": {},
                    "rationale": "proven",
                    "justification": "on_target_company_list"
                }
            ] * 3  # LLM returns 3 proven queries
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={
            "mix_policy": {
                "proven": 0.30,
                "variation": 0.40,
                "exploratory": 0.20,
                "entity_targeted": 0.10
            }
        })

        # Act
        queries = planner.plan_batch(mode="jobs", state={}, budget=10)

        # Assert: we should have more than 3 queries due to backfill for variation, exploratory, entity_targeted
        self.assertGreater(len(queries), 3, f"Expected backfill to add queries, got {len(queries)}")

    def test_broadening_rule_emits_adjacent_title(self):
        # Arrange: We have a low-yield query in memory (from seed: "Software Engineer at Cohere")
        # We want to see if the planner emits a broadened query for the low-yield one.
        # We'll make the LLM return the low-yield query and see if broadening adds an adjacent title.
        fake_llm_response = json.dumps({
            "queries": [
                {
                    "query": "Software Engineer at Cohere",
                    "family": "domain_role",
                    "intent": "Find roles at Cohere",
                    "expected_signals": ["hiring", "open role"],
                    "reject": ["ads", "internship"],
                    "filters": {},
                    "rationale": "low yield",
                    "justification": "unresolved_job_lead"  # we assume this is justified for the test
                }
            ]
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={
            "broaden_after_low_yield": True
        })

        # Act
        queries = planner.plan_batch(mode="jobs", state={}, budget=10)

        # Assert: we should have at least one query with rationale starting with "broaden:"
        broadened = [q for q in queries if q.rationale.startswith("broaden:")]
        self.assertGreaterEqual(len(broadened), 1, f"Expected at least one broadened query, got queries: {[q.rationale for q in queries]}")

    def test_budget_clamp(self):
        # Arrange: LLM returns more queries than the budget
        fake_llm_response = json.dumps({
            "queries": [
                {
                    "query": f"Query {i}",
                    "family": "domain_role",
                    "intent": f"Intent {i}",
                    "expected_signals": [],
                    "reject": [],
                    "filters": {},
                    "rationale": "test",
                    "justification": ""
                }
                for i in range(10)
            ]
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={})

        # Act
        queries = planner.plan_batch(mode="jobs", state={}, budget=5)

        # Assert: exactly 5 queries returned
        self.assertEqual(len(queries), 5, f"Expected 5 queries due to budget clamp, got {len(queries)}")

    def test_feed_mode_returns_empty_or_minimal(self):
        # Arrange: For feed mode, the planner should return empty or minimal plan (as per plan, feed uses a different path)
        fake_llm_response = json.dumps({
            "queries": []
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={})

        # Act
        queries = planner.plan_batch(mode="feed", state={}, budget=5)

        # Assert: empty list
        self.assertEqual(len(queries), 0, f"Feed mode should return empty plan, got {len(queries)} queries")

    def test_malformed_llm_output_raises_PlannerError(self):
        # Arrange: LLM returns malformed JSON
        fake_llm_response = "not json"
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={})

        # Act & Assert
        with self.assertRaises(PlannerError):
            planner.plan_batch(mode="jobs", state={}, budget=5)

    def test_fixation_gate_applied(self):
        # Arrange: We have a query that mentions an entity without justification (e.g., "Software Engineer at Cohere" without justification)
        # We'll seed memory with a query for Cohere but without any justification (so it's seen but not justified)
        # Actually, in our seed memory we have Cohere as a low-yield query, which might be considered justified by yield? 
        # Let's instead test with an entity that is not justified at all.
        # We'll add a query for a company that is not in target list, no hiring signal, low yield, etc.
        # We'll add a query for "SomeRandomCompany" with low yield and no justification.
        # Then we'll see if the planner drops a query for that entity.

        # First, add an unjustified entity query to memory (low yield, no target, no hiring signal, low historical yield)
        now = datetime.now()
        self.mem.append(QueryRecord(
            mode="jobs",
            query="Software Engineer at SomeRandomCompany",
            family="domain_role",
            results_inspected=20,
            relevant_results=2,
            new_results=0,
            duplicate_results=0,
            timestamp=now.isoformat(),
            companies_found=["SomeRandomCompany"],
            roles_found=["Software Engineer"]
        ))

        # Now, we make the LLM return a query for that entity without justification
        fake_llm_response = json.dumps({
            "queries": [
                {
                    "query": "Software Engineer at SomeRandomCompany",
                    "family": "domain_role",
                    "intent": "Find roles at SomeRandomCompany",
                    "expected_signals": ["hiring", "open role"],
                    "reject": ["ads", "internship"],
                    "filters": {},
                    "rationale": "test",
                    "justification": ""  # no justification
                }
            ]
        })
        fake_llm = FakeLLM(fake_llm_response)
        planner = Planner(llm=fake_llm, onto=self.ontology, mem=self.mem, policy={})

        # Act
        queries = planner.plan_batch(mode="jobs", state={}, budget=10)

        # Assert: the query should be dropped by the fixation gate
        self.assertEqual(len(queries), 0, f"Expected fixation gate to drop unjustified entity query, got {len(queries)} queries")


if __name__ == '__main__':
    unittest.main()