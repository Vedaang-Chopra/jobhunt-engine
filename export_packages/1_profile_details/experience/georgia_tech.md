# Georgia Institute of Technology — CORE Robotics Lab @ Siemens, Atlanta, GA
**Role:** Graduate Research Assistant
**Dates:** January 2026 — Present
**Advisor:** Dr. Matthew Gombolay

## Responsibilities
| Area | Details | Evidence | Confidence |
|---|---|---|---|
| Research Leadership | Primary investigator on CAD code generation project | PROJECT_OVERVIEW.md, codebase | VERIFIED |
| System Architecture | Designed 16-module closed-loop agentic pipeline | Codebase (16 modules, 202 tests) | VERIFIED |
| Evaluation Design | Built execution-grounded evaluation harness | metric_evaluation, feature_trees, brep_trajectory modules | VERIFIED |
| Experiment Management | W&B tracking, multi-GPU Slurm clusters | Skills, codebase references | VERIFIED |

## Key Project: CAD Code Generation with Execution-Grounded Verification
- **Objective:** Generate functionally correct parametric CAD programs (CadQuery) using frozen LLMs with inference-time search and geometric verification
- **CRITICAL CORRECTION:** This is **NOT RL post-training**. The model is FROZEN. No weight updates. No PPO/GRPO training loop. No RLHF/RLAIF.
- **Architecture:** 16 modules — agent_langgraph, generation, metric_evaluation, visual_analysis, vlm_evaluation, failure_classification, feature_trees, brep_trajectory, operation_attribution, ast_graphs, code_graphs, roundtrip, structural_diff, rag, prompt_evaluation, infrastructure
- **Verification Pipeline:** Compile validity → Geometric correctness (STL/B-Rep Chamfer/Hausdorff) → Repair trajectory quality → VLM visual judgment
- **Evaluation Harness:** 202 automated tests, RAG-augmented prompt construction, AST/code-graph structural analysis
- **Status:** IN PROGRESS (active research, no publication yet)
- **Evidence:** PROJECT_OVERVIEW.md, full codebase access (private repo: CAD_Code_Generation)
- **Confidence:** VERIFIED (architecture, modules, tests); CLAIMS ABOUT RL: CONTRADICTED (false)

## Resume-Worthy Claims (Verified)
- "Building a closed-loop agentic pipeline for parametric CAD code generation: an LLM generates CadQuery programs, an execution environment returns compile and geometry feedback, and a LangGraph-orchestrated repair loop iteratively corrects errors — framing synthesis as inference-time search with verifiable geometric reward rather than single-pass generation."
- "Designing geometric verification components that score compile validity, parametric 3D correctness (Chamfer/Hausdorff distances on STL and B-Rep representations), and repair trajectory quality; maintaining a 202-test evaluation harness with VLM-based visual judgment and RAG-augmented prompt construction across a 16-module system."
- "Framing synthesis as inference-time search with verifiable geometric reward rather than single-pass generation or RL post-training."

## Metrics Registry
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| System modules | 16 | 16 modules in codebase | SAFE | "16-module system" |
| Automated tests | 202 | Full evaluation harness | SAFE | "202-test evaluation harness" |
| Model status | FROZEN | No training, no fine-tuning, no RL post-training | SAFE | "frozen LLM (no fine-tuning, no RL post-training)" |

---

# Georgia Institute of Technology — CS 8903 Special Problems, Atlanta, GA
**Role:** Graduate Researcher
**Dates:** January 2025 — Present

## Project Portfolio

### SHASTRA — Agentic Workflow Orchestration (Jan 2026 — Present)
- **Objective:** Retrieve and adapt prior agent workflows for new long-horizon tasks under cost/latency constraints
- **Architecture:** Trace-to-graph pipeline: event parsing → LLM semantic annotation → Task-Dependency Graph (TDG) with dependency/control/conditional edges
- **Technologies:** LangGraph-based planner, Pydantic state schemas, component registry with pluggable YAML storage
- **Data:** 94 GAIA sessions (4,037 events, 1,377 semantic blocks, 442 graph nodes)
- **Status:** IN PROGRESS — planner implemented, registry done, orchestrator stub, executor NOT done
- **Evidence:** Private repo (fork of gatech-sysml/shastra), README
- **Confidence:** VERIFIED (planner, registry); ORCHESTRATOR: IN PROGRESS; EXECUTOR: NOT DONE

### ATHENA — Multi-Agent Screenplay Generation (Jan — May 2025)
- **Objective:** Automated screenplay planning and keyframe synthesis via multi-agent orchestration
- **Architecture:** 5 specialized agents (Ideation, Character Design, World/Props, Story Generation, Scene Breakdown) + Research agent; Supervisor-worker pattern via LangGraph Command routing; Reflection/critique loop with dynamic plan modification
- **Tools:** Web search, YouTube, vector memory (tools.py)
- **Evaluation:** BLEU-4 (+0.18 absolute over baseline — NOT +18%), CLIPScore, METEOR, BERTScore, SSIM, PSNR on 100 reference videos (10 prompts × 10 videos)
- **Key Ablation:** Removing Research agent reduced fact coverage by 27%, visual relevance 4.1→3.3/5.0
- **Status:** COMPLETED
- **Co-author:** Prof. Vijay Madisetti
- **Evidence:** Private repo (ATHENA), supervisor.py, evaluation JSONs, paper draft (athena.tex)
- **Confidence:** VERIFIED (architecture, agents, evaluation pipeline); BLEU METRIC: CORRECTED (+0.18 absolute)

### ARTEMIS — Cost-Aware VLM Routing (Aug 2025 — Present)
- **Objective:** Dynamic per-request VLM selection optimizing accuracy, latency, and cost
- **Architecture:** Neural router → SLA-aware load balancer → Unified inference engine (vLLM) serving 6+ VLM backends
- **Models:** Gemma 3 27B, Qwen3-VL 8B, Qwen2.5-VL 7B, DeepSeek OCR, Glider, Llama-4 Scout 17B
- **Routing Modes:** accuracy, cheap, fast, balanced, reward-based (routing reward, NOT RL reward)
- **Verified Artifacts:** Trained checkpoint (best_multitask_router_v1.pt), vLLM serving commands, SLA YAML configs, README
- **UNVERIFIED CLAIMS (DO NOT USE):** "100K+ query profiles", "~30% lower cost", "KL-divergence matching", "outperforming RouteLLM", "F1 0.97-0.98"
- **Status:** IN PROGRESS
- **Evidence:** Public repo (Which-VLM-Router), README, checkpoint file
- **Confidence:** VERIFIED (architecture, checkpoint, serving, models); BENCHMARK CLAIMS: UNVERIFIED

### CERBERUS — Vision-Language Alignment for Edge (Aug 2025 — Present)
- **Objective:** Encoder-frozen cross-modal alignment with compressed embeddings for edge deployment
- **Architecture:** Frozen CLIP ViT-L/14 + SBERT (+ Whisper ablations); Matryoshka Representation Learning (4096→128 dims); Perceiver Resampler; TRM decoder on compressed latents; Qwen-14B decoder integration
- **Training:** DDP distributed training, mixed precision on H100/A100 clusters
- **Results:** R@5 78% on PixMo retrieval; 512-d retains ~96% of full-dimensional performance; TRM decoder outperforms text-only (ROUGE-L: 0.24 vs 0.08)
- **Negative Result:** Perceiver Resampler ablation — retrieval collapses to chance (initialization/gradient issues)
- **Status:** IN PROGRESS
- **Evidence:** Public repo (Edge-Glass), README, CEREBRUS.pdf paper
- **Confidence:** VERIFIED (architecture, training setup, results, negative result)

### AI Security — Adversarial Robustness Evaluation (2025 — 2026)
- **Objective:** Systematic study of failure modes in ML systems
- **Work:** PGD adversarial attacks, embedding poisoning, blind backdoor triggers, model extraction, membership inference on LLMs, LLM watermarking
- **Methodology:** Controlled ablations, attack-success vs clean-accuracy tradeoffs
- **Nature:** Coursework-style project — reads as homework, no novel contribution
- **Status:** COMPLETED
- **Evidence:** Public repo (AI-Security)
- **Confidence:** VERIFIED (work done); RESEARCH VALUE: LOW (coursework)

## Metrics Registry (from METRICS_REGISTRY.md)

### CAD Code Generation Pipeline
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| System modules | 16 | 16 modules in codebase | SAFE | "16-module system" |
| Automated tests | 202 | Full evaluation harness | SAFE | "202-test evaluation harness" |
| Model status | FROZEN | No training, no fine-tuning, no RL post-training | SAFE | "frozen LLM (no fine-tuning, no RL post-training)" |

### SHASTRA
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| GAIA sessions | 94 | Trace-to-graph pipeline input | SAFE | "94 GAIA sessions" |
| GAIA events processed | 4,037 | SHASTRA trace parsing | SAFE | "4,037 events" |
| Semantic blocks identified | 1,377 | SHASTRA LLM annotation | SAFE | "1,377 semantic blocks" |
| Graph nodes constructed | 442 | SHASTRA TDG construction | SAFE | "442 graph nodes" |

### ATHENA
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| Specialized agents | 5 | Ideation, Character, World, Story, Scene + Research | SAFE | "5 specialized agents" |
| Reference videos evaluated | 100 | 10 prompts × 10 videos | SAFE | "100 reference videos" |
| BLEU-4 improvement | +0.18 absolute | Over single-agent baseline | SAFE | "+0.18 BLEU-4 absolute improvement" |
| Fact coverage ablation | -27% | When Research Agent removed | SAFE | "removing Research agent reduced fact coverage by 27%" |
| Visual relevance ablation | 4.1 → 3.3/5.0 | When Research Agent removed (n=5 raters) | SAFE | "visual relevance from 4.1 to 3.3/5.0" |

### ARTEMIS
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| VLM backends served | 6+ | Gemma 3 27B, Qwen3-VL 8B, Qwen2.5-VL 7B, DeepSeek OCR, Glider, Llama-4 Scout 17B | SAFE | "6+ VLM backends" |
| Trained router checkpoint | best_multitask_router_v1.pt | Exists in repo | SAFE | "trained neural multi-task router checkpoint" |
| Routing modes | 5 | accuracy, cheap, fast, balanced, reward-based | SAFE | "5 dynamic routing modes" |
| Tasks supported | 4 | VQA, OCR, Captioning, Reasoning | SAFE | "VQA, OCR, captioning, and reasoning" |

### CERBERUS
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| Embedding compression | 4096 → 128 dims | Matryoshka Representation Learning | SAFE | "compressed embeddings 4096→128 dims" |
| 512-d retention | ~96% | Of full-dimensional R@5 performance | SAFE | "512-d retains ~96% of full-dimensional performance" |
| R@5 on PixMo | 78% | Vision-text retrieval with frozen encoders | SAFE | "R@5 78% on PixMo retrieval" |
| TRM decoder ROUGE-L | 0.24 vs 0.08 | vs text-only baseline | SAFE | "ROUGE-L: 0.24 vs 0.08" |
| TRM decoder BLEU | 0.066 vs 0.008 | vs text-only baseline | SAFE | "BLEU: 0.066 vs 0.008" |
| Training infrastructure | H100/A100 clusters | DDP, mixed precision | SAFE | "H100/A100 clusters" |