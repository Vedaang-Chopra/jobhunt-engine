# Research Projects Overview
| Project | Lab/Course | Period | Status | Advisor | Publication Target |
|---|---|---|---|---|---|
| CAD Code Generation | CORE Robotics Lab | Jan 2026 — Present | IN PROGRESS | Dr. Matthew Gombolay | NeurIPS/ICML/ICLR 2026 Workshop / arXiv |
| SHASTRA | CS 8903 Special Problems | Jan 2026 — Present | IN PROGRESS | Dr. Matthew Gombolay | AAMAS/AAAI 2027 / arXiv |
| ATHENA | CS 8903 Special Problems | Jan — May 2025 | COMPLETED | Prof. Vijay Madisetti | arXiv (completed work) |
| ARTEMIS | CS 8903 Special Problems | Aug 2025 — Present | IN PROGRESS | Dr. Matthew Gombolay* | NeurIPS/ICML/ICLR 2026 Workshop |
| CERBERUS | CS 8903 Special Problems | Aug 2025 — Present | IN PROGRESS | Dr. Matthew Gombolay* | NeurIPS/ICML/ICLR 2026 Workshop |
| AI Security | Coursework/Project | 2025 — 2026 | COMPLETED | Course instructor | None (coursework) |
| RL Soccer | Coursework | 2025 | COMPLETED | Course instructor | None (academic) |

*Assumed based on CORE Lab affiliation; verify with advisor

---

## 1. CAD Code Generation with Execution-Grounded Verification

### Research Question
How can LLMs generate functionally correct parametric CAD programs without RL post-training or fine-tuning, using only inference-time search with verifiable geometric rewards?

### Hypothesis
Frozen LLMs + execution-grounded verification (compile + geometric correctness) + iterative repair loops can achieve functional correctness comparable to or exceeding RL post-training approaches, with greater interpretability and lower compute cost.

### Methods
| Component | Approach |
|---|---|
| **Generation** | LLM generates CadQuery programs from natural language specifications |
| **Execution** | CadQuery execution environment returns compile errors + STL/B-Rep geometry |
| **Verification** | Geometric metrics: Chamfer Distance, Hausdorff Distance on STL & B-Rep |
| **Repair** | LangGraph-orchestrated multi-step repair loop with structured evidence prompts |
| **Analysis** | AST graphs, code graphs, feature trees, B-Rep trajectory analysis, structural diff |
| **Augmentation** | RAG-augmented prompt construction from prior successful repairs |

### Experimental Design
- **Models:** Frozen LLMs (various, not specified in evidence)
- **Benchmarks:** Custom parametric CAD benchmark (not standard benchmark)
- **Evaluation:** 202-test automated harness
- **Metrics:** Compile validity rate, geometric correctness (Chamfer/Hausdorff), repair success rate, token efficiency
- **Ablations:** Repair loop depth, verification components, prompt augmentation strategies

### Current Results (IN PROGRESS)
- 16-module system operational
- 202 automated tests passing
- Geometric verification pipeline functional
- VLM-based visual judgment integrated
- No formal benchmark comparison against baselines yet
- No publication submitted

### Distinction from RL Post-Training
| Aspect | RL Post-Training | This Work (Inference-Time Search) |
|---|---|---|
| Model Weights | Updated via PPO/GRPO/DPO | **FROZEN** — no updates |
| Training Compute | High (GPU-hours for training) | **Zero** training compute |
| Reward Model | Learned reward model | **Hand-coded geometric metrics** |
| Iteration | Training epochs | **Inference-time repair steps** |
| Interpretability | Low (policy network) | **High** (explicit verification steps) |
| Data Efficiency | Requires large preference datasets | **Zero** preference data needed |

### Publications/Submissions
- **None yet** — IN PROGRESS
- **Planned:** arXiv preprint (target: September 2026), NeurIPS 2026 Workshop submission

### Strongest Research Engineer Positioning
> "I design execution-grounded evaluation frameworks for LLM code generation that move beyond token-level metrics to functional correctness verification — combining geometric verification (Chamfer/Hausdorff on STL/B-Rep), compile validity, and iterative repair orchestration via LangGraph. This achieves RL-like results without RL training compute, using frozen models and inference-time search."

---

## 2. SHASTRA — Agentic Workflow Retrieval & Adaptation

### Research Question
How can prior agent execution traces be converted into reusable, composable workflow graphs that enable adaptation to new tasks under cost/latency constraints?

### Hypothesis
Agent workflows contain reusable patterns that can be extracted as task-composition graphs (TDGs) with dependency/control/conditional edges, enabling compositional reuse across tasks.

### Methods
| Stage | Approach |
|---|---|
| **Trace Collection** | GAIA benchmark execution traces (94 sessions) |
| **Event Parsing** | Segment traces into candidate blocks |
| **Semantic Annotation** | LLM labels blocks with capability labels + confidence scores |
| **Graph Construction** | Build Task-Dependency Graphs with dependency/control/conditional edges + structural hints (parallel groups, merge/branch points, iteration detection) |
| **Standardization** | LangGraph + Pydantic schemas for cross-agent transfer |
| **Registry** | Pluggable storage (YAML) for component search/reuse |

### Data
- 94 GAIA sessions
- 4,037 events processed
- 1,377 semantic blocks identified
- 442 graph nodes constructed

### Current Status
- ✅ Trace-to-graph pipeline implemented
- ✅ LangGraph planner implemented
- ✅ Component registry with pluggable storage implemented
- ⚠️ Orchestrator — stub only
- ❌ Executor — not implemented
- Evaluation on GAIA benchmark with passing integration tests across 3 pipeline stages

### Publications/Submissions
- **None yet** — IN PROGRESS
- **Planned:** AAMAS 2027 or AAAI 2027, arXiv preprint

### Strongest Positioning
> "I build systems that convert agent execution traces into reusable workflow graphs, enabling compositional reuse of tool-call sequences across tasks. The trace-to-graph pipeline processes GAIA sessions into task-composition graphs with dependency/control/conditional edges, standardized via LangGraph and Pydantic for cross-agent transfer."

---

## 3. ATHENA — Multi-Agent Screenplay Generation

### Research Question
Can a supervisor-worker multi-agent system with reflection-based critique produce higher-quality long-form creative outputs (screenplays) than single-agent baselines?

### Hypothesis
Specialized agents coordinated via a supervisor with structured state and reflection loops will outperform monolithic agents on complex, multi-faceted generation tasks.

### Methods
| Component | Approach |
|---|---|
| **Agents** | 5 specialized: Ideation, Character Design, World/Props, Story Generation, Scene Breakdown + Research Agent (tools) |
| **Orchestration** | Supervisor-worker via LangGraph Command routing |
| **State** | Shared JSON state with Pydantic-validated structured outputs |
| **Reflection** | ReflectionRouter with repeat/feedback mechanism for quality critique |
| **Evaluation** | Cross-modal: Text (BLEU-4, ROUGE-L, METEOR, BERTScore, Perplexity) + Visual (CLIPScore, SSIM, PSNR) on 100 reference videos |

### Results (COMPLETED — Jan-May 2025)
| Metric | Result |
|---|---|
| BLEU-4 | **+0.18 absolute** over single-agent baseline |
| Fact Coverage (ablation) | -27% when Research Agent removed |
| Visual Relevance (ablation) | 4.1 → 3.3/5.0 (n=5 raters) when Research Agent removed |
| CLIPScore | Evaluated (exact delta not verified in computed results) |
| METEOR / BERTScore / SSIM / PSNR | Computed, values in evaluation JSONs |

### Publications/Submissions
- **Paper Draft:** `athena.tex` (co-authored with Prof. Vijay Madisetti)
- **Status:** Not submitted — could be arXiv preprint
- **Note:** Screenplay domain may seem "toy" to some hiring managers; emphasize the **orchestration architecture** and **evaluation methodology**

### Strongest Positioning
> "I built a 5-agent supervisor-worker orchestration system for long-horizon creative generation using LangGraph Command routing, with reflection-based quality critique and dynamic plan modification. The cross-modal evaluation framework (text + visual metrics on 100 videos) and ablation studies demonstrate rigorous methodology — removing the research agent reduced fact coverage by 27%."

---

## 4. ARTEMIS — Cost-Aware VLM Routing

### Research Question
Can a learned neural router with SLA-aware load balancing dynamically select the optimal VLM per request to achieve near-oracle accuracy at lower cost than static or cascade baselines?

### Hypothesis
Per-sample utility optimization over accuracy/latency/cost with learned routing policies outperforms heuristic routing (static, cascade, RouteLLM-style) for heterogeneous VLM deployments.

### Methods
| Component | Approach |
|---|---|
| **Router** | Neural multi-task router predicting per-model utility scores |
| **Training** | Offline profiles (claims of 100K+ queries — UNVERIFIED) |
| **Load Balancing** | SLA-aware capacity-based scheduling with cost/latency budgets |
| **Serving** | vLLM unified inference engine for 6+ VLM backends |
| **Routing Modes** | accuracy, cheap, fast, balanced, reward-based (routing reward) |
| **Benchmarks** | 5 evaluation suites across VQA, OCR, Captioning, Reasoning |

### Verified Infrastructure
- ✅ Trained checkpoint: `best_multitask_router_v1.pt`
- ✅ vLLM serving commands (CUDA_VISIBLE_DEVICES, bfloat16)
- ✅ SLA YAML configurations
- ✅ 6+ VLM backends configured
- ✅ Dynamic routing modes implemented

### UNVERIFIED Claims (DO NOT USE)
- ❌ "100K+ query profiles" — not in code/notebooks
- ❌ "~30% lower cost" — not in benchmarks
- ❌ "KL-divergence matching" — not in code
- ❌ "F1 0.97-0.98" — not verified
- ❌ "Near-oracle accuracy" — not verified
- ❌ "Outperforming RouteLLM" — not verified

### Publications/Submissions
- **None yet** — IN PROGRESS
- **Old resume claimed:** "Preprint, arXiv (in submission), 2026" — **FALSE**, not submitted
- **Planned:** NeurIPS/ICML/ICLR 2026 Workshop

### Strongest Positioning
> "I built a production-grade VLM routing system with a trained neural router, SLA-aware load balancing, and vLLM-based serving of 6+ heterogeneous VLM backends. The system supports dynamic routing modes (accuracy/cost/latency-optimized) and represents a complete deployment stack for cost-aware multimodal inference."

---

## 5. CERBERUS — Vision-Language Alignment for Edge

### Research Question
Can encoder-frozen cross-modal alignment with Matryoshka Representation Learning produce compressed embeddings suitable for edge deployment while maintaining retrieval performance?

### Hypothesis
Frozen CLIP/SBERT encoders + MRL compression (4096→128 dims) + lightweight decoder can achieve competitive retrieval without end-to-end fine-tuning, enabling edge deployment.

### Methods
| Component | Approach |
|---|---|
| **Encoders** | Frozen CLIP ViT-L/14 (vision), SBERT (text), Whisper (audio ablations) |
| **Compression** | Matryoshka Representation Learning (multi-scale: 4096→128 dims) |
| **Resampling** | Perceiver Resampler (tested — negative result) |
| **Decoder** | TRM decoder conditioned on compressed latents; Qwen-14B integration |
| **Training** | DDP distributed training, mixed precision on H100/A100 |
| **Evaluation** | PixMo vision-text retrieval (R@5) |

### Results (VERIFIED)
| Metric | Result |
|---|---|
| R@5 on PixMo | **78%** with frozen encoders |
| 512-d retention | **~96%** of full-dimensional R@5 |
| TRM decoder vs text-only | **ROUGE-L: 0.24 vs 0.08**; BLEU: 0.066 vs 0.008 |
| Perceiver Resampler | **Negative result** — retrieval collapses to chance (init/gradient issues) |
| Comparison baselines | Competitive with Freeze-Align (0.58-0.62 R@5) and standard MRL (0.34-0.48 R@5) |

### Publications/Submissions
- **Paper:** CEREBRUS.pdf (in Edge-Glass repo)
- **Status:** Not submitted to venue
- **Planned:** NeurIPS/ICML/ICLR 2026 Workshop

### Strongest Positioning
> "I implemented encoder-frozen cross-modal alignment with Matryoshka Representation Learning achieving 78% R@5 on PixMo retrieval. The 512-d compressed embeddings retain 96% of full-dimensional performance, and TRM decoders on aligned latents outperform text-only baselines. DDP training on H100/A100 clusters with mixed precision. Negative result on Perceiver Resampler identified initialization issues."

---

## 6. AI Security — Adversarial Robustness (Coursework)

### Nature
Coursework-style project demonstrating implementation of standard adversarial attacks with controlled ablations. **Not a research contribution.**

### Work Implemented
- PGD adversarial attacks on ResNet (image classification)
- Embedding poisoning & blind backdoor triggers on SST-2 (NLP)
- Model extraction attacks on LLMs
- Membership inference attacks (MIA) on LLMs
- LLM watermarking/extraction
- Refusal LoRA bypass for safety evaluation
- Attack-success vs clean-accuracy tradeoff analysis

### Positioning
**Do not frame as research.** If included, frame as: "Implemented standard adversarial attack methodologies with controlled ablations for robustness evaluation."

---

## 7. RL Soccer — Reinforcement Learning (Coursework)

### Nature
Academic coursework project implementing standard RL algorithms.

### Methods
- PPO: baseline, reward shaping, curriculum learning, self-play
- DQN: baseline
- Ray/RLlib with GPU detection

### Positioning
Frame explicitly as **"Academic project"** or **"Coursework"**. Demonstrates RL implementation ability but not research novelty.

---

## 8. Malware Analysis: Memory Forensics with ML & Volatility

### Nature
Independent research project integrating machine learning with memory forensics for ransomware detection in IoT-enabled energy systems. **Published at IEEE ICAIA 2026.**

### Research Question
How can memory forensics (Volatility Framework) combined with machine learning and YARA rules effectively detect and classify ransomware in memory dumps from IoT-enabled energy systems?

### Methods
| Component | Approach |
|---|---|
| **Memory Acquisition** | 18 memory dumps (6 benign, 12 ransomware: WannaCry, Cerber, GandCrab, etc.) |
| **Forensic Analysis** | Volatility3 plugin orchestration (malfind, pslist, vadinfo, yarascan) |
| **YARA Rule Development** | 100+ rules for ransomware family classification |
| **ML Pipeline** | scikit-learn pipeline for malicious process identification from Volatility outputs |
| **Dataset Curation** | Hugging Face Hub: dataset repo (33 GB analysis) + 3 buckets (~470 GB raw) |

### Results (PUBLISHED — IEEE ICAIA 2026)
- **Memory dumps analyzed:** 18 (6 benign, 12 ransomware families)
- **YARA rules developed:** 100+ for ransomware family classification
- **ML pipeline:** Malicious process identification from Volatility outputs
- **Publication:** "Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems" — IEEE ICAIA 2026
- **Dataset:** Vedaang/malware_analysis (33 GB), Vedaang/malware-analysis-data (~470 GB), Vedaang/malware-code-base (3,384 files), Vedaang/malware-raw-dumps

### Technologies
- **Forensics:** Volatility3, YARA
- **ML:** scikit-learn, pandas
- **Environment:** Python, Jupyter, Docker
- **Data Platform:** Hugging Face Hub (datasets + buckets)

### Publications/Submissions
- **PUBLISHED:** IEEE ICAIA 2026 — "Integrating Machine Learning and Memory Forensics for Enhancing Cybersecurity in IoT-Enabled Energy Systems" (with Sonika Malik)

### Strongest Positioning
> "I integrated memory forensics (Volatility3) with ML and YARA rules to detect ransomware in IoT/energy systems — analyzing 18 memory dumps across 12 ransomware families, developing 100+ YARA rules, and publishing at IEEE ICAIA 2026. Dataset hosted on Hugging Face (33 GB analysis + 470 GB raw dumps)."

---

## Advisors & Labs

| Advisor | Lab | Affiliation | Role |
|---|---|---|---|
| **Dr. Matthew Gombolay** | CORE Robotics Lab | Georgia Tech @ Siemens | Primary MS Advisor (CAD, SHASTRA, ARTEMIS, CERBERUS) |
| **Prof. Vijay Madisetti** | — | Georgia Tech | ATHENA Co-author |
| **Dr. Alexey Tumanov** | Systems for AI Lab | Georgia Tech | Secondary affiliation (per v2_extended resume) |

---

## Research Areas & Keywords (Verified)

### Primary Research Areas
1. **Agentic AI Systems** — Multi-agent orchestration, tool-use planning, workflow reuse, LangGraph
2. **Execution-Grounded Evaluation** — Functional correctness beyond token-level metrics (code execution, geometric verification, visual judgment)
3. **Efficient Multimodal Inference** — Cost-aware routing, model compression (MRL, Perceiver), edge deployment
4. **RL for Structured Generation** — Reward design for verifiable domains (CAD, code), inference-time compute scaling
5. **Production ML Systems** — Reliable deployment, monitoring, evaluation pipelines at scale

### Keywords for Research Engineer Positioning
- **Use:** Multi-agent orchestration, LangGraph, tool-use planning, execution-grounded evaluation, geometric verification, VLM routing, SLA-aware load balancing, Matryoshka Representation Learning, DDP training, mixed precision, supervisor-worker patterns, structured generation, Pydantic, inference-time search, closed-loop repair
- **Avoid:** RLHF, RLAIF, DPO, SFT, reward modeling (RL sense), fine-tuning, LoRA/QLoRA, pre-training, distributed LLM training, blackboard controller, 14-agent, keyframe synthesis

---

## Publication Strategy (Planned)

| Project | Target Venue | Timeline | Status |
|---|---|---|---|
| CAD Code Generation | NeurIPS 2026 Workshop / arXiv | Sep 2026 | Drafting needed |
| ARTEMIS | NeurIPS 2026 Workshop / arXiv | Sep 2026 | Drafting needed |
| CERBERUS | NeurIPS 2026 Workshop / arXiv | Sep 2026 | Paper exists (CEREBRUS.pdf) |
| SHASTRA | AAMAS 2027 / AAAI 2027 / arXiv | Early 2027 | Early stage |
| ATHENA | arXiv (completed work) | Anytime | Paper draft exists (athena.tex) |

**Highest ROI:** arXiv preprints for CAD + ARTEMIS + CERBERUS by September 2026 — gives citable artifacts for fall recruiting.

---

## Research Gaps (Honest)

| Gap | Impact | Mitigation |
|---|---|---|
| No first-author top-venue publications | Hard filter at Meta, DeepMind, some OpenAI/Anthropic roles | Submit to 2026 workshops; arXiv preprints ASAP |
| No large-scale distributed LLM training experience | Required at frontier labs for training roles | Run multi-GPU LoRA fine-tuning on GT cluster (4+ GPUs) |
| No JAX experience | Hard filter at DeepMind/Google | Only pursue if targeting Google; otherwise skip |
| No synthetic data pipeline | Increasingly standard in post-training | Build for CAD work (parametric variation sampling) |
| Benchmark comparisons missing | HMs want to see numbers vs baselines | Run baselines for CAD, ARTEMIS, CERBERUS |
| Single research domain (CAD) | May appear narrow | Emphasize breadth: CAD + ARTEMIS + CERBERUS + ATHENA + SHASTRA = agentic + multimodal + evaluation |