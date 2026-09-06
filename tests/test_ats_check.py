"""Tests for scripts/ats_check.py — ATS score, keyword match, compliance."""
import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ats_check  # noqa: E402


def write_fact_bank(path):
    """Minimal fake resume_fact_bank.yaml with technologies + coursework."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
candidate:
  name: "Test Candidate"
experience:
  - org: "TestCo"
    facts:
      - id: f1
        claim: "Built stuff"
        technologies: ["PyTorch", "Python", "Docker", "LangGraph", "vLLM"]
education:
  - institution: "Test U"
    coursework: ["Deep Learning", "Agentic AI"]
"""
    )
    return path


BASE_FIELDS = [
    "job_id", "company", "title", "location", "job_url",
    "canonical_application_url", "date_posted", "status",
    "key_requirements", "matching_strengths", "main_gaps", "notes",
    "description_file",
]


def make_row(**overrides):
    row = {
        "job_id": "acme_ml_eng_123",
        "company": "Acme AI",
        "title": "Machine Learning Engineer",
        "location": "San Francisco, CA",
        "job_url": "https://jobs.acme.ai/123",
        "canonical_application_url": "",
        "date_posted": "2026-08-01",
        "status": "open",
        "key_requirements": "Requirements: PyTorch, Python, LLM serving experience.",
        "matching_strengths": "",
        "main_gaps": "",
        "notes": "",
        "description_file": "",
    }
    row.update(overrides)
    return row


def write_jobs_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(BASE_FIELDS)
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


class AtsCheckTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ats_test_"))
        self.fact_bank = write_fact_bank(self.tmp / "profile_info" / "resume_fact_bank.yaml")
        self.table = ats_check.build_keyword_table(self.fact_bank)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestKeywordTable(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ats_test_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_builds_from_technologies_and_coursework(self):
        fb = write_fact_bank(self.tmp / "fact_bank.yaml")
        table = ats_check.build_keyword_table(fb)
        for kw in ("pytorch", "python", "docker", "langgraph", "vllm",
                   "deep learning", "agentic ai"):
            self.assertIn(kw, table)

    def test_boost_weights_mirror_tech_skills(self):
        fb = write_fact_bank(self.tmp / "fact_bank.yaml")
        table = ats_check.build_keyword_table(fb)
        self.assertEqual(table["pytorch"], 3)
        self.assertEqual(table["vllm"], 3)
        self.assertGreaterEqual(table["python"], 2)


class TestKeywordMatch(AtsCheckTestCase):
    def test_perfect_text_scores_100(self):
        # Hit enough of the weighted table to saturate the calibration cap.
        words = []
        for kw in self.table:
            if len(kw) <= 3:
                words.append(f" {kw} ")
            else:
                words.append(kw)
        text = " ".join(words)
        score, matched, _ = ats_check.keyword_match(text, self.table)
        self.assertEqual(score, 100.0)
        self.assertIn("pytorch", matched)

    def test_empty_text_scores_zero(self):
        score, matched, missing = ats_check.keyword_match("", self.table)
        self.assertEqual(score, 0.0)
        self.assertEqual(matched, [])
        self.assertTrue(missing)

    def test_partial_match_is_between(self):
        text = "we use pytorch and python for training large models"
        score, matched, missing = ats_check.keyword_match(text, self.table)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 100.0)
        self.assertIn("pytorch", matched)
        self.assertNotIn("pytorch", missing)

    def test_short_keywords_require_word_boundary(self):
        self.assertFalse(ats_check._keyword_in_text("go", "google goes"))


class TestComplianceChecks(AtsCheckTestCase):
    def test_all_pass_on_good_row(self):
        row = make_row()
        text = ("Requirements: 5 years of ML experience. "
                "This is a remote-friendly role based in San Francisco. " * 20)
        passed, total, issues = ats_check.compliance_checks(row, text.lower())
        self.assertEqual(total, 7)
        self.assertEqual(passed, 7, issues)
        self.assertEqual(issues, [])

    def test_thin_jd_flagged(self):
        row = make_row()
        passed, _, issues = ats_check.compliance_checks(row, "requirements: short")
        self.assertLess(passed, 7)
        self.assertTrue(any("thin job description" in i for i in issues))

    def test_missing_location_flagged(self):
        row = make_row(location="")
        _, _, issues = ats_check.compliance_checks(row, "requirements: x" * 60)
        self.assertTrue(any("no explicit location" in i for i in issues))

    def test_bad_apply_url_flagged(self):
        row = make_row(job_url="", canonical_application_url="javascript:void(0)")
        _, _, issues = ats_check.compliance_checks(row, "requirements: x" * 60)
        self.assertTrue(any("apply URL" in i for i in issues))

    def test_unknown_posting_date_flagged(self):
        row = make_row(date_posted="")
        _, _, issues = ats_check.compliance_checks(row, "requirements: x" * 60)
        self.assertTrue(any("posting date unknown" in i for i in issues))

    def test_anti_keyword_flagged(self):
        row = make_row(title="Sales Development Rep")
        _, _, issues = ats_check.compliance_checks(
            row, ("requirements: commission only role " * 30))
        self.assertTrue(any("anti-keyword" in i for i in issues))
        self.assertTrue(any("technical role" in i for i in issues))


class TestScoreMath(AtsCheckTestCase):
    def test_ats_score_formula(self):
        row = make_row()
        result = ats_check.evaluate_job(row, self.table, self.tmp)
        km = result["keyword_match_score"]
        cp = result["compliance_passed"] / result["compliance_total"]
        expected = round(0.6 * km + 0.4 * cp * 100.0, 1)
        self.assertEqual(result["ats_score"], expected)

    def test_bounds(self):
        row = make_row(status="open")
        result = ats_check.evaluate_job(row, self.table, self.tmp)
        self.assertGreaterEqual(result["ats_score"], 0.0)
        self.assertLessEqual(result["ats_score"], 100.0)

    def test_matched_and_missing_capped_at_top10(self):
        row = make_row()
        result = ats_check.evaluate_job(row, self.table, self.tmp)
        self.assertLessEqual(len(result["keyword_matched"]), 10)
        self.assertLessEqual(len(result["keyword_missing"]), 10)


class TestMissingDescription(AtsCheckTestCase):
    def test_no_description_file_still_evaluates(self):
        row = make_row(description_file="", notes="")
        row["key_requirements"] = ""
        result = ats_check.evaluate_job(row, self.table, self.tmp)
        self.assertIsInstance(result["ats_score"], float)

    def test_dangling_description_file_handled(self):
        row = make_row(description_file="tracking/job_descriptions/nope.md")
        result = ats_check.evaluate_job(row, self.table, self.tmp)
        self.assertIsInstance(result["ats_score"], float)

    def test_jd_file_body_extracted(self):
        jd = self.tmp / "jd.md"
        jd.write_text("# Job\n\n## Full Job Description Text\n\n"
                      "we use pytorch and vllm every day\n\n---\nmeta\n")
        text = ats_check.gather_jd_text(
            make_row(description_file=str(jd.relative_to(self.tmp))), self.tmp)
        self.assertIn("pytorch", text)
        self.assertNotIn("meta", text)


class TestApplyVsDryRun(AtsCheckTestCase):
    def _run_main(self, extra_args):
        jobs_csv = write_jobs_csv(self.tmp / "tracking/jobs/jobs.csv", [make_row()])
        ats_check.JOBS_CSV = jobs_csv
        ats_check.FACT_BANK = self.fact_bank
        ats_check.REPORT_PATH = self.tmp / "job_research/data/ats_report.json"
        ats_check.DATA_ROOT = self.tmp
        ats_check.main(extra_args)
        with open(jobs_csv, newline="") as f:
            reader = csv.DictReader(f)
            out_rows = list(reader)
            fields = reader.fieldnames
        return jobs_csv, fields, out_rows

    def test_apply_writes_new_columns(self):
        _, fields, rows = self._run_main([])
        for col in ats_check.ATS_COLUMNS:
            self.assertIn(col, fields)
        self.assertEqual(rows[0]["last_ats_check"], ats_check.TODAY.isoformat())
        self.assertTrue(rows[0]["ats_score"])
        self.assertTrue((self.tmp / "job_research/data/ats_report.json").is_file())

    def test_archived_rows_left_blank_but_columns_added(self):
        write_jobs_csv(self.tmp / "tracking/jobs/jobs.csv",
                       [make_row(), make_row(job_id="x2", status="archived")])
        ats_check.JOBS_CSV = self.tmp / "tracking/jobs/jobs.csv"
        ats_check.FACT_BANK = self.fact_bank
        ats_check.REPORT_PATH = self.tmp / "job_research/data/ats_report.json"
        ats_check.DATA_ROOT = self.tmp
        ats_check.main([])
        with open(self.tmp / "tracking/jobs/jobs.csv", newline="") as f:
            out = {r["job_id"]: r for r in csv.DictReader(f)}
        self.assertEqual(out["x2"]["ats_score"], "")   # archived: untouched
        self.assertTrue(out["acme_ml_eng_123"]["ats_score"])

    def test_dry_run_writes_nothing(self):
        jobs_csv = write_jobs_csv(self.tmp / "tracking/jobs/jobs.csv", [make_row()])
        before = jobs_csv.read_bytes()
        ats_check.JOBS_CSV = jobs_csv
        ats_check.FACT_BANK = self.fact_bank
        ats_check.REPORT_PATH = self.tmp / "job_research/data/ats_report.json"
        ats_check.DATA_ROOT = self.tmp
        ats_check.main(["--dry-run"])
        self.assertEqual(jobs_csv.read_bytes(), before)  # byte-identical
        self.assertFalse((self.tmp / "job_research/data/ats_report.json").exists())


if __name__ == "__main__":
    unittest.main()
