# Resume Score — base_agentic_ai.tex vs AI Engineer — Tessera Labs @ ?

- **Date:** 2026-08-24T15:50:57
- **FINAL SCORE:** **84.4/100** (40% ATS keywords 100 + 60% LLM fit 74)
- **Verdict:** A strong technical match for the agentic core of this posting — production LLM tool-calling systems, evals, and retrieval are all clearly evidenced — but missing TypeScript, enterprise-platform APIs, guardrails/approval semantics, and current full-time-student status keep it short of an easy yes.

## Breakdown

| Dimension | Score |
|---|---|
| Keyword Alignment | 83 |
| Experience Relevance | 79 |
| Title And Seniority Fit | 66 |
| Ats Parseability Formatting | 82 |
| ATS keyword coverage | 100.0 |

## Keywords matched (2 shown)
distributed systems, python

## Keywords missing (top)
—

## Strengths
- Directly mirrors the JD's 'shipped agentic systems real users depend on': at Fortinet the candidate led an agentic RAG diagnostics system where an LLM plans multi-step tool calls over network telemetry with structured function calling and autonomous root-cause analysis, taken from hackathon prototype to production with ~70% reduction in mean resolution time.
- Strong 'evaluation as engineering' evidence: maintains a 202-test evaluation harness with VLM-based visual judgment on the CAD code-generation pipeline, plus BLEU-4/CLIPScore evaluation of ATHENA and an explicit LLM-as-a-Judge skill line — matching the JD's demand for regression coverage and measured retrieval/eval layers.
- Fluent in the exact agent toolkit named in the JD: LangGraph, LangChain, tool/function calling, supervisor-worker orchestration, planning, Pydantic structured generation, demonstrated across three research systems (SHASTRA, ATHENA, CORE Robotics CAD pipeline).
- Real traditional ML background the JD asks for: filed patent PCT/IN2022/058026 on unsupervised distributional thresholding for anomaly detection (~75% less manual troubleshooting), plus a trained neural multi-task VLM router (ARTEMIS) — evidence of reaching for supervised/classical models over extra LLM calls.
- Code generation with execution verification (LLM writes CadQuery programs, execution environment returns compile/geometry feedback, LangGraph repair loop) aligns closely with the JD's nice-to-have on code analysis/program transformation and its representative project of proving agent work correct.
- Retrieval and distributed-systems depth: scaled OpenSearch ingestion from 50 to 2,000 events/sec in Golang, plus FAISS/SBERT/cross-modal retrieval and RAG-augmented prompt construction — covering both the retrieval-layer and partial-failure-tolerance preferences.

## Gaps
- No TypeScript anywhere on the resume; the JD explicitly requires 'strong Python and comfortable in TypeScript.'
- No hands-on experience with the named enterprise platforms (SAP, Salesforce, Workday, Oracle, Snowflake, MuleSoft, ServiceNow) — Fortinet work is network/security telemetry, not business-system landscapes with extension models.
- No explicit guardrails, approval gates, rollback paths, or human-authorization semantics for agent actions; the JD treats traceable human approval and safe write semantics as first-class product requirements, and the resume only shows post-hoc verification, not pre-execution control.
- No LLM observability/tracing tooling named (LangSmith, Langfuse, OpenTelemetry-style run instrumentation, replay pipelines); 'instrument every run so each call can be reconstructed' is a core JD duty and only generic 'observability' on OpenSearch pipelines is claimed.
- No MCP, sub-agent/plugin architectures, workflow engines (e.g., Temporal), or knowledge-graph tooling cited — the ontology-based classification paper and SHASTRA component registry are adjacent but not framed that way.
- Seniority/availability risk: the role implies senior end-to-end ownership ('this is not a prototyping role') and incident ownership, while the candidate is a full-time MS student graduating Dec 2026 whose highest industry title is SDE II; additionally, the Fortinet dates (Feb 2021–Jul 2025) overlap the MS start (Aug 2024) with no explanation, which may read as a red flag to screeners.

## Recommendations
- Add TypeScript honestly if it exists anywhere (internal tooling, web frontends, test harnesses); if truly absent, consider a quick portfolio project exposing agent tools via a typed TS interface so the keyword and skill gap closes before applying.
- Reframe the Fortinet diagnostics bullet in enterprise-system language: name the APIs/integrations the agent called, any permissioning or authorization checks in the tool layer, and the production customers/users who depended on it — mapping directly to the JD's 'typed, permissioned, well-documented interfaces' language.
- Add an explicit bullet on safety controls: describe how the diagnostics agent's proposed actions were constrained, validated, or human-reviewed before execution, and any rollback/replay behavior — even modest detail here addresses the JD's biggest emphasis (guardrails, approval gates, auditability).
- Surface instrumentation explicitly: describe the 202-test harness as CI/regression coverage on every change, and add any run-logging/replay or W&B-traced experiment reconstruction you actually did, using the words 'tracing,' 'replay,' and 'regression' that the JD screens for.
- Reposition existing assets toward the nice-to-haves: label the CEUR paper as ontology/semantic-model work, frame SHASTRA's component registry with pluggable storage as a skill/plugin architecture, and highlight the Go/OpenSearch distributed pipeline as partial-failure-tolerant systems experience.
- Clarify the timeline: add a parenthetical noting the Fortinet role was held concurrently with (or remotely during) the first year of the MS if accurate, and state expected availability (post-Dec 2026 or immediate part-time), so recruiters don't discard the resume over an apparent date conflict.