## Fit Analysis: Stealth Startup (DeepMind/Anthropic alumni) — Research Scientist / Applied AI Engineer

**Role Family**: agentic_ai
**Base Template**: base_agentic_ai.tex
**Overall Fit**: Moderate-Strong — Strong agentic/multimodal evidence; fundamental gap on post-training (RLHF/RLAIF/DPO) explicitly required

### Requirement Coverage

| Requirement | Evidence | Strength |
|---|---|---|
| Multimodal models (video, audio, images, text, keypoints) | ARTEMIS (6+ VLM backends via vLLM), CERBERUS (CLIP/SBERT/Whisper, MRL), CAD (VLM visual judgment) | Strong |
| Post-training (RLHF/RLAIF/DPO/SFT) | **GAP** — Candidate uses frozen models + inference-time search; academic PPO/DQN only | Gap |
| RL / evals | ATHENA cross-modal eval pipeline, CAD 202-test harness, ARTEMIS routing eval, RL Soccer (academic PPO/DQN) | Partial |
| Shipping frontier model products | Fortinet agentic RAG (production, ~70% resolution reduction), ARTEMIS vLLM serving 6+ backends, ONNX edge deployment | Strong |
| Agentic / computer-use systems | CAD closed-loop agentic pipeline (LangGraph), ATHENA 5-agent supervisor-worker, SHASTRA trace-to-graph, Fortinet agentic RAG | Strong |
| 3-6 years experience | 4.5 years Fortinet + MS research | Strong |

### Customization Decisions

- **Tagline**: "Agentic computer-use with execution verification — Multimodal model routing — Production agentic RAG" — mirrors "proactive computer use model", "multimodal", "shipping frontier products"
- **Header**: Added "Multimodal (video, audio, image, text)" to skills to match JD's explicit modalities
- **Lead bullets**: 
  - CAD: Emphasized "inference-time search with verifiable geometric reward" (not RL post-training)
  - ARTEMIS: Lead project — VLM routing directly relevant to multimodal model selection
  - ATHENA: Supervisor-worker + reflection = agentic orchestration
  - SHASTRA: Workflow reuse for long-horizon tasks = computer-use relevant
- **Fortinet**: Condensed to 3 bullets; lead with agentic RAG (production tool-use)
- **Skills**: LLMs/VLMs moved up; added "Multimodal (video, audio, image, text)" explicitly
- **Omitted**: CERBERUS (space), CEUR 2020 paper, AI Security coursework

### Gaps & Mitigations

- **Post-training (RLHF/RLAIF/DPO/SFT/LoRA)**: Fundamental gap. **Mitigation**: Frame honestly — "My research achieves RL-like results via inference-time search with verifiable geometric rewards on frozen models; academic PPO/DQN experience." Do NOT claim post-training experience.
- **Top-venue publications**: No NeurIPS/ICML/ICLR. **Mitigation**: Target arXiv preprints by Sep 2026; highlight patent and production systems.
- **No SWE-bench/WebArena**: **Mitigation**: CAD 202-test harness with geometric verification is analogous rigor; acknowledge gap honestly in conversation.
- **F-1 visa (needs H-1B)**: **Mitigation**: Referral from Keana/Fardeen network can bypass ATS; startup may sponsor.

### H-1B Sponsor Status
- Unknown — stealth startup, likely early stage. **Action**: Ask referrer (Keana/Fardeen) about sponsorship policy before applying.

---

### Factuality Verification Checklist
- [x] Every bullet traces to verified facts (CAD 16 modules/202 tests, ARTEMIS vLLM 6+ backends, ATHENA 5 agents, Fortinet ~70%/~75%/40x/ONNX ~40%)
- [x] Self-reported metrics use "~" qualifier
- [x] NO RLHF, RLAIF, DPO, SFT, LoRA/QLoRA, reward modeling claims
- [x] NO "RL-based post-training" for CAD
- [x] NO "14-agent", "blackboard", "BLEU +18%", "CLIPScore +22%"
- [x] NO ARTEMIS "100K+ profiles", "~30% lower cost", "KL-divergence"
- [x] ATHENA BLEU-4 is "+0.18 absolute"
- [x] RL skills qualified as "(academic projects)"
- [x] Multimodal modalities explicitly listed per JD
- [x] Exactly 1 page PDF