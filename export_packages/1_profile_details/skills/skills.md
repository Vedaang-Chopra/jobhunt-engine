# Skills — Verified Inventory

**Source Authority:** EVIDENCE_LEDGER.md (primary), GitHub repositories, CORRECTED_RESUME_CONTENT.md, MASTER_REPORT.md
**Critical Rule:** Only skills with **verifiable evidence in codebases or production systems** are listed. Skills mentioned only in old resumes without code evidence are marked **UNVERIFIED** and should not be claimed.

---

## Skill Classification

| Status | Meaning | Resume Usage |
|---|---|---|
| **VERIFIED** | Implemented in production/research codebase | Safe to claim prominently |
| **PARTIALLY VERIFIED** | Some evidence but limited scope | Claim with qualifiers ("academic", "coursework", "exposure") |
| **UNVERIFIED** | Listed in old resumes but no code evidence | **DO NOT CLAIM** |
| **CONTRADICTED** | Evidence shows the opposite | **NEVER CLAIM** |

---

## Agentic AI & LLM Systems

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **LangGraph** | VERIFIED | CAD (agent_langgraph), ATHENA (supervisor), SHASTRA (planner) | HIGH | "LangGraph-orchestrated multi-agent systems (repair loops, supervisor patterns, planners)" |
| **LangChain** | VERIFIED | Fortinet agentic RAG, CAD rag module | HIGH | "LangChain for agentic RAG and tool orchestration" |
| **Agentic RAG** | VERIFIED | Fortinet production system (hackathon → production) | HIGH | "Production agentic RAG diagnostics system with multi-step tool calling" |
| **Tool/Function Calling** | VERIFIED | Fortinet (structured), CAD (execution), ATHENA (tools.py) | HIGH | "Structured function calling for autonomous tool use and hypothesis verification" |
| **Multi-Agent Orchestration** | VERIFIED | ATHENA (5 agents), SHASTRA (registry), CAD (repair loop) | HIGH | "Supervisor-worker and planner-executor multi-agent patterns via LangGraph" |
| **Structured Generation (Pydantic)** | VERIFIED | ATHENA (OrchestrationRouter, ReflectionRouter), SHASTRA, CAD | HIGH | "Pydantic-validated structured LLM outputs for agent state and routing" |
| **LLM-as-a-Judge** | VERIFIED | CAD (vlm_evaluation), ATHENA (reflection) | MEDIUM | "LLM/VLM-based evaluation and critique loops" |
| **Planning & Reasoning** | VERIFIED | SHASTRA (trace-to-graph), CAD (repair loop), ATHENA (CoT) | MEDIUM-HIGH | "Multi-step planning with structured reasoning and verification" |
| **Long-Horizon Task Decomposition** | VERIFIED | SHASTRA (workflow reuse), CAD (multi-step repair) | MEDIUM | "Task-decomposition graphs for long-horizon agentic workflows" |
| **Workflow Composition/Reuse** | PARTIALLY VERIFIED | SHASTRA (planner + registry done, orchestrator stub) | MEDIUM | "Designing workflow retrieval and adaptation for compositional reuse" |

---

## AI/ML Core

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **PyTorch** | VERIFIED | CERBERUS (DDP), ARTEMIS, CAD, RL Soccer, Fortinet | HIGH | "PyTorch for research and production ML (DDP, mixed precision, custom modules)" |
| **Hugging Face Transformers** | VERIFIED | ARTEMIS (VLM backends), CERBERUS (CLIP/SBERT), CAD | HIGH | "Hugging Face Transformers for LLM/VLM integration and custom pipelines" |
| **Deep Learning / CNNs** | VERIFIED | CERBERUS, Fortinet classifiers, coursework | HIGH | "CNNs and deep learning for classification and feature extraction" |
| **Vision Transformers** | VERIFIED | CERBERUS (CLIP), ARTEMIS (VLMs), coursework | HIGH | "Vision Transformers (CLIP, VLMs) for multimodal tasks" |
| **NLP / Computer Vision** | VERIFIED | Fortinet, CAD, CERBERUS, coursework | HIGH | "NLP and computer vision across production and research systems" |
| **Scikit-Learn** | VERIFIED | Fortinet (60+ classifiers), coursework | HIGH | "Scikit-Learn for classical ML pipelines and baseline models" |
| **NumPy / Pandas** | VERIFIED | All projects, Fortinet | EXPERT | "NumPy/Pandas for data processing and analysis" |

---

## LLMs / VLMs / Inference / Evaluation (VERIFIED ONLY)

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **vLLM** | VERIFIED | ARTEMIS (serving 6+ backends), CERBERUS | HIGH | "vLLM for high-throughput VLM/LLM serving with dynamic routing" |
| **VLM Routing & Evaluation** | VERIFIED | ARTEMIS (router, load balancer, 5 benchmarks) | HIGH | "Cost-aware VLM routing with neural router and SLA-aware load balancing" |
| **Model Evaluation & Benchmarking** | VERIFIED | CAD (202 tests), ATHENA (BLEU/CLIPScore), ARTEMIS | HIGH | "Automated evaluation harnesses (202 tests) with geometric, compile, and visual metrics" |
| **Inference Optimization** | VERIFIED | Fortinet (ONNX ~40% latency), ARTEMIS (routing), CERBERUS (edge) | HIGH | "ONNX Runtime edge deployment (~40% latency reduction); vLLM routing optimization" |
| **CLIP / SBERT / FAISS** | VERIFIED | CERBERUS (frozen encoders, retrieval), ARTEMIS | HIGH | "CLIP/SBERT for frozen encoder alignment; FAISS for retrieval" |
| **Cross-Modal Retrieval** | VERIFIED | CERBERUS (PixMo R@5 78%), ARTEMIS | MEDIUM-HIGH | "Cross-modal retrieval with frozen encoders and compressed embeddings" |
| **Quantization** | PARTIALLY VERIFIED | Fortinet (ONNX edge deployment involved quantization) | MEDIUM | "Quantization for edge ML inference deployment (ONNX Runtime)" |
| **Matryoshka Representation Learning** | VERIFIED | CERBERUS (4096→128 dims, 96% retention) | MEDIUM-HIGH | "Matryoshka embeddings for efficient multimodal retrieval" |
| **Perceiver Resampler** | VERIFIED (negative result) | CERBERUS (ablation: retrieval collapses) | MEDIUM | "Perceiver Resampler ablation — identified initialization issues" |

---

## ❌ DO NOT CLAIM — UNVERIFIED / CONTRADICTED

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

---

## Reinforcement Learning (Academic / Verified Only)

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **PPO** | VERIFIED (academic) | RL Soccer (coursework: baseline, shaped, curriculum, self-play) | MEDIUM | "PPO with reward shaping, curriculum learning, and self-play (academic project)" |
| **DQN** | VERIFIED (academic) | RL Soccer (coursework) | MEDIUM | "DQN baseline implementation (academic project)" |
| **Reward Shaping** | VERIFIED (academic) | RL Soccer (ppo_shaped stage) | MEDIUM | "Custom reward shaping for RL agents (academic project)" |
| **Curriculum Learning** | VERIFIED (academic) | RL Soccer (ppo_curriculum stage) | MEDIUM | "Curriculum learning strategies for RL (academic project)" |
| **Self-Play** | VERIFIED (academic) | RL Soccer (ppo_selfplay stage) | MEDIUM | "Self-play training regimes (academic project)" |
| **Ray/RLlib** | VERIFIED (academic) | RL Soccer training | MEDIUM | "Ray/RLlib for distributed RL training (academic project)" |

**Framing Rule:** Always qualify RL skills as "(academic project)" or "(coursework)" — these are not production/research RL experience.

---

## Systems & Infrastructure

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **Python** | VERIFIED | All projects, Fortinet (primary) | EXPERT | "Python for ML systems, research pipelines, and production services" |
| **Go** | VERIFIED | Fortinet (OpenSearch scaling, backend services) | HIGH | "Go for high-throughput data pipelines and backend services" |
| **C/C++** | VERIFIED | Coursework, some systems work | MEDIUM | "C/C++ for systems programming and performance-critical components" |
| **SQL / PostgreSQL** | VERIFIED | Fortinet pipelines | MEDIUM | "PostgreSQL for production data pipelines" |
| **Redis** | VERIFIED | Fortinet, listed in skills | MEDIUM | "Redis for caching and real-time data" |
| **OpenSearch / Elasticsearch** | VERIFIED | Fortinet (50→2000 events/sec scaling) | HIGH | "OpenSearch/Elasticsearch at scale (50→2000 events/sec)" |
| **Docker** | VERIFIED | All projects, Fortinet | HIGH | "Docker for containerized ML deployment and development" |
| **Linux** | VERIFIED | Daily driver, Fortinet, clusters | HIGH | "Linux systems administration and development" |
| **Git** | VERIFIED | All repos | HIGH | "Git for version control and collaboration" |
| **ONNX Runtime** | VERIFIED | Fortinet (edge inference ~40% latency reduction) | HIGH | "ONNX Runtime for edge ML inference optimization" |
| **FastAPI** | VERIFIED | ARTEMIS, listed in skills | MEDIUM | "FastAPI for ML model serving APIs" |
| **Azure** | VERIFIED | Fortinet cloud | MEDIUM | "Azure cloud services for ML deployment" |
| **W&B / TensorBoard** | VERIFIED | CAD (experiment tracking), listed | MEDIUM | "Weights & Biases and TensorBoard for experiment tracking" |
| **Slurm** | VERIFIED | CAD (multi-GPU), ARTEMIS (CUDA_VISIBLE_DEVICES) | MEDIUM | "Slurm for multi-GPU cluster job scheduling" |
| **DDP (Distributed Data Parallel)** | VERIFIED | CERBERUS (H100/A100 clusters) | MEDIUM-HIGH | "PyTorch DDP for distributed training on H100/A100 clusters" |
| **Mixed Precision Training** | VERIFIED | CERBERUS (H100/A100) | MEDIUM-HIGH | "Mixed precision training for memory-efficient distributed training" |

---

## ❌ DO NOT CLAIM — Systems (UNVERIFIED)

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

## Research Tooling

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **Weights & Biases** | VERIFIED | CAD experiment tracking, listed in skills | MEDIUM | "W&B for experiment tracking and hyperparameter sweeps" |
| **TensorBoard** | VERIFIED | Listed in skills, CAD infrastructure | MEDIUM | "TensorBoard for training visualization" |
| **Experiment Tracking** | VERIFIED | CAD (W&B), ARTEMIS (checkpoints), CERBERUS | MEDIUM | "Systematic experiment tracking across research projects" |
| **Ablation Study Design** | VERIFIED | ATHENA (research agent ablation), CERBERUS (Perceiver), CAD | HIGH | "Rigorous ablation methodology (agent removal, component substitution)" |
| **Cross-Modal Evaluation** | VERIFIED | ATHENA (text + visual metrics), CERBERUS (retrieval + generation) | HIGH | "Cross-modal evaluation frameworks (text metrics + visual metrics)" |
| **Benchmark Construction** | PARTIALLY VERIFIED | ARTEMIS (5 evaluation suites — unverified claims), CAD (custom) | MEDIUM | "Custom benchmark design for agentic and multimodal systems" |

---

## Cybersecurity & Memory Forensics

| Skill | Status | Evidence | Proficiency | Resume Wording |
|---|---|---|---|---|
| **Volatility Framework (Volatility3)** | VERIFIED | Malware_Analysis repo (malfind, pslist, vadinfo, yarascan orchestration) | HIGH | "Volatility3 for memory forensics and automated dump analysis" |
| **YARA Rule Development** | VERIFIED | Malware_Analysis repo (100+ rules for ransomware classification) | HIGH | "YARA rule development for malware family classification (100+ rules)" |
| **Memory Forensics** | VERIFIED | Malware_Analysis project (18 dumps: 6 benign, 12 ransomware families) | HIGH | "Memory dump analysis for ransomware detection in IoT/energy systems" |
| **Malware Analysis** | VERIFIED | Malware_Analysis project (WannaCry, Cerber, GandCrab, etc.) | MEDIUM-HIGH | "Ransomware family analysis and classification via static/dynamic methods" |
| **Hugging Face Hub (Datasets & Buckets)** | VERIFIED | Vedaang/malware_analysis (33GB), malware-analysis-data (~470GB), malware-code-base (3384 files), malware-raw-dumps | MEDIUM-HIGH | "Large-scale dataset curation on Hugging Face (datasets + buckets)" |

---

## Skill Groupings for Resume Variants

### Variant A: Agentic AI Research Engineer
**Primary Skills (first section):**
- LangGraph, LangChain, Agentic RAG, Tool/Function Calling, Multi-Agent Orchestration, Structured Generation (Pydantic), LLM-as-a-Judge, Planning & Reasoning, Long-Horizon Task Decomposition, Workflow Composition

**Secondary Skills:**
- PyTorch, Transformers, vLLM, Model Evaluation, Inference Optimization, CLIP/SBERT/FAISS
- PPO/DQN (academic), Ray/RLlib (academic)
- Python, Go, Docker, ONNX Runtime, Slurm, W&B

### Variant B: LLM Evaluation / Inference Research Engineer
**Primary Skills (first section):**
- Model Evaluation & Benchmarking, vLLM, VLM Routing & Evaluation, Inference Optimization, Cross-Modal Retrieval, Matryoshka Representation Learning, DDP Training, Mixed Precision

**Secondary Skills:**
- PyTorch, Transformers, CLIP/SBERT/FAISS, Quantization
- LangGraph, Multi-Agent Orchestration, Structured Generation
- Python, Go, Docker, ONNX Runtime, Slurm, W&B
- PPO/DQN (academic)

### Variant C: Applied Scientist / ML Engineer (Production-Focused)
**Primary Skills (first section):**
- Python, Go, PyTorch, Scikit-Learn, OpenSearch/Elasticsearch, Docker, ONNX Runtime, FastAPI, SQL/PostgreSQL, Redis, Azure, Linux, Git
- Agentic RAG, Tool/Function Calling, LangChain/LangGraph
- Model Evaluation, Inference Optimization, vLLM

**Secondary Skills:**
- Deep Learning, CNNs, Vision Transformers, NLP, Computer Vision
- CLIP/SBERT/FAISS, Cross-Modal Retrieval, Matryoshka Embeddings
- DDP Training, Mixed Precision, Slurm, W&B
- PPO/DQN (academic)

---

## Skill Evidence Mapping (Quick Reference)

| If Asked About... | Point To... |
|---|---|
| LangGraph | CAD `agent_langgraph` module, ATHENA `supervisor.py`, SHASTRA planner |
| Agentic RAG | Fortinet LinkedIn description, production deployment |
| Multi-Agent | ATHENA 5-agent supervisor pattern, SHASTRA registry |
| vLLM | ARTEMIS README serving commands, 6+ backend configs |
| Geometric Verification | CAD `metric_evaluation`, `feature_trees`, `brep_trajectory` modules |
| DDP Training | CERBERUS README (H100/A100, mixed precision) |
| Matryoshka Embeddings | CERBERUS README (4096→128 dims, 96% retention, R@5 78%) |
| ONNX Optimization | Fortinet ~40% latency reduction, edge deployment |
| OpenSearch Scaling | LinkedIn + GitHub profile (50→2000 events/sec, consistent) |
| Patent | PCT/IN2022/058026 on Justia |
| PPO/DQN | RL_Soccer_project public repo (staged implementations) |
| Structured Generation | ATHENA `OrchestrationRouter`, `ReflectionRouter` (Pydantic BaseModels) |