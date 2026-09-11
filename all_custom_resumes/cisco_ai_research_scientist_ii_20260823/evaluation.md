# Evaluation — Cisco AI Research Scientist II (Foundation AI)

**Date:** 2026-08-23 · **Family:** general_research_engineer → applied/agentic hybrid · **Page:** 2 (justified below)

## 1. Role Diagnosis
Responsibilities counts: research-to-production/agentic = 9, pre/post-training methods = 6, data curation = 3, publications emphasis = 3 → `general_research_engineer` with agentic+eval narrative (strongest verified overlap per ROLE_FAMILIES §11).

## 2. Requirement Map
| Level | Requirement | Match | Evidence |
|---|---|---|---|
| P0 | MS CS/ML + strong Python/PyTorch | Full | GT MS 4.0, all blocks |
| P0 | LLM training/fine-tuning/eval/inference/optimization | Partial | eval/inference/routing strong; fine-tuning gap (honest) |
| P0 | Data pipelines, experimentation, scalable AI system design | Strong | OpenSearch 40x, financial ingestion platform, CAD curation |
| P1 | Scalable data curation methods | Strong | CAD prompt-evidence curation; platform QC tooling |
| P1 | vLLM/Triton/TorchServe deployment | Partial | vLLM (ARTEMIS), Docker/Azure; Triton never claimed |
| P1 | Publications top-tier / open-source | Partial | IEEE ICAIA 2026 published; no NeurIPS-tier |
| P1 | Agentic workflows / multi-agent frameworks | Strong | CAD, ATHENA, SHASTRA, LangGraph ×4 |
| P2 | Cybersecurity familiarity | Strong | ICAIA paper, patent, security-telemetry ML |

## 3. Fact-Trace Table
| Bullet | Fact source |
|---|---|
| CAD closed-loop + data-curation bullet | BLOCK: CAD |
| ARTEMIS VLM routing (6+ backends, 5 modes, SLA-aware) | BLOCK: ARTEMIS multimodal variant |
| CERBERUS DDP H100/A100, Matryoshka 4096→128 ~96%, R@5 78% | BLOCK: CERBERUS |
| ATHENA cross-modal eval (+0.18 BLEU-4 abs, −27%) | BLOCK: ATHENA |
| Fortinet RAG (~70%), OpenSearch 40x re-architecture, ONNX ~40%, SLA 60+, patent | fort_* fact IDs |
| IEEE ICAIA 2026 entry | Malware Analysis block (published status) |

## 4. JD Keyword Disposition Table (selected)
| Keyword | Disposition |
|---|---|
| agentic, multi-agent, LangChain/LangGraph, tool calling | Integrated |
| data curation / quality control | Integrated (CAD bullet) |
| vLLM, inference optimization, latency/throughput, DDP, mixed precision | Integrated/Listed |
| Docker, Linux, Azure | Listed (verified inventory) |
| Kubernetes, AWS, GCP, Triton, TorchServe | Omitted-with-reason (X-tier / no evidence) |
| pre-training methods | Omitted-with-reason (no evidence) |

**Cross-JD sweep:** 2026-08-23 baseline recorded in KEYWORD_BANK.md.

## Page-count justification
2 pages allowed for research-heavy frontier-style roles (Rules §9); ARTEMIS + CERBERUS + ATHENA all materially strengthen this broad-research role; readability preserved.

## Coverage summary & criticism
P0 coverage ~80%, P1 ~75%. Broadest-fit resume of the three. **Weakness (mandatory):** no hands-on pre-/post-training runs at scale (only encoder-alignment DDP); publication record is one workshop-tier venue vs their stated NeurIPS/ICML/ICLR bar. Note: posting window closes 08/23/2026 — apply today or not at all. Phase K passes: 8 iterations.
