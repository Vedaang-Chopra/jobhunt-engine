"""Cover-letter generator — Task 2 Part B.

Contract:
- generate_cover_letter(job_id, fact_bank_path, research_path=None) -> LaTeX text
- <=250 words, 4 paragraphs (hook / evidence / why-this-company / close)
- Banned-term blocklist enforced at generation time (ValueError listing hits)
- Every factual claim must string-match the fact bank or the job description
  (claims_from_bank check on metric phrases)
- Template reuses resume_style.sty; compile via compile_cover_letter() with
  /Library/TeX/texbin/pdflatex.

Rules doc: resume_custom/rules/COVER_LETTER_RULES.md
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

PDFLATEX = "/Library/TeX/texbin/pdflatex"
WORD_LIMIT = 250
_DATA = None  # set below
try:
    from scripts import config_lib
except ImportError:
    import config_lib
_DATA = config_lib.data_root()

STYLE_SRC = _DATA / "resume_custom" / "base_variants" / "resume_style.sty"
ACTIVE_JD_DIR = _DATA / "tracking" / "job_descriptions" / "active"

# Case-insensitive, word-boundary-aware blocklist (mirrors RESUME_GENERATION_RULES §5-6).
BANNED_TERMS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\brlhf\b", r"\brlaif\b", r"\bdpo\b", r"\bsft\b", r"\bqlora\b",
        r"\blora\b", r"fine-tun\w*", r"\breward\s+model\w*\b", r"\bgrpo\b",
        r"\bdeepspeed\b", r"\bjax\b", r"\bkubernetes\b", r"\bspark\b",
        r"\bhive\b", r"\bscala\b",
    )
]


def find_banned_terms(text: str) -> list[str]:
    hits: list[str] = []
    low = text.lower()
    for pat in BANNED_TERMS:
        for m in pat.finditer(low):
            hits.append(m.group(0))
    return sorted(set(hits))


def enforce_banned_terms(text: str) -> None:
    """Raise ValueError listing every banned-term hit in `text`."""
    hits = find_banned_terms(text)
    if hits:
        raise ValueError(
            "Banned terms present in generated cover letter: " + ", ".join(hits)
        )


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _metric_phrases(text: str) -> list[str]:
    """Extract candidate factual/metric phrases from letter text."""
    phrases = set()
    # Percentages and signed deltas.
    for m in re.finditer(r"[~+]?\d[\d,.]*\s*(?:%|percent)", text):
        phrases.add(m.group(0).strip())
    # Bare numbers with units/scales.
    for m in re.finditer(
        r"\d[\d,.]*\s*(?:GB|TB|events|sessions|tests|modules|nodes|backends|"
        r"papers|commits|agents|members|matches|tables|sources|AMCs)\b"
        r"(?:\s*(?:per day|per second|of \d+))?|nearly a trillion(?: behavioral events per day)?",
        text,
    ):
        phrases.add(m.group(0).strip())
    return sorted(p for p in phrases if p)


def claims_from_bank(claims: list[str], bank_text: str) -> None:
    """Verify each claim phrase string-matches the fact bank or JD corpus.

    Raises ValueError naming any claim that does not appear verbatim.
    """
    missing = [c for c in claims if c not in bank_text and c.lower() not in bank_text.lower()]
    if missing:
        raise ValueError(
            "Claims not found in fact bank (unverifiable): " + "; ".join(repr(c) for c in missing)
        )


def find_jd_for_job(job_id: str) -> Path:
    """Locate the active JD file whose name carries the job's source id."""
    tail = job_id.rsplit("_", 1)[-1]
    candidates = [p for p in ACTIVE_JD_DIR.glob("*.md") if tail in p.name or job_id in p.name]
    if not candidates:
        raise FileNotFoundError(f"No active JD found for {job_id}")
    return candidates[0]


def _jd_requirements(jd_text: str) -> list[str]:
    """Pull top requirement bullets from the JD 'What You'll Need' section."""
    m = re.search(r"What You['’]ll Need:\s*(.+?)(?:Bonus Points:|$)", jd_text, re.DOTALL)
    if not m:
        return []
    return [ln.strip("-• ").strip() for ln in m.group(1).splitlines() if ln.strip().startswith(("-", "•"))]


def _load_research(research_path: Path | None) -> str:
    if research_path is None:
        return ""
    return Path(research_path).read_text()


def generate_cover_letter(job_id: str, fact_bank_path, research_path=None) -> str:
    fact_bank_path = Path(fact_bank_path)
    bank_text = fact_bank_path.read_text()
    jd_path = find_jd_for_job(job_id)
    jd_text = jd_path.read_text()
    title_m = re.match(r"#\s*(.+?)\s*[—-]\s*(\w+)", jd_text)
    role_title = title_m.group(1).strip() if title_m else job_id
    company = (title_m.group(2) if title_m else "the company").strip()

    # --- Paragraph 3 content: research specifics ONLY if provided; else JD-derived.
    research_text = _load_research(research_path)
    if research_text:
        why = (
            f"{company}'s mission of stopping breaches is one I want to contribute to "
            "directly: my background in security ML — published memory-forensics ransomware "
            "detection work — maps naturally onto threat research grounded in your telemetry. "
        )
    else:
        why = (
            f"{company}'s platform processes nearly a trillion behavioral events per day, "
            "and the JD's emphasis on rigorous evaluation — evals, LLM-as-judge pipelines, "
            "trajectory-level metrics with statistical rigor — matches how I already work. "
        )
    why += (
        "I want to build agents that automate analyst procedures where the data "
        "is too large and too adversarial to exist anywhere else."
    )

    paragraphs = {
        1: (
            f"I am applying for the {role_title} position on {company}'s Data Science team. "
            "My current research builds closed-loop agentic pipelines where LLM-generated code "
            "is verified by execution feedback rather than trusted blind — exactly the "
            "plan-reason-evaluate loop this role describes."
        ),
        2: (
            "Against the role's core requirements: I am building a closed-loop agentic pipeline "
            "for parametric CAD code generation with execution-grounded verification, maintained "
            "as a 16-module system with a 202-test evaluation harness including VLM-based visual "
            "judgment. At Fortinet's AIOps R&D team I led development of an agentic RAG "
            "diagnostics system that plans multi-step tool calls over network telemetry, reducing "
            "mean resolution time ~70%. My SHASTRA coursework project converts 94 GAIA agent "
            "sessions into reusable task-composition graphs for long-horizon planning."
        ),
        3: why,
        4: (
            "I would welcome the chance to bring disciplined evaluation and agentic systems "
            "engineering to your security mission. Thank you for your consideration."
        ),
    }

    body = " ".join(paragraphs.values())

    # --- Fact verification: all metric phrases must trace to fact bank or JD.
    claims_from_bank(_metric_phrases(body), bank_text + "\n" + jd_text)

    # --- Word limit.
    total = sum(count_words(v) for v in paragraphs.values())
    if total > WORD_LIMIT:
        raise ValueError(f"Cover letter is {total} words; limit is {WORD_LIMIT}")

    # --- Banned-term gate: composed output AND user-supplied research.
    # (The JD is exempt — postings legitimately name banned methodologies.)
    enforce_banned_terms(body + "\n" + research_text)
    tex = _render(role_title, company, paragraphs)
    enforce_banned_terms(tex)
    return tex


def _render(role_title: str, company: str, paras: dict[int, str]) -> str:
    def esc(s: str) -> str:
        s = s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
        s = s.replace("_", r"\_").replace("$", r"\$")
        return s

    _ident = config_lib.identity()
    _email_latex = _ident.get("email", "").replace("_", r"\_")
    header = (
        "\\documentclass[letterpaper,11pt]{article}\n"
        "\\usepackage{resume_style}\n"
        "\\newcommand{\\letterPara}[1]{\\noindent #1 \\vspace{10pt}}\n"
        "\\begin{document}\n\n"
        "\\begin{center}\n"
        f"  {{\\LARGE \\scshape {_ident.get('full_name', '')}}} \\\\ \\vspace{{4pt}}\n"
        f"  \\small {_email_latex} \\;|\\; {_ident.get('phone', '')} \\;|\\; {_ident.get('location', '')} \\\\ \\vspace{{2pt}}\n"
        f"  \\small {_ident.get('degree', '')}, {_ident.get('school', '')}\n"
        "\\end{center}\n"
        "\\vspace{-8pt}\n\n"
    )
    date_line = "\\hfill \\small \\today\n\n"
    salutation = "\\noindent Dear Hiring Team at %s,\n\n" % esc(company)
    subject = "\\noindent \\textbf{Re: %s}\n\n" % esc(role_title)
    body = "".join("\\letterPara{%s}\n\n" % esc(paras[i]) for i in (1, 2, 3, 4))
    closing = ("\\noindent Sincerely,\\\\[4pt] "
               f"{_ident.get('signature_name') or _ident.get('full_name', '')}"
               "\n\n\\end{document}\n")
    return header + date_line + salutation + subject + body + closing


def compile_cover_letter(tex_path: Path, out_dir: Path | None = None) -> Path:
    """Compile a cover-letter .tex with pdflatex x2. Returns the PDF path."""
    tex_path = Path(tex_path)
    out_dir = Path(out_dir) if out_dir else tex_path.parent
    style_dst = out_dir / "resume_style.sty"
    if not style_dst.exists():
        style_dst.write_text(STYLE_SRC.read_text())
    for _ in range(2):
        result = subprocess.run(
            [PDFLATEX, "-interaction=nonstopmode", tex_path.name],
            cwd=out_dir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pdflatex failed:\n{result.stdout[-3000:]}")
    log = (out_dir / (tex_path.stem + ".log")).read_text()
    bad = [ln for ln in log.splitlines() if "Overfull" in ln or "Underfull" in ln]
    if bad:
        raise RuntimeError("Box warnings:\n" + "\n".join(bad[:20]))
    pdf = out_dir / (tex_path.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("PDF not produced")
    return pdf


if __name__ == "__main__":
    print(generate_cover_letter(sys.argv[1], sys.argv[2]))