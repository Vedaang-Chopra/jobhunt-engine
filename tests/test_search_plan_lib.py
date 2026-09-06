"""Task 3 — filter-first LinkedIn search plan builder (tests written first)."""

import pytest

from scripts.search_plan_lib import build_search_plan

EXPECTED_PASS_IDS = [
    "01_existing_1st",
    "02_existing_2nd",
    "03_existing_3rd",
    "04_hiring_posts",
    "05_gt_alumni",
    "06_former_coworkers",
    "07_team_members",
    "08_hiring_managers",
    "09_recruiters",
    "10_university_recruiters",
]

COMPANY_TARGET = {
    "company": "Scale AI",
    "company_slug": "scale-ai",
    "kind": "company",
    "job": None,
}

JOB_TARGET = {
    "company": "Cohere",
    "company_slug": "cohere",
    "kind": "job",
    "job": {"job_url": "https://jobs.lever.co/cohere/abc", "role_family": "ml"},
}

HINTS = {
    "keywords": ["LLM Evaluation Engineer", "Agentic AI Researcher"],
    "domain_terms": ["model evaluation", "retrieval"],
}


@pytest.fixture(scope="module")
def company_plan():
    return build_search_plan(COMPANY_TARGET)


@pytest.fixture(scope="module")
def job_plan():
    return build_search_plan(JOB_TARGET, hints=HINTS)


class TestShape:
    def test_returns_ordered_ten_passes(self, company_plan):
        assert [p["pass_id"] for p in company_plan] == EXPECTED_PASS_IDS

    def test_every_pass_has_required_keys(self, company_plan):
        required = {"pass_id", "family", "tier", "url", "filters", "verify", "limit"}
        for p in company_plan:
            assert required <= set(p), f"{p['pass_id']} missing keys"

    def test_verify_is_chips_and_result_count(self, company_plan):
        for p in company_plan:
            assert p["verify"] == "chips+result_count"

    def test_limit_hint_propagates(self):
        plan = build_search_plan(COMPANY_TARGET, limit_hint=7)
        assert all(p["limit"] == 7 for p in plan)

    def test_families_match_pass_ids(self, company_plan):
        for p in company_plan:
            assert p["family"] == p["pass_id"].split("_", 1)[1]

    def test_hints_none_is_accepted(self):
        plan = build_search_plan(JOB_TARGET)
        assert len(plan) == 10


class TestFilterFirstRules:
    def test_no_pass_has_empty_filters(self, company_plan, job_plan):
        for plan in (company_plan, job_plan):
            for p in plan:
                assert isinstance(p["filters"], dict) and p["filters"], p["pass_id"]

    def test_every_pass_pins_company(self, company_plan, job_plan):
        for plan in (company_plan, job_plan):
            for p in plan:
                if p["family"] == "hiring_posts":
                    # content search: company pinned via company param, not keywords alone
                    assert p["filters"].get("company") == JOB_TARGET["company_slug"] or p[
                        "filters"
                    ].get("company") == COMPANY_TARGET["company_slug"], p["pass_id"]
                else:
                    assert p["filters"].get("current_company"), p["pass_id"]

    def test_hiring_posts_has_date_posted_and_content_type(self, company_plan, job_plan):
        for plan in (company_plan, job_plan):
            hp = next(p for p in plan if p["family"] == "hiring_posts")
            assert "date_posted" in hp["filters"]
            assert "content_type" in hp["filters"]
            assert hp["filters"]["content_type"] == "posts"

    def test_degree_passes_have_network_filter(self, company_plan, job_plan):
        for plan in (company_plan, job_plan):
            for fam, deg in (
                ("existing_1st", "1st"),
                ("existing_2nd", "2nd"),
                ("existing_3rd", "3rd"),
            ):
                p = next(x for x in plan if x["family"] == fam)
                assert p["filters"].get("network") == [deg], p["pass_id"]

    def test_location_filter_is_us_remote(self, company_plan):
        p = next(p for p in company_plan if p["family"] == "existing_1st")
        loc = p["filters"].get("location")
        assert loc and "US" in str(loc)


class TestUrls:
    def test_people_urls_are_people_search(self, company_plan):
        for p in company_plan:
            if p["family"] != "hiring_posts":
                assert p["url"].startswith(
                    "https://www.linkedin.com/search/results/people/?"
                ), p["pass_id"]

    def test_hiring_posts_url_is_content_search(self, company_plan):
        hp = next(p for p in company_plan if p["family"] == "hiring_posts")
        assert hp["url"].startswith("https://www.linkedin.com/search/results/content/?")

    def test_all_urls_contain_company_pin_param(self, company_plan):
        from urllib.parse import parse_qs, urlparse

        for p in company_plan:
            qs = parse_qs(urlparse(p["url"]).query)
            # company pin: currentCompany or company param mirrors the UI filter
            assert (
                "currentCompany" in qs or "company" in qs
            ), f"no company pin in {p['pass_id']}"

    def test_degree_mirror_params(self, company_plan):
        from urllib.parse import parse_qs, urlparse

        mirrors = {"existing_1st": '["S"]', "existing_2nd": '["O"]', "existing_3rd": '["A"]'}
        for fam, expected in mirrors.items():
            p = next(x for x in company_plan if x["family"] == fam)
            qs = parse_qs(urlparse(p["url"]).query)
            assert qs["network"] == [expected], p["pass_id"]

    def test_geo_mirror_param_on_people_passes(self, company_plan):
        from urllib.parse import parse_qs, urlparse

        for p in company_plan:
            if p["family"] == "hiring_posts":
                continue
            qs = parse_qs(urlparse(p["url"]).query)
            assert qs.get("geoU") == ['["us"]'], p["pass_id"]

    def test_gt_alumni_school_filter_param(self, company_plan):
        from urllib.parse import parse_qs, urlparse

        p = next(x for x in company_plan if x["family"] == "gt_alumni")
        qs = parse_qs(urlparse(p["url"]).query)
        assert qs.get("schoolFilter") == ['["16818"]'], p["pass_id"]

    def test_urls_are_deterministic(self):
        a = build_search_plan(COMPANY_TARGET)
        b = build_search_plan(COMPANY_TARGET)
        assert [p["url"] for p in a] == [p["url"] for p in b]

    def test_company_name_in_url_encoded(self):
        plan = build_search_plan(COMPANY_TARGET)
        p = next(x for x in plan if x["family"] == "existing_1st")
        assert "scale-ai" in p["url"]
        assert " " not in p["url"]  # urlencode applied


class TestKeywordFacet:
    def test_former_coworkers_pinned_fortinet(self, company_plan):
        from urllib.parse import parse_qs, urlparse

        p = next(x for x in company_plan if x["family"] == "former_coworkers")
        assert p["filters"].get("keywords") == "Fortinet"
        qs = parse_qs(urlparse(p["url"]).query)
        assert qs.get("keywords") == ["Fortinet"]

    def test_team_members_default_keywords_without_hints(self, company_plan):
        p = next(x for x in company_plan if x["family"] == "team_members")
        for default in ("ML Engineer", "Applied Scientist", "Research Engineer"):
            assert default in p["filters"]["keywords"]

    def test_hiring_managers_default_keywords(self, company_plan):
        p = next(x for x in company_plan if x["family"] == "hiring_managers")
        kw = p["filters"]["keywords"]
        assert all(t in kw for t in ("Manager", "Lead", "Director"))
        assert "AI" in kw

    def test_recruiters_default_keywords(self, company_plan):
        p = next(x for x in company_plan if x["family"] == "recruiters")
        kw = p["filters"]["keywords"]
        for t in ("Recruiter", "Talent", "Recruiting"):
            assert t in kw

    def test_university_recruiters_keywords(self, company_plan):
        p = next(x for x in company_plan if x["family"] == "university_recruiters")
        kw = p["filters"]["keywords"]
        for t in ("University", "Campus", "Early Career"):
            assert t in kw


class TestJobHintInjection:
    def test_hints_inject_into_passes_7_9(self, job_plan):
        tm = next(p for p in job_plan if p["family"] == "team_members")
        hm = next(p for p in job_plan if p["family"] == "hiring_managers")
        rec = next(p for p in job_plan if p["family"] == "recruiters")
        assert "LLM Evaluation Engineer" in tm["filters"]["keywords"]
        assert "model evaluation" in hm["filters"]["keywords"]
        assert "retrieval" in rec["filters"]["keywords"]

    def test_hints_never_touch_passes_1_6(self, job_plan):
        injected = ["LLM Evaluation Engineer", "Agentic AI Researcher", "model evaluation"]
        for p in job_plan[:6]:
            for term in injected:
                assert term not in str(p["filters"]), p["pass_id"]
                assert term not in p["url"], p["pass_id"]

    def test_hiring_managers_still_have_role_words_with_hints(self, job_plan):
        hm = next(p for p in job_plan if p["family"] == "hiring_managers")
        kw = hm["filters"]["keywords"]
        assert all(t in kw for t in ("Manager", "Lead", "Director"))

    def test_recruiters_keep_recruiting_words_with_hints(self, job_plan):
        rec = next(p for p in job_plan if p["family"] == "recruiters")
        kw = rec["filters"]["keywords"]
        assert all(t in kw for t in ("Recruiter", "Talent", "Recruiting"))
