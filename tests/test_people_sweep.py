"""Unit tests for people_sweep.py pure logic (no browser)."""

from __future__ import annotations

import csv
import importlib
import os
import sys
import tempfile

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

people_sweep = importlib.import_module("people_sweep")

COLUMNS = people_sweep.COLUMNS


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

def test_build_queries_covers_all_four_families():
    prefs = {
        "role_keywords": {"agentic_ai": ["agentic AI"]},
        "companies": ["Cohere"],
    }
    queries = people_sweep.build_queries(
        prefs, policy={"enable_school_family": True})
    fams = {q["family"] for q in queries}
    assert fams == {"a_hiring_posts", "b_recruiters", "c_company_people", "d_gt_alumni"}


def test_build_queries_rotate_role_families():
    prefs = {
        "role_keywords": {
            "agentic_ai": ["agentic AI"],
            "mle_training": ["distributed training"],
        },
        "companies": ["Cohere", "Together AI"],
    }
    queries = people_sweep.build_queries(prefs)
    # family-a queries should rotate across role families
    a_queries = [q for q in queries if q["family"] == "a_hiring_posts"]
    kws = " OR ".join(q["keywords"].lower() for q in a_queries)
    assert "agentic ai" in kws and "distributed training" in kws
    # each query has a search URL
    assert all(q["url"].startswith("https://www.linkedin.com/search/results/") for q in queries)


def test_linkedin_job_catalog_uses_at_most_three_word_queries():
    with open(os.path.join(REPO, "setup", "linkedin-job-queries.yaml"), encoding="utf-8") as handle:
        catalog = yaml.safe_load(handle)

    entries = list(catalog["broad_anchors"])
    for category in catalog["recurring_technical"].values():
        entries.extend(category["queries"])
    for category in catalog["frontier"].values():
        entries.extend(category["queries"])

    too_long = [entry["query"] for entry in entries if len(entry["query"].split()) > 3]
    assert too_long == []


def test_cap_queries_round_robin():
    prefs = {
        "role_keywords": {f"f{i}": [f"kw{i}"] for i in range(4)},
        "companies": ["A", "B"],
    }
    queries = people_sweep.build_queries(
        prefs, policy={"enable_school_family": True})
    capped = people_sweep.cap_queries(queries, 4)
    assert len(capped) == 4
    fams = [q["family"] for q in capped]
    # round-robin: first picks come from distinct families
    assert len(set(fams[:4])) == 4


def test_build_queries_school_family_opt_in():
    """Family d_gt_alumni is opt-in via policy['enable_school_family']."""
    prefs = {
        "role_keywords": {"agentic_ai": ["agentic AI"]},
        "companies": ["Cohere"],
    }
    # default (policy=None): no school/alumni family at all
    default_qs = people_sweep.build_queries(prefs)
    assert all(q["family"] != "d_gt_alumni" for q in default_qs)
    assert all("georgia tech" not in q["keywords"].lower() for q in default_qs)

    # explicitly disabled: same
    off_qs = people_sweep.build_queries(prefs, policy={"enable_school_family": False})
    assert all(q["family"] != "d_gt_alumni" for q in off_qs)

    # enabled: one alumni query per company, school from prefs when present
    on_qs = people_sweep.build_queries(
        {**prefs, "school": "Georgia Institute of Technology"},
        policy={"enable_school_family": True},
    )
    gt_qs = [q for q in on_qs if q["family"] == "d_gt_alumni"]
    assert len(gt_qs) == 1
    assert "Georgia Institute of Technology" in gt_qs[0]["keywords"]

    # enabled without prefs["school"]: canonical default applies
    fallback_qs = [q for q in people_sweep.build_queries(
        prefs, policy={"enable_school_family": True})
        if q["family"] == "d_gt_alumni"]
    assert len(fallback_qs) == 1
    assert "Georgia Tech" in fallback_qs[0]["keywords"]


# ---------------------------------------------------------------------------
# Preferences loading
# ---------------------------------------------------------------------------

def test_load_preferences_missing_raises(tmp_path):
    with pytest.raises(people_sweep.PreferencesMissing):
        people_sweep.load_preferences(tmp_path)


def test_load_preferences_empty_target_companies_raises(tmp_path):
    cfg = tmp_path / "job_research" / "config"
    cfg.mkdir(parents=True)
    (cfg / "target-companies.yaml").write_text("companies: []\n")
    with pytest.raises(people_sweep.PreferencesMissing):
        people_sweep.load_preferences(tmp_path)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_normalize_person_defaults_and_columns():
    row = people_sweep.normalize_person(
        {"name": "Jane Doe", "title": "Tech Lead", "company": "Cohere",
         "person_type": "hiring_manager", "linkedin_url":
             "https://www.linkedin.com/in/jane-doe-123/",
         "post_url": "https://www.linkedin.com/posts/x-9", "why_relevant": "kw: agentic",
         "job_id": "j1"},
        run_id="ps_20260823_0000",
    )
    assert list(row.keys()) == COLUMNS
    assert row["sweep_run_id"] == "ps_20260823_0000"
    assert row["status"] == "pending_review"
    assert row["date"] != ""


def test_normalize_person_requires_name():
    with pytest.raises(ValueError):
        people_sweep.normalize_person({"name": "", "company": "X"}, run_id="r")


def test_linkedin_slug():
    assert people_sweep.linkedin_slug("https://www.linkedin.com/in/jane-doe-123/?x=1") == "jane-doe-123"
    assert people_sweep.linkedin_slug("") == ""
    assert people_sweep.linkedin_slug("https://example.com/foo") == ""


# ---------------------------------------------------------------------------
# Dedup index
# ---------------------------------------------------------------------------

@pytest.fixture()
def contacts_csv(tmp_path):
    p = tmp_path / "contacts.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["contact_id", "name", "company", "role", "relationship",
                    "linkedin_url", "email", "job_id", "reason_to_contact",
                    "shared_context", "outreach_status", "date_identified",
                    "date_contacted", "followup_date", "response", "notes"])
        w.writerow(["c1", "Jane Doe", "Cohere", "", "", 
                    "https://www.linkedin.com/in/jane-doe-123/", "", "", "", "",
                    "requested", "", "", "", "", ""])
        w.writerow(["c2", "Bob Smith", "Together AI", "", "", 
                    "https://www.linkedin.com/in/bob-smith-ai/", "", "", "", "",
                    "not_contacted", "", "", "", "", ""])
    return str(p)


@pytest.fixture()
def prior_sweep_csv(tmp_path):
    p = tmp_path / "people_sweep.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write(",".join(COLUMNS) + "\n")
        fh.write("r1,2026-08-22,Bob Smith,Talent,Cohere,recruiter,"
                 "https://www.linkedin.com/in/bob-smith-ai/,,,why,pending_review,\n")
        fh.write("r1,2026-08-22,Ann Lee,MLE,Anthropic,hiring_manager,"
                 "https://www.linkedin.com/in/ann-lee-ml/,,,why,pending_review,\n")
    return str(p)


def make_index(contacts_csv=None, prior_csv=None):
    idx = people_sweep.PeopleDedupIndex()
    if contacts_csv:
        idx.load_contacts(contacts_csv)
    if prior_csv:
        idx.load_prior_rows(prior_csv)
    return idx


def test_dedup_by_linkedin_slug():
    idx = make_index(prior_csv=None)
    idx.add_seen(slug="jane-doe-123", name="Anything Else", company="")
    assert idx.seen_before("https://www.linkedin.com/in/jane-doe-123/") is True
    assert idx.seen_before("https://www.linkedin.com/in/new-person/") is False


def test_dedup_fuzzy_name_company():
    idx = people_sweep.PeopleDedupIndex()
    idx.add_seen(slug="", name="Bob Smith", company="Together AI")
    hit = idx.fuzzy_seen("Bobby Smith", "Together AI")
    assert hit is True
    assert idx.fuzzy_seen("Totally Different Person", "Other Co") is False


def test_dedup_against_contacts_file(contacts_csv):
    idx = make_index(contacts_csv=contacts_csv)
    # slug hit via contacts.csv regardless of status
    assert idx.seen_before("https://www.linkedin.com/in/jane-doe-123/")
    # fuzzy hit against contacts
    assert idx.fuzzy_seen("Bob Smith", "Together AI")


def test_dedup_against_prior_sweep_rows(prior_sweep_csv):
    idx = make_index(prior_csv=prior_sweep_csv)
    assert idx.seen_before("https://www.linkedin.com/in/bob-smith-ai/")
    assert idx.fuzzy_seen("Ann Lee", "Anthropic")


BLOCKED = ("requested", "connected", "contacted", "responded")


def test_blocked_status_never_resurfaced(tmp_path):
    p = tmp_path / "contacts.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write("contact_id,name,company,outreach_status\n")
        fh.write("c1,Jane Doe,Cohere,responded\n")
    idx = make_index(contacts_csv=str(p))
    verdict = idx.verdict(name="Jane Doe", company="Cohere",
                          linkedin_url="https://www.linkedin.com/in/jane-doe/")
    # fuzzy name+company match AND blocked status -> suppressed outright
    assert verdict == "blocked"


def test_same_name_at_different_company_does_not_cross_block(tmp_path):
    p = tmp_path / "contacts.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["name", "company", "linkedin_url", "outreach_status"])
        writer.writeheader()
        writer.writerow({
            "name": "Alex Kim", "company": "Cohere",
            "linkedin_url": "https://www.linkedin.com/in/alex-kim-cohere/",
            "outreach_status": "message_sent",
        })
    idx = make_index(contacts_csv=str(p))
    assert idx.verdict(
        "Alex Kim", "Cohere", "https://www.linkedin.com/in/alex-kim-cohere/") == "blocked"
    assert idx.verdict(
        "Alex Kim", "Anthropic", "https://www.linkedin.com/in/alex-kim-anthropic/") == "new"


def test_verdict_new_vs_duplicate():
    idx = people_sweep.PeopleDedupIndex()
    idx.add_seen(slug="known-person", name="Known Person", company="Acme")
    v1 = idx.verdict(name="New Person", company="Fresh Co", linkedin_url="https://www.linkedin.com/in/new-person-x/")
    assert v1 == "new"
    v2 = idx.verdict(name="Known Person", company="Acme", linkedin_url="")
    assert v2 == "duplicate"


# ---------------------------------------------------------------------------
# Merge pipeline
# ---------------------------------------------------------------------------

def test_merge_extraction_end_to_end(contacts_csv):
    idx = make_index(contacts_csv=contacts_csv)
    raw = [
        {"name": "Recruiter Rita", "title": "Talent Acquisition", "company": "Cohere",
         "person_type": "recruiter", "linkedin_url": "https://www.linkedin.com/in/recruiter-rita/",
         "post_url": "", "job_id": "cohere_job_1",
         "why_relevant": "family:b recruiter posting agentic AI"},
        {"name": "Bob Smith", "title": "Sourcer", "company": "Together AI",
         "person_type": "recruiter", "linkedin_url": "https://www.linkedin.com/in/bob-smith-ai/",
         "post_url": "", "why_relevant": "dup"},
        {"name": "Jane Doe", "title": "EM", "company": "Cohere",
         "person_type": "hiring_manager", "linkedin_url": "https://www.linkedin.com/in/jd-other/",
         "post_url": "", "why_relevant": "fuzzy blocked"},
    ]
    accepted, dups, blocked = people_sweep.merge_extraction(raw, idx, "run_x")
    assert len(accepted) == 1 and accepted[0]["name"] == "Recruiter Rita"
    assert accepted[0]["status"] == "pending_review"
    assert any(d["name"] == "Bob Smith" for d in dups)
    assert any(b["name"] == "Jane Doe" for b in blocked)


def test_append_rows_creates_csv_with_schema(tmp_path):
    out = tmp_path / "people_sweep.csv"
    rows = [people_sweep.normalize_person({"name": "A B", "company": "C"}, run_id="r")]
    n = people_sweep.append_rows(rows, str(out))
    assert n == 1
    with open(out) as fh:
        lines = list(csv.reader(fh))
    assert lines[0] == COLUMNS
    assert lines[1][9] == "skipped_low_signal"


# ---------------------------------------------------------------------------
# Preferences parsing
# ---------------------------------------------------------------------------

@pytest.mark.jobhunt_env_free
def test_load_preferences_from_repo():
    prefs = people_sweep.load_preferences()  # resolves via config_lib.data_root()
    assert prefs["role_keywords"], "expected role keyword families"
    assert "agentic_ai" in "".join(prefs["role_keywords"].keys()) or len(prefs["role_keywords"]) >= 3
    assert len(prefs["companies"]) >= 5
    assert any("Cohere" in c for c in prefs["companies"])
    assert prefs["role_validation"]["fallback_used"] is False
    assert all(f["source_field"] == "primary_keywords"
               for f in prefs["role_validation"]["families"])


def _write_preferences(root, role_body, target_body="companies:\n  - name: Cohere\n"):
    cfg = root / "job_research" / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "role-keywords.yaml").write_text(role_body, encoding="utf-8")
    (cfg / "target-companies.yaml").write_text(target_body, encoding="utf-8")


@pytest.mark.parametrize("field", ["primary_keywords", "primary", "keywords"])
def test_role_keyword_loader_accepts_active_and_legacy_shapes(tmp_path, field):
    _write_preferences(
        tmp_path,
        f"role_families:\n  post-training:\n    {field}: [rlhf, dpo, grpo]\n",
    )
    prefs = people_sweep.load_preferences(tmp_path)
    assert prefs["role_keywords"]["post-training"] == ["rlhf", "dpo", "grpo"]
    fam = prefs["role_validation"]["families"][0]
    assert fam == {"family": "post-training", "keywords_loaded": 3,
                   "source_field": field}
    assert prefs["role_validation"]["fallback_used"] is False


def test_unrecognized_role_keyword_schema_fails_loudly(tmp_path):
    _write_preferences(
        tmp_path,
        "role_families:\n  agents:\n    primary_terms: [agentic]\n",
    )
    with pytest.raises(people_sweep.RoleKeywordConfigError, match="primary_keywords"):
        people_sweep.load_preferences(tmp_path)


def _planner_prefs():
    return {
        "role_keywords": {
            "post-training": ["rlhf", "dpo", "grpo"],
            "evaluation-inference": ["LLM evaluation", "benchmarks", "red teaming"],
            "agentic-ai": ["AI agents", "tool use", "multi-agent"],
            "research-engineer": ["research engineer", "applied scientist"],
            "ml-training-arch": ["vLLM", "FSDP", "distributed training"],
        },
        "policy": {"enable_school_family": True},
        "company_profiles": {"cohere": {"name": "Cohere", "tags": ["high_priority"]}},
    }


def _qualified_job(**overrides):
    row = {
        "job_id": "j1", "company": "Cohere", "company_slug": "cohere",
        "title": "Research Engineer", "status": "open", "recommended_action": "APPLY",
        "priority_v2": "72", "role_family": "agentic-ai",
        "job_url": "https://example.test/jobs/j1", "date_discovered": "2026-09-10",
    }
    row.update(overrides)
    return row


def test_job_post_packet_plan_is_hiring_post_first_and_max_eight():
    prefs = _planner_prefs()
    packets = people_sweep.build_research_packets(
        prefs, [_qualified_job()], [], today=people_sweep.datetime.date(2026, 9, 12))
    plan = people_sweep.plan_searches(prefs, packets, limit=99)
    assert plan["search_count"] == 8
    assert [q["family"] for q in plan["queries"][:4]] == ["hiring_posts"] * 4
    assert [q["family"] for q in plan["queries"][4:]] == [
        "existing_1st", "existing_2nd_named_mutual", "gt_alumni",
        "hiring_manager_recruiter",
    ]
    assert all(q.get("verify") == "chips+result_count" for q in plan["queries"])
    assert not any(q["family"] == "c_company_people" for q in plan["queries"])
    assert all(q.get("job_id") == "j1" for q in plan["queries"][4:])


def test_hiring_post_queries_use_one_short_role_phrase():
    query = people_sweep._post_query(
        "agentic-ai", ["agentic", "multi-agent", "workflow orchestration"])

    assert query["keywords"] == 'hiring "agentic"'
    assert " OR " not in query["keywords"]
    assert len(query["keywords"].replace('"', '').split()) <= 2


def test_fresh_actionable_post_packet_captures_human_and_job_linkage():
    prefs = _planner_prefs()
    job = _qualified_job(canonical_application_url="https://example.test/apply/j1")
    post = {
        "post_id": "p1", "status": "new", "company": "Cohere",
        "poster_name": "Hiring Lead",
        "poster_type": "hiring_manager", "poster_headline": "Research Lead",
        "posted_date": "2026-09-11", "discovered_date": "2026-09-11",
        "roles_mentioned": "Research Engineer, AI agents", "role_family": "agentic_ai",
        "application_url": "https://example.test/apply/j1",
        "post_url": "https://linkedin.test/posts/p1", "team_or_org": "Agents",
        "notes": "We're hiring — join my team and apply",
    }
    packets = people_sweep.build_research_packets(
        prefs, [job], [post], today=people_sweep.datetime.date(2026, 9, 12))
    packet = next(p for p in packets if p["packet_id"] == "post:p1")
    assert packet["kind"] == "hiring_post"
    assert packet["job_id"] == "j1"
    assert packet["job_url"] == "https://example.test/apply/j1"
    assert packet["team_or_org"] == "Agents"
    assert packet["role_family"] == "agentic-ai"
    assert packet["hiring_post_author"] == "Hiring Lead"
    assert "fresh actionable hiring post" in packet["selection_reasons"]


def test_only_strong_optimistic_jobs_become_packets():
    prefs = _planner_prefs()
    jobs = [
        _qualified_job(job_id="strong", recommended_action="OPTIMISTIC", priority_v2="61"),
        _qualified_job(job_id="weak", recommended_action="OPTIMISTIC", priority_v2="59.9"),
    ]
    packets = people_sweep.build_research_packets(prefs, jobs, [])
    assert {p["job_id"] for p in packets} == {"strong"}


@pytest.mark.parametrize("field,value", [
    ("fit_class", "disqualified"),
    ("is_medical_false_positive", "true"),
    ("stale_flag", "true"),
    ("application_status", "submitted"),
    ("status", "expired"),
])
def test_ineligible_job_states_do_not_create_packets(field, value):
    job = _qualified_job(**{field: value})
    assert people_sweep.build_research_packets(_planner_prefs(), [job], []) == []


def test_url_only_job_gets_stable_non_company_packet_identity():
    job = _qualified_job(job_id="", canonical_application_url="https://example.test/jobs/unique")
    packet = people_sweep.build_research_packets(_planner_prefs(), [job], [])[0]
    assert packet["packet_id"].startswith("job:url_")
    assert packet["packet_id"] != "job:cohere"
    assert packet["job_trigger_id"] == packet["packet_id"].split(":", 1)[1]


def test_non_new_post_status_never_creates_packet():
    post = {
        "post_id": "p1", "status": "verify", "company": "Cohere",
        "poster_name": "Lead", "poster_type": "hiring_manager",
        "posted_date": people_sweep.datetime.date.today().isoformat(),
        "roles_mentioned": "Research Engineer AI agents",
        "post_url": "https://linkedin.test/posts/p1", "notes": "we're hiring",
        "role_family": "agentic_ai",
    }
    assert people_sweep.build_research_packets(_planner_prefs(), [], [post]) == []


def test_companyless_direct_poster_does_not_generate_empty_company_searches():
    today = people_sweep.datetime.date.today().isoformat()
    post = {
        "post_id": "p2", "status": "new", "company": "",
        "poster_name": "Direct Poster", "poster_type": "hiring_manager",
        "posted_date": today, "roles_mentioned": "Research Engineer AI agents",
        "post_url": "https://www.linkedin.com/in/direct-poster/",
        "notes": "we're hiring; join my team", "role_family": "agentic_ai",
    }
    packets = people_sweep.build_research_packets(_planner_prefs(), [], [post])
    assert packets[0]["packet_kind"] == "direct_poster"
    assert packets[0]["poster_profile_url"].endswith("/direct-poster/")
    plan = people_sweep.plan_searches(_planner_prefs(), packets)
    assert plan["search_count"] == 4
    assert all(q["surface"] != "linkedin_people" for q in plan["queries"])
    assert plan["direct_poster_reviews"][0]["poster_name"] == "Direct Poster"


def test_gt_alumni_enabled_in_active_policy_and_selectable(tmp_path):
    _write_preferences(
        tmp_path,
        "role_families:\n  agentic-ai:\n    primary_keywords: [agentic]\n"
        "  post-training:\n    primary_keywords: [rlhf]\n"
        "  evaluation-inference:\n    primary_keywords: [evals]\n"
        "  research-engineer:\n    primary_keywords: [research engineer]\n",
        "people_research:\n  policy:\n    enable_school_family: true\n"
        "companies:\n  - name: Cohere\n",
    )
    prefs = people_sweep.load_preferences(tmp_path)
    assert prefs["policy"]["enable_school_family"] is True
    packets = people_sweep.build_research_packets(prefs, [_qualified_job()], [])
    plan = people_sweep.plan_searches(prefs, packets)
    gt = next(q for q in plan["queries"] if q["family"] == "gt_alumni")
    assert gt["filters"]["school"] == ["Georgia Institute of Technology"]
    assert "16818" in gt["url"]


@pytest.mark.parametrize("raw,priority", [
    ({"degree": "1st", "job_id": "j1", "title": "ML Engineer"}, "P0"),
    ({"degree": "2nd", "mutuals": ["Named Person"], "job_id": "j1",
      "title": "Research Engineer, LLM evaluation"}, "P1"),
    ({"gt_alumni": True, "job_id": "j1", "title": "Research Engineer"}, "P1"),
    ({"fortinet_overlap": True, "job_id": "j1", "title": "AI Security Engineer"}, "P1"),
    ({"job_id": "j1", "title": "Engineering Manager"}, "P2"),
    ({"job_id": "j1", "title": "Technical Recruiter, AI"}, "P2"),
    ({"degree": "3rd", "post_url": "https://linkedin.test/post/1",
      "title": "Research Lead"}, "P3"),
    ({"degree": "3rd", "title": "Generic Employee"}, "SKIP"),
])
def test_candidate_priority_paths(raw, priority):
    assert people_sweep.rank_candidate(raw)["priority"] == priority


def test_recent_hiring_activity_materially_outranks_nominal_degree():
    inactive_first = people_sweep.rank_candidate({
        "degree": "1st", "job_id": "j1", "title": "ML Engineer"})
    active_second = people_sweep.rank_candidate({
        "degree": "2nd", "job_id": "j1", "title": "ML Engineer",
        "post_url": "https://linkedin.test/post/active"})
    assert active_second["score"] > inactive_first["score"]
    assert active_second["breakdown"]["recent_hiring_post_activity"] == 24


def test_duplicate_can_be_re_evaluated_without_becoming_new_contact():
    idx = people_sweep.PeopleDedupIndex()
    idx.add_seen(name="Known Person", company="Cohere", slug="known-person",
                 status="requested")
    raw = {"name": "Known Person", "company": "Cohere",
           "linkedin_url": "https://www.linkedin.com/in/known-person/",
           "job_id": "j2", "new_matching_job": True,
           "title": "Research Engineer"}
    accepted, duplicates, blocked = people_sweep.merge_extraction([raw], idx, "r2")
    assert not duplicates and not blocked
    assert accepted[0]["status"] == "reevaluation_pending"
    assert accepted[0]["re_evaluation_reason"] == "new_matching_job"
    assert "do not duplicate outreach" in accepted[0]["notes"]


def test_build_plan_uses_explicit_data_root(tmp_path, monkeypatch):
    _write_preferences(
        tmp_path,
        "role_families:\n  post-training:\n    primary_keywords: [rlhf]\n"
        "  evaluation-inference:\n    primary_keywords: [evals]\n"
        "  agentic-ai:\n    primary_keywords: [agents]\n"
        "  research-engineer:\n    primary_keywords: [research engineer]\n",
        "people_research:\n  policy:\n    enable_school_family: true\n"
        "companies:\n  - name: Cohere\n",
    )
    jobs = tmp_path / "tracking" / "jobs" / "jobs.csv"
    jobs.parent.mkdir(parents=True)
    with jobs.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_qualified_job()))
        writer.writeheader(); writer.writerow(_qualified_job())
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path))
    plan = people_sweep.build_plan()
    assert plan["canonical_paths"]["data_root"] == str(tmp_path)
    assert all(str(tmp_path) in value for value in plan["canonical_paths"].values())


def test_run_statuses_distinguish_dedupe_auth_zero_and_success():
    assert people_sweep.classify_run_status(
        {"completed": True, "duplicates": 2}) == "completed_no_new_people_dedupe_suppressed"
    assert people_sweep.classify_run_status(
        {"browser_unavailable": True}) == "browser_unavailable_or_auth_wall"
    assert people_sweep.classify_run_status(
        {"completed": True}) == "completed_zero_relevant_results"
    assert people_sweep.classify_run_status(
        {"completed": True, "profiles_examined": 2}) == "completed_successfully"


def test_packet_ranking_uses_coverage_fairness_yield_and_saturation():
    prefs = _planner_prefs()
    jobs = [
        _qualified_job(job_id="fresh", company="Fresh Labs", company_slug="fresh"),
        _qualified_job(job_id="tired", company="Tired Labs", company_slug="tired"),
    ]
    contacts = [{"company": "Tired Labs"} for _ in range(8)]
    history = {
        "freshlabs": {"runs": 1, "new_contacts": 2, "duplicates": 0,
                      "last_searched": "2026-08-20"},
        "tiredlabs": {"runs": 6, "new_contacts": 0, "duplicates": 18,
                      "last_searched": "2026-09-11"},
    }
    packets = people_sweep.build_research_packets(
        prefs, jobs, [], contacts=contacts, history=history,
        today=people_sweep.datetime.date(2026, 9, 12))
    assert packets[0]["job_id"] == "fresh"


def test_record_run_metrics_persists_complete_metric_and_yield_contract(tmp_path):
    path = tmp_path / "runs.jsonl"
    metrics: dict[str, object] = {key: 1 for key in people_sweep.METRIC_KEYS}
    metrics.update({
        "run_id": "r1", "completed": True,
        "degree_distribution": {"1st": 1, "2nd": 2, "3rd": 0},
        "query_yield": [{"query_id": "q1", "profiles": 3, "new_contacts": 1}],
        "company_yield": [{"company": "Cohere", "new_contacts": 1, "duplicates": 1}],
    })
    record = people_sweep.record_run_metrics(metrics, path)
    assert record["status"] == "completed_successfully"
    assert set(people_sweep.METRIC_KEYS) <= set(record)
    loaded = people_sweep.load_planning_history(path)
    assert loaded["cohere"]["new_contacts"] == 1
    assert loaded["cohere"]["duplicates"] == 1
