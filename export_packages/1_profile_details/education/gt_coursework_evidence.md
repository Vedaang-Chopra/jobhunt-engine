# Georgia Tech Coursework Evidence Audit

**Date:** 2026-08-22
**Method:** Direct filesystem audit of `/Users/vedaangchopra/all_data/Georgia Tech/Course Content/` — notebook execution counts, persisted training artifacts, git authorship, report contents. Follows the fact-bank evidence-tier system: executed-output evidence upgrades a claim; collected PDFs do not.
**Companion to:** `profile_info/resume_fact_bank.yaml`, `profile_info/projects/CLAIM_AUDITS_2026-08-22.md`

---

## 1. Per-Course Inventory

Legend: **DONE-WITH-EVIDENCE** (submitted/executed work with artifacts) · **DONE-NO-ARTIFACT** (work done but no local proof) · **MATERIALS-ONLY** (slides/PDFs collected, no execution trace).

| Course | Verdict | Evidence summary |
|---|---|---|
| CS 8803-DRL (Deep RL) | **DONE-WITH-EVIDENCE** | 4 assignment notebooks + soccer-twos project with real Ray training runs, checkpoints, eval results, final report. See §2. |
| CS 7643 (Deep Learning) | **DONE-WITH-EVIDENCE (partial)** | hw4 diffusion + robotics-control notebook run on Colab; theory tests passed for scheduler/denoise/loss/CFG/sampling. Image-gen training cells NOT completed locally (see §3). |
| CS 8803-VLM | **DONE-WITH-EVIDENCE (papers)** | 10 authored paper-review PDFs in `My Analysis/` (MolmoAct, ImageBind, Visionary-r1, EMMA, PalM-E, Groot-1, VITA, hallucination survey) + MolMo/PIXMO presentation deck. |
| CS 8803-MLS (ML Security) | **DONE-WITH-EVIDENCE (papers)** | Authored presentation decks: Blind Backdoors, Invisible Backdoor Attacks on Diffusion Models, Membership Inference on LLMs (+ Truth_Serum.pdf, deepfake/gradient-inversion/memorization reading set, 16 lecture decks). |
| CS 8803-LLM | **DONE-WITH-EVIDENCE (papers)** | Neural Sparse Attention presentation + "The Jailbreak Tax" deck + midsemester presentation report; 23 paper-review slide decks collected. |
| CS 8803-SAI (Systems for AI) | **DONE-WITH-EVIDENCE (papers)** | Presentation decks on ReCycle, Oobleck, Bamboo, DeepSpeed (resiliency), METIS (RAG). No lab/code artifacts. |
| CS 8803-EML (Embedded ML) | **DONE-NO-ARTIFACT** | Lab 0/Lab 1/Lab 4 handouts present (quantization/NAS/distributed-training course); no submitted solution files or outputs found locally. Do not claim specifics beyond course completion. |
| CS 7641 (ML) | MATERIALS-ONLY | Mitchell textbook + lecture resources; one utility notebook (`combine_srt.ipynb`, unrelated transcription tooling). |
| CS 6601 (AI) | MATERIALS-ONLY | AIMA textbook only. No assignments on disk. |
| CS 8001-OCH | MATERIALS-ONLY | Seminar recordings + optional ChatGPT assignment. |
| CS 8803-SRD | MATERIALS-ONLY | `project_plan.pdf` only. No project artifacts. |
| CS 8903 (Agentic AI, Madisetti) | MATERIALS-ONLY locally | Course pack + example proposals only. NOTE: the *actual* CS 8903 research output (ATHENA, SHASTRA, ARTEMIS, CERBERUS) lives in `profile_info/projects/` and is already code-audited in CLAIM_AUDITS_2026-08-22.md — do not double-count here. |

---

## 2. Strongest New Evidence: DRL Soccer-Twos Project (`PPO_SP`)

This is the single biggest coursework upgrade discovered. The fact bank's `rl_soccer_methods` entry ("Implemented PPO and DQN agents…") is **upgraded from generic to artifact-backed**, with one important correction: it is a **team project**, not solo.

### What is on disk (paths relative to `CS 8803- DRL/project/project/soccer-twos-starter/` under the Course Content root)

- **Persisted Ray/RLlib PPO runs** — `artifacts/cs8803_soccer_twos/checkpoints/`: experiment lines `soccer_ppo_baseline`, `soccer_ppo_shaped`, `soccer_ppo_curriculum` (+ `_v2`/`_v3` curriculum resumes) with Tune `progress.csv`, `params.json`, TensorBoard event files, and resumable checkpoint binaries (2026-03 → 2026-04 timestamps).
- **Head-to-head evaluation results** — `artifacts/cs8803_soccer_twos/evals/*.json`: baseline vs curriculum variants over 5–10 episode matches.
- **Final report (CoRL-format LaTeX, compiled PDF)** — `report/corl_2026_template_cameraready/example.tex` + `final report.pdf`.
- **Executed pipeline notebooks** — `notebooks/00–05`: environment probe, smoke training, full training pipeline v3 (9/9 cells executed), submission smoke test (11/11), submission & report (10/10).
- **Submission-ready agent zips** — `TEAMNAME_v2_AGENT.zip`, `TEAMNAME_v3_AGENT.zip`.

### Verified numbers (cite exactly these)

From the report abstract, matching the `evals/` JSONs:
- Plain PPO baseline: mean episode reward **0.2399 @ ~2.0M env steps** (sparse-reward exploration failure).
- Reward shaping: **0.4036 @ same budget** (~1.7× baseline).
- Curriculum learning: **1.7869 @ ~2.06M steps** (~7.4× baseline).
- Final `TEAMNAME_v3_AGENT`: **1.9692 mean reward @ ~30M cumulative steps** (checkpoint resume + extended training), winning **8 of 10 recorded matches vs the PPO baseline**.

Caveat: eval episodes are small (n=5–10 matches per pairing) — qualify as "(course project, small-N evaluation)" if cited numerically outside the report.

### Authorship correction (matters for resume wording)

Git history: 7 commits by Vedaang Chopra out of 64 total (team of 4: Bryan de Oliveira, Manya Jain, Mili Das, Vedaang Chopra). The candidate's commits cover: project workflow organization, the three PROJECT_EXPLANATION docs (overview / modifications / results-and-oral), report drafting + final LaTeX edits/recompile, and notebook updates. Training-run authorship per-experiment is not attributable from git alone (runs executed on the candidate's MacBook — hostname `Vedaangs-MacBook-Pro` appears in tfevents — but pushes were shared).

**Correct framing:** "Team project (4 members): co-developed PPO training pipeline; personally owned project documentation, evaluation write-up, and final CoRL-format report" — or the generic "course team project" without implying sole authorship of training results.

### Assignments (supporting evidence)

- **A1 `solution.ipynb` — fully executed (24/24 cells):** REINFORCE, REINFORCE-with-baseline (VPG), PPO with clipped surrogate objective, optional GAE — implemented from scratch with TensorBoard logging.
- A2/A3/A4 notebooks: solutions present but stored un-executed (`executed=0`) + `replay_buffer_hw3.pkl` artifact. DONE-NO-ARTIFACT for these three unless re-run.
- Self-learning extension (`Self_Learning/RL_Research_Extension.md`): substantial authored research notes covering GRPO/DAPO/KTO/IPO, RLVR vs RLHF, process-vs-outcome reward models, explicitly tied to the CAD code-generation project. **Excellent interview ammunition for post-training roles — demonstrates current (2024–2026) post-training algorithm literacy. A study claim, not a skill-implementation claim.**

---

## 3. CS 7643 hw4 — Diffusion + Visual Action-Recognition Control

Evidence: `CS 7643/hw4/hw4_student_version/main.ipynb` (37 code cells, 10 executed, run in Google Colab).

- **PASSED (pytest green in saved outputs):** noise-scheduler init, denoise step, loss computation, classifier-free-guidance loss, sample generation — i.e., core DDPM components implemented against the course test suite (Colab, Python 3.12.13, pytest 8.4.2).
- **Code present but not evidenced as run:** `diffusion_model.py`, `noise_prediction_net.py`, CIFAR-10 image-generation loop (cells unexecuted after a ModuleNotFoundError during env setup), robotics push-T policy training/rollout.
- **Newly claimable (with qualifier):** "Implemented DDPM noise scheduling, forward/reverse process, and classifier-free guidance for a graduate DL assignment (instructor test suite passing); image-generation and robotics-policy training runs not preserved."
- Do NOT claim "trained a diffusion model on CIFAR-10" or "trained a robot policy" — no persisted outputs.

---

## 4. ML Security (CS 8803-MLS) — Strategic Assessment

**Verdict: supports an AI-security positioning pillar at the knowledge/analysis level, NOT yet at a projects level.**

Evidence on disk:
- Authored presentation decks: *Blind Backdoors in Deep Learning*, *Invisible Backdoor Attacks on Diffusion Models*, *Do Membership Inference Attacks Work on LLMs?* — delivered class presentations (DONE-with-evidence).
- Reading program: Truth_Serum, Sleeper Agents, Many-shot Jailbreaking, gradient-inversion-in-LM-training, deepfake-detection survey, memorization localization + 16 lecture decks (adversarial robustness, differential privacy, watermarking, undetectable backdoors).

Combined with existing VERIFIED facts:
- Fortinet AIOps R&D (4.5 yrs security-telemetry ML),
- IEEE ICAIA 2026 published memory-forensics/malware-classification paper (fact bank: lead evidence for ai_security),
- malware-analysis HF dataset (33 GB),

…the L1 security-AI narrative (Fortinet + malware research + MLS coursework) is now coherent across **industry + publication + graduate coursework**. What is still missing for a dedicated `base_ml_security.tex` variant: **no hands-on attack/defense implementation artifact exists** (no adversarial-example code, no backdoor PoC, no membership-inference experiment on disk).

**Recommendation:**
1. NOW: fold 1–2 MLS bullets into existing variants (applied_ml / agentic_ai skills sections; the ICAIA bullet already leads). Wording: "Graduate coursework in ML security: adversarial robustness, backdoor attacks (incl. diffusion models), membership inference, differential privacy, watermarking — with seminar-level paper analysis."
2. LATER (only after building an artifact): create `base_ml_security.tex`. Fastest unlock: reproduce one small experiment (e.g., membership inference on a public fine-tuned LLM, or a simple backdoor on a small CNN) — a weekend of work converts the pillar from analysis-level to project-level.

---

## 5. Fact-Bank Updates Applied (same change)

To `profile_info/resume_fact_bank.yaml`:

1. **`rl_soccer_methods` UPGRADED** (status stays VERIFIED; evidence strengthened):
   - evidence: now includes "SoccerTwos project artifacts: Ray Tune PPO checkpoints + progress CSVs + head-to-head eval JSONs + compiled CoRL-format report (`Course Content/CS 8803- DRL/project/project/soccer-twos-starter/`)"
   - metrics added: baseline 0.2399 → shaped 0.4036 → curriculum 1.7869 @ ~2M steps; final agent 1.9692 @ ~30M, 8/10 wins vs baseline (small-N)
   - **new critical_note:** TEAM project (4 members; 7/64 commits by candidate — docs/report/notebook organization). Never claim solo training results.
2. **NEW fact under CS 8903 research:** `drl_post_training_literacy` — evidence-backed *study* claim: "Self-studied modern post-training methods (DPO/KTO/IPO/GRPO/DAPO, RLVR, process vs outcome reward models) with authored research-extension notes tied to the CAD project." Rule: usable in interviews/cover letters; on resumes only inside Skills as "(coursework/self-study: RLHF/DPO/GRPO theory)" — never imply implementation.
3. **NEW hw4 diffusion fact (education):** "Implemented DDPM noise scheduling, denoising step, and classifier-free-guidance loss; instructor test suite passing (Colab execution logs)" — status VERIFIED, with the no-training-runs caveat.
4. **No bans touched.** All banned claims remain banned; nothing in the coursework contradicts them. The diffusion claim is NEW (never previously made), added with its qualifier.

---

## 6. Candidate-Facing Positioning Summary (by role family)

**Agentic AI (P1):** No change to lead bullets. New support material: the SoccerTwos reward-design/curriculum story pairs well with the CAD closed-loop narrative ("reward design in verifiable environments"). The RLVR literacy notes directly bridge CAD inference-time search to post-training conversations.

**Post-training / model-improvement (rising family):** Biggest upgrade. Concrete PPO mechanics (from-scratch A1 + ~30M-step project runs) AND current algorithms (GRPO/DAPO/DPO notes). The honest bridge remains: no production post-training implementation. This materially strengthens the ROLE_FIT_RULES.md L2 post-training positioning.

**ML Security / AI-security (recommend ELEVATE to formal family):** Industry (Fortinet) + publication (ICAIA) + coursework (MLS decks) triangle complete at analysis level. Elevate priority for L1 companies (Palo Alto Networks, CrowdStrike, Zscaler, Cisco, Cloudflare, SentinelOne, Fortinet). Dedicated resume variant only after building one hands-on artifact.

**Eval/inference:** unchanged. **Applied ML/production:** unchanged.

**Resume bullet suggestions (verified wording):**
- RL: "Trained PPO agents (Ray/RLlib) with reward shaping and curriculum learning in a sparse-reward multi-agent soccer environment; curriculum raised mean episode reward ~7.4× over baseline (0.24 → 1.79 @ ~2M steps); final agent won 8/10 vs baseline (team project)." *(qualify: academic, small-N)*
- Diffusion: "Implemented DDPM noise scheduling, reverse-process sampling, and classifier-free guidance loss for a graduate deep-learning assignment (instructor test suite passing)."
- Skills line addition: "RL: PPO, DQN, reward shaping, curriculum learning · Post-training theory: RLHF, DPO, GRPO (coursework)"
