# Evaluation — Deloitte Research Engineer, Post-Training & SLMs (Healthcare AI)

**Date:** 2026-08-23 · **Family:** research_engineer_post_training ⚠️ STRETCH · **Page:** 1

## 1. Role Diagnosis
Responsibilities keyword counts: post-training/RLHF-family terms = 14, evaluation = 5, inference = 3 → dominant family `research_engineer_post_training` (STRETCH — checklist hard-stop acknowledged; user explicitly directed this application). Secondary: `research_engineer_agentic` (verifiable rewards, tool use).

## 2. Requirement Map
| Level | Requirement | Match | Evidence |
|---|---|---|---|
| P0 | SFT/preference-opt/RL hands-on depth ("your craft") | **GAP — fundamental** | none; coursework/self-study literacy only |
| P0 | Verifiable-reward (RLVR) workflows | Partial | CAD: verifiable geometric reward framing (not training-time) |
| P0 | PyTorch + distributed training (DeepSpeed/FSDP/Megatron/Ray) | Partial | DDP + mixed precision H100/A100 (CERBERUS); DeepSpeed/FSDP/Megatron/Ray never claimed |
| P0 | LLM eval methodologies, benchmarking, reward modeling | Strong | CAD harness, ATHENA ablations |
| P1 | Open-weight models (Llama/Qwen/Mistral/DeepSeek) | Partial | served via ARTEMIS vLLM (Gemma/Qwen/Llama-4/DeepSeek OCR) |
| P1 | Efficient fine-tuning LoRA/QLoRA/PEFT | **GAP** | X-tier banned |
| P1 | Inference optimization vLLM/TensorRT/TGI | Partial | vLLM (ARTEMIS), ONNX (Fortinet); TensorRT/TGI never claimed |
| P2 | Healthcare domain / PHI-HIPAA | GAP | transferable only |

## 3. Fact-Trace Table
| Bullet | Fact source |
|---|---|
| CAD pipeline (verifiers, reward signals, 202-test) | EVIDENCE_LIBRARY BLOCK: CAD |
| ATHENA critique/ablation (+0.18 BLEU-4 abs, −27%) | BLOCK: ATHENA |
| Fortinet agentic RAG (~70%) | fort_agentic_rag |
| DDP/mixed-precision H100/A100 + ONNX ~40% + OpenSearch 40x | CERBERUS systems variant + fort_onnx + fort_opensearch |
| Patent + SLA forecasting | fort_patent + fort_sla |
| Skills RL row "(academic projects)" | RL Soccer block boundary |

## 4. JD Keyword Disposition Table (selected)
| Keyword | Disposition |
|---|---|
| verifiable reward / verifiers / RLVR concept | Integrated (CAD, honest frozen-model framing) |
| evaluation frameworks / hallucination detection | Integrated (ATHENA) / Listed (coursework) |
| PyTorch, transformers, attention | Integrated/Listed |
| distributed training | Listed as DDP+mixed precision ONLY (no DeepSpeed/FSDP/Megatron/Ray) |
| vLLM, quantization contexts, latency/throughput | Listed (verified equivalents) |
| data quality/deduplication pipelines | Listed (Fortinet/financial-platform equivalents) |
| SFT, RLHF, DPO, GRPO, preference optimization, reward modeling, LoRA/QLoRA/PEFT | Omitted-with-reason: Tier-1/X-tier banned — no hands-on evidence; coursework-literacy phrasing used once in Skills |
| healthcare/HIPAA, TensorRT-LLM/TGI/Ollama, Megatron/Ray | Omitted-with-reason: no evidence |

**Cross-JD sweep:** 2026-08-23 baseline (74 post-training JDs) recorded in KEYWORD_BANK.md.

## Coverage summary & criticism
P0 coverage ~50% (fundamental gap: no hands-on post-training). Honest positioning is the frozen-model/verifiable-reward alternative plus academic RL foundations. **Weakness (mandatory):** this resume cannot satisfy "SFT + at least one preference-opt method evidenced by shipped models" — screening rejection risk is high; referral (4 tracked Deloitte connections) is essential before applying. Phase K passes: 6 iterations.
