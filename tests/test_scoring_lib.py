"""Task 4 tests: weighted person scoring + P0-P3 priority bands + recommended ask.

Targets scripts/scoring_lib.py::score_person. Coordination note: this is a
standalone scoring library; right_people_lib wiring happens later.
"""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
scoring_lib = pytest.importorskip("scoring_lib", reason="scripts/scoring_lib.py not implemented yet")


def _person(**overrides):
    """Baseline person with nothing set (all signals absent)."""
    p = {
        "degree": None,
        "mutuals": [],
        "gt_alumni": False,
        "fortinet_overlap": False,
        "same_team": False,
        "is_hiring_manager": False,
        "same_domain": False,
        "us_based": False,
        "known_personally": False,
        "can_refer": False,
        "is_recruiter": False,
    }
    p.update(overrides)
    return p


BREAKDOWN_KEYS = {
    "degree": 0,
    "mutuals": 0,
    "gt_alumni": 0,
    "fortinet_overlap": 0,
    "same_team": 0,
    "is_hiring_manager": 0,
    "same_domain": 0,
    "us_based": 0,
    "known_personally": 0,
    "can_refer": 0,
    "activity": 0,
}


class TestResultShape:
    def test_returns_required_keys(self):
        r = scoring_lib.score_person(_person())
        assert set(r.keys()) == {"score", "priority", "ask", "breakdown"}
        assert isinstance(r["score"], int)
        assert r["priority"] in {"P0", "P1", "P2", "P3"}
        assert isinstance(r["ask"], str) and r["ask"]

    def test_empty_dict_is_absent_everything(self):
        r = scoring_lib.score_person({})
        assert r["score"] == 0
        assert r["priority"] == "P3"
        assert r["ask"] == "Connection request + informational chat ask"
        assert r["breakdown"] == dict(BREAKDOWN_KEYS)


class TestWeightsAndArithmetic:
    def test_degree_weights(self):
        assert scoring_lib.score_person(_person(degree="1st"))["breakdown"]["degree"] == 10
        assert scoring_lib.score_person(_person(degree="2nd"))["breakdown"]["degree"] == 6
        assert scoring_lib.score_person(_person(degree="3rd"))["breakdown"]["degree"] == 3
        assert scoring_lib.score_person(_person())["breakdown"]["degree"] == 0

    def test_mutuals_capped_at_15(self):
        assert scoring_lib.score_person(_person(mutuals=["a"]))["breakdown"]["mutuals"] == 5
        assert scoring_lib.score_person(_person(mutuals=["a", "b", "c"]))["breakdown"]["mutuals"] == 15
        assert scoring_lib.score_person(_person(mutuals=["a", "b", "c", "d", "e"]))["breakdown"]["mutuals"] == 15

    def test_plan_arithmetic_2nd_2mutuals_gt_us_is_29(self):
        r = scoring_lib.score_person(
            _person(degree="2nd", mutuals=["x", "y"], gt_alumni=True, us_based=True)
        )
        assert r["score"] == 29  # 6 + 10 + 8 + 5 + 0(activity absent)

    def test_all_bool_signals_sum(self):
        r = scoring_lib.score_person(
            _person(
                gt_alumni=True,          # 8
                fortinet_overlap=True,   # 6
                same_team=True,          # 10
                is_hiring_manager=True,  # 15
                same_domain=True,        # 8
                us_based=True,           # 5
                known_personally=True,   # 5
                can_refer=True,          # 10
            )
        )
        assert r["score"] == 67

    def test_breakdown_sums_to_score(self):
        r = scoring_lib.score_person(
            _person(
                degree="2nd",
                mutuals=["a", "b", "c", "d"],
                gt_alumni=True,
                fortinet_overlap=True,
                us_based=True,
                activity_level="active_poster",
                hiring_post_urls=["https://x/post/1"],
            )
        )
        assert r["score"] == sum(r["breakdown"].values())

    def test_full_breakdown_has_exactly_signal_keys_with_points(self):
        r = scoring_lib.score_person(
            _person(
                degree="1st",
                mutuals=["a"],
                gt_alumni=True,
                fortinet_overlap=True,
                same_team=True,
                is_hiring_manager=True,
                same_domain=True,
                us_based=True,
                known_personally=True,
                can_refer=True,
            )
        )
        expected = dict(BREAKDOWN_KEYS)
        expected.update(
            {
                "degree": 10,
                "mutuals": 5,
                "gt_alumni": 8,
                "fortinet_overlap": 6,
                "same_team": 10,
                "is_hiring_manager": 15,
                "same_domain": 8,
                "us_based": 5,
                "known_personally": 5,
                "can_refer": 10,
                "activity": 0,  # activity_level absent
            }
        )
        assert r["breakdown"] == expected


class TestActivityRule:
    def test_active_poster_with_hiring_post_gets_plus6(self):
        r = scoring_lib.score_person(
            _person(activity_level="active_poster", hiring_post_urls=["https://x/p/1"])
        )
        assert r["breakdown"]["activity"] == 6
        assert r["score"] == 6

    def test_active_poster_without_posts_no_bonus(self):
        r = scoring_lib.score_person(_person(activity_level="active_poster"))
        assert r["breakdown"]["activity"] == 0

    def test_posts_without_active_poster_no_bonus(self):
        r = scoring_lib.score_person(_person(hiring_post_urls=["https://x/p/1"]))
        assert r["breakdown"]["activity"] == 0

    def test_active_poster_2nd_beats_inactive_2nd_identical_fields(self):
        base = dict(degree="2nd", mutuals=["a", "b"], gt_alumni=True)
        active = scoring_lib.score_person(
            _person(**base, activity_level="active_poster", hiring_post_urls=["https://x/p/1"])
        )
        inactive = scoring_lib.score_person(
            _person(**base, activity_level="inactive")
        )
        assert active["score"] == inactive["score"] + 6
        # stable tiebreak: activity bonus is reflected in score, priority equal
        assert active["priority"] == inactive["priority"]


class TestPriorityBands:
    @pytest.mark.parametrize(
        "person,expected",
        [
            (_person(degree="1st"), "P0"),
            (_person(degree="1st", is_recruiter=True), "P0"),  # 1st-degree recruiter stays P0
            (_person(degree="2nd", mutuals=["a"]), "P1"),
            (_person(gt_alumni=True, mutuals=["a"]), "P1"),
            (_person(degree="2nd"), "P2"),
            (_person(gt_alumni=True), "P2"),
            (_person(same_team=True), "P2"),
            (_person(is_hiring_manager=True), "P2"),
            (_person(same_domain=True), "P2"),
            (_person(degree="3rd"), "P3"),
            (_person(), "P3"),
            (_person(is_recruiter=True), "P3"),
        ],
    )
    def test_bands(self, person, expected):
        assert scoring_lib.score_person(person)["priority"] == expected

    def test_p1_precedence_over_p2_signals(self):
        # 2nd + mutuals is P1 even without any P2 alignment signal beyond degree
        assert scoring_lib.score_person(_person(degree="2nd", mutuals=["a"]))["priority"] == "P1"


class TestRecruiterCap:
    def test_recruiter_no_relationship_signals_capped_p2_with_recruiter_ask(self):
        # hiring-manager recruiter would be P2 anyway; check the downgrade case:
        # 1st-degree would be P0 but cap must not apply below-1st... use a case
        # that would otherwise be P1: recruiter + gt? gt is exempt. Use P1 path:
        # 2nd + mutuals is exempt (mutuals). The only downgrade-able path is
        # impossible via P1 without a relationship signal, so assert the cap on
        # a P1-shaped person built only from band rules: none exists; assert
        # P2-shaped recruiter keeps P2 and gets the recruiter ask.
        r = scoring_lib.score_person(_person(degree="2nd", is_recruiter=True))
        assert r["priority"] == "P2"
        assert r["ask"] == "Direct message with role reference + 2-sentence pitch"

    def test_recruiter_with_mutuals_not_ask_capped(self):
        r = scoring_lib.score_person(_person(degree="2nd", mutuals=["a"], is_recruiter=True))
        assert r["priority"] == "P1"  # mutuals exempt from cap
        # Ask table: no higher row fires (not 1st, not gt_alumni), so the
        # is_recruiter row applies -> recruiter DM ask.
        assert r["ask"] == "Direct message with role reference + 2-sentence pitch"

    def test_recruiter_with_gt_alumni_exempt(self):
        r = scoring_lib.score_person(_person(gt_alumni=True, is_recruiter=True))
        assert r["priority"] == "P2"

    def test_first_degree_recruiter_stays_p0(self):
        r = scoring_lib.score_person(_person(degree="1st", is_recruiter=True))
        assert r["priority"] == "P0"


class TestRecommendedAsk:
    @pytest.mark.parametrize(
        "person,expected",
        [
            (_person(degree="1st", can_refer=True), "Direct referral request"),
            (_person(degree="1st", known_personally=True), "Direct referral request"),
            (_person(degree="1st"), "Introduction to hiring manager/team"),
            (
                _person(gt_alumni=True, mutuals=["a"]),
                "Connection request + referral ask after connecting",
            ),
            (
                _person(gt_alumni=True),
                "Connection request + informational chat ask",
            ),
            (
                _person(degree="2nd", same_team=True),
                "Connection request + specific technical question",
            ),
            (
                _person(is_hiring_manager=True),
                "Connection request + specific interest in their team's work",
            ),
            (
                _person(is_recruiter=True),
                "Direct message with role reference + 2-sentence pitch",
            ),
            (_person(degree="3rd"), "Connection request + informational chat ask"),
            (_person(), "Connection request + informational chat ask"),
        ],
    )
    def test_ask_precedence(self, person, expected):
        assert scoring_lib.score_person(person)["ask"] == expected

    def test_ask_precedence_1st_beats_lower_rows(self):
        # 1st + can_refer outranks gt_alumni / same_team / recruiter rows
        r = scoring_lib.score_person(
            _person(degree="1st", can_refer=True, same_team=True, is_recruiter=True)
        )
        assert r["ask"] == "Direct referral request"
