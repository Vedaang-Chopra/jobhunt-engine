#!/usr/bin/env python3
"""
backfill_jd_features.py — Extract structured features from all archived JDs
into job_research/data/jd_features.csv (2026-08-22).

Per JD: required-skill hits, research signals, seniority, years requirement,
education requirement, work-type classification. Data-driven basis for
JOB_MARKET_PATTERNS.md regeneration.

Usage: python3 scripts/backfill_jd_features.py
"""

import csv
import re
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
JOBS_CSV = config_lib.path("jobs_csv")
OUT = config_lib.path("jd_features_csv")

SKILLS = ["python", "pytorch", "golang", "go", "cuda", "transformers", "jax",
          "tensorflow", "ray", "vllm", "tensorrt", "triton", "deepspeed", "fsdp",
          "megatron", "kubernetes", "docker", "distributed training",
          "distributed systems", "model serving", "inference", "onnx", "quantization",
          "rag", "retrieval", "langgraph", "langchain", "agents", "agentic",
          "tool use", "function calling", "planning", "reasoning", "multimodal",
          "vision-language", "rlhf", "rlaif", "dpo", "grpo", "sft", "ppo",
          "reinforcement learning", "post-training", "fine-tuning", "reward model",
          "synthetic data", "human feedback", "evaluation", "benchmark",
          "interpretability", "safety", "red team", "pretraining", "alignment",
          "mixture of experts", "speculative decoding", "long context"]

RESEARCH_STRONG = ["experimentation", "novel", "new methods", "research",
                   "publications", "publish", "hypothesis", "prototype"]
RESEARCH_MED = ["evaluation", "benchmark", "agents", "reasoning", "planning",
                "post-training", "rlhf", "dpo", "grpo", "reward", "fine-tuning",
                "synthetic data", "multimodal", "inference optimization"]


def classify_work_type(text, title):
    strong = sum(1 for k in RESEARCH_STRONG if k in text)
    med = sum(1 for k in RESEARCH_MED if k in text)
    tl = title.lower()
    if "research scientist" in tl or ("research" in tl and strong >= 3):
        return "1_research"
    if "applied research" in tl or (strong >= 2 and med >= 3):
        return "2_applied_research_rd"
    if "research" in tl or med >= 5:
        return "3_research_heavy_engineering"
    if any(k in tl for k in ["machine learning", "ml engineer", "ai engineer",
                             "genai", "llm"]):
        return "4_applied_ai_engineering"
    return "5_general_engineering"


def main():
    with open(JOBS_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    out_fields = ["job_id", "company_slug", "title", "role_family",
                  "work_type_class", "seniority_signals", "years_required",
                  "education_req", "skills_hit_count", "skills_matched",
                  "research_strong_hits", "research_med_hits", "is_stale"]

    out = []
    for r in rows:
        df = (r.get("description_file") or "").strip()
        text = ""
        if df:
            p = REPO / df
            if p.exists():
                body = p.read_text(errors="replace")
                mm = re.search(r"## Full Job Description Text\n(.*?)\n---", body, re.S)
                text = (mm.group(1) if mm else body).lower()
        if not text:
            text = (r.get("key_requirements") or "").lower()
        title = r.get("title", "")

        matched = [k for k in SKILLS if k in text]
        strong = [k for k in RESEARCH_STRONG if k in text]
        med = [k for k in RESEARCH_MED if k in text]

        m = re.search(r"(\d{1,2})\+?\s*years", text)
        years = m.group(1) + "+" if m else ""

        if re.search(r"ph\.?d", text):
            edu = "phd_required" if re.search(r"ph\.?d.{0,30}required", text) else "phd_preferred"
        elif "master" in text or "m.s." in text:
            edu = "ms_acceptable"
        else:
            edu = "unspecified"

        seniority = r.get("seniority", "") or ("senior" if "senior" in title.lower()
                     else "staff" if "staff" in title.lower() else "unspecified")

        out.append({
            "job_id": r["job_id"], "company_slug": r.get("company_slug", ""),
            "title": title, "role_family": r.get("role_family", ""),
            "work_type_class": classify_work_type(text, title),
            "seniority_signals": seniority, "years_required": years,
            "education_req": edu, "skills_hit_count": len(matched),
            "skills_matched": ";".join(matched),
            "research_strong_hits": ";".join(strong),
            "research_med_hits": ";".join(med),
            "is_stale": r.get("stale_flag", "false"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out)

    # quick summary
    from collections import Counter
    wc = Counter(o["work_type_class"] for o in out)
    ec = Counter(o["education_req"] for o in out)
    skill_freq = Counter()
    for o in out:
        for s in o["skills_matched"].split(";"):
            if s:
                skill_freq[s] += 1
    print(f"Extracted features for {len(out)} JDs -> {OUT}")
    print("Work types:", dict(wc.most_common()))
    print("Education:", dict(ec.most_common()))
    print("Top 15 skills:", skill_freq.most_common(15))


if __name__ == "__main__":
    main()
