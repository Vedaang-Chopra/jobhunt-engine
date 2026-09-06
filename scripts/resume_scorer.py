#!/usr/bin/env python3
"""resume_scorer.py — score an EXISTING resume against a pasted/fetched JD.

Two scoring layers, both printed to stdout as human-readable lines and saved
as JSON + Markdown under <data_root>/resume_scoring/:

  1. DETERMINISTIC ATS — reuses scripts/ats_check.py's weighted keyword table
     (built from profile_info/resume_fact_bank.yaml) to measure how much of the
     JD-relevant keyword space the resume actually covers.
  2. LLM EVALUATION — sends JD + resume text through the same provider chain
     tailor_from_jd uses (openrouter -> nvidia -> custom) and gets a strict-
     JSON rubric back: overall fit, per-dimension sub-scores, strengths, gaps,
     and concrete rewrite recommendations.

Usage:
  python3 scripts/resume_scorer.py --jd-file jd.txt --resume path/to/resume.tex
  python3 scripts/resume_scorer.py --spec-file spec.json
      # spec.json: {"kind":"url"|"text"|"file", "payload":..., "resume": "..."}
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:  # pragma: no cover - direct-script import shape
    import config_lib

import ats_check
import tailor_from_jd

DATA_ROOT = config_lib.data_root()
OUT_DIR = DATA_ROOT / "resume_scoring"

RUBRIC_DIMENSIONS = [
    "keyword_alignment",
    "experience_relevance",
    "title_and_seniority_fit",
    "ats_parseability_formatting",
]

SYSTEM_PROMPT = (
    "You are a senior technical recruiter and ATS expert. You compare one "
    "candidate resume against one job description and return ONLY a JSON "
    "object — no prose before or after."
)


def log(msg: str) -> None:
    print(f"[scorer] {msg}", flush=True)


# ---------------------------------------------------------------- inputs ----

def load_resume_text(resume_path: str) -> str:
    """Resume text from .tex / .md / .txt / .pdf."""
    path = Path(resume_path).expanduser()
    if not path.exists():
        raise RuntimeError(f"resume not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        out = subprocess.run(["pdftotext", str(path), "-"],
                             capture_output=True, text=True, timeout=30)
        return out.stdout or ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".tex":
        return tailor_from_jd.strip_latex(text)
    return text


def load_jd(kind: str, payload: str) -> dict:
    """JD dict {title, company, description} using tailor_from_jd loaders."""
    args = argparse.Namespace(url="", jd_file="", text_file="",
                              company="", title="")
    if kind == "url":
        row = tailor_from_jd.fetch_jd_from_url(payload)
        log(f"fetched JD from URL: {payload}")
    elif kind == "file":
        path = Path(payload).expanduser()
        row = tailor_from_jd.parse_jd_text(
            path.read_text(encoding="utf-8", errors="replace"))
    else:  # pasted text
        if len(payload.strip()) < 200:
            raise RuntimeError("pasted JD too short (<200 chars)")
        row = tailor_from_jd.parse_jd_text(payload)
        if not row.get("company"):
            # "# Title — Company" on the first line (common manual-upload shape)
            m = re.match(r"#\s*(.+?)\s*[—–]\s*(.+?)\s*$",
                         payload.strip().splitlines()[0]) \
                if payload.strip() else None
            if m:
                row["title"] = row.get("title") or m.group(1).strip()
                row["company"] = m.group(2).strip()
    return row


# ------------------------------------------------------- deterministic ------

def deterministic_scores(jd_desc: str, resume_text: str,
                         fact_bank: Path | None = None) -> dict:
    """Keyword coverage of the resume against the JD-weighted keyword table."""
    bank = Path(fact_bank) if fact_bank else \
        DATA_ROOT / "profile_info" / "resume_fact_bank.yaml"
    table = ats_check.build_keyword_table(bank)
    # Weight each keyword by whether the JD actually mentions it; JD-present
    # keywords count double so the score reflects THIS posting, not the market.
    jd_low = jd_desc.lower()

    total = raw = 0
    matched: list[str] = []
    missing: list[tuple[str, int]] = []
    for kw, w in table.items():
        weight = min(w, ats_check.PER_KW_CAP) * (2 if ats_check._keyword_in_text(kw, jd_low) else 1)
        if not weight:
            continue
        total += weight
        if ats_check._keyword_in_text(kw, resume_text.lower()):
            raw += weight
            matched.append(kw)
        else:
            missing.append((kw, weight))
    ratio = min(1.0, raw / (total * ats_check.FULL_MARKS_RATIO)) if total else 0.0
    # Only keywords the JD actually mentions matter for THIS posting.
    jd_matched = sorted(kw for kw in matched
                        if ats_check._keyword_in_text(kw, jd_low))
    jd_missing = [kw for kw, _wt in sorted(missing, key=lambda kv: -kv[1])
                  if ats_check._keyword_in_text(kw, jd_low)]
    return {
        "ats_keyword_score": round(ratio * 100.0, 1),
        "keywords_matched": sorted(set(jd_matched))[:25],
        "keywords_missing_top": jd_missing[:15],
        "keywords_total_in_jd": len(jd_matched) + len(jd_missing),
    }


# ------------------------------------------------------------------ LLM -----

def llm_evaluation(jd_desc: str, jd_title: str, jd_company: str,
                   resume_name: str, resume_text: str) -> dict:
    """Strict-JSON rubric from the configured provider chain."""
    prompt = f"""Compare this RESUME against this JOB DESCRIPTION.

JOB TITLE: {jd_title or '(unknown)'}
COMPANY: {jd_company or '(unknown)'}

=== JOB DESCRIPTION ===
{jd_desc[:12000]}

=== RESUME ({resume_name}) ===
{resume_text[:12000]}

Return ONLY this JSON object (no markdown fences):
{{
  "overall_fit": <int 0-100>,
  "breakdown": {{
    "keyword_alignment": <int 0-100>,
    "experience_relevance": <int 0-100>,
    "title_and_seniority_fit": <int 0-100>,
    "ats_parseability_formatting": <int 0-100>
  }},
  "verdict": "<one sentence: is this resume strong for THIS posting?>",
  "strengths": ["<specific strength citing resume evidence>", ...],
  "gaps": ["<specific gap vs the JD>", ...],
  "recommendations": ["<concrete edit to raise the score>", ...]
}}
Give 3-6 items in strengths, gaps, and recommendations. Be specific and
evidence-based; do not invent experience that is not on the resume."""
    raw = tailor_from_jd.llm_chat(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": prompt}],
        temperature=0.2,
    )
    data = tailor_from_jd.extract_json_object(raw)
    for dim in RUBRIC_DIMENSIONS:
        b = data.setdefault("breakdown", {})
        b[dim] = int(b.get(dim) or 0)
    data["overall_fit"] = int(data.get("overall_fit") or 0)
    return data


def blended(ats: float, llm_overall: float) -> float:
    """Final score: 40% deterministic keyword coverage + 60% LLM rubric."""
    return round(0.4 * ats + 0.6 * llm_overall, 1)


# --------------------------------------------------------------- reporting --

def write_report(result: dict) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = OUT_DIR / f"{result['resume_stem']}__{result['company_slug']}_{stamp}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")

    json_path.write_text(json.dumps(result, indent=2))

    ev, det, llm = result["evaluation"], result["deterministic"], result["llm"]
    lines = [
        f"# Resume Score — {result['resume_name']} vs "
        f"{result['title'] or 'JD'} @ {result['company'] or '?'}",
        "",
        f"- **Date:** {result['timestamp']}",
        f"- **FINAL SCORE:** **{ev['final']}/100** "
        f"(40% ATS keywords {det['ats_keyword_score']:.0f} + "
        f"60% LLM fit {llm.get('overall_fit', 0)})",
        f"- **Verdict:** {llm.get('verdict', '—')}",
        "",
        "## Breakdown",
        "",
        "| Dimension | Score |",
        "|---|---|",
    ]
    for dim in RUBRIC_DIMENSIONS:
        lines.append(f"| {dim.replace('_', ' ').title()} | "
                     f"{llm.get('breakdown', {}).get(dim, 0)} |")
    lines += [
        f"| ATS keyword coverage | {det['ats_keyword_score']} |",
        "",
        f"## Keywords matched ({len(det['keywords_matched'])} shown)",
        ", ".join(det["keywords_matched"]) or "—",
        "",
        "## Keywords missing (top)",
        ", ".join(det["keywords_missing_top"]) or "—",
        "",
        "## Strengths",
    ]
    lines += [f"- {s}" for s in llm.get("strengths", [])] or ["- —"]
    lines += ["", "## Gaps"]
    lines += [f"- {g}" for g in llm.get("gaps", [])] or ["- —"]
    lines += ["", "## Recommendations"]
    lines += [f"- {r}" for r in llm.get("recommendations", [])] or ["- —"]
    md_path.write_text("\n".join(lines))
    return json_path, md_path


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40] \
        or "unknown"


# -------------------------------------------------------------------- main --

def run_scoring(args: argparse.Namespace) -> int:
    if getattr(args, "spec_file", None):
        spec = json.loads(Path(args.spec_file).read_text())
        kind, payload = spec.get("kind", "text"), spec.get("payload", "")
        resume_path = spec["resume"]
    else:
        kind = "url" if args.url else ("file" if args.jd_file else "text")
        payload = args.url or args.jd_file or args.jd_text or ""
        resume_path = args.resume
        if not payload:
            raise RuntimeError("no JD given (--jd-text/--jd-file/--url)")

    resume_text = load_resume_text(resume_path)
    resume_name = Path(resume_path).name
    log(f"resume loaded: {resume_name} ({len(resume_text)} chars)")

    jd = load_jd(kind, payload)
    jd_desc = jd.get("description") or payload if kind == "text" else \
        jd.get("description", "")
    log(f"JD loaded: {jd.get('title')!r} @ {jd.get('company')!r} "
        f"({len(jd_desc)} chars)")

    det = deterministic_scores(jd_desc, resume_text)
    log(f"deterministic ATS keyword score: {det['ats_keyword_score']}")

    llm = llm_evaluation(jd_desc, jd.get("title", ""), jd.get("company", ""),
                         resume_name, resume_text)
    final = blended(det["ats_keyword_score"], llm.get("overall_fit", 0))
    log(f"LLM overall fit: {llm.get('overall_fit')}  -> FINAL {final}/100")

    result = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "resume_name": resume_name,
        "resume_path": str(Path(resume_path).resolve()),
        "resume_stem": Path(resume_path).stem,
        "company": jd.get("company", ""),
        "company_slug": slug(jd.get("company", "")),
        "title": jd.get("title", ""),
        "jd_source": kind,
        "deterministic": det,
        "llm": llm,
        "evaluation": {"final": final},
    }
    json_path, md_path = write_report(result)
    log(f"report written: {json_path.name}")

    # Machine-readable summary last so callers (and the UI log panel) can parse.
    print("SCORE_RESULT_JSON=" + json.dumps({
        "final": final,
        "ats_keywords": det["ats_keyword_score"],
        "llm_overall": llm.get("overall_fit", 0),
        "verdict": llm.get("verdict", ""),
        "missing_top": det["keywords_missing_top"][:10],
        "report_md": str(md_path),
        "report_json": str(json_path),
    }))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jd-text", help="pasted JD text")
    p.add_argument("--jd-file", help="path to a JD text/markdown file")
    p.add_argument("--url", help="posting URL (Greenhouse/Lever/Ashby APIs)")
    p.add_argument("--resume", required=True, help=".tex/.md/.pdf resume path")
    p.add_argument("--spec-file",
                   help="JSON spec {kind,payload,resume}; overrides the above")
    args = p.parse_args(argv)
    try:
        return run_scoring(args)
    except Exception as exc:  # noqa: BLE001 - single-line failure for the UI
        log(f"FATAL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
