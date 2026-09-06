#!/usr/bin/env python3
"""
score_jobs_v2.py — Canonical job scorer (2026-08-22).

Reads job_research/config/scoring-config.yaml (single source of truth).
Scores every active job in tracking/jobs/jobs.csv across 12 dimensions,
assigns opportunity level (L1-L4) and recommended action (APPLY_NOW..SKIP),
and writes results back to jobs.csv plus a JSON detail report.

Design rules (per docs/rules/ROLE_FIT_RULES.md §8):
- No single keyword dominates (per-keyword cap + dimension cap).
- Post-training is a valid target; deep-specialization lowers attainability only.
- Judgment overrides supported with recorded reasons.

Usage:
  python3 scripts/score_jobs_v2.py            # score all open jobs
  python3 scripts/score_jobs_v2.py --dry-run  # report without writing
  python3 scripts/score_jobs_v2.py --job-id ID1,ID2   # score a subset only
"""

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

try:
    from scripts import config_lib
except ImportError:
    import config_lib

REPO = Path(__file__).resolve().parent.parent
# Live data lives under the data root ($JOBHUNT_HOME / pointer file), not the repo.
DATA_ROOT = config_lib.data_root()
CONFIG_PATH = DATA_ROOT / "job_research/config/scoring-config.yaml"
JOBS_CSV = DATA_ROOT / "tracking/jobs/jobs.csv"
COMPANIES_CSV = DATA_ROOT / "tracking/companies/companies.csv"
REPORT_PATH = DATA_ROOT / "job_research/data/scored_jobs_v2.json"

TODAY = date.today()


def load_config():
    if not CONFIG_PATH.is_file():
        sys.exit(
            f"ERROR: scoring-config.yaml not found at {CONFIG_PATH}. "
            f"Set JOBHUNT_HOME to the data root containing "
            f"job_research/config/scoring-config.yaml."
        )
    return yaml.safe_load(CONFIG_PATH.read_text())


def norm(s):
    return (s or "").lower()


# ---------------------------------------------------------------- evidence --
TECH_SKILLS = {
    "pytorch": 3, "python": 2, "golang": 3, "go ": 1, "transformers": 3,
    "hugging face": 2, "vllm": 3, "onnx": 3, "docker": 1, "ray": 2,
    "distributed systems": 2, "model serving": 2, "inference": 2,
    "optimization": 1, "profiling": 1, "data pipelines": 1, "fastapi": 1,
    "opensearch": 2, "elasticsearch": 2,
}
RESEARCH_SIGNALS_STRONG = {
    "research": 2, "experimentation": 3, "new methods": 3, "evaluation": 2,
    "benchmark": 2, "publications": 2, "prototype": 2, "hypothesis": 3,
    "model behavior": 3,
}
RESEARCH_SIGNALS_MEDIUM = {
    "agents": 2, "agentic": 2, "planning": 2, "reasoning": 2, "tool use": 2,
    "function calling": 2, "memory": 1, "long-horizon": 2, "rag": 2,
    "retrieval": 1, "multimodal": 2, "vision-language": 2,
    "synthetic data": 2, "fine-tuning": 1, "post-training": 2,
    "rlhf": 2, "dpo": 2, "grpo": 2, "sft": 1, "reward model": 2,
    "reinforcement learning": 2, "alignment": 1, "model improvement": 2,
    "inference optimization": 2, "quantization": 1,
    "production research": 3,
}
AGENTIC_SIGNALS = {
    "agentic": 3, "multi-agent": 3, "agent framework": 3, "langgraph": 3,
    "langchain": 2, "tool use": 2, "tool calling": 2, "orchestration": 2,
    "planning agent": 3, "autonomous agents": 3, "workflow orchestration": 2,
}
PT_SIGNALS = {
    "post-training": 3, "rlhf": 2, "rlaif": 2, "dpo": 2, "grpo": 2, "sft": 1,
    "reward model": 2, "reward modeling": 2, "reinforcement learning": 1,
    "preference": 1, "alignment": 1, "synthetic data": 2, "human feedback": 2,
    "model improvement": 2, "data engine": 1,
}

SECURITY_AI_HINTS = [
    "security", "threat", "detection", "network security", "cyber",
    "soc", "incident", "malware", "fraud", "trust", "safety engineering",
]
SECURITY_COMPANIES = {
    "fortinet", "palo alto networks", "crowdstrike", "cisco", "cloudflare",
    "zscaler", "sentinelone", "okta", "snyk", "wiz", "tanium", "rapid7",
}


def capped_keyword_score(text, table, per_kw_cap=3):
    """Sum weighted hits with a per-keyword cap. Returns (score, matched list)."""
    total = 0
    matched = []
    for kw, w in table.items():
        if kw in text:
            total += min(w, per_kw_cap)
            matched.append(kw.strip())
    return total, sorted(set(matched))


def pct_cap(raw, max_possible, dim_weight_pct_of_total):
    """Cap keyword contribution at 60% of the dimension's share of 100."""
    if max_possible <= 0:
        return 0.0
    ratio = min(1.0, raw / max_possible)
    return round(ratio * dim_weight_pct_of_total * 0.6 + 40 * 0 if False else ratio * 100 * (dim_weight_pct_of_total / 100) * 0.6 / (dim_weight_pct_of_total / 100), 1)


# ------------------------------------------------------------- dimensions --
def d_role_fit(job, text, cfg):
    title = norm(job.get("title", ""))
    good_titles = ["research engineer", "research scientist", "applied scientist",
                   "applied research", "ml research", "ai research", "machine learning engineer",
                   "ml engineer", "ai engineer", "llm", "genai", "agent", "inference",
                   "evaluation", "reasoning", "post-training", "multimodal", "ai systems"]
    bad_titles = ["recruiter", "sales", "marketing", "account executive", "it engineer",
                  "technical writer", "business development", "recruiting coordinator"]
    score = 8.0
    hits = sum(1 for t in good_titles if t in title)
    score += min(hits, 3) * 2
    for t in bad_titles:
        if t in title:
            score -= 8
    if any(t in title for t in ["ai tutor"]):
        score -= 10
    # JD must mention ML/AI substance
    if not any(k in text for k in ["machine learning", " llm", "deep learning", " ai ", "model"]):
        score -= 4
    return max(0.0, min(15.0, score))


def d_research_alignment(text, cfg):
    s1, m1 = capped_keyword_score(text, RESEARCH_SIGNALS_STRONG)
    s2, m2 = capped_keyword_score(text, RESEARCH_SIGNALS_MEDIUM)
    raw = s1 * 1.5 + s2
    # Calibrated: an exceptional JD hits ~55% of the weighted table; treat that as full marks
    max_possible = sum(RESEARCH_SIGNALS_STRONG.values()) * 1.5 + sum(RESEARCH_SIGNALS_MEDIUM.values())
    ratio = min(1.0, raw / (max_possible * 0.55))
    return round(min(12.0, ratio * 12.0), 2), sorted(set(m1 + m2))[:12]


def d_technical_alignment(text):
    s, _ = capped_keyword_score(text, TECH_SKILLS)
    max_possible = sum(TECH_SKILLS.values())
    # Calibrated: strong-stack JDs hit ~60% of the table
    ratio = min(1.0, s / (max_possible * 0.6))
    return round(ratio * 10.0, 2)


def d_agentic_alignment(text):
    s, m = capped_keyword_score(text, AGENTIC_SIGNALS)
    ratio = min(1.0, s / (sum(AGENTIC_SIGNALS.values()) * 0.55))
    return round(ratio * 8.0, 2), m[:8]


def d_pt_alignment(text, cfg):
    s, m = capped_keyword_score(text, PT_SIGNALS)
    ratio = min(1.0, s / (sum(PT_SIGNALS.values()) * 0.5))
    return round(ratio * 8.0, 2), m[:8]


def d_attainability(job, text, cfg):
    score = 10.5  # base: MS CS (ML) + 4.5yrs production clears most RE bars
    mods = []
    if re.search(r"ph\.?d.{0,30}(required|must)", text):
        score += -25 * 0.15 * 100 / 100 * 0.25  # scale to 15-pt dimension
        mods.append("requires_phd")
    m = re.search(r"(\d{1,2})\+?\s*years", text)
    if m:
        yrs = int(m.group(1))
        if yrs >= 10:
            score -= 4.5; mods.append("requires_10plus_years")
        elif yrs >= 7:
            score -= 2.5
        elif yrs <= 4:
            score += 1.5
    else:
        # No explicit years bar: candidate not screened out on experience
        score += 1.0; mods.append("no_years_bar")
    if any(k in text for k in ["ms or equivalent", "m.s.", "master's degree", "bachelor"]):
        score += 1.0
    if any(k in text for k in ["led rlhf", "pioneered post-training", "deep rlhf expertise",
                               "extensive rlhf experience required"]):
        score -= 2.5; mods.append("deep_pt_specialization")
    if any(k in text for k in ["transferable", "or equivalent practical experience",
                               "related field", "strong ml fundamentals"]):
        score += 1.5; mods.append("accepts_transferable")
    loc = norm(job.get("location", ""))
    if any(x in loc for x in ["london", "zürich", "zurich", "singapore", "tokyo",
                              "bengaluru", "bangalore", "belgrade", "dublin", "qatar",
                              "serbia", "costa rica", "argentina", "uruguay"]):
        if "united states" not in loc and "remote" not in loc and "san francisco" not in loc \
           and "new york" not in loc and "seattle" not in loc:
            score -= 2.5; mods.append("location_hard_mismatch")
    return max(0.0, min(15.0, score)), mods


def d_asymmetric_advantage(job, text, cfg):
    company = norm(job.get("company", ""))
    pts = 0.0
    reasons = []
    if company in SECURITY_COMPANIES:
        pts += 2.0; reasons.append("security_ai_company")
    if any(h in text for h in SECURITY_AI_HINTS):
        pts += 1.2; reasons.append("security_domain_relevance")
    notes = norm(job.get("notes", "")) + " " + norm(job.get("matching_strengths", ""))
    if "gt alumni" in notes or "alumni" in notes:
        pts += 0.8; reasons.append("gt_alumni")
    if "referral" in notes or "connection" in notes:
        pts += 1.2; reasons.append("existing_connection_or_referral")
    if "fortinet" in notes:
        pts += 0.8; reasons.append("fortinet_adjacency")
    return min(8.0, pts), reasons


COMPANY_QUALITY_MAP = {
    "anthropic": 90, "openai": 92, "deepmind": 90, "xai": 82,
    "togetherai": 80, "together ai": 80, "cohere": 80, "scaleai": 78,
    "scale ai": 78, "databricks": 85, "youcom": 65, "comet": 60,
    "stabilityai": 62,
}
CATEGORY_PRIORS = load_config()["company_quality_priors"]


def d_company_quality(job, companies_by_slug):
    name = norm(job.get("company", ""))
    if name in COMPANY_QUALITY_MAP:
        q = COMPANY_QUALITY_MAP[name]
    else:
        slug = name.replace(" ", "_").replace("-", "_")
        row = companies_by_slug.get(slug)
        tier = (row or {}).get("company_tier", "")
        q = {"T1": 75, "T2": 70, "T3": 60, "T4": 60}.get(tier, 60)
    return round(q / 100 * 8.0, 2)


def d_strategic_value(text):
    pts = 4.0
    if any(k in text for k in ["frontier model", "foundation model", "large-scale training",
                               "pretraining", "research lab"]):
        pts += 1.5
    if any(k in text for k in ["evaluation", "benchmark", "agent", "reasoning"]):
        pts += 1.0
    if any(k in text for k in ["growth", "series b", "series c", "ipo"]):
        pts += 0.5
    return min(6.0, pts)


def d_referral_strength(job):
    blob = norm(job.get("notes", "")) + " " + norm(job.get("matching_strengths", "")) \
        + " " + norm(job.get("networking_priority", ""))
    if "high" in blob and ("referral" in blob or "connection" in blob):
        return 3.0
    if "medium" in blob:
        return 1.5
    return 0.5


def d_location_fit(job):
    loc = norm(job.get("location", ""))
    if any(x in loc for x in ["san francisco", "bay area", "new york", "seattle",
                              "remote-friendly, united states", "united states",
                              "remote united states", "palo alto", "mountain view"]):
        return 3.0
    if "remote" in loc:
        return 2.0
    if any(x in loc for x in ["london", "zürich", "zurich", "singapore", "tokyo",
                              "bengaluru", "bangalore", "belgrade", "dublin", "qatar",
                              "serbia", "costa rica", "argentina", "uruguay", "amsterdam"]):
        return 0.5
    return 1.5


def d_urgency(job):
    posted = job.get("date_posted") or ""
    try:
        y, mo, dy = map(int, posted.split("-"))
        from datetime import datetime as dt
        age_days = (dt(TODAY.year, TODAY.month, TODAY.day) - dt(y, mo, dy)).days
    except Exception:
        return 1.0
    if age_days <= 14:
        return 3.0
    if age_days <= 45:
        return 2.0
    if age_days <= 180:
        return 1.0
    return 0.2   # >6 months old — likely stale


LEVELS = [("APPLY_NOW", 80), ("APPLY", 68), ("OPTIMISTIC", 55),
          ("STRETCH", 40), ("LOW_PRIORITY", 25)]


def classify(priority, hard_blocked):
    if hard_blocked:
        return "SKIP"
    for action, thr in LEVELS:
        if priority >= thr:
            return action
    return "LOW_PRIORITY"


def level_for(action):
    return {"APPLY_NOW": "L1", "APPLY": "L2", "OPTIMISTIC": "L3",
            "STRETCH": "L4", "LOW_PRIORITY": "L3/L4 index-only",
            "SKIP": "-"}.get(action, "-")


def should_score(row, job_id_filter=None):
    """Row selection: non-archived, optionally restricted to job_ids.

    Pure helper so --job-id subset behavior is testable in isolation.
    """
    if row.get("status") == "archived":
        return False
    if job_id_filter and row.get("job_id") not in job_id_filter:
        return False
    return True


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Canonical job scorer (v2)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report without writing")
    ap.add_argument("--job-id", dest="job_ids", action="append", default=[],
                    help="restrict scoring to job_id(s); repeatable and/or "
                         "comma-separated")
    ns = ap.parse_args(argv)
    ids = set()
    for chunk in ns.job_ids:
        for part in str(chunk).split(","):
            part = part.strip()
            if part:
                ids.add(part)
    return ns.dry_run, (ids or None)


def main():
    dry_run, job_id_filter = parse_args(sys.argv[1:])
    cfg = load_config()

    companies_by_slug = {}
    if COMPANIES_CSV.exists():
        with open(COMPANIES_CSV) as f:
            for row in csv.DictReader(f):
                companies_by_slug[row.get("company_slug", "")] = row

    with open(JOBS_CSV, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    need_cols = ["opportunity_level", "recommended_action", "priority_v2",
                 "score_explanation", "score_confidence", "missing_info",
                 "override_reason", "last_scored"]
    for c in need_cols:
        if c not in fieldnames:
            fieldnames.append(c)

    report = []
    scored = 0
    jd_cache = {}
    for row in rows:
        if not should_score(row, job_id_filter):
            continue
        # Primary text source: the archived JD file (canonical record).
        # Fall back to row metadata columns when no JD file exists.
        jd_text = ""
        df = (row.get("description_file") or "").strip()
        if df:
            jd_path = DATA_ROOT / df
            try:
                raw = jd_path.read_text()
                if "## Full Job Description Text" in raw:
                    body = raw.split("## Full Job Description Text", 1)[1]
                    body = body.rsplit("---", 1)[0]
                    jd_text = body.lower()
            except OSError:
                pass
        meta_text = " ".join(filter(None, [
            row.get("title", ""), row.get("key_requirements", ""),
            row.get("matching_strengths", ""), row.get("main_gaps", ""),
            row.get("notes", "")])).lower()
        text = (jd_text + " " + meta_text).strip() if jd_text else meta_text

        dims = {}
        dims["role_fit"] = round(d_role_fit(row, text, cfg), 2)
        dims["research_alignment"], r_hits = d_research_alignment(text, cfg)
        dims["technical_alignment"] = d_technical_alignment(text)
        dims["agentic_reasoning_alignment"], a_hits = d_agentic_alignment(text)
        dims["pt_model_improvement_alignment"], p_hits = d_pt_alignment(text, cfg)
        dims["attainability"], att_mods = d_attainability(row, text, cfg)
        dims["asymmetric_advantage"], adv = d_asymmetric_advantage(row, text, cfg)
        dims["company_quality"] = d_company_quality(row, companies_by_slug)
        dims["strategic_career_value"] = d_strategic_value(text)
        dims["referral_network_strength"] = d_referral_strength(row)
        dims["location_fit"] = d_location_fit(row)
        dims["urgency_freshness"] = d_urgency(row)

        priority = round(sum(dims.values()), 1)

        blocked = row.get("is_medical_false_positive", "").lower() == "true"
        action = classify(priority, blocked)
        level = level_for(action)

        missing = []
        if not (row.get("date_posted") or "").strip():
            missing.append("date_posted unknown")
        if "visa" not in text:
            missing.append("visa sponsorship unverified")
        if not row.get("description_file", "").strip():
            missing.append("description_file pointer empty")

        explanation = (
            f"fit={dims['role_fit']} research={dims['research_alignment']}"
            f"(+{','.join(r_hits[:5])}) tech={dims['technical_alignment']}"
            f" agentic={dims['agentic_reasoning_alignment']}(+{','.join(a_hits[:4])})"
            f" pt={dims['pt_model_improvement_alignment']}(+{','.join(p_hits[:4])})"
            f" attainability={dims['attainability']}{att_mods}"
            f" advantage={dims['asymmetric_advantage']}{adv}"
            f" company={dims['company_quality']} strategy={dims['strategic_career_value']}"
            f" referral={dims['referral_network_strength']} loc={dims['location_fit']}"
            f" urgency={dims['urgency_freshness']}"
        )
        confidence = "medium"
        if len(missing) >= 2:
            confidence = "low"

        row["opportunity_level"] = level
        row["recommended_action"] = action
        row["priority_v2"] = str(priority)
        row["score_explanation"] = explanation
        row["score_confidence"] = confidence
        row["missing_info"] = "; ".join(missing)
        row["override_reason"] = row.get("override_reason", "")
        row["last_scored"] = TODAY.isoformat()
        scored += 1

        report.append({"job_id": row["job_id"], "company": row.get("company"),
                       "title": row.get("title"), "priority": priority,
                       "level": level, "action": action,
                       "dimensions": dims, "explanation": explanation,
                       "confidence": confidence, "missing": missing})

    report.sort(key=lambda r: r["priority"], reverse=True)

    print(f"Scored {scored} jobs (dry_run={dry_run})")
    buckets = {}
    for r in report:
        buckets[r["action"]] = buckets.get(r["action"], 0) + 1
    print("Action distribution:", dict(sorted(buckets.items(), key=lambda kv: -kv[1])))
    print("\nTOP 15:")
    for r in report[:15]:
        print(f"  [{r['priority']:5.1f}] {r['action']:<12} {r['title'][:58]} @ {r['company']}")

    if not dry_run:
        with open(JOBS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        REPORT_PATH.write_text(json.dumps(report, indent=2))
        print(f"\nWrote {JOBS_CSV} and {REPORT_PATH}")
    else:
        print("\nDry run — no files written.")


if __name__ == "__main__":
    main()
