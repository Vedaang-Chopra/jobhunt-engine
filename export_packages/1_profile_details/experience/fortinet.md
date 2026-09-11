# Fortinet Technologies Inc. — AIOps R&D, Bengaluru, India
**Role:** Software Development Engineer I & II (ML/AI Track)
**Dates:** February 2021 — July 2025 (4 years, 6 months)
- **SDE I:** Feb 2021 — Feb 2025
- **SDE II:** Feb 2025 — Jul 2025 (promotion)

## Responsibilities
| Area | Details | Evidence | Confidence |
|---|---|---|---|
| ML Model Development | Designed, trained, deployed classifiers for anomaly detection & SLA forecasting | LinkedIn, patent filing | VERIFIED |
| Production Data Pipelines | Built and scaled telemetry ingestion, preprocessing, feature engineering | LinkedIn (OpenSearch 50→2000), GitHub profile | VERIFIED |
| LLM/Agentic Systems | Led agentic RAG diagnostics system (hackathon → production) | LinkedIn description | VERIFIED (self-reported metrics) |
| Edge ML Inference | ONNX Runtime deployment on network appliances | Original CV, LinkedIn | VERIFIED (self-reported ~40% latency reduction) |
| Intellectual Property | Filed patent on unsupervised wireless anomaly detection | Patent PCT/IN2022/058026 on Justia | VERIFIED |
| Backend Integration | Python-Go integration for ML model serving | LinkedIn | VERIFIED |

## Key Projects & Accomplishments

### 1. Agentic RAG Diagnostics System ("RAC") (SDE II, 2025)
- **Origin:** Fortinet Global Hackathon 2023 — top-5 finalist (5th place); user-built prototype that was later productionized
- **Description:** LLM plans multi-step tool calls over network telemetry, invokes APIs, verifies hypotheses via structured function calling, produces autonomous root-cause analysis
- **Scale:** ~10K+ managed devices (self-reported — use with "~" qualifier)
- **Impact:** Reduced mean resolution time ~70% (hackathon prototype to production deployment)
- **Technologies:** LLM orchestration, tool/function calling, structured output, RAG, LangChain/LangGraph
- **Evidence:** LinkedIn description
- **Confidence:** VERIFIED (system exists); METRICS: PARTIALLY VERIFIED (self-reported)

### 2. Unsupervised Wireless Connectivity Thresholding (Patent)
- **Description:** Distributional thresholding model for wireless connectivity anomaly detection using density-based analysis
- **Patent:** PCT/IN2022/058026 (filed, listed on Justia)
- **Impact:** Reduced manual troubleshooting ~75% (self-reported)
- **Evidence:** Patent filing, LinkedIn, GitHub profile mention
- **Confidence:** VERIFIED (patent exists); METRICS: PARTIALLY VERIFIED

### 3. OpenSearch Ingestion Pipeline Re-Architecture
- **Description:** Complete redesign of the ingestion architecture (not just tuning) — async I/O + Golang, scaling telemetry from <50 to >2,000 events/sec (40x+)
- **Impact:** Enterprise-grade throughput for network monitoring
- **Evidence:** LinkedIn, GitHub profile (consistent across platforms); user confirmation 2026-08-23 that this was a full database/pipeline re-architecture
- **Confidence:** VERIFIED

### 3b. Pickle-Based Model Serving on CPU (Backend Integration)
- **Description:** Integrated data-science team's pickled ML models into Go/Python backend code and deployed inference purely on CPUs (no GPU dependency)
- **Evidence:** User-stated 2026-08-23; consistent with backend-integration role in LinkedIn description
- **Confidence:** VERIFIED (user direct statement) — wording: "integrated DS-team pickle models into production backend; CPU-only inference"

### 3c. DBSCAN Anomaly Detection for SD-WAN Telemetry
- **Description:** Unsupervised DBSCAN-based anomaly detection over SD-WAN telemetry, proactively flagging issues before outages
- **Impact:** Reportedly prevented >50% of potential network outages
- **Evidence:** Old resume material (career_master_context.md)
- **Confidence:** PARTIALLY VERIFIED — use "reportedly" or "~" qualifier

### 4. Edge ML Inference Optimization
- **Description:** Deployed ML models via ONNX Runtime for on-device anomaly detection on access points/switches
- **Impact:** ~40% latency reduction (GPU-to-CPU conversion with quantization)
- **Evidence:** Original CV, LinkedIn
- **Confidence:** VERIFIED (system deployed); METRICS: PARTIALLY VERIFIED (self-reported)

### 5. SLA Forecasting Pipelines
- **Description:** 60+ classifiers across 4 categories (performance, capacity, availability, connectivity) with automated evaluation and retraining; **7-day prediction horizon**
- **Scale:** Production traffic for enterprise network monitoring
- **Evidence:** LinkedIn description + old resume material (7-day horizon from career_master_context.md)
- **Confidence:** VERIFIED (system exists); SCALE: PARTIALLY VERIFIED

## Technologies Used (Verified)
- **Languages:** Python (primary), Go (backend/services), C/C++ (some)
- **ML:** PyTorch, Scikit-Learn, ONNX Runtime
- **Data/Infra:** OpenSearch/Elasticsearch, Docker, Linux, Git, SQL/PostgreSQL, Redis, Azure
- **MLOps:** FastAPI (model serving), W&B/TensorBoard (experiment tracking — listed in skills)

## Resume-Worthy Claims (Verified)
- "Led development of an agentic RAG diagnostics system: LLM plans multi-step tool calls over network telemetry, invokes APIs, and verifies hypotheses via structured function calling, producing autonomous root-cause analysis — reduced mean resolution time ~70% (hackathon prototype to production deployment)."
- "Scaled OpenSearch ingestion pipelines from 50 to 2,000 events/sec using Golang while maintaining reliability and observability; integrated ML models into backend services with Python and Go across distributed systems and telemetry infrastructure."
- "Patent (Filed): PCT/IN2022/058026 — Unsupervised distributional thresholding for wireless connectivity anomaly detection using density-based analysis; reduced manual troubleshooting ~75%."
- "Deployed inference-optimized ML models via ONNX Runtime for edge network appliances (~40% latency reduction); built SLA forecasting pipelines supporting 60+ classifiers across 4 categories with automated evaluation and retraining, processing telemetry at enterprise scale."

## Additional Verified Facts (added 2026-08-23, user-direct)
- **Hackathon origin:** Agentic RAG system began as the user's own Fortinet Global Hackathon 2023 entry — **top-5 finalist (5th place)** — then productionized. Resume wording: "a Fortinet Hackathon 2023 (top-5 finalist) prototype that evolved into a production feature."
- **OpenSearch was a full re-architecture:** complete redesign of the ingestion pipeline/database layer using async I/O + Golang, not incremental tuning. Resume wording: "Re-architected OpenSearch ingestion pipelines using async I/O and Golang, scaling event throughput from under 50 to over 2,000 events per second."
- **Pickle model serving, CPU-only:** connected the data-science team's pickle-format models into backend code and deployed inference purely on CPUs. Resume wording: "Integrated data-science team's pickled ML models into production backend services; deployed CPU-only inference without GPU dependency."
- **DBSCAN SD-WAN anomaly detection:** implemented unsupervised DBSCAN-based anomaly detection for SD-WAN telemetry; reportedly prevented >50% of potential outages (CAUTION — qualify with "reportedly").

## Metrics Registry (from METRICS_REGISTRY.md)
| Metric | Value | Context | Safety | Resume Wording |
|---|---|---|---|---|
| OpenSearch ingestion scaling | 50 → 2,000 events/sec (40x) | Telemetry pipeline scaling using Golang | SAFE | "Scaled OpenSearch ingestion from 50 to 2,000 events/sec (40x)" |
| Mean resolution time reduction | ~70% | Agentic RAG diagnostics (hackathon → production) | CAUTION | "reduced mean resolution time ~70% (hackathon prototype to production deployment)" |
| Manual troubleshooting reduction | ~75% | Patent: wireless connectivity thresholding | CAUTION | "cut manual troubleshooting ~75%" |
| Edge inference latency reduction | ~40% | ONNX Runtime deployment on network appliances | CAUTION | "~40% latency reduction" |
| SLA forecasting classifiers | 60+ | Across 4 categories | SAFE | "60+ classifiers across 4 categories" |
| Patent number | PCT/IN2022/058026 (WIPO) / US app 17/958,026 (pub. US20240121629A1) | Filed; public record shows PENDING — do NOT claim "Granted" without a grant number | SAFE | "Patent (Filed): PCT/IN2022/058026" |
| Hackathon placement | Top-5 finalist, Fortinet Global Hackathon 2023 (one source: 5th place) | Origin of the agentic RAG system | SAFE | "Top-5 finalist, Fortinet Global Hackathon 2023" |
| SD-WAN outage prevention | >50% of potential outages prevented | DBSCAN anomaly detection on SD-WAN telemetry | CAUTION | "reportedly prevented over 50% of potential outages" |
| SLA forecast horizon | 7 days | Multi-domain data collection + forecasting | SAFE | "7-day AI-based performance prediction" |