# Project Index

| Project | Type | Status | Repo | Key Strength |
|---|---|---|---|---|
| **CAD Code Generation** | Research (CORE Lab) | IN PROGRESS | Private: CAD_Code_Generation | 16-module system, 202 tests, execution-grounded verification |
| **SHASTRA** | Research (CS 8903) | IN PROGRESS | Private: fork of gatech-sysml/shastra | Trace-to-graph, LangGraph planner, workflow reuse |
| **ATHENA** | Research (CS 8903) | COMPLETED | Private: ATHENA | 5-agent supervisor pattern, reflection, BLEU/CLIPScore eval |
| **ARTEMIS** | Research (CS 8903) | IN PROGRESS | Public: Which-VLM-Router | Neural router checkpoint, vLLM serving, SLA load balancing |
| **CERBERUS** | Research (CS 8903) | IN PROGRESS | Public: Edge-Glass | DDP training, MRL, H100/A100, negative Perceiver result |
| **Sign Reading AR Glasses** | Research/Engineering | IN PROGRESS | Private: Sign_Reading_AR_Glasses | Multi-platform, production v2, assistive tech |
| **RL Soccer** | Coursework | COMPLETED | Public: RL_Soccer_project | PPO/DQN variants, Ray/RLlib, reward shaping |
| **AI Security** | Coursework | COMPLETED | Public: AI-Security | Adversarial attacks, controlled ablations |
| **Fortinet Agentic RAG** | Production (Industry) | DEPLOYED | Internal (Fortinet) | Hackathon → production, ~70% resolution reduction |
| **Fortinet Wireless Anomaly Detection** | Production (Industry) | PATENTED | Internal (Fortinet) | Patent PCT/IN2022/058026, ~75% troubleshooting reduction |
| **Fortinet OpenSearch Scaling** | Production (Industry) | DEPLOYED | Internal (Fortinet) | 50→2000 events/sec (40x), Golang |
| **Fortinet Edge ONNX Inference** | Production (Industry) | DEPLOYED | Internal (Fortinet) | ~40% latency reduction, edge deployment |
| **Malware Analysis: Memory Forensics + ML** | Research/Production | COMPLETED | Public: Vedaang-Chopra/Malware_Analysis | 18 memory dumps, 100+ YARA rules, IEEE ICAIA 2026 publication, 33GB analysis + 470GB raw on HF |

---

## 1. CAD Code Generation Pipeline (CORE Robotics Lab)

### Basic Information
- **Project Name:** CAD Code Generation / CAD-CODE
- **Type:** Graduate Research (Primary)
- **Lab:** CORE Robotics Lab @ Siemens, Georgia Tech
- **Advisor:** Dr. Matthew Gombolay
- **Dates:** January 2026 — Present
- **Repository:** Private (CAD_Code_Generation) — 113 commits, 7 branches
- **Status:** IN PROGRESS — active research, no publication yet

### Objective
Generate functionally correct parametric CAD programs (CadQuery) using LLMs with **inference-time search and geometric verification** rather than single-pass generation or RL post-training.

### Problem Solved
Traditional code generation uses token-level supervision and single-pass generation. For CAD, functional correctness requires:
- Compilation validity (syntax)
- Geometric correctness (STL/B-Rep matching)
- Structural fidelity (feature-tree alignment)

### Architecture (16 Modules)
| Module | Purpose | Verified |
|---|---|---|
| `agent_langgraph` | LangGraph-orchestrated repair loop | ✅ |
| `generation` | CadQuery code generation from LLM | ✅ |
| `metric_evaluation` | Compile + geometric scoring | ✅ |
| `visual_analysis` | Visual inspection of generated models | ✅ |
| `vlm_evaluation` | VLM-based visual quality judgment | ✅ |
| `failure_classification` | Categorize failure modes | ✅ |
| `feature_trees` | B-Rep feature extraction & comparison | ✅ |
| `brep_trajectory` | Per-step geometric trajectory analysis | ✅ |
| `operation_attribution` | Source-edit span attribution | ✅ |
| `ast_graphs` | AST structural analysis | ✅ |
| `code_graphs` | Code graph construction | ✅ |
| `roundtrip` | Round-trip validation | ✅ |
| `structural_diff` | GT vs generated structural comparison | ✅ |
| `rag` | RAG-augmented prompt construction | ✅ |
| `prompt_evaluation` | Prompt quality assessment | ✅ |
| `infrastructure` | Shared utilities, config, execution | ✅ |

### Technologies
- **LLM Orchestration:** LangGraph (repair loop), structured generation (Pydantic)
- **Geometric Verification:** Chamfer Distance, Hausdorff Distance on STL & B-Rep
- **Code Analysis:** AST graphs, code graphs, feature trees, structural diff
- **Evaluation:** 202 automated tests, VLM visual judgment, RAG-augmented prompts
- **Infrastructure:** Multi-GPU Slurm clusters, W&B experiment tracking
- **Models:** Frozen LLMs (no fine-tuning, no RL post-training)

### CRITICAL CORRECTIONS (from Evidence Ledger)

| False Claim in Resumes | Truth |
|---|---|
| "RL-based post-training (PPO/GRPO)" | **FALSE** — Model is FROZEN, no training loop, no weight updates |
| "RLHF/RLAIF" | **FALSE** — Zero code implementing either |
| "Reward modeling" | **FALSE** — No reward model trained; geometric metrics used as scoring |
| "Fine-tuning / LoRA/QLoRA / SFT / DPO" | **FALSE** — Not in any codebase |
| "Reward functions" (RL sense) | **MISLEADING** — Use "geometric verification scoring" |

### Verified Resume-Worthy Claims
- "Built a closed-loop agentic pipeline for parametric CAD code generation: an LLM generates CadQuery programs, an execution environment returns compile and geometry feedback, and a LangGraph-orchestrated repair loop iteratively corrects errors"
- "Designed geometric verification components scoring compile validity, parametric 3D correctness (Chamfer/Hausdorff distances on STL and B-Rep), and repair trajectory quality"
- "Maintained a 202-test evaluation harness with VLM-based visual judgment and RAG-augmented prompt construction across a 16-module system"
- "Framing synthesis as inference-time search with verifiable geometric reward rather than single-pass generation or RL post-training"

### Current Status
- Active research, no publication submitted yet
- Target: NeurIPS/ICML/ICLR 2026 workshop or arXiv preprint

### Supporting Source Files
- `PROJECT_OVERVIEW.md` (explicitly states "NOT RLVR, model is frozen")
- Full codebase (16 modules, 202 tests)
- Private repo: CAD_Code_Generation

---

## 2. SHASTRA — Agentic Workflow Orchestration

### Basic Information
- **Project Name:** SHASTRA
- **Type:** Graduate Research (CS 8903 Special Problems)
- **Dates:** January 2026 — Present
- **Repository:** Private (fork of gatech-sysml/shastra)
- **Status:** IN PROGRESS

### Objective
Design a system to retrieve and adapt prior agent workflows for new long-horizon tasks under cost/latency constraints; enable compositional reuse via standardized workflow representations.

### Problem Solved
Agent workflows are typically single-use. SHASTRA enables:
- Converting execution traces into reusable task-composition graphs
- Retrieving relevant workflows for new tasks
- Adapting workflows under cost/latency constraints

### Architecture
| Component | Description | Status |
|---|---|---|
| Trace-to-Graph Pipeline | Event parsing → LLM semantic annotation → TDG construction | ✅ Implemented |
| LangGraph Planner | Planner agent with capability labels, confidence scores | ✅ Implemented |
| Component Registry | Pluggable YAML storage for workflow components | ✅ Implemented |
| Orchestrator | Coordination logic for workflow execution | ⚠️ Stub only |
| Executor | Actual workflow execution | ❌ Not done |

### Data Processed
- 94 GAIA sessions
- 4,037 events
- 1,377 semantic blocks
- 442 graph nodes

### Technologies
- LangGraph (planner)
- Pydantic (state schemas)
- YAML (registry storage)
- GAIA benchmark (evaluation)

### Verified Resume-Worthy Claims
- "Designing an agent workflow retrieval and adaptation framework enabling compositional reuse of prior tool-call sequences for new long-horizon tasks under cost/latency constraints"
- "Implementing a LangGraph-based planner with Pydantic state and a component registry with pluggable storage"
- "Trace-to-graph pipeline converting agent execution traces (GAIA, 94 sessions) into reusable task-composition graphs with dependency/control/conditional edges"

### Claims to Avoid
- "Orchestrator implemented" — it's a stub
- "Executor implemented" — not done
- "Workflow reuse in production" — still in design phase

### Supporting Source Files
- Private repo (fork of gatech-sysml/shastra)
- README documentation

---

## 3. ATHENA — Multi-Agent Screenplay Generation

### Basic Information
- **Project Name:** ATHENA
- **Type:** Graduate Research (CS 8903 Special Problems)
- **Dates:** January 2025 — May 2025 (COMPLETED)
- **Repository:** Private (ATHENA)
- **Co-author:** Prof. Vijay Madisetti

### Objective
Build a multi-agent orchestration pipeline for automated screenplay planning and keyframe synthesis with reflection-based quality critique.

### Architecture
- **Agents (5 specialized + Research):**
  1. Ideation Agent
  2. Character Design Agent
  3. World/Props Design Agent
  4. Story Generation Agent
  5. Scene Breakdown Agent
  6. Research Agent (tool-augmented: web search, YouTube, vector memory)
- **Orchestration:** Supervisor-worker pattern via LangGraph Command routing
- **Reflection Loop:** ReflectionRouter with repeat/feedback mechanism for quality critique
- **State Management:** Pydantic-validated structured outputs (OrchestrationRouter, ReflectionRouter)
- **Shared State:** JSON-based blackboard-style state (corrected: not "blackboard controller")

### Evaluation Framework
- **Text Metrics:** BLEU-4, ROUGE-L, METEOR, BERTScore, Perplexity
- **Visual Metrics:** CLIPScore, SSIM, PSNR
- **Dataset:** 100 reference videos (10 prompts × 10 videos), deconstructed into scenes/keyframes
- **Ontology-Bucketed Concept Coverage:** Fact coverage analysis

### Key Results (VERIFIED)
- BLEU-4: **+0.18 absolute improvement** over single-agent baseline (NOT +18%)
- CLIPScore: Evaluated (exact delta not verified in computed results — use "evaluated with CLIPScore")
- Ablation: Removing Research Agent reduced fact coverage by **27%**, visual relevance from **4.1 to 3.3/5.0** (n=5 raters)

### Technologies
- LangGraph (Command routing, supervisor pattern)
- Pydantic (structured outputs)
- GPT-4.1 + o4-mini (LLMs)
- Diffusion models (visual synthesis — referenced in paper)
- sacrebleu (BLEU computation — verified in text_metrics.py)

### Verified Resume-Worthy Claims
- "Built a multi-agent screenplay generation system with supervisor-worker orchestration using LangGraph Command routing"
- "Coordinated 5 specialized agents (ideation, character design, world building, story generation, scene breakdown) with reflection-based quality critique and dynamic plan modification"
- "Evaluated with BLEU-4, CLIPScore, METEOR, BERTScore, SSIM, PSNR metrics on 100 reference videos"
- "Ablation: removing Research agent reduced fact coverage by 27% and visual relevance from 4.1 to 3.3/5.0"

### Claims to Avoid (False/Unverified)
- ❌ "14-agent orchestration" — only 5 specialized + 1 research
- ❌ "Blackboard-style controller" — it's supervisor-worker via LangGraph Command
- ❌ "Keyframe synthesis" — generates screenplays, not keyframes (diffusion referenced but not implemented)
- ❌ "BLEU +18%" — it's +0.18 absolute
- ❌ "CLIPScore +22%" — not verified in computed results
- ❌ "GPT-1 for image/vision tasks" — from old resume, incorrect

### Supporting Source Files
- Private repo: ATHENA
- `supervisor.py` (orchestration logic)
- `tools.py` (web search, YouTube, vector memory)
- `text_metrics.py` (BLEU computation using sacrebleu)
- Evaluation JSONs (computed results)
- `athena.tex` (paper draft)

---

## 4. ARTEMIS — Cost-Aware VLM Routing

### Basic Information
- **Project Name:** ARTEMIS / Which-VLM-Router
- **Type:** Graduate Research (CS 8903 Special Problems)
- **Dates:** August 2025 — Present
- **Repository:** Public (https://github.com/Vedaang-Chopra/Which-VLM-Router)
- **Status:** IN PROGRESS

### Objective
Dynamic per-request VLM selection optimizing accuracy, latency, and cost via learned routing policies with SLA-aware load balancing.

### Architecture
| Component | Description | Verified |
|---|---|---|
| Neural Router | Predicts per-model utility scores | ✅ (checkpoint: best_multitask_router_v1.pt) |
| SLA-Aware Load Balancer | Enforces cost/latency budgets with capacity-aware scheduling | ✅ (YAML configs) |
| Unified Inference Engine | Serves 6+ VLM backends via vLLM | ✅ (README serving commands) |
| Routing Modes | accuracy, cheap, fast, balanced, reward-based | ✅ (README config) |

### Models Served (Verified)
1. Gemma 3 27B
2. Qwen3-VL 8B
3. Qwen2.5-VL 7B
4. DeepSeek OCR
5. Glider
6. Llama-4 Scout 17B

### Tasks Supported
- VQA (Visual Question Answering)
- OCR
- Captioning
- Reasoning

### Technologies
- vLLM (serving with CUDA_VISIBLE_DEVICES, bfloat16)
- PyTorch (router training)
- YAML (SLA configuration)
- CUDA (multi-GPU)

### Verified Resume-Worthy Claims
- "Developing a cost-aware routing system for Vision-Language Models that dynamically selects the optimal VLM per request"
- "Trained a neural multi-task router with SLA-aware load balancing"
- "Serving 6+ VLM backends via vLLM across VQA, OCR, captioning, and reasoning tasks with dynamic routing modes (accuracy/cost/latency)"

### Claims to Avoid (UNVERIFIED — Do Not Use)
- ❌ "100K+ query profiles" — not verified in code or notebooks
- ❌ "~30% lower cost" — not verified in benchmarks
- ❌ "KL-divergence matching" — not verified in code
- ❌ "F1 0.97-0.98" — not verified
- ❌ "Outperforming RouteLLM" — not verified
- ❌ "Near-oracle accuracy" — not verified

### Supporting Source Files
- Public repo: Which-VLM-Router
- README (architecture, serving commands, config)
- `best_multitask_router_v1.pt` (trained checkpoint)
- SLA YAML configs

---

## 5. CERBERUS — Vision-Language Alignment for Edge

### Basic Information
- **Project Name:** CERBERUS / Edge-Glass
- **Type:** Graduate Research (CS 8903 Special Problems)
- **Dates:** August 2025 — Present
- **Repository:** Public (https://github.com/Vedaang-Chopra/Edge-Glass)
- **Status:** IN PROGRESS
- **Paper:** CEREBRUS.pdf (in repo)

### Objective
Encoder-frozen cross-modal alignment with compressed embeddings for edge-deployable multimodal retrieval.

### Architecture
| Component | Description | Verified |
|---|---|---|
| Frozen Encoders | CLIP ViT-L/14 (vision), SBERT (text), Whisper (audio ablations) | ✅ |
| Matryoshka Representation Learning | Multi-scale embeddings 4096→128 dims | ✅ |
| Perceiver Resampler | Input compression | ✅ (but negative result) |
| TRM Decoder | Conditioned on compressed latents | ✅ |
| Qwen-14B Decoder Integration | Large decoder on aligned latents | ✅ |

### Training
- **Method:** DDP (Distributed Data Parallel)
- **Precision:** Mixed precision
- **Infrastructure:** H100/A100 clusters
- **Loss:** Contrastive alignment on frozen encoders

### Results (VERIFIED)
- **R@5 78%** on PixMo vision-text retrieval with frozen encoders
- **512-d retains ~96%** of full-dimensional R@5 performance
- **TRM decoder outperforms text-only baseline:** ROUGE-L 0.24 vs 0.08; BLEU 0.066 vs 0.008
- **Negative Result:** Perceiver Resampler ablation — retrieval collapses to chance (identifies initialization/gradient issues)

### Technologies
- PyTorch (DDP, mixed precision)
- CLIP, SBERT, Whisper
- Matryoshka Representation Learning
- Perceiver Resampler
- TRM decoder, Qwen-14B
- H100/A100 clusters

### Verified Resume-Worthy Claims
- "Cross-modal alignment with frozen encoders (CLIP/SBERT) using Matryoshka Representation Learning"
- "DDP-based distributed training with mixed precision on H100/A100 clusters"
- "Achieved R@5 78% on PixMo retrieval; 512-d retains ~96% of full-dimensional performance"
- "TRM decoder on compressed latents outperformed text-only baseline (ROUGE-L: 0.24 vs 0.08)"
- "Perceiver Resampler ablation: negative result identifying initialization/gradient issues"

### Supporting Source Files
- Public repo: Edge-Glass
- README (architecture, results, training details)
- CEREBRUS.pdf (research paper)

---

## 6. Sign Reading AR Glasses — Assistive Technology

### Basic Information
- **Project Name:** Sign Reading AR Glasses
- **Type:** Research/Engineering (Assistive Tech)
- **Repository:** Private (Sign_Reading_AR_Glasses)
- **Status:** IN PROGRESS

### Objective
AR scene understanding system for Meta Ray-Ban smart glasses designed for blind and low-vision users.

### Architecture
- **Backend:** Gemma 4 26B via LM Studio / OpenRouter
- **Clients:** Android, iOS, Web/PWA
- **Production Version:** v2 with health checks, backend server, monitoring
- **Target Users:** Blind and low-vision users

### Technologies
- VLM (Gemma 4 26B)
- Mobile development (Android, iOS)
- Web/PWA
- LM Studio / OpenRouter (inference)
- Production monitoring

### Verified Resume-Worthy Claims
- "AR scene understanding system for Meta Ray-Ban smart glasses"
- "VLM-powered scene understanding (Gemma 4 26B)"
- "Cross-platform clients (Android, iOS, Web/PWA)"
- "Production-grade system with health monitoring"
- "Assistive technology for blind and low-vision users"

### Supporting Source Files
- Private repo: Sign_Reading_AR_Glasses
- README (full architecture documentation)

---

## 7. RL Soccer — Reinforcement Learning (Coursework)

### Basic Information
- **Project Name:** RL Soccer
- **Type:** Academic Project (Coursework)
- **Repository:** Public (RL_Soccer_project) — fork of soccer-twos-starter
- **Status:** COMPLETED

### Objective
RL agents for 2v2 soccer using Ray/RLlib with various training strategies.

### Methods Implemented
| Stage | Method | Verified |
|---|---|---|
| `ppo_baseline` | PPO baseline | ✅ |
| `ppo_shaped` | PPO with reward shaping | ✅ |
| `ppo_curriculum` | PPO with curriculum learning | ✅ |
| `ppo_selfplay` | PPO with self-play | ✅ |
| `dqn_baseline` | DQN baseline | ✅ |

### Technologies
- Ray/RLlib (distributed training)
- GPU detection and utilization
- PPO, DQN algorithms

### Verified Resume-Worthy Claims
- "Implemented PPO and DQN agents with reward shaping, curriculum learning, and self-play"
- "Ray/RLlib distributed training with GPU detection"
- "Custom reward shaping and curriculum learning strategies"

### Framing Note
**This is coursework/academic project.** Frame as "academic project" or "coursework" — not production research.

### Supporting Source Files
- Public repo: RL_Soccer_project
- Staged implementations in subdirectories

---

## 8. AI Security — Adversarial Robustness Evaluation

### Basic Information
- **Project Name:** AI Security
- **Type:** Coursework-style Project
- **Dates:** 2025 — 2026
- **Repository:** Public (AI-Security)
- **Status:** COMPLETED

### Work Performed
- PGD adversarial attacks on image classifiers (ResNet)
- Embedding poisoning and blind backdoor triggers on NLP models (SST-2)
- Model extraction attacks on LLMs
- Membership inference attacks (MIA) on LLMs
- LLM watermarking/extraction
- Refusal LoRA bypass demonstrations for safety evaluation
- Controlled ablations measuring attack-success vs clean-accuracy tradeoffs

### Assessment
**This reads as coursework/homework.** No novel contribution, no benchmark comparison, no research insight. It demonstrates technical implementation ability but not research contribution.

### Verified Resume-Worthy Claims
- "Implemented PGD adversarial attacks, embedding poisoning, blind backdoor triggers, model extraction, membership inference on LLMs, and LLM watermarking"
- "Controlled ablations measuring attack-success vs clean-accuracy tradeoffs"

### Recommendation
**Remove from 1-page resumes.** Keep only in extended variant if space permits, but rewrite to emphasize any novel methodology (none identified).

### Supporting Source Files
- Public repo: AI-Security

---

## 9. Fortinet Production Systems (Industry)

### 9.1 Agentic RAG Diagnostics System
- **Period:** 2025 (SDE II)
- **Description:** LLM plans multi-step tool calls over network telemetry, invokes APIs, verifies hypotheses via structured function calling, produces autonomous root-cause analysis
- **Scale:** ~10K+ managed devices (self-reported)
- **Impact:** ~70% reduction in mean resolution time (hackathon → production)
- **Technologies:** LLM orchestration, tool/function calling, structured output, RAG, LangChain/LangGraph
- **Evidence:** LinkedIn description
- **Confidence:** VERIFIED (system deployed); METRICS: PARTIALLY VERIFIED

### 9.2 Wireless Connectivity Anomaly Detection (Patent)
- **Period:** 2022-2025
- **Description:** Unsupervised distributional thresholding for wireless connectivity anomaly detection using density-based analysis
- **Patent:** PCT/IN2022/058026 (filed, on Justia)
- **Impact:** ~75% reduction in manual troubleshooting (self-reported)
- **Evidence:** Patent filing, LinkedIn, GitHub profile
- **Confidence:** VERIFIED (patent); METRICS: PARTIALLY VERIFIED

### 9.3 OpenSearch Ingestion Scaling
- **Period:** 2021-2025
- **Description:** Scaled telemetry ingestion from 50 to 2,000 events/sec (40x) using Golang
- **Impact:** Enterprise-grade throughput for network monitoring
- **Evidence:** LinkedIn, GitHub profile (consistent)
- **Confidence:** VERIFIED

### 9.4 Edge ML Inference (ONNX Runtime)
- **Period:** 2021-2025
- **Description:** Deployed ML models via ONNX Runtime for on-device anomaly detection on access points/switches
- **Impact:** ~40% latency reduction (GPU-to-CPU with quantization)
- **Evidence:** Original CV, LinkedIn
- **Confidence:** VERIFIED (deployed); METRICS: PARTIALLY VERIFIED

### 9.5 SLA Forecasting Pipelines
- **Period:** 2021-2025
- **Description:** 60+ classifiers across 4 categories (performance, capacity, availability, connectivity) with automated evaluation and retraining
- **Scale:** Production traffic for enterprise network monitoring
- **Evidence:** LinkedIn
- **Confidence:** VERIFIED (system); SCALE: PARTIALLY VERIFIED

---

## Project Evidence Mapping for Resume Customization

### For Agentic AI Roles → Lead With:
1. **CAD Pipeline** (closed-loop agentic, LangGraph repair, 202 tests)
2. **ATHENA** (5-agent supervisor, reflection, structured generation)
3. **SHASTRA** (workflow reuse, trace-to-graph, LangGraph planner)
4. **Fortinet Agentic RAG** (production agentic system)

### For LLM Evaluation/Inference Roles → Lead With:
1. **CAD Evaluation Harness** (202 tests, geometric verification, VLM judgment)
2. **ARTEMIS** (VLM routing benchmarks, vLLM serving, SLA optimization)
3. **CERBERUS** (edge deployment, DDP training, compression)
4. **Fortinet ONNX Inference** (production edge optimization)

### For Applied Scientist / ML Engineer Roles → Lead With:
1. **Fortinet Production Suite** (agentic RAG, patent, OpenSearch scaling, ONNX, 60+ classifiers)
2. **CAD Pipeline** (production-grade evaluation, 16 modules, 202 tests)
3. **ARTEMIS** (production VLM serving, routing, load balancing)
4. **CERBERUS** (distributed training, H100/A100, edge optimization)

### For Research Engineer — Agents/Reasoning → Lead With:
1. **CAD Pipeline** (inference-time search, verification, repair loops)
2. **ATHENA** (multi-agent, supervisor, reflection, evaluation)
3. **SHASTRA** (workflow reuse, compositional graphs)
4. **Fortinet Agentic RAG** (production tool-use, function calling)

---

## 10. Malware Analysis: Memory Forensics with ML & Volatility

### Basic Information
- **Project Name:** Malware Analysis: Memory Forensics with ML & Volatility
- **Type:** Research/Production (Cybersecurity + ML)
- **Dates:** 2025 — 2026
- **Repository:** Public (https://github.com/Vedaang-Chopra/Malware_Analysis)
- **Status:** COMPLETED
- **Publication:** "Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems" — IEEE ICAIA 2026
- **Hugging Face Dataset:** Vedaang/malware_analysis (33 GB analysis files)
- **Hugging Face Buckets:** 
  - malware-analysis-data (~470 GB)
  - malware-code-base (3,384 files)
  - malware-raw-dumps (raw dumps + scans)

### Objective
Integrate machine learning with memory forensics (Volatility Framework) and YARA rules for ransomware detection in IoT-enabled energy systems.

### Work Performed
- **Memory Dump Analysis:** Automated analysis of 18 memory dumps (6 benign, 12 ransomware families: WannaCry, Cerber, GandCrab, etc.)
- **YARA Rule Development:** Developed 100+ YARA rules for ransomware family classification
- **ML Pipeline:** Built ML pipeline for malicious process identification from Volatility outputs
- **Volatility Plugin Orchestration:** Automated Volatility plugin orchestration (malfind, pslist, vadinfo, yarascan)
- **Dataset Curation:** Hosted on Hugging Face — 33 GB analysis files + 470 GB raw memory dumps across dataset repo and buckets

### Technologies
- **Forensics:** Volatility3, YARA
- **ML:** scikit-learn, pandas
- **Environment:** Python, Jupyter, Docker
- **Data Platform:** Hugging Face Hub (datasets + buckets)

### Verified Resume-Worthy Claims
- "Analyzed 18 memory dumps (6 benign, 12 ransomware: WannaCry, Cerber, GandCrab, etc.) using Volatility Framework"
- "Developed 100+ YARA rules for ransomware family classification"
- "Built ML pipeline for malicious process identification from Volatility outputs"
- "Published at IEEE ICAIA 2026: 'Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems'"
- "Dataset hosted on Hugging Face: 33GB analysis + 470GB raw memory dumps across dataset repo and buckets"
- "Automated Volatility plugin orchestration (malfind, pslist, vadinfo, yarascan)"

### Supporting Source Files
- Public repo: Vedaang-Chopra/Malware_Analysis
- IEEE ICAIA 2026 publication
- Hugging Face: Vedaang/malware_analysis (dataset), Vedaang/malware-analysis-data (bucket), Vedaang/malware-code-base (bucket), Vedaang/malware-raw-dumps (bucket)