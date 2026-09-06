"""Tests for scripts/generate_cover_letter.py — Task 2 Part B (TDD).

Contract:
- generate_cover_letter(job_id, fact_bank_path, research_path=None) -> LaTeX text
- <=250 words, 4 paragraphs, banned-term ValueError, fact-bank-only claims,
  JD-only fallback paragraph 3 without research_path.
"""
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from generate_cover_letter import (  # noqa: E402
    BANNED_TERMS,
    claims_from_bank,
    compile_cover_letter,
    count_words,
    find_jd_for_job,
    generate_cover_letter,
)

REPO_ROOT = REPO
from scripts import config_lib  # noqa: F401  (kept for parity with other suites)

# Personal fact bank is gitignored; resolve against the repo-local data root
# and skip the whole module on a fresh clone where it has never been created.
FACT_BANK = (
    REPO_ROOT / "jobhunt-data" / "profile_info" / "resume_fact_bank.yaml"
)
CROWDSTRIKE_JOB_ID = "crowdstrike_ai_research_scientist_agentic_systems_remote_4425331670"

try:
    import pytest as _pytest
    if not FACT_BANK.exists():
        _pytest.skip(
            "fresh clone: personal resume fact bank not found at "
            f"{FACT_BANK} (gitignored profile data; these tests need it)",
            allow_module_level=True,
        )
except ImportError:
    pass

# ACTIVE_JD_DIR is resolved through data_root() at import time, which is
# polluted by ambient $JOBHUNT_HOME during collection. Re-point it at the
# repo-local shipped tracking dir so the module is deterministic here.
import generate_cover_letter as _gcl  # noqa: E402

_gcl.ACTIVE_JD_DIR = (
    REPO_ROOT / "jobhunt-data" / "tracking" / "job_descriptions" / "active"
)


def latex_visible_words(tex: str) -> str:
    """Strip LaTeX preamble/comments/commands to approximate rendered words."""
    body = tex.split(r"\begin{document}", 1)[-1]
    body = re.sub(r"%.*", "", body)
    body = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})*", " ", body)
    body = body.replace("{", " ").replace("}", " ").replace("~", " ")
    return body


class TestWordCount(unittest.TestCase):
    def test_generated_letter_is_four_paragraphs_and_under_250_words(self):
        tex = generate_cover_letter(CROWDSTRIKE_JOB_ID, FACT_BANK)
        paras = re.findall(r"\\letterPara\{(.*?)\}\n\n", tex, flags=re.DOTALL)
        self.assertEqual(len(paras), 4, "must be exactly 4 paragraphs")
        n = count_words(latex_visible_words(tex))
        self.assertLessEqual(n, 250, f"word count {n} exceeds 250")


class TestBannedTerms(unittest.TestCase):
    def test_banned_term_raises_value_error_listing_hits(self):
        from generate_cover_letter import enforce_banned_terms
        with self.assertRaises(ValueError) as ctx:
            enforce_banned_terms("My work spans RLHF fine-tuning and reward models")
        msg = str(ctx.exception).lower()
        self.assertIn("rlhf", msg)

    def test_research_path_with_banned_term_is_rejected(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("Company does lots of DPO and SFT internally.\n")
            bad_research = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                generate_cover_letter(CROWDSTRIKE_JOB_ID, FACT_BANK,
                                      research_path=bad_research)
        finally:
            bad_research.unlink()

    def test_clean_generation_does_not_contain_banned_terms(self):
        tex = generate_cover_letter(CROWDSTRIKE_JOB_ID, FACT_BANK)
        low = tex.lower()
        for term in BANNED_TERMS:
            hits = re.findall(term.pattern, low)
            self.assertEqual(hits, [], f"banned term {term!r} found")


class TestFactBankOnly(unittest.TestCase):
    def test_planted_fake_claim_raises(self):
        fake = "cut detection latency by 87% across 40 sensors"
        with self.assertRaises(ValueError):
            claims_from_bank([fake], FACT_BANK.read_text())

    def test_verified_metric_passes(self):
        bank_text = FACT_BANK.read_text()
        claims_from_bank(["reduced mean resolution time ~70%"], bank_text)

    def test_generated_letter_claims_are_from_bank(self):
        tex = generate_cover_letter(CROWDSTRIKE_JOB_ID, FACT_BANK)
        # Extract numeric/metric phrases from visible text and verify each.
        visible = latex_visible_words(tex)
        metrics = re.findall(
            r"[~+]?\d[\d,.]*\s*(?:%|GB|TB|events|sessions|tests|modules|nodes|"
            r"backends|papers)?"
            r"(?:\s*(?:per day|fewer|faster|improvement))?",
            visible,
        )
        metrics = [m.strip() for m in metrics if len(m.strip()) > 2]
        self.assertTrue(metrics)
        claims_from_bank(metrics, FACT_BANK.read_text() + _jd_text())


def _jd_text():
    jd = find_jd_for_job(CROWDSTRIKE_JOB_ID)
    return "\n" + jd.read_text()


class TestFallbackWithoutResearch(unittest.TestCase):
    def test_paragraph3_is_jd_derived_without_research(self):
        tex = generate_cover_letter(CROWDSTRIKE_JOB_ID, FACT_BANK)
        paras = re.findall(r"\\letterPara\{(.*?)\}\n\n", tex, flags=re.DOTALL)
        p3 = latex_visible_words(paras[2]).lower()
        # Must reference JD specifics, not invented research artifacts.
        self.assertIn("crowdstrike", p3)
        # No fabricated research-file markers.
        for marker in ["our research shows", "according to our study"]:
            self.assertNotIn(marker, p3)


class TestJDFinding(unittest.TestCase):
    def test_find_jd_resolves_crowdstrike(self):
        jd = find_jd_for_job(CROWDSTRIKE_JOB_ID)
        self.assertTrue(jd.exists())
        self.assertIn("4425331670", jd.name)


if __name__ == "__main__":
    unittest.main()
