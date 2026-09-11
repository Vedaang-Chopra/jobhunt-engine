# LinkedIn Profile Strategy

**Source Authority:** raw_data/profile/PROFILE.md (canonical), raw_data/skills/SKILLS.md, raw_data/accomplishments/ACCOMPLISHMENTS.md

---

## Headline Options

### Option A: Agentic AI Focus (Primary)
```
AI Research Engineer | Agentic AI & Multi-Agent Systems | LangGraph • vLLM • Production ML (4.5 yrs @ Fortinet) | MS CS @ Georgia Tech (4.0 GPA)
```

### Option B: Evaluation/Inference Focus
```
ML Research Engineer | LLM Evaluation & Inference Systems | vLLM • DDP • Geometric Verification | 4.5 yrs Production ML @ Fortinet | MS CS @ Georgia Tech
```

### Option C: Broad Applied AI (Recruiter-Friendly)
```
Applied AI Engineer | Production ML + Agentic Systems Research | 4.5 yrs @ Fortinet (Patent, 40x scaling) | MS CS @ Georgia Tech (4.0 GPA)
```

---

## About Section (Agentic AI Focus - Recommended)

**Character limit: ~2600 chars (LinkedIn shows first ~300 before "See more")**

```
I build production agentic AI systems and research execution-grounded evaluation for LLMs.

Currently: MS CS (ML) at Georgia Tech (4.0 GPA), advised by Dr. Matthew Gombolay at CORE Robotics Lab @ Siemens. Graduating Dec 2026.

Previously: 4.5 years at Fortinet (SDE I → II) building production ML systems for enterprise network security:
• Led agentic RAG diagnostics: LLM plans multi-step tool calls over 10K+ device telemetry, verifies hypotheses via structured function calling, ~70% resolution time reduction (hackathon → production)
• Patented unsupervised wireless anomaly detection (PCT/IN2022/058026) — ~75% manual troubleshooting reduction
• Scaled OpenSearch ingestion 50→2,000 events/sec (40x) with Golang
• Deployed ONNX Runtime edge inference on network appliances (~40% latency reduction)
• Built 60+ classifier SLA forecasting pipelines with automated retraining

Graduate Research (Agentic AI / LLM Evaluation / Cybersecurity):
• CAD Code Generation: 16-module closed-loop agentic pipeline with LangGraph repair loops, geometric verification (Chamfer/Hausdorff on STL/B-Rep), 202-test evaluation harness — frozen model, inference-time search (NOT RL post-training)
• ATHENA: 5-agent supervisor-worker orchestration via LangGraph Command, reflection/critique loop, +0.18 BLEU-4 absolute over baseline, 27% fact coverage ablation
• SHASTRA: Trace-to-graph workflow reuse — 94 GAIA sessions → 442-node task-composition graphs with dependency/control/conditional edges
• ARTEMIS: Cost-aware VLM routing with trained neural router, SLA-aware load balancing, vLLM serving 6+ backends (Gemma 3 27B, Qwen3-VL, Llama-4 Scout)
• CERBERUS: Frozen encoder alignment with Matryoshka Representation Learning (4096→128 dims, 96% retention), DDP training on H100/A100, R@5 78% PixMo
• **Malware Analysis (Published IEEE ICAIA 2026):** Memory forensics (Volatility3) + ML + 100+ YARA rules for ransomware detection in IoT/energy systems — 18 memory dumps, 12 ransomware families, 33GB + 470GB dataset on Hugging Face

Targeting: Agentic AI Research Engineer, LLM Evaluation/Inference Research Engineer, Applied Scientist roles. Visa: F-1 (OPT eligible Dec 2026), H-1B sponsorship needed.

Open to: Referral conversations, research collaborations, coffee chats about agentic systems.
```

---

## Experience Section (Mirror raw_data/experience/)

### Fortinet Technologies Inc. (Feb 2021 – Jul 2025)
**Software Development Engineer I & II (ML/AI Track)**
- Led development of an agentic RAG diagnostics system: LLM plans multi-step tool calls over network telemetry, invokes APIs, verifies hypotheses via structured function calling — reduced mean resolution time ~70% (hackathon → production)
- Scaled OpenSearch ingestion from 50 to 2,000 events/sec (40x) using Golang; integrated ML models into Python/Go backend services
- Patent (Filed): PCT/IN2022/058026 — Unsupervised distributional thresholding for wireless connectivity anomaly detection; reduced manual troubleshooting ~75%
- Deployed ONNX Runtime edge inference on network appliances (~40% latency reduction); built 60+ classifier SLA forecasting pipelines with automated evaluation/retraining
- Technologies: Python, Go, PyTorch, Scikit-Learn, OpenSearch, ONNX Runtime, Docker, Linux, SQL, Redis, Azure, FastAPI

### Georgia Tech — CORE Robotics Lab @ Siemens (Jan 2026 – Present)
**Graduate Research Assistant** — Advisor: Dr. Matthew Gombolay
- Building closed-loop agentic pipeline for parametric CAD code generation: frozen LLM + execution-grounded geometric verification + LangGraph repair loop (16 modules, 202 tests)
- Designed evaluation harness with Chamfer/Hausdorff distances on STL/B-Rep, VLM visual judgment, AST/code-graph structural analysis
- Key innovation: Inference-time search with verifiable geometric reward (no RL post-training, no fine-tuning)

### Georgia Tech — CS 8903 Special Problems (Jan 2025 – Present)
**Graduate Researcher**
- **SHASTRA:** Trace-to-graph pipeline converting GAIA agent traces (94 sessions, 4,037 events) into reusable task-composition graphs; LangGraph planner with Pydantic registry
- **ATHENA:** 5-agent supervisor-worker screenplay generation with reflection/critique loop; +0.18 BLEU-4 absolute, 27% fact coverage ablation
- **ARTEMIS:** Trained neural VLM router with SLA-aware load balancing; vLLM serving 6+ backends across VQA/OCR/Captioning/Reasoning
- **CERBERUS:** Frozen CLIP/SBERT alignment with Matryoshka embeddings (4096→128 dims); DDP on H100/A100; R@5 78% PixMo; Perceiver Resampler negative result

---

## Skills Section (Top 50, from raw_data/skills/SKILLS.md)

**Priority Order (Agentic AI Focus):**
1. LangGraph, LangChain, Agentic RAG, Tool/Function Calling, Multi-Agent Orchestration
2. Structured Generation (Pydantic), LLM-as-a-Judge, Planning & Reasoning
3. vLLM, VLM Routing & Evaluation, Model Evaluation & Benchmarking, Inference Optimization
4. PyTorch, Hugging Face Transformers, CLIP, SBERT, FAISS, Cross-Modal Retrieval
5. DDP Training, Mixed Precision, Matryoshka Representation Learning, Perceiver Resampler
6. ONNX Runtime, OpenSearch/Elasticsearch, Golang, Python, Docker, Linux, Git
7. PPO, DQN, Reward Shaping, Curriculum Learning, Self-Play (academic)
8. Slurm, W&B, TensorBoard, FastAPI, Azure, SQL/PostgreSQL, Redis
9. **Volatility3, YARA, Memory Forensics, Malware Analysis, Hugging Face Hub (Datasets & Buckets)**

**Remove from LinkedIn (UNVERIFIED):**
- RLHF, RLAIF, DPO, SFT, LoRA/QLoRA, Reward Modeling
- Kubernetes, DeepSpeed, FSDP, JAX, TensorRT, Triton, Airflow, MLflow

---

## Projects to Pin on LinkedIn
1. **Malware_Analysis (Memory Forensics + ML)** — Public repo, 18 memory dumps, 100+ YARA rules, IEEE ICAIA 2026 publication, 33GB + 470GB on Hugging Face
2. **Which-VLM-Router (ARTEMIS)** — Public repo, cost-aware VLM routing, vLLM serving
3. **Edge-Glass (CERBERUS)** — Public repo, multimodal alignment, DDP training, MRL
4. **RL_Soccer_project** — Public repo, PPO/DQN variants, Ray/RLlib
5. **AI-Security** — Public repo, adversarial attacks, controlled ablations

**Do NOT pin:** Audit_Script_Development

---

## Education Section
- **Georgia Institute of Technology** — M.S. Computer Science (Machine Learning), GPA 4.0/4.0, 2024-2026
  - Advisor: Dr. Matthew Gombolay, CORE Robotics Lab @ Siemens
  - Coursework: Deep Learning, Deep RL, ML Security, Large & Vision Language Models, Agentic AI, Systems for AI
- **Maharaja Surajmal Institute of Technology** — B.Tech Information Technology, CGPA 8.8/10.0, 2016-2020

---

## Publications & Patents
- **Patent (Filed):** PCT/IN2022/058026 — Unsupervised distributional thresholding for wireless connectivity anomaly detection (Justia link)
- **Conference Paper:** Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems — IEEE ICAIA 2026 (with Sonika Malik)
- **Workshop Paper:** Ontology-based Text Classification — CEUR Workshop Proceedings Vol. 2786, 2020

---

## Maintenance Notes
- Update "Graduating Dec 2026" → "Graduated Dec 2026" after graduation
- Add arXiv preprints when submitted (CAD, ARTEMIS, CERBERUS target Sep 2026)
- Update headline when role changes
- Request recommendations from: Dr. Gombolay, Prof. Madisetti, Fortinet manager