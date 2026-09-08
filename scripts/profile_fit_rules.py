#!/usr/bin/env python3
"""profile_fit_rules.py — Profile-based hard/soft qualification gates.

Answers one question for every job row: does this ROLE CLASS ever fit the
candidate, regardless of keyword score? Scoring config section
``profile_fit_rules`` (job_research/config/scoring-config.yaml) is the single
source of truth — every rule has an ``enabled`` flag, a regex, a mode
(hard/soft) and a reason so the user can flip any rule without code changes.

Pure functions only; both score_jobs_v2.py (at scoring time) and
qualify_sweep.py (bulk backlog cleanup) import from here.
"""

from __future__ import annotations

import re
from typing import Optional

try:
    from scripts import config_lib
except ImportError:  # pragma: no cover - direct script execution
    import config_lib  # type: ignore[no-redef]

from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

FIT_COL = "fit_class"            # fit | borderline | disqualified
REASON_COL = "disqualify_reason"

# Big-tech/frontier companies where a "senior" title implies more depth than
# the candidate's 4.5 yrs warrants — senior+ stays borderline (stretch) there.
# Everywhere else (startups, AI-native scale-ups, unknown companies) senior+
# counts as fit: startups level titles generously and the candidate is a real
# 4.5-yr production engineer. Fail-open by design — the goal is visibility,
# not silent filtering.
BIG_TECH_COMPANIES = {
    "google", "meta", "microsoft", "amazon", "apple", "nvidia", "netflix",
    "anthropic", "openai", "deepmind", "databricks", "snowflake", "oracle",
    "salesforce", "ibm", "intel", "qualcomm", "uber", "airbnb", "linkedin",
    "bytedance", "tiktok", "byte_dance", "tencent", "alibaba",
}

# company_category values (companies.csv) that count as startup-class.
STARTUP_CATEGORIES = {
    "ai_native_leader", "ai_infrastructure", "security_ai", "strong_startup",
    "specialist_cad_sim", "enterprise_ai", "startup",
}


def company_is_startup(company: str, companies_by_slug: Optional[dict] = None) -> bool:
    """True unless the company is a known big-tech/frontier name.

    companies_by_slug (optional, from tracking/companies/companies.csv) can
    override via company_category when present.
    """
    name = (company or "").strip().lower().replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)
    if name in BIG_TECH_COMPANIES:
        return False
    if companies_by_slug:
        row = companies_by_slug.get(name) or {}
        cat = (row.get("company_category") or "").strip().lower()
        if cat in STARTUP_CATEGORIES:
            return True
        if cat == "frontier_lab":
            return False
    return True  # unknown → fail open

# Defaults used when the config has no profile_fit_rules section.
# Patterns are matched against the lowercased job title.
DEFAULT_RULES = [
    {
        "id": "internship",
        "mode": "hard",
        "enabled": True,
        "reason": "internship/co-op role; candidate seeks experienced IC roles",
        "pattern": r"\bintern\b|\binternship\b|co-?op\b|summer\s+\d{4}\s+intern",
    },
    {
        "id": "new_grad_program",
        "mode": "hard",
        "enabled": True,
        "reason": "new-grad/campus program; candidate has 4.5 yrs experience",
        "pattern": r"new\s*grad(\uate)?\b|\bgraduate\b(?=.*engineer|.*scientist)|(engineer|scientist|ml|mle)\s+graduate\b|\bcampus\b(?!.*event)|university\s+grad(uate)?\b|\bearly career\b",
    },
    {
        "id": "exec_leadership",
        "mode": "hard",
        "enabled": True,
        "reason": "director/VP/head/manager level; not an experienced-IC target",
        "pattern": r"\b(vp|vice president)\b|\bdirector\b|\bhead of\b|\bmanager\b|\bpeople lead\b",
    },
    {
        "id": "tutor_annotation",
        "mode": "hard",
        "enabled": True,
        "reason": "tutor/annotation/data-labeling gig; not engineering",
        "pattern": r"\btutor\b|\bannotat|\bdata label|\blabeling\b|\brlhf annotator\b|\bai trainer\b",
    },
    {
        "id": "consulting_sales",
        "mode": "hard",
        "enabled": True,
        "reason": "consulting/advisory/sales/recruiting; not product engineering",
        "pattern": r"\bconsultant\b|\badvisory consultant\b|\bsolutions consultant\b|\bsales\b|\baccount executive\b|\brecruiter\b|\bsourcer\b|\bbusiness development\b",
    },
    {
        "id": "senior_plus_ic",
        "mode": "soft",
        "enabled": True,
        "reason": "senior/staff/principal/lead IC; attainable stretch only",
        # 'sr.' variant handled via word-boundary title check
        "pattern": r"\bsenior\b|\bsr\.?\b|\bstaff\b(?!.*account)|\bprincipal\b(?!.*investigator)|\blead\b",
    },
]


def load_fit_rules() -> list[dict]:
    """Rules from scoring-config.yaml ``profile_fit_rules``, else defaults."""
    if yaml is None:
        return [dict(r) for r in DEFAULT_RULES]
    path = config_lib.data_root() / "job_research/config/scoring-config.yaml"
    try:
        cfg = yaml.safe_load(path.read_text()) or {}
    except OSError:
        return [dict(r) for r in DEFAULT_RULES]
    rules = cfg.get("profile_fit_rules")
    if not rules:
        return [dict(r) for r in DEFAULT_RULES]
    out = []
    for r in rules:
        rr = dict(r)
        if "pattern" in rr and isinstance(rr["pattern"], str) and not rr["pattern"].startswith("("):
            pass  # keep raw regex strings as-is
        out.append(rr)
    return out


def _compile(rules: list[dict]) -> list[dict]:
    compiled = []
    for r in rules:
        if not r.get("enabled", True):
            continue
        try:
            rx = re.compile(r["pattern"], re.IGNORECASE)
        except re.error:
            continue
        compiled.append({**r, "_rx": rx})
    return compiled


def evaluate_title(title: str, rules: Optional[list[dict]] = None) -> dict:
    """Classify a job title.

    Returns {"fit_class": fit|borderline|disqualified,
             "matched_rules": [rule ids], "reason": str}
    Hard rules win over soft rules; first hard match wins.
    """
    if rules is None:
        rules = load_fit_rules()
    compiled = _compile(rules)
    t = title or ""
    hard = [r for r in compiled if r.get("mode") == "hard"]
    soft = [r for r in compiled if r.get("mode") == "soft"]
    for r in hard:
        if r["_rx"].search(t):
            return {"fit_class": "disqualified",
                    "matched_rules": [r["id"]],
                    "reason": r.get("reason", r["id"])}
    soft_hits = [r["id"] for r in soft if r["_rx"].search(t)]
    if soft_hits:
        return {"fit_class": "borderline", "matched_rules": soft_hits,
                "reason": "; ".join(r.get("reason", r["id"])
                                    for r in soft if r["id"] in soft_hits)}
    return {"fit_class": "fit", "matched_rules": [], "reason": ""}


def evaluate_row(row: dict, rules: Optional[list[dict]] = None,
                 companies_by_slug: Optional[dict] = None) -> dict:
    """Row-level wrapper: title + explicit seniority + company awareness.

    Senior+ titles stay 'borderline' only at big-tech/frontier companies; at
    startups and unknown companies they are 'fit' (startups level titles
    generously, and the candidate's 4.5 production years are real experience).
    """
    res = evaluate_title(row.get("title", ""), rules)
    if res["fit_class"] == "fit":
        sen = (row.get("seniority") or "").strip().lower()
        sen_soft = re.search(r"senior|staff|principal|lead|manager|director", sen)
        if sen_soft:
            res = {"fit_class": "borderline",
                   "matched_rules": res["matched_rules"] + ["seniority_column"],
                   "reason": "seniority column indicates senior+ role"}
    elif res["fit_class"] == "borderline":
        # Company-aware soft rule: senior/staff/principal at startup-class
        # companies counts as fit; only big-tech keeps the stretch cap.
        matched = set(res["matched_rules"])
        if matched & {"senior_plus_ic", "seniority_column"}:
            if company_is_startup(row.get("company", ""), companies_by_slug):
                res = {"fit_class": "fit",
                       "matched_rules": res["matched_rules"],
                       "reason": "senior+ at startup-class company = fit "
                                 "(title leveling is generous; 4.5y production)"}
    return res
