import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
import csv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from search_strategy.fixation import (
    ENTITY_JUSTIFICATIONS,
    entity_search_allowed,
    filter_planned_queries,
)
from search_strategy.memory import SearchMemory, QueryRecord


def make_mem_with_companies_seen(companies):
    """Helper: seed memory with past queries containing the company names."""
    # Set JOBHUNT_HOME to temporary directory for clean test environment
    old_env = os.environ.get("JOBHUNT_HOME")
    os.environ["JOBHUNT_HOME"] = str(Path(tempfile.mkdtemp()))
    try:
        mem = SearchMemory(root=Path(os.environ["JOBHUNT_HOME"]))
        # Create necessary directory structure
        (mem.path.parent.parent.parent / "tracking" / "jobs").mkdir(parents=True, exist_ok=True)
        (mem.path.parent.parent.parent / "tracking" / "hiring_posts").mkdir(parents=True, exist_ok=True)
        (mem.path.parent.parent.parent / "job_research" / "config").mkdir(parents=True, exist_ok=True)
        # Create empty CSV files with headers
        jobs_csv = mem.path.parent.parent.parent / "tracking" / "jobs" / "jobs.csv"
        if not jobs_csv.exists():
            with open(jobs_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "date", "company", "title", "location", "compensation", 
                    "status", "priority_v2", "notes"
                ])
                writer.writeheader()
        hiring_posts_csv = mem.path.parent.parent.parent / "tracking" / "hiring_posts" / "hiring_posts.csv"
        if not hiring_posts_csv.exists():
            with open(hiring_posts_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "discovered_date", "company", "title", "location", 
                    "status", "notes"
                ])
                writer.writeheader()
        # Create minimal config files for ontology (if needed)
        # For now, we'll rely on the ontology stub in tests
        for i, company in enumerate(companies):
            # Each query: "Some role at {company}" -> entity appears in query text
            # Also set companies_found to indicate this company was seen in results
            mem.append(
                QueryRecord(
                    mode="jobs",
                    query=f"Software Engineer at {company}",
                    family="domain_role",
                    results_inspected=10,
                    relevant_results=5,
                    new_results=2,
                    duplicate_results=0,
                    timestamp=datetime.now().isoformat(),
                    companies_found=[company],  # Indicate this company was seen in results
                )
            )
        return mem
    finally:
        if old_env is not None:
            os.environ["JOBHUNT_HOME"] = old_env
        else:
            os.environ.pop("JOBHUNT_HOME", None)


def make_mem_with_target_list():
    """Helper: seed memory with target company list via on_target_list justification."""
    old_env = os.environ.get("JOBHUNT_HOME")
    os.environ["JOBHUNT_HOME"] = str(Path(tempfile.mkdtemp()))
    try:
        mem = SearchMemory(root=Path(os.environ["JOBHUNT_HOME"]))
        # Create necessary directory structure
        (mem.path.parent.parent.parent / "tracking" / "jobs").mkdir(parents=True, exist_ok=True)
        (mem.path.parent.parent.parent / "tracking" / "hiring_posts").mkdir(parents=True, exist_ok=True)
        (mem.path.parent.parent.parent / "job_research" / "config").mkdir(parents=True, exist_ok=True)
        # Create empty CSV files with headers
        jobs_csv = mem.path.parent.parent.parent / "tracking" / "jobs" / "jobs.csv"
        if not jobs_csv.exists():
            with open(jobs_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "date", "company", "title", "location", "compensation", 
                    "status", "priority_v2", "notes"
                ])
                writer.writeheader()
        hiring_posts_csv = mem.path.parent.parent.parent / "tracking" / "hiring_posts" / "hiring_posts.csv"
        if not hiring_posts_csv.exists():
            with open(hiring_posts_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "discovered_date", "company", "title", "location", 
                    "status", "notes"
                ])
                writer.writeheader()
        # Create target-companies.yaml with Anthropic
        import yaml
        config_dir = mem.path.parent.parent.parent / "job_research" / "config"
        target_companies_file = config_dir / "target-companies.yaml"
        target_companies_data = {"companies": [{"name": "Anthropic"}, {"name": "OpenAI"}]}
        with open(target_companies_file, 'w') as f:
            yaml.dump(target_companies_data, f)
        return mem
    finally:
        if old_env is not None:
            os.environ["JOBHUNT_HOME"] = old_env
        else:
            os.environ.pop("JOBHUNT_HOME", None)


class TestFixationGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Set JOBHUNT_HOME to temporary directory for clean test environment
        self.old_env = os.environ.get("JOBHUNT_HOME")
        os.environ["JOBHUNT_HOME"] = str(self.tmp.name)
        self.mem = SearchMemory(root=Path(self.tmp.name))
        # Create necessary directory structure
        (self.mem.path.parent.parent.parent / "tracking" / "jobs").mkdir(parents=True, exist_ok=True)
        (self.mem.path.parent.parent.parent / "tracking" / "hiring_posts").mkdir(parents=True, exist_ok=True)
        (self.mem.path.parent.parent.parent / "job_research" / "config").mkdir(parents=True, exist_ok=True)
        # Create empty CSV files with headers
        jobs_csv = self.mem.path.parent.parent.parent / "tracking" / "jobs" / "jobs.csv"
        if not jobs_csv.exists():
            with open(jobs_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "date", "company", "title", "location", "compensation", 
                    "status", "priority_v2", "notes"
                ])
                writer.writeheader()
        hiring_posts_csv = self.mem.path.parent.parent.parent / "tracking" / "hiring_posts" / "hiring_posts.csv"
        if not hiring_posts_csv.exists():
            with open(hiring_posts_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "discovered_date", "company", "title", "location", 
                    "status", "notes"
                ])
                writer.writeheader()
        # Minimal ontology stub
        class OntologyStub:
            def target_companies(self):
                return ["Anthropic", "OpenAI"]
            def domain_terms(self, fam):
                return []
            def role_families(self):
                return {}
        self.onto = OntologyStub()

    def tearDown(self):
        if self.old_env is not None:
            os.environ["JOBHUNT_HOME"] = self.old_env
        else:
            os.environ.pop("JOBHUNT_HOME", None)
        self.tmp.cleanup()

    def test_entity_justifications_constant(self):
        expected = {
            "on_target_company_list",
            "recent_hiring_signal",
            "newly_discovered_relevant_team",
            "known_referral_opportunity",
            "unresolved_job_lead",
            "explicit_user_instruction",
            "high_historical_query_yield",
        }
        self.assertEqual(set(ENTITY_JUSTIFICATIONS), expected)

    def test_on_target_company_list_allows(self):
        # Ensure target company list includes Anthropic (from ontology stub)
        allowed, why = entity_search_allowed("Anthropic", self.mem, self.onto)
        self.assertTrue(allowed)
        self.assertEqual(why, "on_target_company_list")

    def test_non_target_company_blocks_without_other_justification(self):
        allowed, why = entity_search_allowed("Cohere", self.mem, self.onto)
        self.assertFalse(allowed)
        self.assertEqual(why, "")  # we return empty string when not allowed

    def test_high_historical_yield_allows(self):
        # Seed memory with queries for Cohere that have high yield
        for _ in range(3):
            self.mem.append(
                QueryRecord(
                    mode="jobs",
                    query="Cohere research engineer",
                    family="domain_role",
                    results_inspected=10,
                    relevant_results=5,  # average 5 >=3 threshold
                    new_results=2,
                    duplicate_results=0,
                    timestamp=datetime.now().isoformat(),
                )
            )
        allowed, why = entity_search_allowed("Cohere", self.mem, self.onto)
        self.assertTrue(allowed)
        self.assertEqual(why, "high_historical_query_yield")

    def test_filter_planned_queries_drops_unjustified_entity(self):
        # First, seed memory with companies_seen so that Cohere is considered an entity from prior results
        mem_seeded = make_mem_with_companies_seen(["Georgia Tech", "Cohere", "Together AI"])
        planned = [
            {
                "query": "Cohere machine learning engineer",
                "family": "domain_role",
                "intent": "find engineers at Cohere",
                "expected_signals": ["hiring"],
                "reject": ["ads"],
                "filters": {},
                "rationale": "",
                "notes": "",
            },
            {
                "query": "Software Engineer at Anthropic",
                "family": "domain_role",
                "intent": "find engineers at Anthropic (target company)",
                "expected_signals": ["hiring"],
                "reject": ["ads"],
                "filters": {},
                "rationale": "",
                "notes": "",
            },
            {
                "query": "random query",
                "family": "other",
                "intent": "",
                "expected_signals": [],
                "reject": [],
                "filters": {},
                "rationale": "",
                "notes": "",
            },
        ]
        filtered = filter_planned_queries(planned, mem_seeded, self.onto)
        # Cohere query should be dropped (seen in prior results, no justification), Anthropic kept (not seen in prior results as entity), random kept.
        self.assertEqual(len(filtered), 2)
        queries_left = [q["query"] for q in filtered]
        self.assertIn("Software Engineer at Anthropic", queries_left)
        self.assertIn("random query", queries_left)
        self.assertNotIn("Cohere machine learning engineer", queries_left)
        # Check that the kept queries' notes are unchanged
        for q in filtered:
            if q["query"] == "Software Engineer at Anthropic":
                self.assertEqual(q["notes"], "")

    def test_filter_planned_queries_sets_notes_on_drop(self):
        # Seed memory so that Cohere is considered an entity from prior results
        mem_seeded = make_mem_with_companies_seen(["Cohere"])
        planned = [
            {
                "query": "Cohere machine learning engineer",
                "family": "domain_role",
                "intent": "find engineers at Cohere",
                "expected_signals": ["hiring"],
                "reject": ["ads"],
                "filters": {},
                "rationale": "",
                "notes": "original notes",
            },
        ]
        filtered = filter_planned_queries(planned, mem_seeded, self.onto)
        # The original should be unchanged
        self.assertEqual(planned[0]["notes"], "original notes")
        # The returned list should be empty (all dropped)
        self.assertEqual(len(filtered), 0)

    def test_filter_planned_queries_keeps_justified_entity(self):
        # Seed memory so that Cohere is considered an entity from prior results
        mem_seeded = make_mem_with_companies_seen(["Cohere"])
        # But we need to make Anthropic justified - it's justified by being in target companies list
        # However, for the query "Software Engineer at Anthropic", the primary token is "software"
        # which is not seen in prior results, so it should be kept regardless
        planned = [
            {
                "query": "Software Engineer at Anthropic",
                "family": "domain_role",
                "intent": "find engineers at Anthropic (target company)",
                "expected_signals": ["hiring"],
                "reject": ["ads"],
                "filters": {},
                "rationale": "",
                "notes": "original notes",
            },
        ]
        filtered = filter_planned_queries(planned, mem_seeded, self.onto)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["query"], "Software Engineer at Anthropic")
        self.assertEqual(filtered[0]["notes"], "original notes")


if __name__ == "__main__":
    unittest.main()