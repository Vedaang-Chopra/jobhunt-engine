# Evaluation — OpenAI Research Engineer, Codex

**Date:** 2026-08-23 · **Family:** research_engineer_agentic (coding-agents emphasis) · **Secondary:** llm_reasoning · **Page:** 1

## 1. Role Diagnosis
Responsibilities counts: agentic/tool-use/coding-agent terms = 12, evals/graders = 7, post-training/RL = 5 → primary `research_engineer_agentic`, secondary `research_engineer_llm_reasoning`. RL/post-training mentioned but not gated as P0 hands-on.

## 2. Requirement Map
| Level | Requirement | Match | Evidence |
|---|---|---|---|
| P0 | Improve agentic model behavior (tool use, function calling, multi-agent, long-horizon) | Strong | CAD, ATHENA, SHASTRA, ARTEMIS, Fortinet RAG |
| P0 | Evals/environments that expose failures → graders | Strong | 202-test harness, failure classification, grader design |
| P0 | Debug qualitative behavior → hypotheses/fixes | Strong | repair-loop diagnostics, AST/code-graph analysis |
| P1 | Post-training stack ownership incl. RL | Partial/GAP | honest inference-time-search framing; academic RL only |
| P1 | Production ML systems | Strong | Fortinet 40x scaling, ONNX, production RAG |
| P2 | Early-training/data mixtures/synthetic data | GAP | omitted |

## 3. Fact-Trace Table
| Bullet | Fact source |
|---|---|
| Coding-agent pipeline, Chamfer/Hausdorff graders, 202 tests | BLOCK: CAD |
| Graders/failure-diagnostics bullet | CAD (verification components variants) |
| SHASTRA trace-to-graph (94 sessions, 4,037 events, 442 nodes) | BLOCK: SHASTRA |
| ATHENA 5-agent supervisor-worker (+0.18 BLEU-4 abs, −27%) | BLOCK: ATHENA |
| ARTEMIS routing as dynamic tool selection (6+ backends, vLLM) | BLOCK: ARTEMIS agentic variant |
| Fortinet RAG (~70%), OpenSearch 40x, ONNX ~40%, SLA 60+, patent | fort_* fact IDs |

## 4. JD Keyword Disposition Table (selected)
| Keyword | Disposition |
|---|---|
| coding agents, tool use, function calling, multi-agent, long-horizon | Integrated |
| evals, graders, diagnostics, failure classification | Integrated |
| structured outputs (Pydantic), workflow composition | Integrated/Listed |
| vLLM, inference optimization, cross-modal retrieval | Listed |
| RLHF/RLAIF/post-training hands-on, synthetic data | Omitted-with-reason (banned/no evidence); RL row qualified "(academic projects)" |

**Cross-JD sweep:** 2026-08-23 baseline recorded in KEYWORD_BANK.md.

## Coverage summary & criticism
P0 coverage ~85%. Narrative: execution-grounded verification + multi-agent orchestration maps directly onto Codex's grader/environment work. **Weakness (mandatory):** zero production agent-training experience and no benchmark results on standard agent suites (WebArena/SWE-bench); frontier-lab bar makes this a stretch despite strong keyword alignment. Phase K passes: 8 iterations.
