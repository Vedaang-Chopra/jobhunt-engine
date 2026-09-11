BLOCK: CAD Code Generation Pipeline

- **Canonical name:** CAD Code Generation Pipeline (closed-loop agentic CAD synthesis)
- **Dates / status:** Jan 2026 – Present · IN_PROGRESS (use "Building/Designing")
- **Org:** Georgia Tech — CORE Robotics Lab @ Siemens (Graduate Research Assistant, advisor Dr. Matthew Gombolay)
- **One-line:** Closed-loop agentic pipeline for parametric CAD code generation with execution-grounded verification.
- **Research question:** Can code synthesis be framed as inference-time search with verifiable geometric reward instead of single-pass generation or RL post-training?
- **Architecture:** LLM generates CadQuery programs → execution environment returns compile/geometry feedback → LangGraph-orchestrated repair loop iteratively corrects errors. 16 modules (generation, metric_evaluation, visual_analysis, vlm_evaluation, failure_classification, feature_trees, brep_trajectory, operation_attribution, ast_graphs, code_graphs, roundtrip, structural_diff, rag, prompt_evaluation, infrastructure, agent_langgraph).
- **Methods:** execution feedback loops; geometric verification (Chamfer/Hausdorff on STL and B-Rep); AST/code-graph structural analysis; VLM-based visual judgment; RAG-augmented prompt construction; failure classification; repair-trajectory quality scoring.
- **Technologies:** LangGraph, CadQuery, Pydantic, VLMs, RAG.
- **Verified metrics (all SAFE):** 16 modules · 202-test evaluation harness.
- **Scale:** 16-module system, 202 automated tests.
- **Production status:** research system (production-grade evaluation discipline, not deployed product).
- **Contributions:** pipeline design; verification/evaluation components; harness maintenance.
- **Role families:** research_engineer_agentic, research_engineer_llm_reasoning, research_engineer_multimodal_vlm (VLM judgment), ml_systems_inference (eval systems), applied_scientist.
- **ATS keywords:** agentic pipeline, execution-grounded verification, inference-time search, verifiable reward, code generation, evaluation harness, geometric verification, LangGraph, tool use, closed-loop.
- **MUST NOT claim:** RL post-training / PPO / GRPO for this project; fine-tuning of any kind; reward modeling (RL sense); production deployment; publication.

**Bullet variants:**
- *Agentic:* "Building a closed-loop agentic pipeline for parametric CAD code generation: LLM generates CadQuery programs, execution feedback drives a LangGraph repair loop — framing synthesis as inference-time search with verifiable geometric reward (16-module system)."
- *Eval-oriented:* "Designing execution-grounded evaluation for LLM code generation: compile validity, geometric correctness (Chamfer/Hausdorff on STL/B-Rep), and repair-trajectory quality, maintained as a 202-test harness with VLM-based visual judgment."
- *Systems-oriented:* "Built a 16-module agentic code-generation system with structured execution feedback (Pydantic), RAG-augmented prompting, and a 202-test automated evaluation harness."
- *Reasoning/search-oriented:* "Framing program synthesis as inference-time search: dense geometric reward signals (compile, geometry, structural diffs) guide iterative repair on a frozen model — no post-training required."
- *Multimodal-oriented:* "Integrating VLM-based visual judgment into code-generation evaluation: rendered-geometry assessment complements Chamfer/Hausdorff metrics across a 202-test harness."

---

BLOCK: ATHENA

- **Canonical name:** ATHENA — Multi-Agent Screenplay Generation
- **Dates / status:** Jan – May 2025 · COMPLETED. Co-author: Prof. Vijay Madisetti. Manuscript in preparation — NEVER claim submitted/published.
- **Org:** Georgia Tech — CS 8903
- **One-line:** 5-agent supervisor-worker orchestration system with reflection-based critique, evaluated cross-modally.
- **Architecture:** 5 specialized agents (ideation, character design, world building, story generation, scene breakdown) + research agent; supervisor-worker via LangGraph Command routing; reflection/critique loop with dynamic plan modification; Pydantic structured outputs.
- **Verified metrics:** BLEU-4 **+0.18 absolute** over single-agent baseline (SAFE) · 100 reference videos (SAFE) · ablation: removing research agent → fact coverage −27% (SAFE) · visual relevance 4.1→3.3/5.0, n=5 raters (SAFE) · evaluated with BLEU-4, CLIPScore, METEOR, BERTScore, SSIM, PSNR.
- **Technologies:** LangGraph Command, Pydantic, supervisor-worker pattern.
- **Role families:** research_engineer_agentic, research_engineer_llm_reasoning, applied_scientist (eval angle), research_engineer_multimodal_vlm (cross-modal eval angle).
- **ATS keywords:** multi-agent orchestration, supervisor-worker, reflection, critique loop, structured generation, cross-modal evaluation, ablation study.
- **MUST NOT claim:** 14-agent; blackboard controller; keyframe synthesis; BLEU +18%; CLIPScore +22%; publication.

**Bullet variants:**
- *Agentic:* "Built a 5-agent supervisor-worker screenplay generation system via LangGraph Command routing with reflection-based critique and dynamic plan modification; +0.18 BLEU-4 absolute over single-agent baseline on 100 reference videos."
- *Eval-oriented:* "Designed cross-modal evaluation framework (BLEU-4, METEOR, BERTScore, CLIPScore, SSIM, PSNR) over 100 reference videos; ablation showed removing the research agent cut fact coverage 27% and visual relevance 4.1→3.3/5.0 (n=5 raters)."
- *Reasoning-oriented:* "Demonstrated reflection-based quality critique in multi-agent orchestration: dynamic plan modification improved output quality measurably (+0.18 BLEU-4 absolute; −27% fact coverage without the critique agent)."

---

BLOCK: Fortinet — Agentic RAG Diagnostics

- **Canonical name:** Fortinet Agentic RAG Diagnostics System
- **Dates / org:** Fortinet AIOps R&D, Bengaluru (SDE II scope) · within Feb 2021 – Jul 2025 · production-deployed
- **One-line:** LLM-driven diagnostics: multi-step tool calls over network telemetry with structured function calling → autonomous root-cause analysis.
- **Verified/registered metrics:** mean resolution time **~70%** reduction (CAUTION — self-reported; always `~`) · hackathon prototype → production deployment (SAFE) · telemetry from ~10K managed devices (CAUTION, use `~` or omit).
- **Technologies:** LLM orchestration, tool/function calling, structured output, RAG, LangChain.
- **Role families:** all agentic/reasoning/applied families.
- **ATS keywords:** agentic RAG, LLM agents, tool calling, function calling, multi-step planning, root-cause analysis, production LLM.
- **MUST NOT claim:** metrics without `~`; "frontier" framing; unverified device counts stated precisely.

**Bullet variants:**
- *Agentic/production:* "Led agentic RAG diagnostics system from hackathon prototype to production: LLM plans multi-step tool calls over network telemetry and verifies hypotheses via structured function calling — autonomous root-cause analysis reducing mean resolution time ~70%."
- *Reasoning:* "Production LLM agent that plans multi-step tool use over telemetry and verifies hypotheses through structured function calling before concluding — verification-gated autonomous diagnosis at enterprise scale."

---

BLOCK: Fortinet — Systems & ML Engineering (composite)

- **Contents (each independently usable):**
  - **OpenSearch scaling (SAFE):** 50 → 2,000 events/sec (40x) ingestion pipelines in Golang with reliability/observability.
  - **ONNX edge inference (CAUTION ~40%):** inference-optimized ML models via ONNX Runtime for edge network appliances.
  - **SLA forecasting (SAFE):** 60+ classifiers across 4 categories (performance/capacity/availability/connectivity) with automated evaluation and retraining.
  - **Patent (SAFE):** PCT/IN2022/058026 (FILED — never "Granted") — unsupervised distributional thresholding for wireless connectivity anomaly detection; manual troubleshooting **~75%** reduction (CAUTION).
  - **Backend integration (SAFE):** ML models integrated into backend services (Python/Go) across distributed telemetry infrastructure.
- **Role families:** ml_engineer, ml_systems_inference, ai_engineer, applied_scientist; secondary everywhere.
- **ATS keywords:** production ML, scaling, throughput, inference optimization, edge deployment, ONNX, forecasting, distributed systems, Golang, patent.
- **MUST NOT claim:** Kubernetes/Airflow/MLflow; exact percentages without `~`; "Granted" patent.

**Bullet variants:**
- *ML Engineer:* "Scaled OpenSearch telemetry ingestion 50→2,000 events/sec (40x) with Golang; deployed edge ML inference via ONNX Runtime (~40% latency reduction) across network appliances."
- *Applied/production:* "Built SLA forecasting pipelines for 60+ production classifiers across 4 categories with automated evaluation and retraining; filed patent PCT/IN2022/058026 for unsupervised wireless anomaly detection (~75% less manual troubleshooting)."

---