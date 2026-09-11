# Canonical Professional Profile — Vedaang Chopra
**Last Updated:** August 20, 2026
**Authority:** This is the authoritative source of truth. All downstream artifacts (resumes, LinkedIn, applications) must derive from this file.

---

## Identity
- **Full Name:** Vedaang Chopra
- **Email:** vedaangchopra@gatech.edu
- **Phone:** +1 (404) 740-9905
- **Location:** Atlanta, GA
- **LinkedIn:** https://linkedin.com/in/vedaang-chopra
- **GitHub:** https://github.com/Vedaang-Chopra
- **Website:** https://vedaangchopra.live/
- **Visa Status:** F-1 (OPT eligible Dec 2026)
- **H-1B Sponsorship:** Required for long-term roles; referral bypasses ATS filters

---

## Executive Summary
Vedaang Chopra is an **MS Computer Science (Machine Learning) student at Georgia Tech (GPA: 4.0/4.0, graduating Dec 2026)** with **4+ years of production ML/AI engineering experience at Fortinet** and **active graduate research in agentic AI systems, LLM evaluation, and vision-language model routing**.

**Core Differentiator:** Rare combination of **production ML systems at scale** (enterprise telemetry pipelines, 60+ classifiers, patented anomaly detection) AND **graduate research on cutting-edge agentic systems** (multi-agent orchestration, execution-grounded evaluation, cost-aware VLM routing) **PLUS published cybersecurity/ML research** (IEEE ICAIA 2026: memory forensics + ML for ransomware detection).

**Target Positioning:** Applied AI Researcher / Research Engineer who builds production systems AND does novel research on agentic AI, model evaluation, efficient multimodal inference, and ML for cybersecurity.

---

## Education

### Georgia Institute of Technology, Atlanta, GA
- **Degree:** M.S. in Computer Science (Machine Learning Specialization)
- **Dates:** August 2024 — December 2026 (expected)
- **GPA:** 4.0/4.0 (verified on LinkedIn)
- **Primary Advisor:** Dr. Matthew Gombolay, CORE Robotics Lab @ Siemens
- **Secondary Affiliation:** Systems for AI Lab (Advisor: Dr. Alexey Tumanov) — per v2_extended resume; verify before use
- **Relevant Coursework (Completed):**
  - Deep Learning
  - Deep Reinforcement Learning
  - ML Security / Adversarial Robustness
  - Large & Vision Language Models
  - Agentic AI
  - Systems for AI
- **Research Focus:** Agentic AI systems, LLM evaluation, VLM routing, execution-grounded verification

### Maharaja Surajmal Institute of Technology (GGSIPU), New Delhi, India
- **Degree:** B.Tech. in Information Technology
- **Dates:** August 2016 — August 2020
- **CGPA:** 8.8/10.0
- **Relevant Foundation:** Core CS, programming, systems

---

## Employment History

### Fortinet Technologies Inc. — AIOps R&D, Bengaluru, India
**Software Development Engineer I & II (ML/AI Track)**
**February 2021 — July 2025** (4 years, 6 months)

**Role Evolution:**
- SDE I (Feb 2021 — Feb 2025): Core ML pipeline development, anomaly detection, forecasting
- SDE II (Feb 2025 — Jul 2025): Led agentic RAG diagnostics system, architecture ownership

**Key Responsibilities:**
- Designed, trained, and deployed ML models for network anomaly detection and SLA forecasting
- Built production data pipelines processing enterprise telemetry at scale
- Led development of LLM-based agentic diagnostics system (hackathon → production)
- Optimized ML inference for edge deployment via ONNX Runtime
- Filed patent on unsupervised wireless connectivity thresholding

**Major Projects:**
1. **Agentic RAG Diagnostics System** (SDE II): Originated as user's Fortinet Global Hackathon 2023 entry (top-5 finalist, 5th place) → productionized. LLM plans multi-step tool calls over network telemetry from 10K+ managed devices, verifies hypotheses via structured function calling, produces autonomous root-cause analysis
2. **Unsupervised Wireless Anomaly Detection** (Patent PCT/IN2022/058026; US app 17/958,026, pub. US20240121629A1 — filed/pending): Distributional thresholding model for connectivity anomaly detection
3. **OpenSearch Ingestion Re-Architecture**: Complete pipeline redesign (async I/O + Golang), 50 → 2,000 events/sec (40x improvement)
4. **Pickle Model Serving (CPU-only)**: Integrated data-science team's pickle models into backend; deployed CPU-only inference
5. **DBSCAN SD-WAN Anomaly Detection**: Unsupervised detection over SD-WAN telemetry (reported >50% potential-outage prevention)
6. **Edge ML Inference**: ONNX Runtime deployment on network appliances (~40% latency reduction)
7. **SLA Forecasting Pipelines**: 60+ classifiers across 4 categories, 7-day prediction horizon

**Technologies:** Python, Go, PyTorch, Scikit-Learn, OpenSearch/Elasticsearch, ONNX Runtime, Docker, Linux, Git, SQL/PostgreSQL, Redis, Azure, FastAPI

---

## Graduate Research (Georgia Tech)

### CORE Robotics Lab @ Siemens — Graduate Research Assistant
**Advisor:** Dr. Matthew Gombolay
**Dates:** January 2026 — Present

**Primary Research: CAD Code Generation with Execution-Grounded Verification**
- Building a **closed-loop agentic pipeline** for parametric CAD code generation
- LLM generates CadQuery programs → execution environment returns compile/geometry feedback → LangGraph-orchestrated repair loop iteratively corrects errors
- **Key Innovation:** Framing synthesis as *inference-time search with verifiable geometric reward* rather than single-pass generation or RL post-training (model weights are FROZEN)
- **Evaluation Harness:** 16-module system, 202 automated tests, geometric verification (Chamfer/Hausdorff on STL/B-Rep), AST/code-graph structural analysis, VLM-based visual judgment, RAG-augmented prompts

---

### CS 8903 Special Problems — Graduate Researcher
**Dates:** January 2025 — Present

**Project Portfolio:**

| Project | Period | Description | Status |
|---|---|---|---|
| **SHASTRA** | Jan 2026 — Present | Agent workflow retrieval & adaptation framework; LangGraph-based planner with Pydantic state & component registry; trace-to-graph pipeline (GAIA: 94 sessions, 4,037 events, 1,377 semantic blocks, 442 graph nodes) | IN PROGRESS |
| **ATHENA** | Jan — May 2025 | Multi-agent screenplay generation (5 specialized agents: ideation, character, world, story, scene); supervisor-worker orchestration via LangGraph Command; reflection/critique loop; BLEU-4 & CLIPScore evaluation | COMPLETED |
| **ARTEMIS** | Aug 2025 — Present | Cost-aware VLM routing: neural multi-task router with SLA-aware load balancing; 6+ VLM backends (Gemma 3 27B, Qwen3-VL, DeepSeek OCR, Llama-4 Scout) via vLLM; dynamic routing modes (accuracy/cost/latency) | IN PROGRESS |
| **CERBERUS** | Aug 2025 — Present | Cross-modal alignment with frozen encoders (CLIP/SBERT) using Matryoshka Representation Learning; DDP distributed training, mixed precision on H100/A100; Perceiver Resampler; Qwen-14B decoder integration | IN PROGRESS |
| **AI Security** | 2025 — 2026 | Adversarial attacks (PGD), embedding poisoning, blind backdoors, model extraction, membership inference on LLMs, watermarking — controlled ablations, attack-success vs clean-accuracy tradeoffs | COMPLETED (coursework-style) |

---

## Major Projects (Detailed)

### 1. CAD Code Generation Pipeline (CORE Lab)
- **Objective:** Generate functionally correct parametric CAD programs (CadQuery) using LLMs with execution-grounded verification
- **Architecture:** 16 modules — agent_langgraph, generation, metric_evaluation, visual_analysis, vlm_evaluation, failure_classification, feature_trees, brep_trajectory, operation_attribution, ast_graphs, code_graphs, roundtrip, structural_diff, rag, prompt_evaluation, infrastructure
- **Key Innovation:** Model is FROZEN — no RL post-training, no fine-tuning. Uses inference-time search with geometric verification as reward signal
- **Verification:** Compile validity + geometric correctness (STL/B-Rep Chamfer/Hausdorff) + repair trajectory quality
- **Evaluation:** 202 automated tests, VLM-based visual judgment, RAG-augmented prompt construction
- **Status:** IN PROGRESS — active research, no publication yet

### 2. SHASTRA (Agentic Workflow Orchestration)
- **Objective:** Retrieve and adapt prior agent workflows for new long-horizon tasks under cost/latency constraints
- **Architecture:** Trace-to-graph pipeline: event parsing → LLM semantic annotation with capability labels → Task-Dependency Graph (TDG) construction with dependency/control/conditional edges
- **Technologies:** LangGraph, Pydantic schemas, component registry with pluggable storage (YAML)
- **Data:** 94 GAIA sessions processed
- **Status:** IN PROGRESS — planner implemented, orchestrator stub, executor not done

### 3. ATHENA (Multi-Agent Screenplay Generation)
- **Objective:** Automated screenplay planning and keyframe synthesis via multi-agent orchestration
- **Architecture:** 5 specialized agents (Ideation, Character Design, World/Props, Story Generation, Scene Breakdown) + Research agent; supervisor-worker pattern via LangGraph Command routing; reflection/critique loop with dynamic plan modification
- **Evaluation:** BLEU-4 (+0.18 absolute over baseline), CLIPScore, METEOR, BERTScore, SSIM, PSNR on 100 reference videos
- **Key Finding:** Removing Research agent reduced fact coverage by 27%, visual relevance 4.1→3.3/5.0
- **Status:** COMPLETED (Jan-May 2025), co-authored with Prof. Vijay Madisetti

### 4. ARTEMIS (Cost-Aware VLM Routing)
- **Objective:** Dynamic per-request VLM selection optimizing accuracy, latency, and cost
- **Architecture:** Neural router predicts per-model utility → SLA-aware load balancer enforces budgets → unified inference engine serves 6+ VLM backends via vLLM
- **Models Served:** Gemma 3 27B, Qwen3-VL 8B, Qwen2.5-VL 7B, DeepSeek OCR, Glider, Llama-4 Scout 17B
- **Routing Modes:** accuracy, cheap, fast, balanced, reward-based
- **Verified Artifacts:** Trained checkpoint (best_multitask_router_v1.pt), vLLM serving configs, SLA YAML configs
- **Unverified Claims (DO NOT USE):** "100K+ query profiles", "~30% lower cost", "KL-divergence matching", "outperforming RouteLLM"
- **Status:** IN PROGRESS

### 5. CERBERUS (Vision-Language Alignment for Edge)
- **Objective:** Encoder-frozen cross-modal alignment with compressed embeddings for edge deployment
- **Architecture:** Frozen CLIP ViT-L/14 (vision) + SBERT (text) + optional Whisper (audio); Matryoshka Representation Learning (4096→128 dims); Perceiver Resampler; TRM decoder on compressed latents; Qwen-14B decoder integration
- **Training:** DDP distributed training, mixed precision on H100/A100 clusters
- **Results:** R@5 78% on PixMo retrieval; 512-d retains ~96% of full-dimensional performance; TRM decoder outperforms text-only baseline (ROUGE-L: 0.24 vs 0.08)
- **Negative Result:** Perceiver Resampler ablation — retrieval collapses to chance (initialization/gradient issues)
- **Status:** IN PROGRESS

### 6. Sign Reading AR Glasses (Assistive Tech)
- **Objective:** AR scene understanding for Meta Ray-Ban smart glasses for blind/low-vision users
- **Architecture:** Production v2 system with Android, iOS, Web/PWA clients; backend uses Gemma 4 26B via LM Studio/OpenRouter; health checks, monitoring
- **Status:** IN PROGRESS (private repo)

### 7. RL Soccer (Academic Project)
- **Objective:** RL agents for 2v2 soccer using Ray/RLlib
- **Methods:** PPO (baseline, shaped reward, curriculum, self-play), DQN baseline
- **Status:** COMPLETED (coursework), public repo

### 8. Malware Analysis: Memory Forensics with ML & Volatility
- **Objective:** Integrate machine learning with memory forensics (Volatility Framework) and YARA rules for ransomware detection in IoT-enabled energy systems
- **Work Performed:** 
  - Analyzed 18 memory dumps (6 benign, 12 ransomware families: WannaCry, Cerber, GandCrab, etc.)
  - Developed 100+ YARA rules for ransomware family classification
  - Built ML pipeline for malicious process identification from Volatility outputs
  - Automated Volatility plugin orchestration (malfind, pslist, vadinfo, yarascan)
- **Publication:** "Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems" — IEEE ICAIA 2026
- **Dataset:** Hugging Face — Vedaang/malware_analysis (33 GB analysis), Vedaang/malware-analysis-data bucket (~470 GB), Vedaang/malware-code-base bucket (3,384 files), Vedaang/malware-raw-dumps bucket
- **Technologies:** Python, Volatility3, YARA, scikit-learn, pandas, Jupyter, Docker, Hugging Face Hub
- **Status:** COMPLETED
- **Repository:** Public (https://github.com/Vedaang-Chopra/Malware_Analysis)

---

## Publications & Intellectual Property

| Item | Type | Venue/Status | Date | Notes |
|---|---|---|---|---|
| PCT/IN2022/058026 | Patent (Filed) | WIPO / Justia | 2022 | Unsupervised distributional thresholding for wireless connectivity anomaly detection |
| Ontology-based Text Classification | Workshop Paper | CEUR Workshop Proceedings Vol. 2786 | 2020 | DOID ontology-driven classifier; 10% improvement over ML baselines. **OUTDATED** — different domain, 6 years old |
| Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems | Conference Paper | IEEE ICAIA 2026 | 2026 | Memory forensics + ML + YARA for ransomware detection; co-author Sonika Malik |
| CAD RL Post-Training / ARTEMIS / CERBERUS | Target Publications | NeurIPS/ICML/ICLR workshops (planned) | 2026-2027 | IN PROGRESS — no submissions yet |

---

## Technical Skills (Verified)

### Agentic AI & LLM Systems
| Skill | Evidence | Proficiency |
|---|---|---|
| LangGraph | CAD (agent_langgraph), ATHENA (supervisor), SHASTRA (planner) | **HIGH** — multiple production/research systems |
| LangChain | Fortinet agentic RAG, CAD rag module | **HIGH** |
| Agentic RAG | Fortinet production system | **HIGH** |
| Tool/Function Calling | Fortinet (structured), CAD (execution), ATHENA (tools.py) | **HIGH** |
| Multi-Agent Orchestration | ATHENA (5 agents), SHASTRA (registry), CAD (repair loop) | **HIGH** |
| Structured Generation (Pydantic) | ATHENA (OrchestrationRouter, ReflectionRouter), SHASTRA, CAD | **HIGH** |
| LLM-as-a-Judge | CAD (vlm_evaluation), ATHENA (reflection) | **MEDIUM** |
| Planning & Reasoning | SHASTRA (trace-to-graph), CAD (repair loop), ATHENA (CoT) | **MEDIUM-HIGH** |
| Long-Horizon Task Decomposition | SHASTRA (workflow reuse), CAD (multi-step repair) | **MEDIUM** |

### AI/ML Core
| Skill | Evidence | Proficiency |
|---|---|---|
| PyTorch | CERBERUS (DDP), ARTEMIS, CAD, RL Soccer, Fortinet | **HIGH** |
| Hugging Face Transformers | ARTEMIS (VLM backends), CERBERUS (CLIP/SBERT), CAD | **HIGH** |
| Deep Learning / CNNs | CERBERUS, Fortinet classifiers, coursework | **HIGH** |
| Vision Transformers | CERBERUS (CLIP), ARTEMIS (VLMs), coursework | **HIGH** |
| NLP / Computer Vision | Fortinet, CAD, CERBERUS, coursework | **HIGH** |
| Scikit-Learn | Fortinet (60+ classifiers), coursework | **HIGH** |

### LLMs / VLMs / Inference / Evaluation (VERIFIED ONLY)
| Skill | Evidence | Proficiency |
|---|---|---|
| vLLM | ARTEMIS (serving 6+ backends), CERBERUS | **HIGH** |
| VLM Routing & Evaluation | ARTEMIS (router, load balancer, 5 benchmarks) | **HIGH** |
| Model Evaluation & Benchmarking | CAD (202 tests), ATHENA (BLEU/CLIPScore), ARTEMIS | **HIGH** |
| Inference Optimization | Fortinet (ONNX ~40% latency), ARTEMIS (routing), CERBERUS (edge) | **HIGH** |
| CLIP / SBERT / FAISS | CERBERUS (frozen encoders, retrieval), ARTEMIS | **HIGH** |
| Cross-Modal Retrieval | CERBERUS (PixMo R@5 78%), ARTEMIS | **MEDIUM-HIGH** |
| Quantization | Fortinet (ONNX edge deployment involved quantization) | **MEDIUM** |
| Matryoshka Representation Learning | CERBERUS (4096→128 dims, 96% retention) | **MEDIUM-HIGH** |
| Perceiver Resampler | CERBERUS (ablation: retrieval collapses) | **MEDIUM** |

### ❌ DO NOT CLAIM — UNVERIFIED / CONTRADICTED
| Skill | Status | Reason |
|---|---|---|
| RLHF | CONTRADICTED | Zero code implementing RLHF in any codebase |
| RLAIF | CONTRADICTED | Zero code implementing RLAIF |
| DPO | CONTRADICTED | No DPO implementation |
| SFT (Supervised Fine-Tuning) | CONTRADICTED | No fine-tuning code in any codebase |
| LoRA / QLoRA Fine-tuning | CONTRADICTED | Not in any codebase |
| Reward Modeling (RL sense) | CONTRADICTED | No reward model trained; geometric metrics used as scoring |
| Pre-training / LLM Training | UNVERIFIED | No pre-training or large-scale LLM training experience |
| Distributed LLM Training (FSDP, DeepSpeed, Megatron) | UNVERIFIED | No multi-node LLM training; DDP only for CERBERUS (encoder alignment) |
| JAX | UNVERIFIED | No JAX code in any repository |
| TPU | UNVERIFIED | No TPU experience |
| CUDA Kernel Programming | UNVERIFIED | No custom CUDA kernels |

### Reinforcement Learning (Academic/Verified)
| Skill | Evidence | Proficiency |
|---|---|---|
| PPO | RL Soccer (coursework: baseline, shaped, curriculum, self-play) | **MEDIUM** (academic) |
| DQN | RL Soccer (coursework) | **MEDIUM** (academic) |
| Reward Shaping | RL Soccer (ppo_shaped stage) | **MEDIUM** (academic) |
| Curriculum Learning | RL Soccer (ppo_curriculum stage) | **MEDIUM** (academic) |
| Self-Play | RL Soccer (ppo_selfplay stage) | **MEDIUM** (academic) |
| Ray/RLlib | RL Soccer training | **MEDIUM** |

**Framing Rule:** Always qualify RL skills as "(academic project)" or "(coursework)" — these are not production/research RL experience.

### Systems & Infrastructure
| Skill | Evidence | Proficiency |
|---|---|---|
| Python | All projects, Fortinet (primary) | **EXPERT** |
| Go | Fortinet (OpenSearch scaling, backend services) | **HIGH** |
| C/C++ | Coursework, some systems work | **MEDIUM** |
| SQL/PostgreSQL | Fortinet pipelines | **MEDIUM** |
| Redis | Fortinet, listed in skills | **MEDIUM** |
| OpenSearch/Elasticsearch | Fortinet (50→2000 events/sec) | **HIGH** |
| Docker | All projects, Fortinet | **HIGH** |
| Linux | Daily driver, Fortinet, clusters | **HIGH** |
| Git | All repos | **HIGH** |
| ONNX Runtime | Fortinet (edge inference) | **HIGH** |
| FastAPI | ARTEMIS, listed in skills | **MEDIUM** |
| Azure | Fortinet cloud | **MEDIUM** |
| W&B / TensorBoard | CAD (experiment tracking), listed | **MEDIUM** |
| Slurm | CAD (multi-GPU), ARTEMIS (CUDA_VISIBLE_DEVICES) | **MEDIUM** |
| DDP (Distributed Data Parallel) | CERBERUS (H100/A100 clusters) | **MEDIUM-HIGH** |
| Mixed Precision Training | CERBERUS (H100/A100) | **MEDIUM-HIGH** |

### ❌ DO NOT CLAIM — Systems (UNVERIFIED)
| Skill | Status | Reason |
|---|---|---|
| Kubernetes | UNVERIFIED | Listed in GitHub profile README but not in any codebase |
| DeepSpeed | UNVERIFIED | Listed in career fair resumes but no code evidence |
| FSDP | UNVERIFIED | No Fully Sharded Data Parallel experience |
| Megatron-LM | UNVERIFIED | No Megatron experience |
| TensorRT | UNVERIFIED | No TensorRT code |
| Triton Inference Server | UNVERIFIED | No Triton experience |
| Airflow / Prefect | UNVERIFIED | No orchestration framework code |
| MLflow | UNVERIFIED | Listed but no evidence (W&B used instead) |

---

## Research Interests
1. **Agentic AI Systems** — Multi-agent orchestration, tool-use planning, workflow reuse, long-horizon task decomposition
2. **Execution-Grounded Evaluation** — Moving beyond token-level metrics to functional correctness (code execution, geometric verification, visual judgment)
3. **Efficient Multimodal Inference** — Cost-aware routing, model compression (Matryoshka, Perceiver), edge deployment
4. **RL for Structured Generation** — Reward design for verifiable domains (CAD, code), inference-time compute scaling
5. **Production ML Systems** — Reliable deployment, monitoring, evaluation pipelines at scale

---

## Role Interests (Priority Order)

| Role Family | Fit Rationale | Target Companies |
|---|---|---|
| **Agentic AI / Applied AI Research Engineer** | Strongest fit: 3 agentic projects (CAD, ATHENA, SHASTRA) + production agentic RAG + LangGraph expertise | Cohere, Databricks, Scale AI, Salesforce Research, Together AI, Fireworks AI, Anyscale, W&B, xAI, AI2, Reka, Character.AI, Runway |
| **LLM Evaluation / Inference Research Engineer** | CAD evaluation harness (202 tests), ARTEMIS routing benchmarks, CERBERUS edge deployment, Fortinet ONNX | Anthropic (evals), OpenAI (evals), Together AI, Fireworks, NVIDIA, Anyscale |
| **ML Engineer / Applied Scientist (Production-Focused)** | 4+ years production ML, patent, scaling pipelines, edge inference, SLA forecasting | Google, Amazon, Microsoft, Meta (applied), Salesforce, ServiceNow, Snowflake, Palantir |
| **Research Engineer — Agents/Reasoning** | Multi-agent orchestration, tool-use, planning, LangGraph, structured generation | OpenAI (Agent team), Anthropic, Sierra AI, Cognition, Adept (referral required) |

**NOT Targeting:** Research Scientist roles (PhD required), Pure RL/Post-Training RE roles (cannot credibly claim — model is frozen in CAD work), Frontier lab principal RE roles (publication gap)

---

## Known Gaps (Honest Assessment)

| Gap | Severity | Mitigation |
|---|---|---|
| No first-author top-venue publications (NeurIPS/ICML/ICLR) | HIGH | Submit CAD/ARTEMIS/CERBERUS to 2026 workshops; arXiv preprint ASAP |
| No distributed LLM training experience (multi-node, FSDP, DeepSpeed) | HIGH | Run multi-GPU training experiment on GT cluster (even LoRA on 4 GPUs) |
| No JAX experience | MEDIUM (Google-specific) | Only pursue if targeting Google/DeepMind; otherwise skip |
| No synthetic data pipeline experience | MEDIUM | Build one for CAD work (parametric variation sampling) |
| F-1 visa / sponsorship requirement | STRUCTURAL | Referrals, target H-1B sponsors, OPT for initial employment |
| GitHub/web presence weak | LOW-MEDIUM | Pin AI repos, write READMEs, update website with project pages |
| Zero referrals used in job search | HIGH | Activate GT alumni network, Fortinet contacts, professor connections |