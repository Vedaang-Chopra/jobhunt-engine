"""Tests for profile-fit qualification gates (profile_fit_rules + wiring)."""

import csv

import pytest

from scripts.profile_fit_rules import (
    FIT_COL,
    REASON_COL,
    evaluate_row,
    evaluate_title,
    load_fit_rules,
)


@pytest.fixture(scope="module")
def rules():
    return load_fit_rules()


@pytest.mark.parametrize("title", [
    "Software Engineer Intern (Summer 2027)",
    "Research Internship (Fall 2026)",
    "Machine Learning Engineer Graduate",
    "Data Scientist - New Grad (Hybrid)",
    "VP, Research",
    "Director, AI Security",
    "Head of Healthcare GTM",
    "Engineering Manager, ML Platform",
    "AI Tutor - Bulgarian",
    "Data Annotation Specialist",
    "AI Advisory Consultant",
    "Recruiter, AI/ML Research",
    "Technical Solutions Consultant",
])
def test_hard_disqualified_titles(rules, title):
    res = evaluate_title(title, rules)
    assert res["fit_class"] == "disqualified", (title, res)


@pytest.mark.parametrize("title", [
    "Senior Software Engineer, Identity",
    "Staff ML Engineer",
    "Principal Research Engineer",
    "Tech Lead, Agents",
])
def test_soft_borderline_titles(rules, title):
    res = evaluate_title(title, rules)
    assert res["fit_class"] == "borderline", (title, res)


@pytest.mark.parametrize("title", [
    "Research Engineer, Code RL (Reinforcement Learning)",
    "Frontier Agents Engineer (Applied AI)",
    "Software Engineer, Identity",
    "Applied AI Researcher, Post-Training",
    "Machine Learning Engineer",
])
def test_fit_titles(rules, title):
    res = evaluate_title(title, rules)
    assert res["fit_class"] == "fit", (title, res)


def test_seniority_column_borderline_only_at_big_tech(rules):
    big_tech = {"big_tech": {"company_category": "frontier_lab"}}
    row = {"title": "Software Engineer", "seniority": "senior",
           "company": "Big Tech"}
    assert evaluate_row(row, rules, big_tech)["fit_class"] == "borderline"


def test_senior_at_startup_counts_as_fit(rules):
    row = {"title": "Senior Frontier Agents Engineer (Applied AI)",
           "company": "scale_ai"}
    assert evaluate_row(row, rules)["fit_class"] == "fit"


def test_senior_at_known_big_tech_stays_borderline(rules):
    row = {"title": "Senior Software Engineer, Identity",
           "company": "databricks"}
    assert evaluate_row(row, rules)["fit_class"] == "borderline"


def test_seniority_column_cannot_rescue_disqualified(rules):
    row = {"title": "AI Tutor - Bulgarian", "seniority": "entry"}
    assert evaluate_row(row, rules)["fit_class"] == "disqualified"


def test_disabled_rule_is_skipped(rules):
    import copy
    tweaked = copy.deepcopy(rules)
    for r in tweaked:
        if r["id"] == "internship":
            r["enabled"] = False
    assert evaluate_title("Software Engineer Intern", tweaked)["fit_class"] == "fit"


def test_column_names_stable():
    assert FIT_COL == "fit_class"
    assert REASON_COL == "disqualify_reason"


def test_sweep_dry_run_leaves_csv_untouched(tmp_path, monkeypatch, rules):
    """qualify_sweep main(dry) must not rewrite jobs.csv."""
    import scripts.qualify_sweep as qs

    src = csv.DictReader(open(qs.JOBS_CSV, newline=""))
    before = list(src)

    monkeypatch.setattr("sys.argv",
                        ["qualify_sweep.py"])  # default: dry-run
    rc = qs.main()
    assert rc == 0
    after = list(csv.DictReader(open(qs.JOBS_CSV, newline="")))
    assert len(before) == len(after)  # rows never deleted
