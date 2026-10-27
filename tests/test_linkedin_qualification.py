"""Pure, network-free tests for structured LinkedIn qualification."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from linkedin_qualification import cheap_qualify, qualify_job


def card(**overrides):
    row = {
        "title": "Machine Learning Engineer, LLM Agents",
        "company": "Acme AI", "location": "Austin, TX", "salary": "$180K-$230K",
    }
    row.update(overrides)
    return row


def test_cheap_gates_reject_seniority_early_career_location_and_pay():
    cases = [
        (card(title="Staff Machine Learning Engineer"), "G2_seniority_ceiling"),
        (card(title="Junior AI Engineer"), "G3_early_career"),
        (card(location="Toronto, Canada"), "G6_location_not_supported"),
        (card(salary="$120K-$145K"), "G4_pay_floor"),
        (card(title="Frontend Engineer"), "G5_profile_fit"),
    ]
    for row, reason in cases:
        result = cheap_qualify(row, "ml-engineering", "agents")
        assert result.eligibility == "rejected"
        assert result.reject_reason == reason
        assert result.needs_jd is False


def test_compensation_at_floor_and_us_location_survive_cheap_gate():
    result = cheap_qualify(card(salary="$150K-$190K"), "ml-engineering", "agents")
    assert result.eligibility == "eligible"
    assert result.salary_evidence == "posted_floor=150000"
    assert result.needs_jd is True


def test_hard_five_year_requirement_remains_rejected():
    desc = "Minimum required: 5+ years building production software. Work on AI agents and tool use."
    result = qualify_job(card(), desc, "ml-engineering", "agents")
    assert result.eligibility == "rejected"
    assert result.reject_reason == "G1_experience_ceiling"


def test_flexible_five_year_requirement_is_explicit_optimistic_stretch():
    desc = "5+ years of ML experience or equivalent experience preferred. Build AI agents and tool calling systems."
    result = qualify_job(card(), desc, "ml-engineering", "agents")
    assert result.eligibility == "stretch_review"
    assert result.recommended_action == "OPTIMISTIC"
    assert result.experience_flexibility == "flexible_or_preferred"
    assert result.rationale
    fields = result.ledger_fields()
    assert fields["eligibility_verdict"] == "stretch_review"
    assert fields["qualification_json"]


def test_unusually_aligned_hard_requirement_is_pending_not_auto_eligible():
    desc = (
        "Minimum required: 6+ years. Build LLM post-training and reward models, "
        "plus AI agents, planning, tool calling, and agent evaluation."
    )
    result = qualify_job(card(), desc, "post-training", "post_training_alignment")
    assert result.eligibility == "stretch_review"
    assert result.reject_reason == "G1_hard_experience_pending_exception_review"
    assert result.recommended_action == ""
    assert len(result.technical_families) >= 2


def test_missing_jd_and_unrelated_jd_are_hard_rejections():
    missing = qualify_job(card(), "", "ml-engineering", "")
    assert missing.reject_reason == "G6_no_jd_unreachable"
    unrelated = qualify_job(card(title="Machine Learning Engineer", salary=""),
                            "Build ordinary ETL pipelines with SQL and dashboards.",
                            "ml-engineering", "")
    assert unrelated.eligibility == "rejected"
    assert unrelated.reject_reason == "G5_profile_fit_no_technical_signal"
