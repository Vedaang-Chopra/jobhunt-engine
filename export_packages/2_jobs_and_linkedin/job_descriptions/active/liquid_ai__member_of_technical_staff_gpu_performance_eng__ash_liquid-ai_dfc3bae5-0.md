# Member of Technical Staff - GPU Performance Engineer — Liquid AI

- **job_id:** liquid_ai_member_of_technical_staff_gpu_performance_eng_ash_liquid-ai_dfc3bae5-0
- **source:** ashby (official board: liquid-ai)
- **location:** San Francisco
- **url:** https://jobs.ashbyhq.com/liquid-ai/dfc3bae5-003f-4438-b51a-4cdfdb4199ba
- **date_discovered:** 2026-08-22

## Full Job Description Text

ABOUT LIQUID AI

Spun out of MIT CSAIL, we build general-purpose AI systems that run efficiently across deployment targets, from data center accelerators to on-device hardware, ensuring low latency, minimal memory usage, privacy, and reliability. We partner with enterprises across consumer electronics, automotive, life sciences, and financial services. We are scaling rapidly and need exceptional people to help us get there.




THE OPPORTUNITY

Our models and workflows require performance work that generic frameworks don’t solve. You’ll design and ship custom CUDA kernels, profile at the hardware level, and integrate research ideas into production code that delivers measurable speedups in real pipelines (training, post-training, and inference). Our team is small, fast-moving, and high-ownership. We're looking for someone who finds joy in memory hierarchies, tensor cores, and profiler output.



While San Francisco and Boston are preferred, we are open to other locations.




WHAT WE'RE LOOKING FOR

We need someone who:

 - Works profiler-first: You use tools like Nsight Systems / Nsight Compute to find bottlenecks, validate hypotheses, and iterate until improvements show up in end-to-end benchmarks.

 - Bridges theory and practice:  You can translate ideas from papers into implementations that are robust, testable, and performant.

 - Executes independently: Given an ambiguous bottleneck, you can drive from profiling to kernel/integration changes to benchmarked results to maintained ownership.

 - Cares about the details: Memory hierarchy, occupancy, launch configs, tensor core utilization, bandwidth vs compute limits.




THE WORK

 - Write high-performance GPU kernels for our novel model architectures

 - Integrate kernels into PyTorch pipelines (custom ops, extensions, dispatch, benchmarking)

 - Profile and optimize training and inference workflows to eliminate bottlenecks

 - Build correctness tests and numerics checks

 - Build/maintain performance benchmarks and guardrails to prevent regressions

 - Collaborate closely with researchers to turn promising ideas into shipped speedups




DESIRED EXPERIENCE

Must-have:

 - Authored custom CUDA kernels (not only calling cuDNN/cuBLAS)

 - Strong understanding of GPU architecture and performance: memory hierarchy, warps, shared memory/register pressure, bandwidth vs compute limits

 - Proficiency with low-level profiling (Nsight Systems/Compute) and performance methodology

 - Strong C/C++ skills

Nice-to-have:

 - CUTLASS experience and tensor core utilization strategies

 - Triton kernel experience and/or PyTorch custom op integration

 - Experience building benchmark harnesses and perf regression tests




WHAT SUCCESS LOOKS LIKE (YEAR ONE)

 - Measurable improvement on at least one critical end-to-end pipeline (throughput and/or latency), validated by repeatable benchmarks

 - At least one research-driven technique shipped as a production kernel and maintained over time

 - Performance regressions are detectable early via benchmarks/guardrails, not discovered late




WHAT WE OFFER

 - Unique challenges: Our architectural innovations and efficiency requirements offer unique optimization challenges. High ownership from day one.

 - Compensation: Competitive base salary with equity in a unicorn-stage company

 - Health: We pay 100% of medical, dental, and vision premiums for employees and dependents

 - Financial: 401(k) matching up to 4% of base pay

 - Time Off: Unlimited PTO plus company-wide Refill Days throughout the year

---
