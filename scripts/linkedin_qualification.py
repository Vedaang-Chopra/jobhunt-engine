"""Structured deterministic qualification for LinkedIn-discovered jobs.

Cheap title/location/salary checks run before JD retrieval. Full qualification
adds experience flexibility and technical-fit evidence. Ambiguous exceptional
cases are marked stretch_review; hard rejections remain non-eligible.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

try:
    from scripts.discovery_lib import _location_supported, _is_india
    from scripts.profile_fit_rules import evaluate_title
except ImportError:  # pragma: no cover
    from discovery_lib import _location_supported, _is_india
    from profile_fit_rules import evaluate_title

TARGET_TITLE_RE = re.compile(
    r"\b(ai|ml|machine learning|llm|model|research|scientist|inference|"
    r"evaluation|safety|alignment|agent|multimodal|vision|security)\b", re.I)
UNRELATED_TITLE_RE = re.compile(
    r"\b(frontend|front-end|product manager|program manager|data analyst|"
    r"sales|account executive|recruiter|talent acquisition|bioinformatics|"
    r"hardware engineer|electrical engineer|mechanical engineer)\b", re.I)
HARD_SENIORITY_RE = re.compile(
    r"\b(chief|vice president|vp|director|head of|manager|people lead|lead|staff|principal)\b",
    re.I,
)
EARLY_RE = re.compile(
    r"\b(intern(ship)?|co-?op|new.?grad(uate)?|university (hire|graduate)|"
    r"early.?career|entry.?level|junior)\b", re.I,
)
YEARS_RE = re.compile(r"(?P<years>\d{1,2})\s*\+?\s*(?:-|to\s+)?\s*years?", re.I)
FLEXIBLE_RE = re.compile(r"or equivalent|equivalent experience|preferred|nice to have", re.I)
HARD_REQUIREMENT_RE = re.compile(r"minimum|required|must have|at least|\d+\+\s*years", re.I)
SALARY_RE = re.compile(r"\$\s*(\d{2,3})(?:[,.](\d{3}))?\s*([kK]?)")

TECHNICAL_PATTERNS = {
    "post_training_alignment": re.compile(
        r"post[- ]training|rlhf|alignment|preference optimization|reward model|\bdpo\b|\bgrpo\b|"
        r"supervised fine[- ]tuning|\bsft\b|model behavior", re.I),
    "llm_evaluation_reliability_safety": re.compile(
        r"llm evaluation|model evaluation|evaluation harness|benchmark|model quality|"
        r"safety evaluation|red team|adversarial evaluation", re.I),
    "agents": re.compile(
        r"ai agents?|agentic|tool use|tool calling|agent evaluation|multi-agent|planning|"
        r"reasoning|orchestration", re.I),
    "llm_inference_serving": re.compile(r"inference|vllm|serving|kv cache", re.I),
    "distributed_training_gpu_systems": re.compile(r"distributed training|fsdp|gpu systems?", re.I),
    "multimodal_vision_language": re.compile(r"multimodal|vision-language|\bvlm\b|image-text", re.I),
    "contrastive_representation_learning": re.compile(r"contrastive|\bclip\b|representation learning", re.I),
    "ai_security_adversarial_ml": re.compile(r"ai security|adversarial ml|model red team", re.I),
}


@dataclass
class Qualification:
    role_family: str = ""
    technical_families: tuple[str, ...] = ()
    seniority_risk: str = "none"
    experience_requirement: str = ""
    experience_flexibility: str = "unknown"
    salary_evidence: str = ""
    eligibility: str = "eligible"  # eligible | stretch_review | rejected
    reject_reason: str = ""
    recommended_action: str = ""
    rationale: str = ""
    needs_jd: bool = True

    def to_dict(self) -> dict:
        row = asdict(self)
        row["technical_families"] = list(self.technical_families)
        return row

    def ledger_fields(self) -> dict[str, str]:
        return {
            "role_family": self.role_family,
            "technical_families": ";".join(self.technical_families),
            "seniority_risk": self.seniority_risk,
            "experience_requirement": self.experience_requirement,
            "experience_flexibility": self.experience_flexibility,
            "salary_evidence": self.salary_evidence,
            "eligibility_verdict": self.eligibility,
            "eligibility_reason": self.reject_reason,
            "stretch_rationale": self.rationale if self.eligibility == "stretch_review" else "",
            "recommended_action": self.recommended_action,
            "qualification_json": json.dumps(self.to_dict(), sort_keys=True),
        }


def _salary_floor(text: str) -> int | None:
    values = []
    for major, minor, suffix in SALARY_RE.findall(text or ""):
        value = int(major)
        if suffix:
            value *= 1000
        elif minor:
            value = int(major + minor)
        elif value < 1000:
            continue
        values.append(value)
    return min(values) if values else None


def cheap_qualify(row: dict, role_family: str = "", technical_family: str = "") -> Qualification:
    """Reject obvious misses using card fields only; never requires a JD fetch."""
    title = str(row.get("title") or "")
    location = str(row.get("location") or "")
    salary = str(row.get("salary") or row.get("compensation") or "")
    technical = (technical_family,) if technical_family else ()
    q = Qualification(role_family=role_family, technical_families=technical)

    fit = evaluate_title(title)
    if HARD_SENIORITY_RE.search(title) or fit.get("fit_class") == "disqualified" and "exec_leadership" in fit.get("matched_rules", []):
        q.eligibility, q.reject_reason, q.seniority_risk, q.needs_jd = (
            "rejected", "G2_seniority_ceiling", "hard", False)
        return q
    if EARLY_RE.search(title) or fit.get("fit_class") == "disqualified" and set(fit.get("matched_rules", [])) & {"internship", "new_grad_program"}:
        q.eligibility, q.reject_reason, q.needs_jd = "rejected", "G3_early_career", False
        return q
    if UNRELATED_TITLE_RE.search(title) or not TARGET_TITLE_RE.search(title):
        q.eligibility, q.reject_reason, q.needs_jd = "rejected", "G5_profile_fit", False
        return q
    if not _location_supported(location):
        q.eligibility, q.reject_reason, q.needs_jd = (
            "rejected", "G6_india_requires_scored_exception" if _is_india(location)
            else "G6_location_not_supported", False)
        return q
    floor = _salary_floor(salary)
    if floor is not None:
        q.salary_evidence = f"posted_floor={floor}"
        if floor < 150000:
            q.eligibility, q.reject_reason, q.needs_jd = "rejected", "G4_pay_floor", False
            return q
    return q


def qualify_job(row: dict, description: str, role_family: str = "",
                technical_family: str = "") -> Qualification:
    q = cheap_qualify(row, role_family, technical_family)
    if q.eligibility == "rejected":
        return q
    if not (description or "").strip():
        q.eligibility, q.reject_reason, q.needs_jd = "rejected", "G6_no_jd_unreachable", False
        return q

    text = f"{row.get('title', '')}\n{description}"
    matches = tuple(name for name, pattern in TECHNICAL_PATTERNS.items() if pattern.search(text))
    q.technical_families = tuple(dict.fromkeys(q.technical_families + matches))
    q.needs_jd = False

    year_matches = list(YEARS_RE.finditer(description))
    if year_matches:
        highest = max(int(match.group("years")) for match in year_matches)
        q.experience_requirement = f"{highest}+ years"
        snippets = []
        for match in year_matches:
            start, end = max(0, match.start() - 90), min(len(description), match.end() + 120)
            snippets.append(description[start:end])
        evidence = " ".join(snippets)
        flexible = bool(FLEXIBLE_RE.search(evidence))
        hard = bool(HARD_REQUIREMENT_RE.search(evidence)) and not flexible
        q.experience_flexibility = "flexible_or_preferred" if flexible else "hard_minimum" if hard else "ambiguous"
        if highest >= 5:
            q.seniority_risk = "stretch"
            if flexible:
                q.eligibility = "stretch_review"
                q.recommended_action = "OPTIMISTIC"
                q.rationale = "5+ years stated with preferred/or-equivalent flexibility"
            elif hard:
                # Preserve the hard ceiling. Strong alignment is surfaced for review,
                # but the candidate is not silently admitted to the open ledger.
                if len(q.technical_families) >= 2:
                    q.eligibility = "stretch_review"
                    q.recommended_action = ""
                    q.reject_reason = "G1_hard_experience_pending_exception_review"
                    q.rationale = "hard 5+ minimum plus unusually strong multi-family alignment; human/LLM review required before ingest"
                else:
                    q.eligibility = "rejected"
                    q.reject_reason = "G1_experience_ceiling"
            else:
                q.eligibility = "stretch_review"
                q.recommended_action = "OPTIMISTIC"
                q.rationale = "5+ years wording is ambiguous; explicit review required"

    if not q.technical_families and q.eligibility != "rejected":
        q.eligibility = "rejected"
        q.reject_reason = "G5_profile_fit_no_technical_signal"
    return q
