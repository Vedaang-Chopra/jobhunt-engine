# Research Engineer, Code Agents Infra — Mistral AI

- **job_id:** mistral_ai_research_engineer_code_agents_infra_ash_mistral.ai_af7c3cf8-
- **source:** ashby (official board: mistral.ai)
- **location:** Palo Alto
- **url:** https://jobs.ashbyhq.com/mistral.ai/af7c3cf8-f4f4-4a16-80e9-fdfb0c14104d
- **date_discovered:** 2026-08-22

## Full Job Description Text

ABOUT MISTRAL

Mistral provides full-stack AI solutions: from frontier models to developer tools, applications, and compute. We partner with enterprises tackling the hardest problems—across high-stakes industries like finance, manufacturing, defense, healthcare, and the public sector—co-creating customized AI systems that they can run on their terms.

We are a dynamic, collaborative team passionate about AI and its potential to transform society. Our diverse workforce thrives in competitive environments and is committed to driving innovation. Our teams are distributed between Europe, North America, Asia and the Middle East. We are creative, low-ego and team-spirited.




THE ROLE

This role focuses on building and operating the end-to-end execution, training, and data infrastructure that powers Mistral’s agentic models and coding assistants. You will be a core contributor to our agent research stack: designing scalable systems for synthetic data generation, building ultra-fast training and RL execution environments, and maintaining high-throughput execution engines.

You will tackle the engineering challenges at every step of the agent lifecycle: from orchestrating 1M+ concurrent and short-lived sandboxes for untrusted code execution to optimizing agent training codebases, distributed trajectory collection pipelines, and dataset processing workflows across massive hybrid and multi-cloud clusters.


WHAT YOU WILL DO

 - Large-Scale Sandboxing Infrastructure: Design, deploy, and operate our high-throughput sandboxing platform, executing LLM-generated untrusted code across over 1 million isolated environments concurrently for model evaluation and interactive RL environments.

 - Agent Data Generation Pipelines: Architect and scale high-throughput pipelines for synthetic code generation, agent trajectories, rollouts, and self-play data collection to power post-training and RL loops.

 - Training Codebase & Systems Optimization: Optimize agent training codebases and distributed execution runtimes (PyTorch, Ray, SLURM/Kubernetes) to minimize multi-step rollout overhead, improve GPU utilization, and eliminate scaling bottlenecks.

 - Low-Latency Orchestration & Warm Pooling: Reduce sandbox cold-start times to sub-second levels using container warm pools, snapshot/restore technology (e.g., CRIU, microVMs), and optimized image delivery layers across hybrid clusters.

 - Multi-Cluster Queueing & Resource Allocation: Implement Kubernetes-native custom controllers, CRDs, and queuing systems to dynamically route short-lived evaluation, synthetic data, and agent execution tasks across diverse hardware fleets.

 - Isolation, Security & Security Boundary: Ensure strict multi-tenant network and process isolation for untrusted agent code using container/sandboxing runtimes (e.g., gVisor, Firecracker) and default-deny network postures.

 - Operational Excellence: Maintain high availability, telemetry, and automated self-healing across millions of transient jobs while participating in on-call rotations for critical agent training and execution pipelines.


WHAT WE'RE LOOKING FOR

 - 4+ years of experience in Systems Engineering, Distributed Systems, Cloud Infrastructure, or MLOps supporting LLM/RL workloads.

 - Data & Pipeline Engineering: Proven experience building high-throughput data processing and generation pipelines for large-scale datasets (e.g., Ray, Spark, custom distributed queues).

 - Deep experience with Kubernetes & Container Tech: Strong expertise writing custom K8s operators/controllers, managing Linux cgroups/namespaces, and optimizing Docker image layers and distribution systems.

 - High-Performance Software Engineering: Advanced proficiency in Python, Go, C++ or Rust, with a track record of profiling and optimizing high-performance ML or backend systems codebases.

 - Sandboxing & Isolation Technologies: Hands-on experience with lightweight virtualization, container runtimes, or WASM (e.g., Docker, gVisor, Firecracker).

 - Queueing & Scheduling: Deep familiarity with task queue systems, resource schedulers, and low-latency queuing architectures for high-volume, short-lived workloads.

 - Comfort with Ambiguity: Passion for working directly alongside AI researchers to rapidly turn frontier agent ideas into scalable, production-grade infrastructure.




WHAT WE OFFER

We offer a comprehensive benefits package designed to support your well-being, growth, and work-life balance. Benefits vary by country and may include healthcare coverage, parental leave, retirement plans, relocation support, wellness programs, meal and transportation allowances, and other location-specific perks.

For the most up-to-date details on benefits available in your location, please refer to our Benefits page https://app.notion.com/p/mistralai/Benefits-at-Mistral-36e6ba59a7fe836b93dd01737fcc27ef?source=copy_link.




PRIVACY POLICY

Your privacy matters to us. You can learn more about how we handle your personal data in our Applicant Privacy Policy https://legal.mistral.ai/terms/applicant-privacy-policy.

---
