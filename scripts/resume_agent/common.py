"""Shared assets, LLM chain, and QA gates for the resume agent.

Reuses proven pieces of scripts/tailor_from_jd.py (provider chain shape,
banned-term patterns, LaTeX letter renderer) but restructured into the
spec-004 stage contracts. All authority files live under
<data_root>/resume_custom/ and <data_root>/profile_info/.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:  # pragma: no cover - direct-script import shape
    import config_lib

DATA = config_lib.data_root()

# --- canonical assets ------------------------------------------------------
BASE_VARIANTS = DATA / "resume_custom" / "base_variants"
EVIDENCE_MD = DATA / "resume_custom" / "evidence" / "EVIDENCE_LIBRARY.md"
ROLE_FAMILIES_MD = DATA / "resume_custom" / "rules" / "ROLE_FAMILIES.md"
BULLET_PATTERNS_MD = DATA / "resume_custom" / "rules" / "BULLET_PATTERNS.md"
KEYWORD_BANK_MD = DATA / "resume_custom" / "rules" / "KEYWORD_BANK.md"
CHECKLIST_MD = DATA / "resume_custom" / "rules" / "SMALL_LLM_CHECKLIST.md"
JD_ACTIVE_DIR = DATA / "tracking" / "job_descriptions" / "active"
APPLICATIONS_DIR = REPO / "all_custom_resumes"
STYLE_SRC = BASE_VARIANTS / "resume_style.sty"

FAMILY_TEMPLATE = {
    "research_engineer_agentic": "base_agentic_ai",
    "ai_engineer": "base_agentic_ai",
    "research_engineer_llm_reasoning": "base_agent_reasoning",
    "general_research_engineer": "base_agent_reasoning",
    "research_engineer_post_training": "base_agent_reasoning",
    "ml_engineer": "base_applied_ml",
    "applied_scientist": "base_applied_ml",
    "ml_systems_inference": "base_eval_inference",
    "research_engineer_multimodal_vlm": "base_eval_inference",
    "research_scientist": "base_eval_inference",
    "ai_security": "base_applied_ml",
}
# Page policy per family (spec 004 §6): default 1 page.
TWO_PAGE_FAMILIES = {
    "research_engineer_llm_reasoning", "research_engineer_multimodal_vlm",
    "research_scientist",
}
HARD_STOP_FAMILIES = {"research_engineer_post_training", "research_scientist"}

FAMILY_KEYWORDS = {
    "research_engineer_agentic": ["agent", "agentic", "tool use", "function calling",
                                  "orchestration", "langgraph", "langchain",
                                  "multi-agent", "workflow", "rag"],
    "research_engineer_llm_reasoning": ["reasoning", "planning", "inference-time",
                                        "search", "verifier", "long-horizon",
                                        "code generation"],
    "research_engineer_post_training": ["post-training", "rlhf", "dpo", "ppo",
                                        "grpo", "sft", "preference", "reward model"],
    "research_engineer_multimodal_vlm": ["vision-language", "multimodal", "vlm",
                                         "video", "image understanding", "cross-modal"],
    "applied_scientist": ["applied scientist", "experimentation", "productionize",
                          "model quality"],
    "research_scientist": ["research scientist", "publications", "novel methods"],
    "ml_engineer": ["machine learning engineer", "production ml", "pipeline",
                    "deployment", "feature engineering"],
    "ai_engineer": ["ai engineer", "llm application", "rag", "product integration",
                    "eval loop"],
    "ml_systems_inference": ["inference optimization", "serving", "vllm", "tensorrt",
                             "triton", "gpu cluster", "slo", "sla", "routing"],
    "ai_security": ["adversarial", "red team", "ml security", "model security",
                    "jailbreak"],
    "general_research_engineer": ["research engineer"],
}

BANNED_TIER_1 = [
    "14-agent", "blackboard", "BLEU +18%", "CLIPScore +22%", "100K+",
    "~30% lower cost", "RouteLLM", "RLHF", "RLAIF", "DPO", "GRPO", "arXiv",
    "6+ VLM",
]
FINE_TUNING_ALLOWED_CONTEXT = re.compile(r"(Qwen|LoRA)", re.IGNORECASE)
CL_BANNED = ["rlhf", "rlaif", "dpo", "sft", "qlora", "lora", "grpo", "deepspeed",
             "jax", "kubernetes", "spark", "hive", "scala"]


def log(msg: str) -> None:
    print(f"[agent] {msg}", flush=True)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "job"


# ---------------------------------------------------------------------------
# LLM provider chain (same shape as tailor_from_jd.llm_chat; SDK clients only)
# ---------------------------------------------------------------------------

def llm_config() -> list[dict]:
    """Provider chain for LLM calls; delegates to ``config_lib.llm_config()``.

    Single source of truth lives in config_lib (openrouter first, then nvidia,
    then custom — small-model chain). Kept as a thin wrapper so module-level
    references and tests keep working unchanged.
    """
    return config_lib.llm_config()


def llm_chat(messages: list[dict], temperature: float = 0.3,
             max_tokens: int | None = None) -> str:
    from openai import OpenAI

    last_err: Exception | None = None
    for prov in llm_config():
        for i, model in enumerate(prov["models"]):
            timeout = 420 if i == 0 else 90
            try:
                client = OpenAI(base_url=prov["base_url"], api_key=prov["key"],
                                timeout=timeout, max_retries=0)
                t0 = time.time()
                kwargs: dict = {"model": model, "messages": messages,
                                "temperature": temperature}
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens
                resp = client.chat.completions.create(**kwargs)
                content = (resp.choices[0].message.content or "").strip()
                if not content:
                    raise RuntimeError("empty completion")
                log(f"llm ok: {prov['name']}/{model} in {time.time()-t0:.0f}s "
                    f"({len(content)} chars)")
                return content
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                log(f"llm miss: {prov['name']}/{model}: {type(exc).__name__}")
    raise RuntimeError(f"no LLM provider responded: {last_err}")


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    depth = 0
    instr = esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            instr = not instr
            continue
        if instr:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON in reply")


# ---------------------------------------------------------------------------
# Deterministic QA gates (spec 004 S4 + §8 ATS round-trip)
# ---------------------------------------------------------------------------

def sanitize_tex(tex: str) -> tuple[str, list[str]]:
    """Escape bare % (not already a comment or \\%) outside verbatim contexts.

    The JD corpus is percentage-heavy; the drafter routinely emits '27%'
    which LaTeX reads as a comment start and swallows the closing brace
    (observed on Tessera run 1). Deterministic fix, no LLM round-trip.
    Returns (fixed_tex, fixes) where fixes describes each change.
    """
    fixes = []
    out_lines = []
    for ln_no, line in enumerate(tex.split("\n"), 1):
        if line.lstrip().startswith("%"):
            out_lines.append(line)  # real comment — leave alone
            continue
        fixed_line = []
        i = 0
        changed = False
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                fixed_line.append(line[i:i + 2])  # keep escaped pairs intact
                i += 2
                continue
            if ch == "%":
                fixed_line.append(r"\%")
                changed = True
                continue
            fixed_line.append(ch)
            i += 1
        if changed:
            fixes.append(f"line {ln_no}: escaped bare %")
        out_lines.append("".join(fixed_line))
    return "\n".join(out_lines), fixes


def factuality_gate(tex: str) -> list[str]:
    violations = []
    for pat in BANNED_TIER_1:
        if re.search(re.escape(pat), tex, re.IGNORECASE):
            violations.append(f"tier-1 banned term: {pat}")
    for m in re.finditer(r"fine-tun\w*|QLoRA|\bSFT\b", tex, re.IGNORECASE):
        ctx = tex[max(0, m.start() - 160):m.end() + 160]
        if not FINE_TUNING_ALLOWED_CONTEXT.search(ctx):
            violations.append(
                f"fine-tuning-family term outside allowed context: {m.group(0)!r}")
    return violations


def number_audit(tex: str, evidence_text: str) -> list[str]:
    """Every numeral token in the .tex must exist in the selected evidence."""
    ev_nums = set(re.findall(r"\d[\d,.]*\d|\d", evidence_text))
    body = strip_latex(tex)
    missing = []
    # Skip header/contact/date boilerplate numbers (phone, zip, GPA years).
    allowed = {"404", "740", "9905", "30332", "11", "10"}
    for tok in sorted(set(re.findall(r"\d[\d,.]*%?x?|\d+", body))):
        clean = tok.rstrip("%x").replace(",", "")
        if clean in allowed or clean in {n.replace(",", "") for n in ev_nums}:
            continue
        missing.append(tok)
    return missing


def compile_tex(tex_path: Path, out_dir: Path) -> tuple[Path, list[str]]:
    """pdflatex x2; returns (pdf_path, warnings)."""
    style_dst = out_dir / "resume_style.sty"
    if not style_dst.exists():
        style_dst.write_text(STYLE_SRC.read_text())
    env = {**os.environ, "PATH": "/Library/TeX/texbin:" + os.environ.get("PATH", "")}
    warn = []
    for _ in range(2):
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_path.name],
            cwd=out_dir, capture_output=True, text=True, env=env, timeout=180)
        if result.returncode != 0:
            tail = "\n".join(result.stdout.splitlines()[-30:])
            raise RuntimeError(f"pdflatex failed:\n{tail}")
    log_file = out_dir / (tex_path.stem + ".log")
    if log_file.exists():
        warn = [ln for ln in log_file.read_text(errors="replace").splitlines()
                if re.match(r"^(Overfull|Underfull)", ln)]
    pdf = out_dir / (tex_path.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("PDF not produced")
    return pdf, warn


def check_page_count(pdf_path: Path) -> int:
    out = subprocess.run(["pdftotext", str(pdf_path), "-"],
                         capture_output=True, text=True, timeout=30)
    return max(out.stdout.count("\f"), 1) if out.stdout.strip() else -1


def orphan_lines(pdf_path: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"],
                         capture_output=True, text=True, timeout=30)
    bad = []
    for i, ln in enumerate(out.stdout.splitlines(), 1):
        words = [w for w in ln.split() if w]
        if len(words) <= 2 and words:
            low = ln.lower()
            if any(k in low for k in ("georgia", "atlanta", "experience",
                                      "education", "skills")) or (
                    config_lib.identity_line("first_name").lower() in low or
                    config_lib.identity_line("full_name").lower() in low):
                continue  # headers exempt
            bad.append(f"{i}: {ln.strip()}")
    return bad


def ats_roundtrip(pdf_path: Path, plan: dict) -> list[str]:
    """Spec 004 §8: verify pdftotext extraction of the final PDF."""
    out = subprocess.run(["pdftotext", str(pdf_path), "-"],
                         capture_output=True, text=True, timeout=30)
    text = out.stdout
    problems = []
    _email = config_lib.identity_line("email").lower()
    if not _email or _email not in text.replace(" ", "").lower():
        problems.append("email not extractable from PDF")
    for kd in plan.get("keyword_dispositions", []):
        if kd.get("disposition") == "integrated":
            term = kd.get("term", "")
            if term and term.lower() not in text.lower():
                problems.append(f"integrated keyword missing from PDF text: {term}")
    return problems


def cl_gate(text: str) -> list[str]:
    low = text.lower()
    bad = []
    for b in CL_BANNED:
        if re.search(rf"\b{re.escape(b)}\b", low):
            bad.append(b)
    if re.search(r"fine-tun", low):
        bad.append("fine-tuning family")
    if re.search(r"reward\s+model", low):
        bad.append("reward model")
    return bad


def strip_latex(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}]", "", text)
    return re.sub(r"\s+", " ", text)


def render_letter_tex(role_title: str, company: str, letter_body: str) -> str:
    """House LaTeX letter format (reused from tailor_from_jd)."""
    def esc(s: str) -> str:
        s = s.replace("\\", "").replace("&", r"\&").replace("%", r"\%")
        s = s.replace("#", r"\#").replace("_", r"\_").replace("$", r"\$")
        return s

    paras = [p.strip() for p in re.split(r"\n\s*\n", letter_body) if p.strip()]

    def _is_meta(p: str) -> bool:
        low = p.lower()
        return (low.startswith(("dear ", "hello,", "hi,", "to whom")) or
                low.startswith(("sincerely", "best regards", "best,", "regards",
                                "thank you for your consideration,")))

    paras = [p for p in paras if not _is_meta(p)]
    if not paras:
        raise RuntimeError("cover letter came back empty")
    body = "".join("\\letterPara{%s}\n\n" % esc(p) for p in paras)
    _ident = config_lib.identity()
    header = (
        "\\documentclass[letterpaper,11pt]{article}\n"
        "\\usepackage{resume_style}\n"
        "\\newcommand{\\letterPara}[1]{\\noindent #1 \\vspace{10pt}}\n"
        "\\begin{document}\n\n"
        "\\begin{center}\n"
        f"  {{\\LARGE \\scshape {_ident.get('full_name', '')}}} \\\\ \\vspace{{4pt}}\n"
        f"  \\small \\href{{mailto:{_ident.get('email', '')}}}{{{_ident.get('email', '')}}}"
        f" \\;|\\; {_ident.get('phone', '')} \\;|\\; {_ident.get('location', '')} \\\\ \\vspace{{2pt}}\n"
        f"  \\small {_ident.get('degree', '')}, {_ident.get('school', '')}\n"
        "\\end{center}\n"
        "\\vspace{-8pt}\n\n"
        "\\hfill \\small \\today\n\n"
        "\\noindent Dear Hiring Team at %s,\n\n" % esc(company)
    )
    subject = "\\noindent \\textbf{Re: %s}\n\n" % esc(role_title)
    closing = ("\\noindent Sincerely,\\\\[4pt] "
               f"{_ident.get('signature_name') or _ident.get('full_name', '')}"
               "\n\n\\end{document}\n")
    return header + subject + body + closing
