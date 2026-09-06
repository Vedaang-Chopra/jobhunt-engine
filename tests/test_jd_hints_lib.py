"""TDD tests for scripts/jd_hints_lib.py — JD intelligence hint extraction (Task 2).

Pure regex/string extraction of "right people" hints from a job description:
team name, hiring-manager hints, recruiter hints, title keywords, and technical
domain terms. Plus the thin LLM contract wrapper (no network in tests).
"""

import asyncio
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import jd_hints_lib  # noqa: E402

EMPTY_HINTS = {
    "team": None,
    "manager_hints": [],
    "recruiter_hints": [],
    "keywords": [],
    "domain_terms": [],
}

FIXTURE_JD = """
Senior ML Engineer — Agentic AI Platform

Northwind Labs is building the next generation of LLM evaluation tooling.
You will join our Applied AI team to ship agentic AI systems for enterprise
customers. We design RAG pipelines, VLM routing, and fine-tuning of
foundation models on multimodal data.
Responsibilities: build embeddings, own inference infrastructure, run RLHF
experiments, and mature our MLOps practice.
Reports to the Engineering Manager for Agent Platform.
Hiring manager: Priya Raghavan
Recruiter: jane (jane@northwindlabs.com)
We are also recruiting a Research Scientist and a Data Scientist.
"""


class TestExtractJDHints(unittest.TestCase):
    def test_realistic_jd_team(self):
        hints = jd_hints_lib.extract_jd_hints(FIXTURE_JD)
        self.assertEqual(hints["team"], "Applied AI")

    def test_realistic_jd_manager_hints(self):
        hints = jd_hints_lib.extract_jd_hints(FIXTURE_JD)
        # Name after "Hiring manager:" plus the seniority role after
        # "Reports to the" — in order of appearance, deduplicated.
        self.assertEqual(hints["manager_hints"], ["Engineering Manager", "Priya Raghavan"])

    def test_realistic_jd_recruiter_hints(self):
        hints = jd_hints_lib.extract_jd_hints(FIXTURE_JD)
        self.assertEqual(hints["recruiter_hints"], ["jane", "recruiting"])

    def test_realistic_jd_keywords(self):
        hints = jd_hints_lib.extract_jd_hints(FIXTURE_JD)
        self.assertEqual(
            hints["keywords"],
            ["ML Engineer", "Research Scientist", "Data Scientist", "Engineering Manager"],
        )

    def test_realistic_jd_domain_terms(self):
        hints = jd_hints_lib.extract_jd_hints(FIXTURE_JD)
        self.assertEqual(
            hints["domain_terms"],
            [
                "agentic AI",
                "LLM",
                "evaluation",
                "VLM",
                "routing",
                "fine-tuning",
                "RLHF",
                "RAG",
                "inference",
                "multimodal",
                "foundation models",
                "embeddings",
                "MLOps",
            ],
        )

    def test_realistic_jd_result_keys(self):
        hints = jd_hints_lib.extract_jd_hints(FIXTURE_JD)
        self.assertEqual(
            set(hints.keys()),
            {"team", "manager_hints", "recruiter_hints", "keywords", "domain_terms"},
        )

    def test_empty_text(self):
        self.assertEqual(jd_hints_lib.extract_jd_hints(""), EMPTY_HINTS)

    def test_none_text(self):
        self.assertEqual(jd_hints_lib.extract_jd_hints(None), EMPTY_HINTS)

    def test_no_matches_text(self):
        hints = jd_hints_lib.extract_jd_hints(
            "We sell widgets. Our sales team travels a lot. Bring a positive attitude."
        )
        self.assertEqual(hints, EMPTY_HINTS)

    def test_team_via_colon_pattern(self):
        hints = jd_hints_lib.extract_jd_hints("We are hiring. Team: Agent Platform.\nApply now.")
        self.assertEqual(hints["team"], "Agent Platform")

    def test_manager_seniority_fallback_without_names(self):
        text = (
            "You will partner with the Director of Platform and report to the "
            "Head of AI Infrastructure."
        )
        hints = jd_hints_lib.extract_jd_hints(text)
        self.assertEqual(hints["manager_hints"], ["Director", "Head of"])

    def test_recruiter_via_talent_acquisition(self):
        hints = jd_hints_lib.extract_jd_hints(
            "Our talent acquisition partner will guide you through the process."
        )
        self.assertEqual(hints["recruiter_hints"], ["talent acquisition"])

    def test_keywords_order_follows_fixed_list(self):
        text = "Roles: Data Scientist, AI Engineer, Software Engineer, and Applied Scientist."
        hints = jd_hints_lib.extract_jd_hints(text)
        self.assertEqual(
            hints["keywords"],
            ["Software Engineer", "Applied Scientist", "Data Scientist", "AI Engineer"],
        )

    def test_domain_terms_canonical_casing(self):
        hints = jd_hints_lib.extract_jd_hints("we use llms, rags and do rlhf work")
        self.assertEqual(hints["domain_terms"], ["LLM", "RLHF", "RAG"])


class TestLLMJDHints(unittest.TestCase):
    def test_llm_output_wins_on_non_empty_fields(self):
        def fake_llm_call(_text):
            return {"team": "Agent Platform"}

        hints = jd_hints_lib.llm_jd_hints(FIXTURE_JD, fake_llm_call)
        self.assertEqual(hints["team"], "Agent Platform")
        # Non-overridden fields pass through from the regex extraction.
        self.assertEqual(
            hints["manager_hints"], ["Engineering Manager", "Priya Raghavan"]
        )
        self.assertEqual(hints["keywords"][0], "ML Engineer")

    def test_llm_empty_fields_do_not_override(self):
        def fake_llm_call(_text):
            return {"team": "", "manager_hints": [], "keywords": None}

        hints = jd_hints_lib.llm_jd_hints(FIXTURE_JD, fake_llm_call)
        self.assertEqual(hints["team"], "Applied AI")
        self.assertEqual(
            hints["manager_hints"], ["Engineering Manager", "Priya Raghavan"]
        )

    def test_llm_json_string_output(self):
        def fake_llm_call(_text):
            return '{"team": "Agent Platform"}'

        hints = jd_hints_lib.llm_jd_hints(FIXTURE_JD, fake_llm_call)
        self.assertEqual(hints["team"], "Agent Platform")

    def test_llm_async_call(self):
        async def fake_llm_call(_text):
            return {"team": "Agent Platform"}

        hints = jd_hints_lib.llm_jd_hints(FIXTURE_JD, fake_llm_call)
        self.assertEqual(hints["team"], "Agent Platform")

    def test_llm_none_result_returns_regex_hints(self):
        def fake_llm_call(_text):
            return None

        hints = jd_hints_lib.llm_jd_hints(FIXTURE_JD, fake_llm_call)
        self.assertEqual(hints["team"], "Applied AI")
        self.assertEqual(hints["recruiter_hints"], ["jane", "recruiting"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
