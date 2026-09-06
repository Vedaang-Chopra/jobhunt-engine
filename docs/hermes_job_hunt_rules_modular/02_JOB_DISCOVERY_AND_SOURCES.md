# Job Discovery and Source Rules

## Goal
Find strong open roles intelligently. Do not return a random list of AI jobs.

## A general job search means multi-source search
Search the configured source registry, including as applicable:
- LinkedIn Jobs
- LinkedIn hiring posts
- official company career pages
- Indeed
- Jobride.io
- additional platforms supplied by the user
- startup/research/AI job boards
- search engines for discovery

Maintain one canonical source registry. New platforms should update that registry.

## Search workflow
1. Read canonical profile and current request.
2. Search relevant configured sources.
   **Filter-first rule:** on every source, use that site's native filter UI
   (see `08_BROWSER_AND_TOOLS.md` § Filter-first search rule). At minimum apply
   date-posted/recency and location filters; add experience-level,
   remote/on-site, company, or connection-degree filters as the source offers
   them. Navigate the UI like an agent — read page state, apply filters, verify
   they registered — rather than firing bare keyword queries.
3. Discover additional relevant companies, not only famous labs.
4. Verify strong roles on official career pages where possible.
5. Deduplicate identical roles across sources.
6. Analyze JD and classify domain.
7. Score fit, attainability, gaps, location, strategic value, connection strength, urgency.
8. Rank application priority.
9. Save/update canonical records.
10. Record source coverage and failures.

## Company universe
Do not restrict search to AI labs. Include frontier labs, big tech, AI-native startups, semiconductor/inference, AI infrastructure, enterprise AI, robotics/autonomy, security, CAD/design/manufacturing AI, multimodal/vision, developer tools, and serious AI teams inside non-AI-first companies.

Examples such as OpenAI, Anthropic, DeepMind, NVIDIA, Apple, Google, Meta, Microsoft, Amazon, Salesforce, Adobe, Siemens, Cisco are examples only, never the complete universe.

## Official career page rule
Third-party boards are discovery channels and may be stale. For important roles, verify the role on the official company career page and prefer the official application URL.

## Search coverage
Every run should record sources attempted, successfully searched, login required, failures, skipped sources/reasons, and last checked time. Never call a search comprehensive when major configured sources were not checked.
