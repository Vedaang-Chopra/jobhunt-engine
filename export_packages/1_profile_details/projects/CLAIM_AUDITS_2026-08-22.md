# Project Claim Audits — Consolidated Results

**Date:** 2026-08-22
**Method:** 4 parallel subagents audited actual project codebases (read-only), checking every disputed resume claim against code, git history, configs, and the repos' own audit trails.
**Supersedes:** blanket bans in `resume_fact_bank.yaml` `banned_tier_1_anywhere` (several were wrong or imprecise).

## Verdict tiers used

- **VERIFIED-CODE** — artifact in repo proves it; claim freely
- **CANDIDATE-ATTESTED** — user confirms, no local artifact; method-level claims only
- **FALSE** — evidence contradicts it; never claim
- **UNVERIFIABLE** — code exists but no persisted result; do not cite numbers

---

## ATHENA (`all_projects_implemented/ATHENA`)

| # | Claim | Verdict | Correct wording |
|---|---|---|---|
| 1 | 14-agent system | **FALSE** | v1 = 6 active supervisor members (5 creative + intent/planning). v0.2 experimental: 11 workers + supervisor. "14" existed only in athena.tex placeholders. |
| 2 | Blackboard controller | **FALSE** (never in code) | Git pickaxe: "blackboard" only in markdown docs. Code = supervisor-worker via LangGraph Command. |
| 3 | BLEU-4 +0.18 absolute | **UNVERIFIABLE** | sacrebleu computation exists; zero persisted BLEU results anywhere. |
| 4 | CLIPScore +22% | **UNVERIFIABLE** | Computation only in explicitly unused file; zero computed values. |
| 5 | Ablation 27% fact coverage; 4.1→3.3 n=5 | **UNVERIFIABLE** | Only in athena.tex placeholders; repo audit: "No such evidence was found." |
| 6 | 5 specialized agents | **VERIFIED-CODE** | `athena_v1/agents/screenplay/{ideation,charachter,world_prop,story,scene_breakdown}.py` |
| 7 | Reflection critique + dynamic plan modification | **VERIFIED-CODE** (integration partial) | ReflectionRouter (repeat/feedback/next) + OrchestrationRouter DYNAMIC_FLOW; router validation commented out; not wired to runnable entry point. |
| 8 | LangGraph Command supervisor-worker | **VERIFIED-CODE** | `Command[Literal[...]]` in supervisor + workers. |

**Tech stack:** LangGraph (Command/StateGraph/MemorySaver), pydantic 2.10.2, langchain 0.2.14, Azure OpenAI gpt-4.1 + gpt-4.1-mini, Ollama, openai 1.47, torch 2.3, transformers 4.44, sentence-transformers, OpenAI CLIP ViT-B/32, TransNetV2, YOLOv8, Whisper, sacrebleu, nltk, FFmpeg, yt-dlp, Redis. **No vLLM.**

---

## ARTEMIS / Which_VLM_Router

| # | Claim | Verdict | Correct wording |
|---|---|---|---|
| 1 | 100K+ query profiles | **PARTIAL (bigger than claimed)** | 339,056 model-response profiles; ~68K unique queries × 5 models. Say "~340K profiles across ~68K queries." |
| 2 | ~30% lower cost | **FALSE** | Recomputed: +591% (n=100) / +385% (n=1000) MORE expensive than CascadeFlow — production router crashes on construction (`inference_reward_router.py` self.model never assigned) and silently falls back. |
| 3 | KL-divergence matching | **VERIFIED-CODE** (ban lifted) | `classical_router.py:157` F.kl_div CE+KL loss + notebooks — classical router lineage only. |
| 4 | Outperforming RouteLLM | **FALSE** | Citation only; zero comparisons. |
| 5 | arXiv preprint | **FALSE** | Draft PDF exists; no submission. |
| 6 | Neural router, SLA-aware LB | **PARTIAL** | Training code + SLA monitor real; simulation-only (vLLM backends never reachable live). Say "simulation-validated." |
| 7 | 6+ VLM backends | **FALSE as worded** | Exactly **5 distinct models** × 2 endpoints: gemma_3_27b, qwen3_vl_8b_thinking, qwen2_5_vl_7b, qwen2_5_vl_3b, deepseek_ocr. Say "5 VLMs, 10 endpoints." |
| — | (new, usable) | **VERIFIED-CODE** | **90.3% oracle-utility recovery** (balanced mode, multitask_eval_summary.csv) — strongest defensible metric. |

**Tech stack:** PyTorch, Transformers, FastAPI/uvicorn/pydantic, SQLAlchemy + Postgres (17GB vlmrouter DB), parquet/pyarrow, wandb, Docker Compose, httpx/openai-compatible clients, vendored CascadeFlow baselines, pytest.

---

## SHASTRA (`all_projects_implemented/Shastra`)

| # | Claim | Verdict | Correct wording |
|---|---|---|---|
| 1 | Retrieves prior workflows | **PLANNED-ONLY** | Design docs only (deer-flow fork checklist); no implementation. Do NOT claim retrieval/agent-memory as built. |
| 2 | Composes/adapts workflows | **FALSE** | No composition engine. Real asset: runnable GAIA trace→graph pipeline (event parsing → semantic blocks → canonical TDG extraction). |
| 3 | Cost/latency constraints | **VERIFIED-CODE** | `Constraints(max_cost, max_latency, min_accuracy)`; greedy + constrained-aware search; feasibility filtering. |
| 4 | LangGraph planner / Pydantic state | **FALSE** | Zero LangGraph imports; plain ABC planners; dataclasses not Pydantic (Pydantic only in GAIA LLM I/O). |
| 5 | Component registry + pluggable storage | **PARTIAL** | Registry + YAML connector real; db_connector is in-memory dict with TODO. |
| 6 | "Orchestrator is a stub" | **CONFIRMED** | Only MockComponent; cannot run real task end-to-end; 157 tests pass against mocks. |
| 7 | deer-flow | Vendored pristine bytedance clone + planning notes — not own work. |

**Correct SHASTRA description:** "Built an orchestration framework (event-sourced orchestrator, constraint-aware plan search, component registry) plus a runnable GAIA trace→graph analysis pipeline; executor integration and workflow retrieval not yet implemented."

**Tech stack:** Python, dataclasses, ABC planners, YAML, GAIA pipeline (pgvector planned), 157 pytest.

---

## Edge Assistant / CERBERUS (`all_projects_implemented/Edge Assistant`)

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Qwen SLM fine-tuning | **VERIFIED-CODE** | peft LoraConfig r=32 α=64 (q/k/v/o_proj); real runs: Qwen2.5-7B (40.4M trainable/7.66B), Qwen2.5-1.5B (17.4M/1.56B); configs for 7B/3B/1.5B-Instruct; notebooks 01–07 with executed outputs (Qwen2.5-3B QA training). |
| 2 | Ran on Fortinet | **FALSE on disk** | Training paths = **Georgia Tech HICE cluster** (`/home/hice1/vchopra37/...`, H100/A100). Zero Fortinet references. |
| 3 | Architecture changes | **VERIFIED-CODE** (reframed) | Custom projection/alignment stack on frozen CLIP ViT-L/14-336 + SBERT; attention-pooling vs Perceiver-resampler ablations; MRL nested prefix embeddings conditioning Qwen. Architecture AROUND Qwen, not of Qwen. |
| 4 | Matryoshka 4096→128 | **VERIFIED-CODE** | `src/encoders/mrl.py` + eval tables; ~77.7% R@5 @4096-d → ~63% @128-d (attention model); Perceiver branch honest negative (~0.2%). MRL = prefix-slicing of learned projector. |
| 5 | CERBERUS = this repo | **TRUE** | README "Project CEREBRUS/CERBERUS"; paper + midsem report present. |

**Tech stack:** torch 2.9, transformers 4.57.1, peft 0.18, accelerate, bitsandbytes, DeepSpeed (logs), timm, sentence-transformers, datasets, jiwer, wandb (37 run dirs). **No TRL.** No checkpoints committed locally.

**Caveats (repo's own 2026-08-17 audit):** shipped Perceiver ≠ V3 Perceiver in final table; TRM ROUGE-L table has no surviving artifact; advertised CLI trainer buggy; checkpoints unreproducible. Avoid "production-ready" language.

---

## ATHENA — SECOND DEEP SCAN ADDENDUM (2026-08-22, docs/notebooks/archives)

The first audit's "no persisted results" was **partially wrong**. Deep scan of docs,
notebooks, and dataset dirs found:

| Finding | Detail |
|---|---|
| **Persisted per-video results EXIST** | `dataset/processed_dataset/results/` — 10 concept JSONs, 97 videos: BLEU 0.154, ROUGE-L 0.306, METEOR 0.302, BERTScore-F1 0.333 (text means); CLIPScore 0.471, SSIM 0.196, PSNR 8.29 dB (85 non-null videos) |
| VATEX baseline in notebook | `retired_code_files/old_code/vatex_dataset.ipynb` cell 7: BLEU 0.298, METEOR 0.452 |
| Execution evidence | `eval_pipelin_v1.ipynb` traces (2025-05-04), SceneEvaluator runs — evaluation WAS run |
| Caveats | ~5 of 10 result files partial/null; bucket-alignment notebook shows broken aligner run (global sim 0.0000) |
| Still NOT found | +0.18 comparative, +22% relative, 27% ablation, any n=5 rater records — confirmed absent across notebooks too |
| Research agent | Existed as v0.2 `scene_research_agent` code + unwired v1 suite (`agents/research/`); no ablation experiment record |

**Revised claim status:** absolute corpus metrics citable as "preliminary" (BLEU ~0.15,
CLIPScore ~0.47); all relative/comparative figures and the human study remain banned.
Note: repo's own `08_EVIDENCE_INDEX.md` had already listed these result files —
first audit missed the evidence index.

## CAD Design

*(Audited 2026-08-22, follow-up pass.)*

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Closed-loop pipeline (CadQuery + compile/geometry feedback + LangGraph repair) | **VERIFIED-CODE** | routers.py gates on compile_success/stl_generated; generator.py RAG system-instruction; execution/analysis/control modules |
| 2 | "16-module system" | **PARTIAL — stale** | Actually **12 top-level packages** under modules/ (+visualization); 507 .py files. "16 modules" survives only in archived refactor-era docs. Say "modular multi-package system" or "12-module". |
| 3 | "202-test harness" | **FALSE as stated** | pytest collects **188 tests, 97 collection errors** (unresolved imports). Not 202 anywhere in current code. Say "pytest harness" without the number until suite is repaired. |
| 4 | Chamfer AND Hausdorff on STL | **TRUE** | `modules/evaluation/metric_evaluation/evaluation/distances.py` (also precision/recall/F1, normal_consistency); trimesh STL evaluator (`services/evaluator.py`). B-Rep comparison separate (brep_trajectory) — metrics operate on tessellated STL, not B-Rep directly. Resume's "STL and B-Rep" phrasing overstates: metrics are STL-based. |
| 5 | VLM-as-judge visual judgment | **TRUE** | `modules/evaluation/vlm_evaluation/` (VLMVisualAnalysisTool/Analyzer, fail-open guardrails, 9 dedicated tests incl. test_vlm_no_correctness_claim.py); visual_analysis computes Visual_Match_Score, Silhouette IoU, Depth MAE, Edge_Chamfer feeding repair feedback |
| 6 | Frozen model / no RL training | **TRUE** | 362 grep hits for train/fit/ppo/reward all substring false positives ("support", "unsupported"). No training code. |
| 7 | RAG-augmented prompts | **TRUE** | rag_system_instruction wired through generator.py; modules/rag package |

**Tech stack:** Python, cadquery (54 importers), pandas, numpy, sqlalchemy, pydantic (17), langgraph, trimesh, matplotlib, PIL, plotly, networkx, scipy, seaborn, tqdm, pytest, unittest; OpenAI-compatible connector (model per-run config: gpt-5.4-mini, openai/gpt-oss-120b via OpenRouter, google/gemma-4-26b-a4b, qwen-coder, kimi, nemotron); Ollama blocked as primary backend by design. Dataset: CADPrompt benchmark (200 samples).

---

## Immediate resume corrections required (Scale AI application)

1. ~~ATHENA unverifiable metrics~~ — FIXED 2026-08-22
2. ~~ARTEMIS 6+ backends~~ — FIXED 2026-08-22
3. ~~SHASTRA LangGraph/memory wording~~ — FIXED 2026-08-22
4. ~~CAD "16-module" and "202-test"~~ — FIXED 2026-08-22 (now "modular multi-package system", "pytest harness with VLM-as-judge")

