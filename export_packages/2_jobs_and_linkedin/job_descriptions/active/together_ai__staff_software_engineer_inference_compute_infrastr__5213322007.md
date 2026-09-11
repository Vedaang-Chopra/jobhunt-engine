# Staff Software Engineer, Inference / Compute Infrastructure Engineering — together_ai

- **Source:** greenhouse
- **URL:** https://job-boards.greenhouse.io/togetherai/jobs/5213322007
- **Location:** Amsterdam
- **Posted (board):** 2026-08-19T12:12:12-04:00
- **Discovered:** 2026-08-23 (lab sweep)
- **source_id:** gh_5213322007
- **full_description_hash:** 46459c56bf177238

## Full Job Description Text

&lt;h3&gt;&lt;strong&gt;About the Role&lt;/strong&gt;&lt;/h3&gt;
&lt;p&gt;We&#39;re looking for a Software Engineer to build the systems that treat infrastructure as software. This role owns the software state machines that provision hardware, bring it into service, and manage its full lifecycle — turning racks of GPUs into &lt;strong&gt;running inference clusters&lt;/strong&gt; without a human touching a runbook. The Research and Inference team is your customer: today they file tickets and wait; the target state is that they issue a single API call to stand up, scale, or tear down a cluster, and the system takes care of the rest. The platform is manifest-driven such that teams declare the desired state of a cluster or host — shape, topology, software stack — and the system is responsible for reconciling reality to that manifest, continuously, through every stage of its lifecycle. You will design the engines that manifest the schema, the engines that execute against it, and the workflows that carry a piece of hardware or a cluster from one state to the next—taking it from bare metal to a fully functioning AI cluster for training or inference.&lt;/p&gt;
&lt;p&gt;You&#39;ll write production code which is typed, tested, versioned, and deployed through CI/CD that models infrastructure state and reconciles it, the same way a Kubernetes controller reconciles a cluster&#39;s desired state. Success looks like eliminating manual provisioning work, not documenting it better.&lt;/p&gt;
&lt;p&gt;A product mindset - you&#39;ve built internal platforms or APIs consumed by other engineering teams and care about the developer experience of what you ship.&lt;strong&gt;You build it, you own it.&lt;/strong&gt; You are not only responsible for delivering the software but also for operating and supporting it in production.&lt;/p&gt;
&lt;h3&gt;&lt;strong&gt;Responsibilities&lt;/strong&gt;&lt;/h3&gt;
&lt;ul&gt;
&lt;li&gt;&lt;strong&gt;Build the provisioning state machine: &lt;/strong&gt;design and implement the software that models the full lifecycle of a physical host from discovery, inference bring-up to GPU driver/CUDA stack, health validation, and decommission/RMA — as explicit, versioned states and transitions.&lt;/li&gt;
&lt;li&gt;&lt;strong&gt;Build the self-service API: &lt;/strong&gt;design declarative APIs and a control plane so the inference team can request, scale, and tear down inference clusters with one API call — no ticket, no human in the loop.&lt;/li&gt;
&lt;li&gt;&lt;strong&gt;Automate self-healing: &lt;/strong&gt;detect degraded or failed nodes, drain them safely, trigger repair or replacement, and reintroduce healthy capacity into the pool automatically.&lt;/li&gt;
&lt;li&gt;&lt;strong&gt;Own reliability of the pipeline: &lt;/strong&gt;idempotency, retries, rollback, and drift detection so the provisioning system is as dependable as any other production service.&lt;/li&gt;
&lt;li&gt;&lt;strong&gt;Partner with the inference/ML platform team: &lt;/strong&gt;understand the cluster shapes they need — topology, interconnect, scheduling constraints — and encode them as first-class abstractions in the platform.&lt;/li&gt;
&lt;li&gt;&lt;strong&gt;Engineer it like software: &lt;/strong&gt;strong typing, automated tests, code review, versioning, and CI/CD for infrastructure code — this is a product, not a collection of Ansible playbooks.&lt;/li&gt;
&lt;/ul&gt;
&lt;h3&gt;&lt;strong&gt;Requirements&lt;/strong&gt;&lt;/h3&gt;
&lt;p&gt;Core requirements (all levels):&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Strong software engineering background in Go, Python, Rust, or similar — you write and test real software for a living.&lt;/li&gt;
&lt;li&gt;Experience with durable workflow orchestration tools such as Temporal, Cadence, or equivalent to run long-lived, manifest-driven workflows that survive failures and resume mid-execution.&lt;/li&gt;
&lt;li&gt;Experience building software control planes or orchestration systems that model state and reconcile it over time (e.g., Kubernetes controllers/operators, custom reconciliation loops, workflow engines).&lt;/li&gt;
&lt;li&gt;Experience with event-driven systems — designing and building software around message queues, event streams, or pub/sub (e.g., Kafka, NATS, SQS) rather than polling or cron-driven scripts.&lt;/li&gt;
&lt;li&gt;A product mindset. You’ve built internal platforms or APIs consumed by other engineering teams and care about the developer experience of what you ship.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Nice to have:&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Exposure to bare-metal provisioning (PXE/iPXE, Redfish/IPMI, BMC) and/or networking fundamentals (VLANs, BGP, fabric design), or GPU/accelerator infrastructure.&lt;/li&gt;
&lt;li&gt;Experience with GPU cluster software stacks (NCCL, CUDA, InfiniBand/RoCE).&lt;/li&gt;
&lt;li&gt;Prior work at a hyperscaler, GPU cloud, or datacenter-scale infrastructure organization.&lt;/li&gt;
&lt;li&gt;Systems programming in Rust or Go.&lt;/li&gt;
&lt;/ul&gt;
&lt;h3&gt;&lt;strong&gt;About Together AI&lt;/strong&gt;&lt;/h3&gt;
&lt;p&gt;Together AI is a research-driven artificial intelligence company. We believe open and transparent AI systems will drive innovation and create the best outcomes for society, and together we are on a mission to significantly lower the cost of modern AI systems by co-designing software, hardware, algorithms, and models. We have contributed to leading open-source research, models, and datasets to advance the frontier of AI, and our team has been behind technological advancement such as FlashAttention, Hyena, FlexGen, and RedPajama. We invite you to join a passionate group of researchers and engineers in our journey in building the next generation AI infrastructure.&lt;/p&gt;
&lt;h3&gt;&lt;strong&gt;Equal Opportunity&lt;/strong&gt;&lt;/h3&gt;
&lt;p&gt;Together AI is an Equal Opportunity Employer and is proud to offer equal employment opportunity to everyone regardless of race, color, ancestry, religion, sex, national origin, sexual orientation, age, citizenship, marital status, disability, gender identity, veteran status, and more.&lt;/p&gt;
&lt;p&gt;Please see our privacy policy at&lt;a href=&quot;https://www.together.ai/privacy&quot;&gt;&amp;nbsp;https://www.together.ai/privacy&lt;/a&gt;.&amp;nbsp;&amp;nbsp;&lt;/p&gt;

---
