# Accomplishments & Metrics Registry

**Source Authority:** EVIDENCE_LEDGER.md, VERIFIED_FACTS.md, LinkedIn, GitHub, patent records

**Purpose:** Every numerical claim that could appear on a resume must be registered here with its evidence trail. If a metric is not in this registry, it should not be on a resume.

**Safety Classification:**
- **SAFE** — Verified evidence, safe to put on resume (use "~" for self-reported)
- **CAUTION** — Partially verified, use with qualifiers and context
- **UNSAFE** — Unverified or contradicted, do not use

---

## Fortinet Metrics

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| OpenSearch ingestion scaling | 50 → 2,000 events/sec (40x) | Telemetry pipeline scaling using Golang | LinkedIn + GitHub profile (consistent) | **SAFE** | "Scaled OpenSearch ingestion from 50 to 2,000 events/sec (40x)" |
| Mean resolution time reduction | ~70% | Agentic RAG diagnostics (hackathon → production) | LinkedIn (self-reported) | **CAUTION** | "reduced mean resolution time ~70% (hackathon prototype to production deployment)" |
| Manual troubleshooting reduction | ~75% | Patent: wireless connectivity thresholding | LinkedIn + Patent (self-reported) | **CAUTION** | "cut manual troubleshooting ~75%" |
| Edge inference latency reduction | ~40% | ONNX Runtime deployment on network appliances | Original CV + LinkedIn (self-reported) | **CAUTION** | "~40% latency reduction" |
| SLA forecasting classifiers | 60+ | Across 4 categories: performance, capacity, availability, connectivity | LinkedIn | **SAFE** | "60+ classifiers across 4 categories" |
| Managed devices (agentic RAG) | ~10K+ | Network telemetry sources | LinkedIn (self-reported) | **CAUTION** | "~10K managed devices" (use "~" or omit exact number) |
| Patent number | PCT/IN2022/058026 | Filed with WIPO/India | Justia patents database | **SAFE** | "Patent (Filed): PCT/IN2022/058026" |

---

## Georgia Tech Research Metrics

### CAD Code Generation Pipeline

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| System modules | 16 | agent_langgraph, generation, metric_evaluation, visual_analysis, vlm_evaluation, failure_classification, feature_trees, brep_trajectory, operation_attribution, ast_graphs, code_graphs, roundtrip, structural_diff, rag, prompt_evaluation, infrastructure | Codebase | **SAFE** | "16-module system" |
| Automated tests | 202 | Full evaluation harness | Codebase | **SAFE** | "202-test evaluation harness" |
| GAIA sessions (SHASTRA) | 94 | Trace-to-graph pipeline input | SHASTRA repo/README | **SAFE** | "94 GAIA sessions" |
| GAIA events processed | 4,037 | SHASTRA trace parsing | SHASTRA repo/README | **SAFE** | "4,037 events" |
| Semantic blocks identified | 1,377 | SHASTRA LLM annotation | SHASTRA repo/README | **SAFE** | "1,377 semantic blocks" |
| Graph nodes constructed | 442 | SHASTRA TDG construction | SHASTRA repo/README | **SAFE** | "442 graph nodes" |
| Model status | FROZEN | No training, no fine-tuning, no RL post-training | PROJECT_OVERVIEW.md | **SAFE** | "frozen LLM (no fine-tuning, no RL post-training)" |

### ATHENA (Multi-Agent Screenplay Generation)

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| Specialized agents | 5 | Ideation, Character Design, World/Props, Story Generation, Scene Breakdown + Research Agent | ATHENA codebase (supervisor.py) | **SAFE** | "5 specialized agents" |
| Reference videos evaluated | 100 | 10 prompts × 10 videos | athena.tex, evaluation JSONs | **SAFE** | "100 reference videos" |
| BLEU-4 improvement | +0.18 absolute | Over single-agent baseline | text_metrics.py (sacrebleu), athena.tex | **SAFE** | "+0.18 BLEU-4 absolute improvement" |
| Fact coverage ablation | -27% | When Research Agent removed | athena.tex | **SAFE** | "removing Research agent reduced fact coverage by 27%" |
| Visual relevance ablation | 4.1 → 3.3/5.0 | When Research Agent removed (n=5 raters) | athena.tex | **SAFE** | "visual relevance from 4.1 to 3.3/5.0" |
| Raters for visual relevance | 5 | Human evaluation | athena.tex | **SAFE** | "(n=5 raters)" |

**UNSAFE ATHENA Metrics (DO NOT USE):**
- ❌ "14-agent" — only 5 specialized + 1 research
- ❌ "BLEU +18%" — it's +0.18 absolute, not 18% relative
- ❌ "CLIPScore +22%" — not verified in computed results
- ❌ "Keyframe synthesis" — generates screenplays, not keyframes

### ARTEMIS (VLM Routing)

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| VLM backends served | 6+ | Gemma 3 27B, Qwen3-VL 8B, Qwen2.5-VL 7B, DeepSeek OCR, Glider, Llama-4 Scout 17B | README | **SAFE** | "6+ VLM backends" |
| Trained router checkpoint | best_multitask_router_v1.pt | Exists in repo | Repo file | **SAFE** | "trained neural multi-task router checkpoint" |
| Routing modes | 5 | accuracy, cheap, fast, balanced, reward-based | README config | **SAFE** | "5 dynamic routing modes" |
| Tasks supported | 4 | VQA, OCR, Captioning, Reasoning | README | **SAFE** | "VQA, OCR, captioning, and reasoning" |

**UNSAFE ARTEMIS Metrics (DO NOT USE):**
- ❌ "100K+ query profiles" — not in code/notebooks
- ❌ "~30% lower cost" — not in benchmarks
- ❌ "KL-divergence matching" — not in code
- ❌ "F1 0.97-0.98" — not verified
- ❌ "Near-oracle accuracy" — not verified
- ❌ "Outperforming RouteLLM" — not verified

### CERBERUS (Vision-Language Alignment)

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| Embedding compression | 4096 → 128 dims | Matryoshka Representation Learning | Edge-Glass README | **SAFE** | "compressed embeddings 4096→128 dims" |
| 512-d retention | ~96% | Of full-dimensional R@5 performance | Edge-Glass README | **SAFE** | "512-d retains ~96% of full-dimensional performance" |
| R@5 on PixMo | 78% | Vision-text retrieval with frozen encoders | Edge-Glass README | **SAFE** | "R@5 78% on PixMo retrieval" |
| TRM decoder ROUGE-L | 0.24 vs 0.08 | vs text-only baseline | Edge-Glass README | **SAFE** | "ROUGE-L: 0.24 vs 0.08" |
| TRM decoder BLEU | 0.066 vs 0.008 | vs text-only baseline | Edge-Glass README | **SAFE** | "BLEU: 0.066 vs 0.008" |
| Training infrastructure | H100/A100 clusters | DDP, mixed precision | Edge-Glass README | **SAFE** | "H100/A100 clusters" |
| Freeze-Align baseline | 0.58-0.62 R@5 | Comparison baseline | Edge-Glass README | **SAFE** | "competitive with Freeze-Align (0.58-0.62 R@5)" |
| Standard MRL baseline | 0.34-0.48 R@5 | Comparison baseline | Edge-Glass README | **SAFE** | "standard MRL baselines (0.34-0.48 R@5)" |

**UNSAFE CERBERUS Metrics (DO NOT USE):**
- ❌ "Perceiver Resampler works" — negative result (collapses to chance)
- ❌ "Edge deployment ready" — not verified as production-deployed

### Sign Reading AR Glasses

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| VLM model | Gemma 4 26B | Backend inference | Private repo README | **SAFE** | "Gemma 4 26B" |
| Platforms | 3 | Android, iOS, Web/PWA | Private repo README | **SAFE** | "Android, iOS, Web/PWA" |
| Production version | v2 | With health checks, monitoring | Private repo README | **SAFE** | "production v2 with health monitoring" |

### RL Soccer (Academic)

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| PPO variants | 4 | baseline, shaped, curriculum, self-play | Public repo | **SAFE** (academic) | "PPO with reward shaping, curriculum learning, self-play (academic)" |
| DQN variants | 1 | baseline | Public repo | **SAFE** (academic) | "DQN baseline (academic)" |

---

## Malware Analysis: Memory Forensics + ML

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| Memory dumps analyzed | 18 | 6 benign, 12 ransomware families (WannaCry, Cerber, GandCrab, etc.) | Malware_Analysis repo, publication | **SAFE** | "Analyzed 18 memory dumps (6 benign, 12 ransomware families)" |
| Ransomware families covered | 12 | WannaCry, Cerber, GandCrab, etc. | Malware_Analysis repo, publication | **SAFE** | "12 ransomware families: WannaCry, Cerber, GandCrab, etc." |
| YARA rules developed | 100+ | For ransomware family classification | Malware_Analysis repo, publication | **SAFE** | "Developed 100+ YARA rules for ransomware family classification" |
| Publication | IEEE ICAIA 2026 | "Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems" | IEEE Xplore, publication record | **SAFE** | "Published at IEEE ICAIA 2026" |
| Hugging Face dataset size | 33 GB | Analysis files (scripts, scan outputs, YARA rules) | HF Hub: Vedaang/malware_analysis | **SAFE** | "33 GB analysis dataset on Hugging Face" |
| Hugging Face bucket: malware-analysis-data | ~470 GB | Raw memory dumps + detailed scans | HF Hub: Vedaang/malware-analysis-data | **SAFE** | "~470 GB raw memory dumps + scans on HF bucket" |
| Hugging Face bucket: malware-code-base | 3,384 files | Codebase files | HF Hub: Vedaang/malware-code-base | **SAFE** | "3,384 code files on HF bucket" |
| Hugging Face bucket: malware-raw-dumps | Raw dumps + scans | Raw .raw dumps, memmap scans, ELF binaries, vadinfo/vadwalk | HF Hub: Vedaang/malware-raw-dumps | **SAFE** | "Raw memory dumps + scans on HF bucket" |

---

## Education Metrics

| Metric | Value | Context | Source | Safety | Resume Wording |
|---|---|---|---|---|---|
| Georgia Tech GPA | 4.0/4.0 | MS CS (ML) | LinkedIn | **SAFE** | "GPA: 4.0/4.0" |
| MSIT CGPA | 8.8/10.0 | B.Tech IT | All resumes | **SAFE** | "CGPA: 8.8/10.0" |
| Graduation | Dec 2026 | Expected | LinkedIn | **SAFE** | "Dec 2026 (expected)" |

---

## Skills Metrics (Years/Depth)

| Skill | Depth Indicator | Evidence | Safety | Resume Wording |
|---|---|---|---|---|
| Python | 6+ years | Fortinet (4.5) + GT research (1.5) + coursework | **SAFE** | "6+ years Python" |
| PyTorch | 3+ years | Fortinet + GT research + coursework | **SAFE** | "3+ years PyTorch" |
| Go | 2+ years | Fortinet (OpenSearch scaling, backend) | **SAFE** | "2+ years Go" |
| LangGraph | 1+ year | CAD, ATHENA, SHASTRA (all 2025-2026) | **SAFE** | "LangGraph across 3 research projects" |
| vLLM | 1+ year | ARTEMIS, CERBERUS (2025-2026) | **SAFE** | "vLLM for production VLM serving" |
| ONNX Runtime | 2+ years | Fortinet edge deployment (2021-2025) | **SAFE** | "ONNX Runtime for edge inference" |
| OpenSearch/Elasticsearch | 3+ years | Fortinet (50→2000 events/sec) | **SAFE** | "OpenSearch at scale (50→2000 events/sec)" |

---

## Metric Usage Rules

### For Self-Reported Metrics (Fortinet ~70%, ~75%, ~40%)
1. **Always use "~" qualifier** — signals "approximately" / "self-reported"
2. **Include context** — "hackathon prototype to production", "manual troubleshooting"
3. **Never present as A/B test results** — no evidence of controlled experiments

### For Verified System Metrics (OpenSearch 50→2000, 60+ classifiers, 202 tests)
1. **Safe to state precisely** — cross-platform consistency or code evidence
2. **Include scale context** — "40x improvement", "enterprise-grade", "automated evaluation"

### For Research Metrics (BLEU +0.18, R@5 78%, etc.)
1. **Specify absolute vs relative** — "+0.18 absolute" not "+18%"
2. **Include benchmark/dataset name** — "PixMo", "GAIA", "100 reference videos"
3. **Note ablation conditions** — "when Research agent removed", "n=5 raters"

### For Academic/Coursework Metrics
1. **Always qualify** — "(academic project)", "(coursework)"
2. **Don't mix with production metrics** — separate sections

---

## Metrics That Must Never Appear on Resume

| Metric | Claimed In | Why Unsafe |
|---|---|---|
| "RLHF/RLAIF implemented" | Multiple old resumes | Zero code evidence |
| "PPO/GRPO for CAD training" | Research Engineer resume | Model is frozen (PROJECT_OVERVIEW.md) |
| "Reward model trained" | Research Engineer resume | No reward model; geometric metrics used as scoring |
| "Fine-tuned LLM with LoRA/QLoRA" | Multiple resumes | No fine-tuning code |
| "100K+ query profiles (ARTEMIS)" | Together AI resume, v3_6 | Not in code/notebooks |
| "~30% lower cost (ARTEMIS)" | Together AI resume, v3_6 | Not in benchmarks |
| "KL-divergence matching (ARTEMIS)" | Research Engineer resume | Not in code |
| "F1 0.97-0.98 (ARTEMIS)" | v3_6 resume | Not verified |
| "14-agent orchestration (ATHENA)" | Agentic AI resume | Only 5 specialized + 1 research |
| "Blackboard controller (ATHENA)" | Multiple resumes | It's supervisor-worker via LangGraph Command |
| "Keyframe synthesis (ATHENA)" | Multiple resumes | Generates screenplays, not keyframes |
| "BLEU +18% (ATHENA)" | Multiple resumes | It's +0.18 absolute |
| "CLIPScore +22% (ATHENA)" | Multiple resumes | Not verified in computed results |
| "DeepSpeed experience" | Career fair resumes | No code evidence |
| "Kubernetes experience" | GitHub profile only | No code evidence |
| "JAX experience" | Never actually claimed but gap | No code evidence |
| "Distributed LLM training (FSDP/Megatron)" | Never claimed but gap | Only DDP for encoder alignment (CERBERUS) |

---

## Quick Metric Lookup for Resume Customization

### Agentic AI Roles → Lead With:
- 16-module agentic CAD pipeline, 202 tests
- 5-agent supervisor orchestration (ATHENA)
- Production agentic RAG at Fortinet (~70% resolution reduction)
- LangGraph across 3 projects (CAD, ATHENA, SHASTRA)
- Trace-to-graph: 94 GAIA sessions → 442 graph nodes

### LLM Evaluation/Inference Roles → Lead With:
- 202-test evaluation harness (CAD)
- Geometric verification: Chamfer/Hausdorff on STL/B-Rep
- VLM routing: 6+ backends via vLLM, 5 routing modes
- R@5 78% on PixMo (CERBERUS)
- 512-d embeddings retain 96% performance (CERBERUS)
- DDP training on H100/A100 (CERBERUS)
- ONNX ~40% latency reduction (Fortinet)
- OpenSearch 50→2000 events/sec (Fortinet)

### Applied Scientist / ML Engineer → Lead With:
- 4.5 years production ML at Fortinet
- Patent PCT/IN2022/058026
- OpenSearch 50→2000 events/sec (40x)
- 60+ classifiers in production SLA forecasting
- ONNX edge deployment (~40% latency reduction)
- Agentic RAG production system (~70% resolution reduction)
- 16-module research system with 202 tests (CAD)
- vLLM serving 6+ VLM backends (ARTEMIS)

### Research Engineer — Agents/Reasoning → Lead With:
- Closed-loop agentic CAD: inference-time search with geometric verification
- 5-agent supervisor-worker with reflection (ATHENA)
- Workflow reuse via trace-to-graph (SHASTRA): 94 sessions → 442 nodes
- Production agentic RAG with tool-use (Fortinet)
- LangGraph orchestration across 3 projects
- Structured generation with Pydantic (ATHENA, SHASTRA, CAD)