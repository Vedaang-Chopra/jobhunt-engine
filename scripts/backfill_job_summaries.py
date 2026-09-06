#!/usr/bin/env python3
"""
backfill_job_summaries.py — Populate key_requirements / matching_strengths /
main_gaps for every open job row from its archived JD file (2026-08-22).

Fixes the systemic gap where newly-discovered rows were scored only on title +
notes because summary columns were left empty. After this script, every open
row is self-explanatory and the scorer's metadata fallback has real content.

Extraction (deterministic, no fabrication):
  key_requirements    — sentences from the JD body containing requirement
                        signals (years, degree, must/required, skill keywords)
  matching_strengths  — profile evidence keywords found in the JD (vllm, onnx,
                        rlhf, dpo, grpo, agentic, opensearch, pytorch, ...)
  main_gaps           — common requirement categories with zero hits

Usage:
  python3 scripts/backfill_job_summaries.py            # apply
  python3 scripts/backfill_job_summaries.py --dry-run  # report only
"""

import csv
import re
import sys
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
JOBS_CSV = config_lib.path("jobs_csv")
TODAY = "2026-08-22"

# Profile-evidence keywords (from profile_info/ fact bank: Fortinet agentic RAG,
# OpenSearch scaling, ONNX latency, GT PPO/GRPO research)
PROFILE_STRENGTHS = {
    "agentic": "agentic RAG systems (Fortinet)",
    "rag": "RAG pipelines (Fortinet)",
    "retrieval": "retrieval systems",
    "opensearch": "OpenSearch 40x scaling",
    "elasticsearch": "search infrastructure",
    "onnx": "ONNX ~40% latency reduction",
    "vllm": "vLLM inference",
    "inference optimization": "inference optimization",
    "quantization": "quantization",
    "model serving": "model serving",
    "pytorch": "PyTorch",
    "python": "Python",
    "reinforcement learning": "RL coursework + PPO/GRPO research (GT)",
    "rlhf": "RLHF familiarity",
    "dpo": "DPO familiarity",
    "grpo": "GRPO research (CAD)",
    "ppo": "PPO research (CAD)",
    "reward model": "reward modeling exposure",
    "post-training": "post-training research alignment",
    "evaluation": "LLM evaluation work",
    "benchmark": "benchmarking",
    "agents": "agent systems (ATHENA supervisor-worker)",
    "multi-agent": "multi-agent architecture (ATHENA)",
    "tool use": "tool-use integration",
    "function calling": "function-calling integration",
    "langgraph": "LangGraph",
    "langchain": "LangChain",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "distributed systems": "distributed systems",
    "patent": "patented ML work (PCT/IN2022/058026)",
}

REQUIREMENT_PATTERNS = [
    r"[^.]*\b(\d{1,2}\+?\s*(?:to\s*\d{1,2}\s*)?years?)[^.]*\.",
    r"[^.]*(?:ph\.?d|master'?s|bachelor'?s|m\.s\.|degree)[^.]*\.",
    r"[^.]*(?:must have|required|minimum|at least)[^.]*\.",
    r"[^.]*(?:experience (?:with|in|building)|proficiency|expertise)[^.]*\.",
    # Narrative-style JDs (Ashby-era startups): "You have ... / You will ... /
    # background in / familiarity with / track record"
    r"[^.]*(?:you have|you will|you bring|background in|familiarity with|"
    r"track record|nice to have|ideally)[^.]*\.",
    # "experience <verb-ing>" and qualified-experience phrasings
    r"[^.]*experience\s+[a-z]+ing\b[^.]*\.",
    r"[^.]*(?:deep|proven|extensive|strong)\s+(?:knowledge|experience)\b[^.]*\.",
]
SKIP_SENTENCE = re.compile(
    r"(equal opportunity|benefit|salary|compensation|apply|click|privacy|"
    r"©|all rights reserved|cookie)", re.I)


def extract_body(raw):
    if "## Full Job Description Text" in raw:
        body = raw.split("## Full Job Description Text", 1)[1]
        return body.rsplit("---", 1)[0].strip()
    # legacy format
    m = re.search(r"## Full Job Description\n(.*?)\n---", raw, re.S)
    return m.group(1).strip() if m else ""


def split_sentences(body):
    # Bullet fragments without terminal punctuation must still become sentences:
    # insert a boundary before capitalized bullet starts after a comma/line break.
    text = body.replace("\r", "")
    # newline bullet markers -> sentence boundary
    text = re.sub(r"\n\s*[-•*]\s*", ". ", text)
    # "X, Are comfortable..." style: boundary before capitalized verb fragments
    text = re.sub(r"(?<=[a-z,])\s+(?=(?:Have|Are|Is|Do|Can|Will|You|Enjoy|Bring|Bring|Own|Work|Thrive|Communicate|Collaborate|Demonstrate|Hold|Feel|Love|Know|Understand|Pay|Move|Excel)\b)", ". ", text)
    # Space-collapsed bullet lists (markdown conversion lost newlines): split
    # before capitalized fragment starts (gerunds/nouns typical of requirement bullets)
    text = re.sub(r"(?<=[a-z0-9)])\s+(?=[A-Z][a-z]+(?:ing|ed|ity|ills|ence|ance|als|els|ons|ies)\b)", ". ", text)
    text = re.sub(r"\s+(?=(?:Minimum|Preferred|Required|Basic|Nice-to-have)\s+Qualifications)", ". ", text)
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 25]


def extract_requirements(sentences):
    reqs = []
    seen = set()
    for s in sentences:
        if SKIP_SENTENCE.search(s):
            continue
        for pat in REQUIREMENT_PATTERNS:
            if re.search(pat, s, re.I):
                key = s[:80].lower()
                if key not in seen:
                    seen.add(key)
                    reqs.append(s.strip()[:200])
                break
    return reqs[:8]


def extract_gaps(text_lower, strengths_found):
    strength_blob = " ".join(desc for _, desc in strengths_found).lower()
    gap_checks = [
        ("production LLM deployment at scale", ["production", "deploy", "large-scale"]),
        ("PhD-level research track record", ["ph.?d"]),
        ("publications at top venues", ["publications?", "publish"]),
        ("Kubernetes/cloud infra", ["kubernetes", "cloud infra"]),
        ("CUDA/GPU kernel work", ["cuda", "gpu kernel", "triton"]),
    ]
    gaps = []
    for label, kws in gap_checks:
        if any(re.search(k, text_lower) for k in kws):
            head = label.split()[0].lower()
            if not any(kw in strength_blob for kw in
                       [head, "research (gt)", "patented"]):
                gaps.append(label)
    return gaps[:4]


def main():
    dry_run = "--dry-run" in sys.argv
    with open(JOBS_CSV, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated = filled = kept = no_jd = 0
    for row in rows:
        if row.get("status") != "open":
            continue
        df = (row.get("description_file") or "").strip()
        if not df:
            no_jd += 1
            continue
        path = REPO / df
        if not path.exists():
            no_jd += 1
            continue
        body = extract_body(path.read_text(errors="replace"))
        if not body:
            no_jd += 1
            continue
        updated += 1

        existing = (row.get("key_requirements") or "").strip()
        if existing and "--force" not in sys.argv:
            kept += 1
            continue

        tl = body.lower()
        sentences = split_sentences(body)
        reqs = extract_requirements(sentences)
        strengths = [(kw, desc) for kw, desc in PROFILE_STRENGTHS.items() if kw in tl]

        row["key_requirements"] = " | ".join(reqs)[:1000]
        row["matching_strengths"] = "; ".join(desc for _, desc in strengths)[:600]
        row["main_gaps"] = "; ".join(extract_gaps(tl, strengths))[:300]
        filled += 1

    print(f"Open rows scanned: {updated} | summaries filled: {filled} "
          f"| already had summaries (kept): {kept} | no JD file/body: {no_jd}")

    if dry_run:
        print("Dry run — nothing written.")
        return

    with open(JOBS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {JOBS_CSV}")


if __name__ == "__main__":
    main()
