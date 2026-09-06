"""S2 — deterministic plan validation (spec 004).

Validates plan.json against schema + invariants. Returns list of errors;
empty list = valid.
"""
from __future__ import annotations

from .common import FAMILY_TEMPLATE, HARD_STOP_FAMILIES, TWO_PAGE_FAMILIES
from ._blocks import _norm_block


def verify_plan(plan: dict, evidence_md: str, jd_text: str = "") -> list[str]:
    errors: list[str] = []
    required = ["family", "seniority", "chosen_narrative", "p0", "p1", "p2",
                "keyword_dispositions", "featured_blocks", "omitted_blocks",
                "skills_rows"]
    for key in required:
        if key not in plan:
            errors.append(f"missing required key: {key}")
    if errors:
        return errors

    family = plan["family"]
    if family not in FAMILY_TEMPLATE:
        errors.append(f"unknown family: {family}")

    # Block names must exist in the evidence library.
    block_names = {_norm_block(c.splitlines()[0])
                   for c in evidence_md.split("## ")[1:] if c.splitlines()}
    featured = plan["featured_blocks"]
    if not isinstance(featured, list) or not featured:
        errors.append("featured_blocks must be a non-empty list")
    else:
        if len(featured) > 4:
            errors.append(f"too many featured blocks ({len(featured)} > 4)")
        for fb in featured:
            name = (fb.get("block") or "").strip()
            fb["block"] = name
            if _norm_block(name) not in block_names:
                errors.append(f"featured block not found in library: {name!r}")

    for ob in plan.get("omitted_blocks", []):
        name = (ob.get("block") or "").strip()
        ob["block"] = name
        if _norm_block(name) not in block_names:
            errors.append(f"omitted block not found in library: {name!r}")
        elif not (ob.get("reason") or "").strip():
            errors.append(f"omitted block lacks reason: {name!r}")

    # Keyword dispositions: every integrated one must resolve to a block.
    valid_tiers = {"U", "F", "L"}
    for kd in plan.get("keyword_dispositions", []):
        term = kd.get("term") or ""
        disp = kd.get("disposition")
        if disp not in {"integrated", "listed", "omitted"}:
            errors.append(f"bad disposition for term {term!r}: {disp!r}")
            continue
        tier = str(kd.get("tier") or "").upper()
        if tier == "X" and disp != "omitted":
            # Deterministic coercion (spec §2 I3): X-tier can only be omitted.
            kd["disposition"] = "omitted"
            kd.setdefault("note", "auto-coerced to omitted: X-tier/banned")
        if disp == "integrated":
            block = (kd.get("evidence_block") or "").strip()
            if _norm_block(block) not in block_names:
                errors.append(
                    f"integrated keyword {term!r} has no valid evidence_block")

    # P0 coverage: every featured block must cover >=1 P0 (via 'why' mention
    # or explicit mapping); and every P0 should be covered by some block.
    p0_texts = [p.get("requirement", "") if isinstance(p, dict) else str(p)
                for p in plan["p0"]]
    covered_words = set()
    for fb in featured:
        why = (fb.get("why") or "").lower()
        covered_words.update(w for w in why.split() if len(w) > 3)
    for i, p0 in enumerate(p0_texts):
        words = [w.lower() for w in p0.split() if len(w) > 4]
        if words and not any(w in covered_words for w in words):
            errors.append(f"P0 #{i+1} not claimed by any featured block: {p0[:60]!r}")

    skills_rows = plan["skills_rows"]
    if len(skills_rows) > 5:
        errors.append(f"too many skills rows ({len(skills_rows)} > 5)")

    # Hard-stop families need explicit user sign-off flag in plan.
    if family in HARD_STOP_FAMILIES and not plan.get("user_approved"):
        errors.append(
            f"family {family} is a hard-stop/stretch family — user approval "
            f"required before planning proceeds")
    return errors


def page_target_for(plan: dict) -> int:
    fam = plan.get("family", "")
    if plan.get("page_override") == 2:
        return 2
    return 2 if fam in TWO_PAGE_FAMILIES else 1
