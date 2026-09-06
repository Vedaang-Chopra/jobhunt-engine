"""Prompt templates for the resume agent's three LLM stages (spec 004 S1/S3/S5 + CL2).

Each prompt is a function returning (system, user) strings. Prompts receive
already-validated structured inputs — never raw dumps of everything.
"""
from __future__ import annotations

import json

from .common import log


def evidence_index(evidence_md: str) -> str:
    """Compact block index: name + first bullet-ish line per block."""
    lines = []
    for chunk in evidence_md.split("## ")[1:]:
        title = chunk.splitlines()[0].strip()
        body_lines = [ln.strip("- ").strip() for ln in chunk.splitlines()[1:]
                      if ln.strip() and not ln.startswith(("#", "**"))]
        summary = " ".join(body_lines)[:220]
        lines.append(f"### {title}\n{summary}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# S1 — PLAN
# ---------------------------------------------------------------------------

PLAN_SYSTEM = (
    "You are a strict resume strategist. You NEVER invent facts. You select "
    "evidence that exists in the library, map JD keywords to dispositions, and "
    "output a JSON plan conforming EXACTLY to the requested schema. No prose "
    "outside the JSON."
)


def plan_prompt(jd_text: str, quick_family: str, families_md: str,
                ev_index: str, keyword_bank: str,
                recent_plans: list[dict]) -> tuple[str, str]:
    rotation_note = ""
    if recent_plans:
        rotation_note = (
            "\n=== RECENT APPLICATIONS (cross-application variation, spec §12) ===\n"
            "These featured blocks were used recently; rotate at least one "
            "featured block away from any set repeating >=2 identical blocks "
            "(unless the dropped block solely covers a P0):\n"
            + "\n".join(f"- {p['slug']}: {', '.join(p.get('blocks', []))}"
                        for p in recent_plans))
    user = f"""Produce a resume customization plan as JSON.

=== ROLE FAMILIES (section order + narrative guidance) ===
{families_md[:7000]}

=== EVIDENCE LIBRARY INDEX (the ONLY usable fact blocks; full text comes later) ===
{ev_index}

=== KEYWORD BANK (tiers U/F/L/X by family) ===
{keyword_bank[:4000]}

=== JOB DESCRIPTION ===
{jd_text[:12000]}

Keyword-scan suggests family "{quick_family}" — verify or override.
{rotation_note}

Return ONLY minified JSON with EXACTLY these keys:
{{
 "family": "<one of the 11 family names>",
 "seniority": "<new-grad|junior|mid|senior>",
 "chosen_narrative": "<one line>",
 "alternative_narrative": "<one competing narrative you rejected and why>",
 "p0": [{{"requirement": "...", "jd_quote": "..."}}],
 "p1": ["..."], "p2": ["..."],
 "keyword_dispositions": [{{"term": "...", "tier": "U|F|L",
   "disposition": "integrated|listed|omitted",
   "evidence_block": "<block name if integrated>"}}],
 "featured_blocks": [{{"block": "<exact block name>", "target_section":
   "research|industry", "why": "<which P0s it covers>", "bullet_count": 2}}],
 "omitted_blocks": [{{"block": "...", "reason": "..."}}],
 "skills_rows": [{{"category": "...", "items": ["..."]}}]
}}

Rules:
- featured_blocks: rank by P0 coverage; max 4 blocks, every one must cover >=1 P0.
- Every P0 keyword must appear in keyword_dispositions. Zero silent omissions.
- skills_rows items may only be terms dispositioned integrated/listed or present
  in the base template already. Max 5 rows.
- Never disposition an X-tier term as anything but omitted.
"""
    return PLAN_SYSTEM, user


PLAN_SCHEMA_REQUIRED = ["family", "seniority", "chosen_narrative", "p0", "p1",
                        "p2", "keyword_dispositions", "featured_blocks",
                        "omitted_blocks", "skills_rows"]


# ---------------------------------------------------------------------------
# S3 — DRAFT
# ---------------------------------------------------------------------------

DRAFT_SYSTEM = (
    "You are an expert LaTeX resume writer bound by hard factual gates. You "
    "fill a locked skeleton with selected evidence ONLY. Freedom tiers: header "
    "contact/education/employer/date lines are copied VERBATIM from the "
    "skeleton; bullets may re-emphasize toward JD keywords but numbers, dates, "
    "and status verbs are immutable and each bullet draws from exactly ONE "
    "evidence block; skills contents come only from the plan. Output compiles "
    "with pdflatex using the provided style unchanged. Return ONLY complete "
    ".tex source, no code fences, no commentary."
)


def draft_prompt(base_tex: str, selected_evidence: str, plan: dict,
                 jd_text: str, bullet_rules: str, page_target: int,
                 tagline_candidates: int = 3) -> tuple[str, str]:
    user = f"""=== BULLET WRITING RULES ===
{bullet_rules[:5000]}

=== LOCKED BASE SKELETON (copy structure/contact/date lines verbatim) ===
{base_tex}

=== SELECTED EVIDENCE BLOCKS (sole factual source for content) ===
{selected_evidence}

=== PLAN (JSON) ===
{json.dumps(plan)}

=== JOB DESCRIPTION (terminology reference only) ===
{jd_text[:8000]}

Fill the skeleton into a job-tailored resume:
1. Header tagline: produce {tagline_candidates} candidates as LaTeX comments
   (% TAGLINE-CANDIDATE: ...) right above the tagline line; make the ACTIVE
   tagline line use the first candidate. Each candidate: 1-3 themes separated
   by en-dashes, <=2 rendered lines, themes must map to featured blocks.
2. Include exactly the featured_blocks from the plan, ordered by P0 coverage;
   within each section strongest-first. Omitted blocks must NOT appear.
3. Bullets: adapt emphasis toward integrated JD keywords where truthfully
   applicable. NEVER alter metrics (keep ~ qualifiers), dates, employers,
   degrees, GPA, status language. IN_PROGRESS projects stay present tense.
4. Skills section: use exactly the plan's skills_rows (categories + items).
5. Target {page_target} rendered page(s). If content exceeds it, trim the
   lowest-priority bullets rather than shrinking type.
6. Return ONLY the complete .tex document.
"""
    return DRAFT_SYSTEM, user


REPAIR_SYSTEM = (
    "You fix LaTeX resumes that violated factual or layout gates. Return only "
    "the corrected complete .tex."
)


def repair_prompt(violations: list[str], tex: str) -> tuple[str, str]:
    user = f"""These gate violations were found in the resume below:
{chr(10).join('- ' + v for v in violations)}

Remove or rewrite ONLY the offending wording (keep all true facts and metrics).
Return the full corrected .tex.

{tex}"""
    return REPAIR_SYSTEM, user


PAGE_FIT_PROMPT_TRIM = """The resume below renders at {pages} page(s); target is {target}.
Apply the spec-004 repair ladder rungs that apply, IN ORDER, minimally:
1. Shorten P2-driven bullets first (P0/P1 bullets untouched).
2. Compress any bullet >3 rendered lines to <=2 via emphasis-swap (facts immutable).
3. Merge Fortinet composite sub-bullets (drop least-P0-relevant).
4. Compress Skills rows (merge categories; drop L-tier items first).
Do NOT touch resume_style.sty, font size, Education, or any metric.
Return the full corrected .tex only.

{tex}"""


# ---------------------------------------------------------------------------
# CL2 — COVER LETTER DRAFT
# ---------------------------------------------------------------------------

CL_SYSTEM = (
    "You write concise, factual cover letters. Every claim must be supported "
    "by the provided evidence. Banned words anywhere: rlhf, rlaif, dpo, sft, "
    "qlora, lora, fine-tuning/fine-tuned/fine-tune, reward model, grpo, "
    "deepspeed, jax, kubernetes, spark, hive, scala. Never exceed 240 words "
    "across four paragraphs."
)


def cover_letter_prompt(jd_text: str, company: str, role_title: str,
                        top_p0s: list[dict], letter_evidence: str,
                        research_text: str | None) -> tuple[str, str]:
    research_block = (f"=== COMPANY RESEARCH (sole source for paragraph 3 specifics) ===\n"
                      f"{research_text[:3000]}" if research_text else
                      "No research file exists: ground paragraph 3 ONLY in the "
                      "JD's own stated mission/product. Never invent findings.")
    user = f"""Write a four-paragraph cover letter (<=240 words total) for:
{role_title} @ {company}

Paragraph contract:
(1) Hook naming the exact role and the candidate's sharpest relevant proof.
(2) Evidence paragraph mapping the JD's TOP requirements to specific facts —
use ONLY facts from the evidence excerpts below; keep every metric EXACTLY.
Top P0 requirements to address: {json.dumps(top_p0s)}
(3) Why-this-company. {research_block}
(4) Two-line close, no signature.

Rules: no em-dash spam; professional but human tone; never mention GPA unless
the JD asks; no banned words; output plain paragraphs separated by blank lines.

=== EVIDENCE EXCERPTS (sole factual source) ===
{letter_evidence}

=== JOB DESCRIPTION ===
{jd_text[:6000]}"""
    return CL_SYSTEM, user


CL_REPAIR_PROMPT = """Remove/replace these terms without inventing new claims:
{bad}

Also keep total under 240 words. Return only the corrected letter.

{text}"""
