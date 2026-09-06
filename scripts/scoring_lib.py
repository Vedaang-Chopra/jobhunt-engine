"""Weighted person scoring for the right-people referral sweep.

Task 4 of .hermes/plans/2026-08-27_232352-right-people-feature.md.

Implements REFERRAL_RESEARCH_WORKFLOW.md (Phase 6) weights + recommended-ask
table, the P0-P3 priority bands, and the activity bonus / tiebreak rule from
docs/rules/LINKEDIN_REFERRAL_RULES.md.

score_person(p: dict) -> {"score": int, "priority": "P0"|"P1"|"P2"|"P3",
                          "ask": str, "breakdown": dict}
"""

# Signal weights (REFERRAL_RESEARCH_WORKFLOW.md Phase 6).
DEGREE_WEIGHTS = {"1st": 10, "2nd": 6, "3rd": 3}
MUTUAL_WEIGHT = 5
MUTUAL_CAP = 15
BOOL_WEIGHTS = {
    "gt_alumni": 8,
    "fortinet_overlap": 6,
    "same_team": 10,
    "is_hiring_manager": 15,
    "same_domain": 8,
    "us_based": 5,
    "known_personally": 5,
    "can_refer": 10,
}
ACTIVITY_BONUS = 6

# Priority bands, best to worst.
BAND_ORDER = ["P0", "P1", "P2", "P3"]

ASK_DIRECT_REFERRAL = "Direct referral request"
ASK_INTRO = "Introduction to hiring manager/team"
ASK_GT_MUTUALS = "Connection request + referral ask after connecting"
ASK_INFO_CHAT = "Connection request + informational chat ask"
ASK_TECH_QUESTION = "Connection request + specific technical question"
ASK_HM_INTEREST = "Connection request + specific interest in their team's work"
ASK_RECRUITER_DM = "Direct message with role reference + 2-sentence pitch"


def _as_bool(v):
    return bool(v)


def _signal_breakdown(p):
    """Per-signal point contributions; 0 for absent signals."""
    mutuals = p.get("mutuals") or []
    breakdown = {"degree": DEGREE_WEIGHTS.get(p.get("degree"), 0)}
    breakdown["mutuals"] = min(len(mutuals) * MUTUAL_WEIGHT, MUTUAL_CAP)
    for key, weight in BOOL_WEIGHTS.items():
        breakdown[key] = weight if _as_bool(p.get(key)) else 0
    active = p.get("activity_level") == "active_poster" and bool(p.get("hiring_post_urls"))
    breakdown["activity"] = ACTIVITY_BONUS if active else 0
    return breakdown


def _band(p):
    """P0-P3 priority band, evaluated in precedence order."""
    degree = p.get("degree")
    mutuals = p.get("mutuals") or []
    if degree == "1st":
        return "P0"
    has_mutuals = len(mutuals) > 0
    if (degree == "2nd" and has_mutuals) or (_as_bool(p.get("gt_alumni")) and has_mutuals):
        return "P1"
    if (
        degree == "2nd"
        or _as_bool(p.get("gt_alumni"))
        or _as_bool(p.get("same_team"))
        or _as_bool(p.get("is_hiring_manager"))
        or _as_bool(p.get("same_domain"))
    ):
        return "P2"
    return "P3"


def _recruiter_cap_applies(p):
    """Recruiter cap: only a recruiter with no relationship signals is capped,
    and a 1st-degree recruiter is never capped (existing relationship wins)."""
    if not _as_bool(p.get("is_recruiter")):
        return False
    if p.get("degree") == "1st":
        return False
    has_relationship = bool(p.get("mutuals")) or _as_bool(p.get("gt_alumni")) or _as_bool(p.get("known_personally")) or _as_bool(p.get("same_team"))
    return not has_relationship


def _recommended_ask(p):
    degree = p.get("degree")
    mutuals = p.get("mutuals") or []
    if _recruiter_cap_applies(p):
        # Recruiter cap note: the ask takes the recruiter value when the cap fires.
        return ASK_RECRUITER_DM
    if degree == "1st" and (_as_bool(p.get("can_refer")) or _as_bool(p.get("known_personally"))):
        return ASK_DIRECT_REFERRAL
    if degree == "1st":
        return ASK_INTRO
    if _as_bool(p.get("gt_alumni")) and len(mutuals) > 0:
        return ASK_GT_MUTUALS
    if _as_bool(p.get("gt_alumni")):
        return ASK_INFO_CHAT
    if _as_bool(p.get("same_team")) and degree in ("2nd", "3rd"):
        return ASK_TECH_QUESTION
    if _as_bool(p.get("is_hiring_manager")):
        return ASK_HM_INTEREST
    if _as_bool(p.get("is_recruiter")):
        return ASK_RECRUITER_DM
    return ASK_INFO_CHAT


def score_person(p):
    """Score one person: weighted score, P0-P3 band, recommended ask, breakdown.

    All fields are optional; missing fields are treated as absent (0 / False).
    The activity bonus (+6 for active_poster with hiring posts) doubles as the
    tiebreak: higher score wins, active posters outrank otherwise-identical
    inactive people.
    """
    breakdown = _signal_breakdown(p)
    score = int(sum(breakdown.values()))
    priority = _band(p)
    # Recruiter cap: downgrade to P2 (never above P2 applies only downward
    # from P1; P0 1st-degree recruiters are exempt and P3 stays P3).
    if _recruiter_cap_applies(p) and BAND_ORDER.index(priority) < BAND_ORDER.index("P2"):
        priority = "P2"
    return {
        "score": score,
        "priority": priority,
        "ask": _recommended_ask(p),
        "breakdown": breakdown,
    }
