# Research Scientist / Engineer – Reinforcement Learning Infrastructure — Luma

- **job_id:** li_luma_research_scientist_engineer_reinforcemen_4445276729
- **source:** linkedin
- **source_id:** li_4445276729
- **location:** Redwood City, CA (Hybrid)
- **url:** https://www.linkedin.com/jobs/view/4445276729/
- **date_discovered:** 2026-08-22
- **queries:** Research Engineer Machine Learning, Post-Training LLM, LLM Fine-Tuning Engineer

## Full Job Description Text

You'll build the systems that make reinforcement learning work at frontier scale — coupling policy optimization with large fleets of inference workers, agentic environments, and the reward and verification systems that turn model behavior into learning signal. RL is how Luma's models go from capable to useful.

RL at scale is a full-loop systems problem: training, rollout generation, environment execution, and reward computation running concurrently across thousands of GPUs, all needing to stay fast, stable, and correct together. It fits someone who has lived this — post-trained LLMs with RL, built environments and verifiers, and debugged asynchronous rollout pipelines at scale. If you haven't operated RL at real scale, this will be deep water.

What You'll Own

- Design, build, and scale distributed RL post-training systems, orchestrating trainer, rollout, environment, and reward workloads across thousands of GPUs.
- Build high-throughput rollout generation, integrating inference engines (vLLM, SGLang), weight synchronization, and asynchronous/off-policy schemes.
- Design RL environments for agentic, multi-step tasks — sandboxed code execution, tool use, computer use, multimodal interaction — reproducible and scalable to millions of episodes.
- Build reward infrastructure: verifiable/programmatic rewards, reward-model serving, LLM-as-judge pipelines, and defenses against reward hacking.
- Develop the evaluation, monitoring, and debugging tooling that keeps large RL runs stable.
- Advance training efficiency and stability, and turn new post-training ideas into production runs with researchers.



First 90 Days

One way the first 90 could unfold.

- Days 1–30 — Immerse & Diagnose: Learn the current RL stack and where throughput, stability, or correctness break.
- Days 30–60 — Ship & Validate: Improve a piece of the loop (rollout throughput, reward infra, or an environment) and prove it on a real run.
- Days 60–90 — Scale & Systemize: Harden the full loop across thousands of GPUs and asynchronous architectures.



What You Bring

- Hands-on experience post-training LLMs with RL (PPO/GRPO-family, RLHF, RLVR) at meaningful scale.
- Extensive distributed PyTorch training and parallelism (FSDP, Tensor/Pipeline/Expert Parallel) for foundation models.
- Experience building RL environments, reward functions, verifiers, or evaluation harnesses for LLM agents, including sandboxed execution and multi-turn tool use.
- Deep familiarity with RL post-training frameworks (veRL, OpenRLHF, TRL, Ray orchestration) and rollout inference engines (vLLM, SGLang).
- Strong understanding of GPU clusters, networking, and communication libraries (NCCL, MPI) under mixed training and inference workloads.



Nice to Have

- Running RL training across 100+ GPUs, including asynchronous or disaggregated trainer/rollout architectures.
- Containerization and orchestration (Kubernetes, Ray) for large environment fleets and sandboxed workloads.
- Research contributions in RL for LLMs, or open-source contributions to RL training frameworks.



About Luma: Luma's mission is to build unified general intelligence that can generate, understand, and operate in the physical world. We believe multimodality is critical for intelligence — the next step beyond language models comes from vision. Luma is an equal opportunity employer.

---
