#!/usr/bin/env python3
"""
categorize_roles.py — LLM role-family categorizer for tracking/jobs/jobs.csv.

Fills the `role_family` column using the controlled vocabulary from
tracking/jobs/SCHEMA.md:
  agentic_ai, agent_reasoning, applied_ml, eval_inference,
  post_training, other

By default only rows whose role_family is blank/'nan'/'unknown'/'none' are
classified; --all reclassifies every row. The LLM call reuses
tailor_from_jd.llm_chat (NVIDIA/OpenRouter providers from config.yaml);
invalid or unavailable LLM replies fall back to a keyword heuristic.

Usage:
  python3 scripts/categorize_roles.py                 # dry-run (default)
  python3 scripts/categorize_roles.py --apply         # write changes
  python3 scripts/categorize_roles.py --job-id ID1 --job-id ID2,ID3
  python3 scripts/categorize_roles.py --all --limit 50
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from scripts import tailor_from_jd
except ImportError:
    import tailor_from_jd


VOCAB = [
    "agentic_ai",
    "agent_reasoning",
    "applied_ml",
    "eval_inference",
    "post_training",
    "other",
]

FAMILY_DEFINITIONS = {
    "agentic_ai": "agentic / applied AI agents engineering (agent frameworks, "
                  "tool use, orchestration, autonomous workflows)",
    "agent_reasoning": "frontier reasoning / planning research engineering "
                       "(test-time search, verifiers, long-horizon reasoning)",
    "applied_ml": "classic ML engineer / Applied Scientist production ML "
                  "(pipelines, model deployment, experimentation)",
    "eval_inference": "inference optimization / serving / evaluation systems "
                      "(vLLM-style serving, latency/throughput, eval harnesses)",
    "post_training": "post-training: RLHF, SFT, preference data, reward models",
    "other": "everything else including infra, data, and analytics roles",
}

# Keyword heuristic mapped onto the jobs.csv vocabulary. Two-tier weighting:
# strong signals are near-decisive on their own; weak signals only count when
# no strong signal fires. Every keyword is matched as a WHOLE WORD/PHRASE
# (regex \b boundaries) — never raw substring ("ppo" must not hit
# "opportunity"/"support").
STRONG_KEYWORDS = {
    "post_training": [
        "post-training", "post training", "rlhf", "rlaif", "grpo", "dpo",
        "preference optimization", "reward modeling", "reward model",
        "reward hacking", "human feedback", "preference data",
        "reinforcement learning from human", "policy optimization",
        "fine-tuning language models", "fine-tuning llms", "model alignment",
        "alignment research", "safety training",
    ],
    "agent_reasoning": [
        "chain-of-thought", "test-time compute", "inference-time search",
        "tree of thoughts", "self-consistency", "process reward",
        "verifier model", "long-horizon reasoning", "frontier reasoning",
        "reasoning models", "o1-style", "deep research",
    ],
    "eval_inference": [
        "inference optimization", "model serving", "serving infrastructure",
        "vllm", "sglang", "tensorrt-llm", "triton inference server",
        "kv cache", "speculative decoding", "quantization", "gpu kernel",
        "cuda kernel", "eval harness", "evaluation framework",
        "model evaluation", "benchmark suite", "llm evaluation",
        "inference engine", "low-latency inference",
    ],
    "agentic_ai": [
        "agentic", "multi-agent", "agent framework", "autonomous agent",
        "tool use", "tool calling", "function calling", "langgraph",
        "langchain", "mcp server", "agent orchestration", "computer use",
        "browser agent", "coding agent",
    ],
    "applied_ml": [
        "applied scientist", "applied machine learning", "recommendation system",
        "recommender", "ranking model", "ctr prediction", "feature store",
        "machine learning pipeline", "ml platform", "forecasting",
    ],
}

WEAK_KEYWORDS = {
    "post_training": ["sft", "distillation", "synthetic data generation"],
    "agent_reasoning": [
        "planning", "verifier", "world model", "code generation",
        "math reasoning",
    ],
    "eval_inference": [
        "latency", "throughput", "inference", "benchmark", "evaluation",
        "a/b test",
    ],
    "agentic_ai": [
        "agent workflow", "orchestration", "workflow automation", "copilot",
        "assistant", "rag", "retrieval-augmented",
    ],
    "applied_ml": [
        "machine learning engineer", "production ml", "ml pipeline",
        "model deployment", "experimentation", "data scientist",
        "computer vision", "nlp", "speech", "personalization",
    ],
}

UNSET_VALUES = {"", "nan", "unknown", "none"}

_VOCAB_RE = re.compile(
    r"(?<![a-z])("
    + "|".join(re.escape(v) for v in sorted(VOCAB, key=len, reverse=True))
    + r")(?![a-z])"
)


def log(msg):
    print(f"[categorize] {msg}", flush=True)


def parse_job_ids(raw_ids):
    """Flatten repeatable and comma-separated --job-id values into a set."""
    out = set()
    for chunk in raw_ids or []:
        for part in str(chunk).split(","):
            part = part.strip()
            if part:
                out.add(part)
    return out


def is_target(row, force_all=False):
    """True when role_family should be filled (blank-ish, or --all)."""
    if force_all:
        return True
    val = (row.get("role_family") or "").strip().lower()
    return val in UNSET_VALUES


def select_targets(rows, force_all=False, job_id_filter=None):
    """Rows to categorize, in file order."""
    out = []
    for row in rows:
        jid = (row.get("job_id") or "").strip()
        if job_id_filter is not None and jid not in job_id_filter:
            continue
        if not jid:
            continue
        if (row.get("status") or "").strip().lower() == "archived":
            continue
        if is_target(row, force_all=force_all):
            out.append(row)
    return out


def build_jd_text(row, data_root):
    """JD body text: description_file (relative to data_root), else meta columns."""
    text = ""
    df = (row.get("description_file") or "").strip()
    if df:
        jd_path = Path(data_root) / df
        try:
            raw = jd_path.read_text(encoding="utf-8")
            if "## Full Job Description Text" in raw:
                body = raw.split("## Full Job Description Text", 1)[1]
                body = body.rsplit("---", 1)[0]
                text = body.strip()
        except OSError:
            pass
    if text:
        return text
    meta = " ".join(filter(None, [
        row.get("title", ""), row.get("key_requirements", ""),
        row.get("matching_strengths", ""), row.get("main_gaps", ""),
        row.get("notes", "")]))
    return meta.strip()


def validate_family_reply(reply):
    """Extract a controlled-vocab token from an LLM reply, else None.

    Models often answer in prose despite the one-token instruction
    ("This role involves RLHF..., so the answer is: post-training"), or use
    natural variants ("post-training", "applied ML"). Match against several
    normalized variants (hyphen->underscore, whitespace->underscore) using
    letter-boundary lookarounds, preferring the LAST match across variants
    (prose tends to end with the verdict).
    """
    text = (reply or "").strip().lower()
    matches: list[str] = []
    for variant in (text.replace("-", "_"),
                    re.sub(r"\s+", "_", text.replace("-", " "))):
        matches.extend(_VOCAB_RE.findall(variant))
    return matches[-1] if matches else None


def _kw_pattern(keyword: str):
    """Whole-word/phrase regex for a keyword (hyphen/space equivalent)."""
    parts = [re.escape(p) for p in keyword.replace("-", " ").split()]
    return re.compile(r"\b" + r"[\s-]+".join(parts) + r"\b")


def keyword_family(text):
    """Weighted whole-word keyword fallback mapped to the jobs.csv vocab.

    Strong signals dominate; weak signals only break ties when no strong
    signal fired. Ties resolve by family order in VOCAB (stable).
    """
    low = (text or "").lower()
    strong_scores = {}
    weak_scores = {}
    hits = {}
    for fam in VOCAB[:-1]:  # 'other' has no keywords — it's the default
        s_hits = [_kw_pattern(k).search(low) and k for k in STRONG_KEYWORDS.get(fam, [])]
        s_hits = [k for k in s_hits if k]
        w_hits = [_kw_pattern(k).search(low) and k for k in WEAK_KEYWORDS.get(fam, [])]
        w_hits = [k for k in w_hits if k]
        hits[fam] = s_hits or w_hits
        strong_scores[fam] = len(s_hits)
        weak_scores[fam] = len(w_hits)

    best_strong = max(strong_scores.values())
    if best_strong > 0:
        # Strong signals decide; most distinct strong keywords wins.
        ranked = sorted(strong_scores.items(), key=lambda kv: (-kv[1], VOCAB.index(kv[0])))
        top_fam, top_score = ranked[0]
        return top_fam, hits[top_fam]
    ranked = sorted(weak_scores.items(), key=lambda kv: (-kv[1], VOCAB.index(kv[0])))
    top_fam, top_score = ranked[0]
    if top_score == 0:
        return "other", {}
    return top_fam, hits[top_fam]


def _keyword_criteria_block() -> str:
    """Shared classification criteria for the LLM prompt.

    Built from the SAME strong/weak keyword tiers the offline fallback uses,
    so the model and `keyword_family` apply identical standards.
    """
    lines = []
    for fam in VOCAB[:-1]:
        strong = STRONG_KEYWORDS.get(fam, [])
        weak = WEAK_KEYWORDS.get(fam, [])
        if strong:
            lines.append(f"  - {fam}: strong signals = {', '.join(strong)}")
        if weak:
            lines.append(f"      weak supporting signals = {', '.join(weak)}")
    return "\n".join(lines)


def build_prompt(row, jd_text):
    vocab_block = "\n".join(
        f"  - {fam}: {FAMILY_DEFINITIONS[fam]}" for fam in VOCAB
    )
    title = row.get("title", "")
    company = row.get("company", "")
    system = (
        "You are a strict job-taxonomy classifier. You reply with exactly one "
        "token and nothing else."
    )
    user = (
        "Classify this job posting into exactly ONE of these role families:\n"
        f"{vocab_block}\n\n"
        "Classification criteria (use these consistently):\n"
        f"{_keyword_criteria_block()}\n\n"
        "Decision rules:\n"
        "- Classify by what the job BUILDS or RESEARCHES day-to-day, not by "
        "title prestige or one incidental word.\n"
        "- A mention of RLHF/reward-models/post-training as CORE work means "
        "post_training; a passing reference does not.\n"
        "- Serving/latency/GPU-inference work is eval_inference even at an "
        "agents company; agent frameworks/orchestration work is agentic_ai "
        "even if inference is mentioned.\n"
        "- Generic ML engineering (pipelines, deployment, recommendations, "
        "experimentation) without a frontier-research focus is applied_ml.\n"
        "- If nothing above clearly applies (infra, data, full-stack, PM, "
        "analytics), answer other.\n\n"
        f"Company: {company}\nTitle: {title}\n\n"
        "=== JOB DESCRIPTION ===\n"
        f"{jd_text[:12000]}\n\n"
        "Reply with ONLY the single family token from the list above "
        "(example of exact expected format: post_training). The reply must "
        "contain at minimum that token. No explanation, no punctuation."
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


def classify_job(row, jd_text, chat_fn=None):
    """Return (family, method) for one row.

    method is 'llm', 'keyword_fallback', or 'keyword_only' (no usable LLM).
    """
    if chat_fn is None:
        chat_fn = tailor_from_jd.llm_chat
    messages = build_prompt(row, jd_text)
    for attempt in range(2):  # initial try + one retry on invalid reply
        try:
            # max_tokens must be generous: reasoning-style models (e.g.
            # stealth/ox-alpha, nemotron) emit preamble/thinking before the
            # verdict token and return empty/truncated content at tiny budgets,
            # which fails validate_family_reply and wastes the retry.
            reply = chat_fn(messages, max_tokens=4000, temperature=0.0)
        except Exception as exc:  # noqa: BLE001 - provider down -> fallback
            log(f"llm unavailable ({type(exc).__name__}: {exc}); "
                f"falling back to keyword heuristic")
            fam, _ = keyword_family(jd_text + " " + row.get("title", ""))
            return fam, "keyword_only"
        fam = validate_family_reply(reply)
        if fam is not None:
            return fam, "llm"
        if attempt == 0:
            log(f"invalid LLM reply for {row.get('job_id')} "
                f"({reply!r:.60}); retrying once")
    fam, _ = keyword_family(jd_text + " " + row.get("title", ""))
    return fam, "keyword_fallback"


def run(jobs_csv=None, data_root=None, apply=False, job_ids=None,
        force_all=False, limit=None, sleep_s=0.5, chat_fn=None):
    """Categorize targets; returns summary dict. Writes only when apply=True."""
    jobs_csv = Path(jobs_csv) if jobs_csv else Path(config_lib.data_root()) / "tracking/jobs/jobs.csv"
    data_root = Path(data_root) if data_root else config_lib.data_root()
    job_id_filter = parse_job_ids(job_ids) if job_ids else None

    with open(jobs_csv, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "role_family" not in fieldnames:
        fieldnames.append("role_family")

    targets = select_targets(rows, force_all=force_all, job_id_filter=job_id_filter)
    if limit is not None:
        targets = targets[:limit]

    mode = "APPLY" if apply else "DRY-RUN"
    scope = f"--all" if force_all else "blank role_family rows"
    if job_id_filter:
        scope += f", job_id filter={sorted(job_id_filter)}"
    print(f"[categorize] {mode}: {len(targets)} target row(s) ({scope})")

    changed = {}
    methods = {}
    for i, row in enumerate(targets, start=1):
        jid = row["job_id"]
        jd_text = build_jd_text(row, data_root)
        fam, method = classify_job(row, jd_text, chat_fn=chat_fn)
        old = (row.get("role_family") or "").strip()
        log(f"{i}/{len(targets)} {jid} -> {fam} ({method})"
            + (f" [was: {old}]" if old else ""))
        row["role_family"] = fam
        changed[jid] = fam
        methods[jid] = method
        if sleep_s and i < len(targets):
            time.sleep(sleep_s)

    if apply and targets:
        today = date.today().isoformat()
        for jid in changed:
            for row in targets:
                if row["job_id"] == jid:
                    row["date_updated"] = today
                    break
        with open(jobs_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    fam_counts = {}
    method_counts = {}
    for jid, fam in changed.items():
        fam_counts[fam] = fam_counts.get(fam, 0) + 1
        m = methods[jid]
        method_counts[m] = method_counts.get(m, 0) + 1
    print("[categorize] per-family:",
          dict(sorted(fam_counts.items(), key=lambda kv: -kv[1])))
    print("[categorize] per-method:", dict(sorted(method_counts.items())))
    if apply:
        print(f"[categorize] wrote {len(targets)} updated row(s) to {jobs_csv}")
    else:
        print("[categorize] dry run — no files written.")
    return {
        "total_targets": len(targets),
        "per_family": fam_counts,
        "per_method": method_counts,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="LLM role-family categorizer for jobs.csv")

    ap.add_argument("--apply", action="store_true",
                    help="write changes to jobs.csv (default: dry-run)")
    ap.add_argument("--job-id", dest="job_ids", action="append", default=[],
                    help="restrict to job_id(s); repeatable/comma-separated")
    ap.add_argument("--all", action="store_true",
                    help="reclassify every row, not just blanks")
    ap.add_argument("--limit", type=int, default=None, help="cap number of rows")
    args = ap.parse_args(argv)
    run(apply=args.apply, job_ids=args.job_ids, force_all=args.all,
        limit=args.limit)


if __name__ == "__main__":
    main()
