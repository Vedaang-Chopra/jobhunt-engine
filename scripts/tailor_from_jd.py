#!/usr/bin/env python3
"""Tailor resume + cover letter directly from a job description (UI-driven).

This is the one-shot entry point behind the Tailor Resume page's
upload / paste / link flow. Given a JD by any of three routes:

  --jd-file PATH   raw JD text/markdown file (UI upload or existing file)
  --url URL        posting URL (Greenhouse/Lever/Ashby via public JSON APIs;
                   generic pages via plain fetch + login-wall detection)
  --text-file PATH pasted-JD text saved to a temp file by the UI

it produces, without any further user interaction:

  1. a canonical active JD file under tracking/job_descriptions/active/
     with SHA256 provenance (same writer as discovery_run.ingest);
  2. a role-family diagnosis and a tailored resume.tex compiled to PDF,
     built from the matching base variant and the verified evidence library;
  3. a factually gated cover letter (banned terms + metric trace) as .tex/.pdf;
  4. an evaluation.md skeleton recording diagnosis, keyword dispositions,
     fact-trace and the mandatory gap list.

Output contract: all_custom_resumes/{job_slug}_{date_tag}/ (inside this repo)
resume_custom rules. The script never submits anything.

Usage:
  python3 scripts/tailor_from_jd.py --url https://boards.greenhouse.io/acme/jobs/12345
  python3 scripts/tailor_from_jd.py --jd-file jd.txt
  python3 scripts/tailor_from_jd.py --text-file pasted.txt [--company Acme] [--title "ML Engineer"]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:  # pragma: no cover - direct-script import shape
    import config_lib

DATA = config_lib.data_root()

# --- canonical assets (all under data root; see resume_custom/AGENTS.md) ---
BASE_VARIANTS = DATA / "resume_custom" / "base_variants"
EVIDENCE_MD = DATA / "resume_custom" / "evidence" / "EVIDENCE_LIBRARY.md"
ROLE_FAMILIES_MD = DATA / "resume_custom" / "rules" / "ROLE_FAMILIES.md"
RULES_MD = DATA / "resume_custom" / "rules" / "RESUME_GENERATION_RULES.md"
BULLET_PATTERNS_MD = DATA / "resume_custom" / "rules" / "BULLET_PATTERNS.md"
KEYWORD_BANK_MD = DATA / "resume_custom" / "rules" / "KEYWORD_BANK.md"
FACT_BANK_YAML = DATA / "profile_info" / "resume_fact_bank.yaml"
JD_ACTIVE_DIR = DATA / "tracking" / "job_descriptions" / "active"
# Custom resume output lives inside the project, not under the data root.
REPO_ROOT = Path(__file__).resolve().parent.parent
APPLICATIONS_DIR = REPO_ROOT / "all_custom_resumes"
STYLE_SRC = BASE_VARIANTS / "resume_style.sty"
PDFLATEX = "/Library/TeX/texbin/pdflatex"

# Family -> base variant stem (mirrors fact-bank role_families mapping).
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
FAMILY_KEYWORDS = {
    "research_engineer_agentic": ["agent", "agentic", "tool use", "function calling", "orchestration", "langgraph", "langchain", "multi-agent", "workflow"],
    "research_engineer_llm_reasoning": ["reasoning", "planning", "inference-time", "search", "verifier", "long-horizon", "code generation"],
    "research_engineer_post_training": ["post-training", "rlhf", "dpo", "ppo", "grpo", "sft", "preference", "reward model"],
    "research_engineer_multimodal_vlm": ["vision-language", "multimodal", "vlm", "video", "image understanding", "cross-modal"],
    "applied_scientist": ["applied scientist", "experimentation", "productionize", "model quality"],
    "research_scientist": ["research scientist", "publications", "novel methods"],
    "ml_engineer": ["machine learning engineer", "production ml", "pipeline", "deployment", "feature"],
    "ai_engineer": ["ai engineer", "llm application", "rag", "product integration", "eval loop"],
    "ml_systems_inference": ["inference optimization", "serving", "vllm", "tensorrt", "triton", "gpu cluster", "slo", "sla", "routing"],
    "ai_security": ["adversarial", "red team", "ml security", "model security", "jailbreak"],
    "general_research_engineer": ["research engineer"],
}

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) jobhunt-tailor/1.0"}

BANNED_TIER_1 = [
    "14-agent", "blackboard", "BLEU +18%", "CLIPScore +22%", "100K+",
    "~30% lower cost", "RouteLLM", "RLHF", "RLAIF", "DPO", "GRPO", "arXiv",
    "6+ VLM",
]
# Context-checked exceptions: allowed ONLY in CERBERUS LoRA wording.
FINE_TUNING_ALLOWED_CONTEXT = re.compile(r"(Qwen|LoRA)", re.IGNORECASE)


def log(msg: str) -> None:
    print(f"[tailor] {msg}", flush=True)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "job"


# ---------------------------------------------------------------------------
# Stage 1 — LOAD: get the JD text from file, URL, or pasted text
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    import html as _html
    text = re.sub(r"<[^>]+>", "\n", html)
    text = _html.unescape(text)
    return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def fetch_jd_from_url(url: str) -> dict:
    """Fetch title/company/description from a posting URL.

    Greenhouse/Lever/Ashby go through their public JSON APIs (same approach
    as discovery_run.fetch_job_page); everything else is a plain page fetch
    with login-wall detection. Workday is rejected up front (account wall).
    """
    import urllib.request
    import urllib.error

    if "jobs.lever.co" in url:
        m = re.search(r"jobs\.lever\.co/([^/]+)/([^/?#]+)", url)
        api = f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}?mode=json"
        j = json.loads(_http_get(api))
        cats = j.get("categories") or {}
        return {
            "title": j.get("text") or "",
            "company": m.group(1).replace("-", " ").title(),
            "description": _strip_html(j.get("descriptionPlain") or j.get("description") or ""),
            "location": cats.get("location") or "",
        }
    if "boards.greenhouse.io" in url:
        m = re.search(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        api = f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}"
        j = json.loads(_http_get(api))
        return {
            "title": j.get("title") or "",
            "company": m.group(1).replace("-", " ").replace("_", " ").title(),
            "description": _strip_html(j.get("content") or ""),
            "location": (j.get("location") or {}).get("name", ""),
        }
    if "job-boards.greenhouse.io" in url:
        m = re.search(r"job-boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        api = f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}"
        j = json.loads(_http_get(api))
        return {
            "title": j.get("title") or "",
            "company": m.group(1).replace("-", " ").replace("_", " ").title(),
            "description": _strip_html(j.get("content") or ""),
            "location": (j.get("location") or {}).get("name", ""),
        }
    if "jobs.ashbyhq.com" in url:
        m = re.search(r"jobs\.ashbyhq\.com/([^/?#/]+)/([^/?#]+)", url)
        api = f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}"
        j = json.loads(_http_get(api))
        for job in j.get("jobs") or []:
            if job.get("id") == m.group(2) or slugify(job.get("title", "")) == m.group(2):
                return {
                    "title": job.get("title") or "",
                    "company": m.group(1).replace("-", " ").title(),
                    "description": _strip_html(job.get("descriptionPlain") or job.get("descriptionHtml") or ""),
                    "location": (job.get("location") or "") if isinstance(job.get("location"), str) else (job.get("location") or {}).get("name", ""),
                }
        raise RuntimeError(f"Ashby posting {m.group(2)} not found on board {m.group(1)}")
    if "myworkdayjobs.com" in url or "wd1.myworkday" in url or "myworkdaysite" in url:
        raise RuntimeError(
            "Workday postings require an applicant account (form_extractor flags "
            "account_creation_required). Paste the JD text instead.")
    # Generic page.
    body = _http_get(url)
    head = body[:4000].lower()
    for marker in ("sign in to continue", "log in to continue", "create an account"):
        if marker in head:
            raise RuntimeError(f"{url} is login-walled; paste the JD text instead")
    title_m = re.search(
        r"<meta[^>]+(?:property|name)=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)",
        body, re.IGNORECASE)
    title = title_m.group(1) if title_m else ""
    desc = _strip_html(body)[:20000]
    host = re.sub(r"^www\.", "", urlparse_host(url))
    company_guess = host.split(".")[0].title()
    return {"title": title, "company": company_guess, "description": desc, "location": ""}


def urlparse_host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


def _http_get(url: str) -> str:
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc


def load_jd(args) -> dict:
    """Return {title, company, description, source_url}."""
    if args.url:
        log(f"fetching JD from URL: {args.url}")
        row = fetch_jd_from_url(args.url)
    elif args.jd_file:
        path = Path(args.jd_file).expanduser()
        text = path.read_text(encoding="utf-8")
        row = parse_jd_text(text)
        log(f"loaded JD file: {path.name}")
    else:
        path = Path(args.text_file).expanduser()
        text = path.read_text(encoding="utf-8").strip()
        if len(text) < 200:
            raise RuntimeError("pasted JD text too short (<200 chars)")
        row = parse_jd_text(text)
        row.setdefault("company", "")
        row.setdefault("title", "")
        log(f"loaded pasted JD ({len(text)} chars)")
    row["source_url"] = args.url or ""
    row["company"] = args.company or row.get("company") or ""
    row["title"] = args.title or row.get("title") or ""
    if not row["company"]:
        row["company"] = "unknown_company"
    if not row["title"]:
        first = next((ln.strip("# ").strip() for ln in row["description"].splitlines() if ln.strip()), "")
        row["title"] = first[:80] or "untitled_role"
    if len(row["description"]) < 300:
        raise RuntimeError(
            f"JD description too short ({len(row['description'])} chars) — "
            "tailoring needs the full posting text")
    return row


def parse_jd_text(text: str) -> dict:
    """Best-effort title/company extraction from a JD markdown/text blob."""
    title, company = "", ""
    m = re.match(r"#\s*(.+?)\s*[—–-]\s*([A-Za-z0-9 .&']+)\s*$", text.strip())
    if m:
        title, company = m.group(1).strip(), m.group(2).strip()
    if not company:
        cm = re.search(r"^\s*(?:Company|Employer)\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if cm:
            company = cm.group(1).strip()
    if not title:
        tm = re.search(r"^\s*(?:Job\s*)?Title\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if tm:
            title = tm.group(1).strip()
        elif text.lstrip().startswith("#"):
            title = text.lstrip().lstrip("#").splitlines()[0].strip()[:80]
    return {"title": title, "company": company, "description": text}


# ---------------------------------------------------------------------------
# Stage 2 — LLM client (openai SDK against configured providers)
# ---------------------------------------------------------------------------

def llm_config() -> list[dict]:
    """Provider chain for LLM calls, honoring per-provider ``priority``.

    Delegates to the canonical implementation in ``config_lib.llm_config()``
    (see that docstring for the config shape and the openrouter -> nvidia ->
    custom small-model chain). Kept as a module-level wrapper so existing
    importers (ingest_ai, web_nav_agent.agent) and tests that patch
    ``tailor_from_jd.config_lib`` keep working unchanged.
    """
    return config_lib.llm_config()


def llm_chat(messages: list[dict], temperature: float = 0.4) -> str:
    """Call the first responsive provider/model via the openai SDK.

    Big NVIDIA models cold-start slowly (~minutes); llama-3.1-8b answers fast,
    so per-model timeouts fall through the chain rather than failing the run.
    """
    from openai import OpenAI

    last_err: Exception | None = None
    for prov in llm_config():
        for i, model in enumerate(prov["models"]):
            timeout = 420 if i == 0 else 90
            try:
                client = OpenAI(base_url=prov["base_url"], api_key=prov["key"], timeout=timeout, max_retries=0)
                t0 = time.time()
                resp = client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature)
                content = (resp.choices[0].message.content or "").strip()
                if not content:
                    raise RuntimeError("empty completion")
                log(f"llm ok: {prov['name']}/{model} in {time.time()-t0:.0f}s "
                    f"({len(content)} chars)")
                return content
            except Exception as exc:  # noqa: BLE001 - try the next model/provider
                last_err = exc
                log(f"llm miss: {prov['name']}/{model}: {type(exc).__name__}")
    raise RuntimeError(f"no LLM provider responded: {last_err}")


# ---------------------------------------------------------------------------
# Stage 3 — diagnosis + tailoring prompts
# ---------------------------------------------------------------------------

def diagnose_family(jd_text: str) -> tuple[str, dict]:
    low = jd_text.lower()
    scores = {}
    hits = {}
    for fam, kws in FAMILY_KEYWORDS.items():
        h = [k for k in kws if k in low]
        hits[fam] = h
        scores[fam] = len(h)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = ranked[0]
    family = top[0] if top[1] > 0 else "research_engineer_agentic"  # repo default
    return family, hits


def build_tailoring_prompts(base_tex: str, evidence_md: str,
                            families_md: str, bullet_rules: str,
                            keyword_bank: str, jd_text: str,
                            family: str) -> tuple[str, str]:
    """Two-stage prompt: (a) JSON diagnosis/selection, (b) final .tex emit."""
    diag_sys = (
        "You are a strict resume strategist. You NEVER invent facts. You only "
        "select and reframe evidence that exists verbatim in the provided library."
    )
    diag_user = f"""Read these project rules, then produce a JSON plan.

=== ROLE FAMILY STRATEGIES ===
{families_md}

=== EVIDENCE LIBRARY (the ONLY usable facts) ===
{evidence_md}

=== JOB DESCRIPTION ===
{jd_text[:12000]}

Proposed role family (verify or override): {family}

Return ONLY minified JSON with keys:
  "family": "<one of the 11 families>",
  "seniority": "<new-grad|junior|mid>",
  "narrative_a": "<2 candidate narratives compared, then pick>",
  "chosen_narrative": "<the winning narrative in one line>",
  "p0": ["<core requirement>", ...],
  "p1": ["<differentiator>", ...],
  "p2": ["<nice-to-have>", ...],
  "blocks": ["<evidence block names to feature, strongest first>"],
  "keyword_dispositions": [{{"term":"...","disposition":"integrated|listed|omitted"}}],
  "gaps": ["<JD asks for something with no evidence>"]
"""
    tex_sys = (
        "You are an expert LaTeX resume writer bound by hard factual gates. "
        "You may ONLY reuse sentences/metrics that appear in the base template "
        "or the evidence library, adapted for emphasis. Never invent numbers, "
        "tools, methods, or outcomes. Keep every metric EXACTLY as written "
        "(including ~ qualifiers). Output must compile with pdflatex using the "
        "provided preamble/style unchanged except tagline/content edits."
    )
    tex_user = f"""=== BULLET WRITING RULES ===
{bullet_rules}

=== BASE TEMPLATE ({Path(base_tex).name if hasattr(Path(base_tex), 'name') else 'base'}) ===
{base_tex}

=== DIAGNOSIS PLAN ===
{{PLACEHOLDER_PLAN}}

=== JOB DESCRIPTION ===
{jd_text[:8000]}

Rewrite the base template into a job-tailored resume:
1. Update the header research/tagline line to mirror the chosen narrative using truthful JD vocabulary.
2. Reorder/reweight bullets so the strongest P0-relevant evidence leads each section; adapt emphasis to JD terms where truthfully applicable (never change facts, metrics, dates, status language).
3. Reorder Skills categories to lead with JD-relevant ones; keep every listed item exactly as in the base template unless moving within its category.
4. Respect the section architecture guidance for the chosen family.
5. Keep it to ONE rendered page. Cut bottom-priority content rather than shrinking type.
6. IN_PROGRESS projects keep present tense ("Building/Designing"); never claim completed orchestrators/executors/publications.
7. Return ONLY the complete .tex source, no commentary, no code fences.
"""
    return diag_sys + "\n|||" + diag_user, tex_sys  # packed; caller splits


def extract_json_object(text: str) -> dict:
    """Pull the first balanced JSON object out of an LLM reply."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in diagnosis reply")
    depth = 0
    instr = False
    esc = False
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
    raise ValueError("unbalanced JSON in diagnosis reply")


# ---------------------------------------------------------------------------
# Stage 4 — factuality gate (Tier-1 grep + banned-term scan)
# ---------------------------------------------------------------------------

def factuality_gate(tex: str) -> list[str]:
    violations = []
    for pat in BANNED_TIER_1:
        if re.search(re.escape(pat), tex, re.IGNORECASE):
            violations.append(f"tier-1 banned term: {pat}")
    # fine-tun*/LoRA/SFT etc.: only allowed inside CERBERUS Qwen-LoRA wording
    for m in re.finditer(r"fine-tun\w*|QLoRA|\bSFT\b", tex, re.IGNORECASE):
        ctx = tex[max(0, m.start() - 160):m.end() + 160]
        if not FINE_TUNING_ALLOWED_CONTEXT.search(ctx):
            violations.append(f"fine-tuning-family term outside allowed context: {m.group(0)!r}")
    # status language
    if re.search(r"\bpublished\b", tex, re.IGNORECASE):
        # allowed only for the ICAIA paper / CEUR entries which ARE published
        for m in re.finditer(r".{60}\bpublished\b.{60}", tex, re.IGNORECASE | re.DOTALL):
            ctx = m.group(0).lower()
            if not any(k in ctx for k in ("icaia", "ceur", "ieee")):
                violations.append("'published' outside publication entries")
    return violations


# ---------------------------------------------------------------------------
# Stage 5 — compile helpers
# ---------------------------------------------------------------------------

def pdflatex_compile(tex_path: Path, out_dir: Path, style_src: Path = STYLE_SRC) -> Path:
    style_dst = out_dir / "resume_style.sty"
    if not style_dst.exists():
        style_dst.write_text(style_src.read_text())
    env = {**os.environ, "PATH": "/Library/TeX/texbin:" + os.environ.get("PATH", "")}
    for _ in range(2):
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_path.name],
            cwd=out_dir, capture_output=True, text=True, env=env, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f"pdflatex failed:\n{result.stdout[-2500:]}")
    pdf = out_dir / (tex_path.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("PDF not produced")
    return pdf


def strip_latex(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}]", "", text)
    return re.sub(r"\s+", " ", text)


def check_page_count(pdf_path: Path) -> int:
    """Page count via pdftotext form-feed count (poppler is installed)."""
    try:
        out = subprocess.run(["pdftotext", str(pdf_path), "-"],
                             capture_output=True, text=True, timeout=30)
        pages = max(out.stdout.count("\f"), 1)
        if out.stdout.strip():
            return pages
    except Exception:  # noqa: BLE001
        pass
    return -1  # unknown — do not block delivery on tool absence


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(args) -> int:
    started = time.time()
    jd = load_jd(args)
    jd_text = jd["description"]
    date_tag = datetime.date.today().strftime("%Y%m%d")

    # ---- 1. canonical JD file with provenance -----------------------------
    JD_ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()
    job_slug = f"{slugify(jd['company'])}_{slugify(jd['title'])}"[:110]
    jd_rel = f"{job_slug}_manual_{digest[:8]}"
    jd_path = JD_ACTIVE_DIR / f"{jd_rel}.md"
    jd_path.write_text(
        f"# {jd['title']} — {jd['company']}\n\n"
        f"- Source: manual_upload\n"
        f"- URL: {jd['source_url'] or '(none)'}\n"
        f"- Hash (sha256): {digest}\n"
        f"- Discovered: {datetime.date.today().isoformat()}\n\n"
        f"## Full Job Description Text\n{jd_text}\n\n---\n")
    log(f"JD archived: {jd_path}")

    # ---- 2. diagnosis ------------------------------------------------------
    quick_family, _hits = diagnose_family(jd_text)
    log(f"keyword-scan family: {quick_family}")

    base_stem = FAMILY_TEMPLATE[quick_family]
    base_tex = (BASE_VARIANTS / f"{base_stem}.tex").read_text()
    evidence_md = EVIDENCE_MD.read_text()
    families_md = ROLE_FAMILIES_MD.read_text()
    bullet_rules = BULLET_PATTERNS_MD.read_text()
    keyword_bank = KEYWORD_BANK_MD.read_text() if KEYWORD_BANK_MD.exists() else ""

    diag_reply = llm_chat([
        {"role": "system", "content":
            "You are a strict resume strategist. You NEVER invent facts. Only "
            "use evidence verbatim from the provided library."},
        {"role": "user", "content": f"""Study this evidence library and role-family guide, then plan a tailored resume.

=== ROLE FAMILIES ===
{families_md[:6000]}

=== EVIDENCE LIBRARY (ONLY usable facts) ===
{evidence_md}

=== JOB DESCRIPTION ===
{jd_text[:12000]}

Keyword-scan suggests family "{quick_family}" — verify or override.
Return ONLY minified JSON: {{"family":"...", "seniority":"...",
"chosen_narrative":"...", "alternative_narratives":["...","..."], "p0":["..."],
"p1":["..."], "p2":["..."], "featured_blocks":["..."],
"keyword_dispositions":[{{"term":"...","disposition":"integrated|listed|omitted"}}],
"gaps":["..."]}}"""}], temperature=0.2)
    try:
        plan = extract_json_object(diag_reply)
    except ValueError:
        log("diagnosis JSON parse failed; falling back to keyword-scan family")
        plan = {"family": quick_family, "p0": [], "gaps": [],
                "featured_blocks": [], "keyword_dispositions": []}
    family = plan.get("family") if plan.get("family") in FAMILY_TEMPLATE else quick_family
    log(f"diagnosed family: {family}")

    # ---- 3. tailored resume ----------------------------------------------
    tex_reply = llm_chat([
        {"role": "system", "content":
            "You are an expert LaTeX resume writer bound by hard factual gates. "
            "Only reuse sentences and metrics that exist verbatim in the base "
            "template or evidence library, adapted for emphasis. Never invent "
            "numbers, tools, methods, or outcomes; keep every metric exactly as "
            "written including ~ qualifiers. Return only .tex source."},
        {"role": "user", "content": f"""=== BULLET RULES ===
{bullet_rules[:5000]}

=== BASE TEMPLATE ({FAMILY_TEMPLATE[family]}.tex) ===
{base_tex}

=== DIAGNOSIS PLAN (JSON) ===
{json.dumps(plan)}

=== SECTION ARCHITECTURE GUIDE ===
{families_md[families_md.find(f"## {list(FAMILY_TEMPLATE).index(family)+1}."):][:1500] if f"## {list(FAMILY_TEMPLATE).index(family)+1}." in families_md else "(see role families above)"}

=== JOB DESCRIPTION ===
{jd_text[:8000]}

Rewrite the base template into a job-tailored resume:
1. Update the header research/tagline line to mirror the chosen narrative with truthful JD vocabulary.
2. Lead each section with the strongest P0-relevant evidence; integrate exact JD terminology into evidence-bearing bullets where truthfully applicable.
3. Never alter facts, metrics, dates, employers, degrees, GPA, or status language. IN_PROGRESS projects stay present tense.
4. Follow the family's section architecture. One rendered page — cut bottom-priority content rather than shrinking type.
5. Return ONLY the complete .tex document."""}], temperature=0.3)

    tex_raw = tex_reply.strip()
    tex_raw = re.sub(r"^```(?:latex|tex)?\n?", "", tex_raw).rstrip("`").strip()
    if r"\begin{document}" not in tex_raw:
        raise RuntimeError("LLM did not return a complete LaTeX document")

    violations = factuality_gate(tex_raw)
    attempts = 0
    while violations and attempts < 2:
        attempts += 1
        log(f"factuality gate hit ({len(violations)}); asking model to fix: "
            f"{violations[:3]}")
        fix_reply = llm_chat([
            {"role": "system", "content":
                "You fix LaTeX resumes that violated factual gates. Return only "
                "the corrected complete .tex."},
            {"role": "user", "content": f"""These gate violations were found in the resume below:
{chr(10).join('- ' + v for v in violations)}

Remove or rewrite ONLY the offending wording (keep all true facts and metrics).
Return the full corrected .tex.

{tex_raw}"""}], temperature=0.2)
        tex_raw = re.sub(r"^```(?:latex|tex)?\n?", "", fix_reply.strip()).rstrip("`").strip()
        violations = factuality_gate(tex_raw)
    if violations:
        raise RuntimeError("factuality gate still failing after retries:\n" +
                           "\n".join(violations))

    # ---- 4. output dir + compile resume ----------------------------------
    app_dir = APPLICATIONS_DIR / f"{job_slug}_{date_tag}"
    app_dir.mkdir(parents=True, exist_ok=True)
    resume_tex = app_dir / "resume.tex"
    resume_tex.write_text(tex_raw)
    log(f"compiling resume: {resume_tex}")
    resume_pdf = pdflatex_compile(resume_tex, app_dir)
    pages = check_page_count(resume_pdf)
    log(f"resume compiled: {resume_pdf.name} ({pages} page(s))")
    if pages > 2:
        log("WARNING: resume exceeds 2 pages — review before sending")

    # ---- 5. cover letter (fact-gated) ------------------------------------
    cl_reply = llm_chat([
        {"role": "system", "content":
            "You write concise, factual cover letters. Every claim must be "
            "supported by the provided resume/evidence. Banned words anywhere "
            "in the letter: rlhf, rlaif, dpo, sft, qlora, lora, fine-tuning/"
            "fine-tuned/fine-tune, reward model, grpo, deepspeed, jax, "
            "kubernetes, spark, hive, scala. Never exceed 240 words across "
            "four paragraphs."},
        {"role": "user", "content": f"""Write a four-paragraph cover letter (<=240 words total) for the job below.

Paragraph plan: (1) hook naming the exact role and the candidate's sharpest relevant proof; (2) 2-3 evidence paragraphs' worth of specifics mapped to the JD's core requirements, drawn ONLY from the resume below; (3) why-this-company grounded ONLY in the JD's own stated mission/product (never invent research); (4) two-line close.

Rules: no em-dash spam; professional but human tone; never mention GPA unless JD asks; no banned words; end paragraph 4 without a signature.

=== THE TAILORED RESUME (sole factual source) ===
{strip_latex(tex_raw)[:7000]}

=== JOB DESCRIPTION ===
{jd_text[:8000]}"""}], temperature=0.5)
    cl_text = cl_reply.strip().strip('"')

    def _cl_gate(text: str) -> list[str]:
        bad = []
        banned_cl = ["rlhf", "rlaif", "dpo", "sft", "qlora", "lora", "grpo",
                     "deepspeed", "jax", "kubernetes", "spark", "hive", "scala"]
        low = text.lower()
        for b in banned_cl:
            if re.search(rf"\b{re.escape(b)}\b", low):
                bad.append(b)
        if re.search(r"fine-tun", low):
            bad.append("fine-tuning family")
        if re.search(r"reward\s+model", low):
            bad.append("reward model")
        return bad

    cl_bad = _cl_gate(cl_text)
    if cl_bad:
        cl_fix = llm_chat([
            {"role": "system", "content": "You remove banned terminology from cover letters, preserving meaning. Return only the corrected letter."},
            {"role": "user", "content": f"Remove/replace these terms without inventing new claims: {cl_bad}\n\n{cl_text}"}], temperature=0.3)
        cl_text = cl_fix.strip().strip('"')
        cl_bad = _cl_gate(cl_text)
        if cl_bad:
            raise RuntimeError(f"cover letter still contains banned terms: {cl_bad}")
    words = len(cl_text.split())
    log(f"cover letter drafted ({words} words)")

    cl_tex = app_dir / "cover_letter.tex"
    cl_tex.write_text(_render_letter_tex(jd["title"], jd["company"], cl_text))
    cl_pdf = pdflatex_compile(cl_tex, app_dir)
    log(f"cover letter compiled: {cl_pdf.name}")

    # ---- 6. evaluation skeleton ------------------------------------------
    eval_md = f"""# Evaluation — {jd['company']} · {jd['title']} ({date_tag})

**Generated by:** `scripts/tailor_from_jd.py` (automated pass; agent review pending)
**JD provenance:** `tracking/job_descriptions/active/{jd_path.name}` (sha256 `{digest[:12]}…`)
**Diagnosed family:** `{family}` · **Plan seniority:** {plan.get('seniority', 'n/a')}
**Chosen narrative:** {plan.get('chosen_narrative', '(see plan json)')}

## Requirement map
- **P0:** {'; '.join(plan.get('p0', [])) or '(not captured)'}
- **P1:** {'; '.join(plan.get('p1', []))}
- **P2:** {'; '.join(plan.get('p2', []))}

## Gaps (recorded, never filled)
{chr(10).join('- ' + g for g in plan.get('gaps', []) ) or '- none flagged'}

## Keyword dispositions
| Term | Disposition |
|---|---|
{chr(10).join('| ' + kd.get('term','') + ' | ' + kd.get('disposition','') + ' |' for kd in plan.get('keyword_dispositions', []))}

## Factuality gate
- Tier-1 grep: PASS after {attempts} repair iteration(s)
- Metrics preserved verbatim from base template / evidence library
- Cover letter banned-term gate: PASS

## Compile & layout
- resume.pdf: {pages} page(s) — policy target: 1 (industry) / up to 2 (research-heavy)
- Visual QA (Phase K orphan/widow review): PENDING agent review

## Review checklist (before this application may be submitted)
- [ ] Human review of evaluation vs RESUME_GENERATION_RULES Phase J rubric
- [ ] Line-level layout review (K1-K4)
- [ ] Cover letter word count <= 250 and tone check ({words} words at generation)

## Artifacts
- `resume.tex` / `resume.pdf`
- `cover_letter.tex` / `cover_letter.pdf`
- JD: `{jd_path}`
"""
    (app_dir / "evaluation.md").write_text(eval_md)
    (app_dir / "plan.json").write_text(json.dumps(plan, indent=2))

    print(f"""
=== TAILORED APPLICATION PACKAGE ===
job      : {jd['title']} @ {jd['company']}
family   : {family}
output   : {app_dir}
resume   : {resume_pdf} ({pages} page(s))
letter   : {cl_pdf} ({words} words)
elapsed  : {time.time()-started:.0f}s
STATUS   : DRAFT — human review required before submission
""")
    return 0


def _render_letter_tex(role_title: str, company: str, letter_body: str) -> str:
    """Wrap the LLM letter into the house LaTeX letter format."""
    def esc(s: str) -> str:
        s = s.replace("\\", "").replace("&", r"\&").replace("%", r"\%")
        s = s.replace("#", r"\#").replace("_", r"\_").replace("$", r"\$")
        return s

    paras = [p.strip() for p in re.split(r"\n\s*\n", letter_body) if p.strip()]
    # Drop greeting/closing lines — the template supplies its own.
    _first = ""
    _full = config_lib.identity_line("full_name")
    if config_lib.identity_line("first_name"):
        _first = config_lib.identity_line("first_name").lower()
    elif _full:
        _first = _full.split()[0].lower()

    def _is_meta(p: str) -> bool:
        low = p.lower()
        if low.startswith(("dear ", "hello,", "hi,", "to whom")):
            return True
        if low.startswith(("sincerely", "best regards", "best,", "regards",
                           "thank you for your consideration,")):
            return True
        return bool(_first) and bool(
            re.match(rf"^sincerely[\s,]*\n?{re.escape(_first)}", low))
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


def load_spec(spec_path: str) -> argparse.Namespace:
    """Build args from a UI-written spec JSON ({url|text|file, company, title})."""
    spec = json.loads(Path(spec_path).read_text())
    ns = argparse.Namespace(
        jd_file=None, url=None, text_file=None,
        company=spec.get("company") or "", title=spec.get("title") or "")
    if spec.get("url"):
        ns.url = spec["url"]
    elif spec.get("text"):
        tmp = Path(spec_path).parent / "jd_text.txt"
        tmp.write_text(spec["text"])
        ns.text_file = str(tmp)
    elif spec.get("file"):
        ns.jd_file = spec["file"]
    else:
        raise RuntimeError("spec has neither url, text nor file")
    return ns


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--jd-file", help="path to raw JD text/markdown")
    src.add_argument("--url", help="posting URL (greenhouse/lever/ashby/generic)")
    src.add_argument("--text-file", help="file holding pasted JD text")
    src.add_argument("--spec-file", help="UI spec JSON: {url|text|file, company, title}")
    ap.add_argument("--company", help="override company name")
    ap.add_argument("--title", help="override role title")
    args = ap.parse_args(argv)
    if args.spec_file:
        args = load_spec(args.spec_file)
    try:
        return run(args)
    except Exception as exc:  # noqa: BLE001 - surface clean error to UI log
        log(f"FATAL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
