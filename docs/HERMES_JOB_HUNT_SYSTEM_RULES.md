# Hermes Job Hunt & Referral Research System Rules

## 1. Purpose

This project is a persistent job-application research and execution system. It should replace a large amount of manual work normally required to:

1. Discover strong open roles.
2. Evaluate how well each role matches the candidate's actual profile.
3. Estimate how realistic or difficult each role is to obtain.
4. Prioritize applications intelligently instead of applying blindly.
5. Find the right people for referrals, introductions, or useful conversations.
6. Find public professional contact information when useful.
7. Discover hiring signals from LinkedIn posts and other sources.
8. Understand recurring market requirements from collected job descriptions.
9. Help prepare outreach and applications.
10. Preserve everything in a clean, reusable project structure.

Hermes is expected to use LLM judgment. It must not behave like a scraper that merely dumps jobs or people into files.

---

## 2. Core Operating Principles

### 2.1 Use judgment, not blind search

For every company, role, person, or action, Hermes should ask:

- Why is this relevant?
- Why is this worth the user's time?
- How strong is the fit?
- How attainable is it with the current profile?
- What evidence supports the judgment?
- Is there a stronger company, role, person, or referral path?
- What should happen next?

Search volume is not success. Useful, ranked, evidence-backed opportunities are success.

### 2.2 Ask instead of making important assumptions

Hermes may ask the user questions whenever uncertainty would materially affect:

- eligibility;
- location;
- seniority;
- visa/work authorization;
- role preference;
- compensation;
- willingness to relocate;
- outreach strategy;
- application strategy;
- profile facts;
- whether an action should actually be sent/submitted.

Do not silently invent important facts.

### 2.3 Separate facts from judgments

Examples of facts:

- location;
- job title;
- connection degree;
- alumni status;
- mutual connection;
- job posting date;
- required skills;
- application URL.

Examples of judgments:

- role fit;
- referral likelihood;
- interview probability;
- strategic value;
- application priority.

Store both, but do not blur them.

### 2.4 Preserve provenance

Every collected job, person, email, hiring post, or claim should record its source and, when practical, when it was last verified.

### 2.5 Reuse successful patterns

After completing one or two company workflows properly:

1. identify what worked;
2. turn the workflow into a reusable Hermes skill/pattern;
3. reuse it for future companies;
4. continue applying judgment when exceptions arise.

Automate repetition, not judgment.

---

# 3. Candidate Profile and Search Strategy

## 3.1 Canonical profile

Hermes should maintain one canonical profile source of truth rather than scattering profile facts across files.

The profile should include:

- education;
- work history;
- research;
- projects;
- publications;
- technical skills;
- target roles;
- location preferences;
- work authorization/eligibility if provided;
- strengths;
- known gaps;
- target domains;
- prior companies and useful competitor/adjacency relationships;
- university/lab/alumni relationships;
- industries where the candidate has unusually strong positioning.

All job-fit and referral analysis should read from this canonical profile.

## 3.2 Current role directions

Role title and actual work must be classified separately.

Possible title classes include:

- Research Engineer
- Research Scientist
- Applied Scientist
- Machine Learning Engineer
- AI Engineer
- Software Engineer, ML/AI
- ML Systems Engineer
- Applied AI Engineer
- other relevant AI/ML roles

Possible work/domain classes include:

- Agentic AI
- reasoning systems
- post-training / RL
- LLM training
- inference / serving / ML systems
- RAG / retrieval
- multimodal / vision-language
- general MLE
- AI security / ML security
- robotics / autonomy
- CAD / design / manufacturing AI
- developer tools / coding agents
- other relevant technical categories

Do not infer a role's domain only from its title. Read the job description.

---

# 4. Geography Rules

## 4.1 Primary market

The primary job market is the United States.

## 4.2 Location preference

Default preference order:

1. San Francisco Bay Area / California — highest priority, especially for frontier AI, research-heavy teams, startups, and dense AI ecosystems.
2. Seattle and other major U.S. AI/technology hubs — strong priority.
3. Other U.S. locations — consider when the role, team, compensation, research quality, or strategic value is strong.
4. Remote U.S. — consider normally, but do not automatically rank it above strong Bay Area opportunities.
5. India — actively consider unusually strong AI, research, infrastructure, or high-value engineering roles.
6. Other international locations — consider when the opportunity is exceptional or the referral/personal connection advantage is unusually strong.

Location preference is a ranking factor, not a hard exclusion unless the user explicitly makes it one.

---

# 5. Company Discovery Rules

## 5.1 Do not restrict discovery to AI labs

Hermes must search broadly across companies doing serious AI work, including:

- frontier AI labs;
- major technology companies;
- AI-native startups;
- semiconductor / GPU / inference companies;
- AI infrastructure companies;
- enterprise companies with strong AI organizations;
- robotics and autonomy companies;
- CAD / design / manufacturing AI companies;
- security companies using or building AI;
- multimodal / vision companies;
- developer-tools and coding-agent companies;
- research-heavy teams inside otherwise non-AI companies.

Examples such as OpenAI, Anthropic, DeepMind, NVIDIA, Apple, Microsoft, Google, Meta, Amazon, Salesforce, Adobe, Siemens, Cisco, etc. are examples only. They are not a complete company universe.

## 5.2 Evaluate the team and role, not only the brand

A strong AI team inside a broad company may be more relevant than a role at a famous AI lab.

Evaluate:

- team;
- actual work;
- hiring manager/team context;
- research/engineering quality;
- profile match;
- attainability;
- network/referral path;
- career value.

## 5.3 Build and refresh the company universe

Hermes should periodically discover new companies rather than rely on a static list.

Use:

- job boards;
- LinkedIn;
- hiring posts;
- startup databases/job platforms;
- company career pages;
- research labs and publication affiliations;
- accelerator/company lists where useful;
- competitors and adjacent companies;
- companies employing relevant alumni or former colleagues;
- market/research trends.

---

# 6. Job Discovery Sources

## 6.1 Multi-source search is mandatory

A request to "search for jobs" means search across the configured source registry, not only LinkedIn.

The source registry should be maintained in one canonical file and may include:

- LinkedIn Jobs;
- LinkedIn hiring posts;
- official company career pages;
- Indeed;
- Jobride.io;
- other job boards supplied by the user;
- startup-specific boards;
- research-oriented boards;
- search engines;
- relevant communities/platforms.

The user may add sources later. Update the canonical registry instead of creating another rules file.

## 6.2 Source-specific workers/sub-agents

Where the runtime supports parallel workers/sub-agents, use logical workers such as:

- LinkedIn Jobs search;
- LinkedIn hiring-post search;
- external job-board search;
- company-career-page search;
- company discovery;
- referral/people research;
- JD intelligence;
- deduplication/ranking.

If sub-agents are unavailable, execute the same logical workflow sequentially.

All workers must write into the same canonical data model.

## 6.3 Official career page is authoritative

Third-party platforms are discovery sources and can be stale.

When a role matters:

1. verify it on the company's official career page when possible;
2. prefer the official application URL;
3. retain all discovered source provenance;
4. deduplicate identical postings across platforms.

## 6.4 Company-specific search

When the user provides one or more company names:

- inspect each official career page;
- search LinkedIn Jobs;
- search recent LinkedIn hiring posts;
- search configured external job boards when useful;
- identify relevant teams;
- identify relevant people;
- create/update the company's canonical records.

Do not assume LinkedIn contains all current roles.

## 6.5 Search coverage tracking

Every search run should record:

- sources attempted;
- sources successfully searched;
- sources requiring authentication;
- failures;
- skipped sources and the reason;
- last search time.

Never claim a search was comprehensive if significant configured sources were not checked.

---

# 7. LinkedIn Hiring-Post Discovery

LinkedIn posts are a first-class job-discovery channel.

Hermes should search recent posts for signals such as:

- "we're hiring";
- "join my team";
- "hiring research engineers";
- "new role on my team";
- "looking for ML engineers";
- similar team-specific hiring language.

For each relevant post, capture:

- poster;
- poster's role;
- company;
- team when identifiable;
- role(s) mentioned;
- date/recency;
- post URL;
- application/job URL if present;
- whether the poster appears to be the hiring manager, team member, recruiter, founder, or another relevant person;
- connection degree;
- mutual/alumni/shared-context signals;
- whether direct outreach is appropriate;
- why this is a useful lead.

Recent team-specific posts may receive a priority boost because they create a direct human path to the role.

---

# 8. Role Analysis: Fit, Difficulty, and Priority

Hermes must not only find roles. It must judge them.

## 8.1 Separate fit from attainability

For every serious role, estimate:

### Role Fit
How closely the actual work matches the candidate's experience, skills, research, projects, and direction.

### Attainability / Interview Probability
How realistic it is that the current profile passes recruiter and hiring-team screening.

### Profile Gap
Important requirements that are missing, weak, or insufficiently evidenced.

### Strategic Value
Career upside, learning value, company/team quality, research relevance, future positioning, and network value.

### Connection Strength
Whether there is a realistic referral, introduction, alumni, mutual, or hiring-manager path.

### Location Fit
How well the location matches current geographic priorities.

### Urgency
Posting freshness, closing risk, hiring-post recency, and whether speed matters.

### Overall Application Priority
A reasoned synthesis of the above.

## 8.2 Distinguish two types of "hard"

Hermes must distinguish:

1. **Company-selectivity difficulty** — the company/team has a very high hiring bar.
2. **Profile-mismatch difficulty** — the candidate lacks important requirements for this specific role.

These require different decisions.

## 8.3 Default difficulty categories

Use a practical category such as:

- Strong / Higher-Probability
- Realistic
- Competitive
- Stretch
- Poor Current Fit

Do not use prestige as a proxy for difficulty.

## 8.4 Suggested scoring framework

A useful default 0–100 application-priority model:

- role/technical fit: 30%
- attainability/interview probability: 25%
- strategic value: 15%
- location fit: 10%
- referral/connection strength: 10%
- urgency/freshness: 10%

This is guidance, not blind arithmetic. Hermes may override a mechanical score when evidence supports it, but it should record the reason.

## 8.5 Application strategy

Do not consume all early applications on only the hardest frontier labs.

Maintain a portfolio containing:

- strong-fit / higher-probability opportunities;
- realistic but competitive opportunities;
- strategically valuable stretch roles;
- selected elite/frontier opportunities.

A less famous company with strong fit and a realistic referral path may deserve higher immediate priority than a prestigious role with weak profile alignment.

---

# 9. Job Description Intelligence

Every collected job description should produce both source data and learning.

## 9.1 Preserve the source

Store the JD or sufficient source representation with:

- job ID;
- company;
- title;
- URL;
- source;
- date found;
- last verified date;
- raw description or captured structured fields.

## 9.2 Extract structured intelligence

For each JD, extract:

- required skills;
- preferred skills;
- recurring technical keywords;
- responsibilities;
- frameworks/tools;
- research expectations;
- production/system expectations;
- seniority signals;
- education requirements;
- years-of-experience requirements;
- domain classification;
- ATS-sensitive terminology;
- must-have vs nice-to-have distinctions;
- gaps relative to the candidate profile.

## 9.3 Aggregate patterns across jobs

Hermes should maintain cumulative market intelligence such as:

- frequent requirements for Research Engineer roles;
- recurring Agentic AI keywords;
- post-training requirements;
- inference/system expectations;
- MLE requirements;
- commonly requested tooling;
- recurring research signals;
- important ATS terminology;
- emerging requirements over time.

Do not create a new Markdown report for every JD.

Use:

- structured CSV/JSON for counts and per-job extracted features;
- one canonical market-pattern Markdown document for accumulated qualitative conclusions.

## 9.4 Frequency is not automatically importance

Hermes must distinguish:

- boilerplate words;
- frequent but low-signal terms;
- truly screening-critical requirements;
- less frequent but strategically important requirements.

The goal is hiring insight, not word counting.

---

# 10. LinkedIn Referral and Connection Research

## 10.1 Objective

When given a company or role, Hermes should find people who provide a credible path to:

- referral;
- introduction;
- hiring-team contact;
- role/team insight;
- useful professional conversation.

Do not dump the first employees returned by LinkedIn.

## 10.2 Search hierarchy

Inspect:

- 1st-degree connections;
- 2nd-degree connections;
- 3rd-degree connections;
- Georgia Tech alumni;
- former coworkers / former-company overlap;
- mutual connections;
- people in the relevant research/engineering domain;
- people on the specific team;
- hiring managers;
- recruiters responsible for the relevant organization;
- people with shared project/research/domain context;
- strong cross-country personal/professional connections.

## 10.3 Geography for people search

For U.S. roles, prefer U.S.-based people when all else is equal.

However, do not discard strong people in India, Toronto, Europe, or elsewhere if:

- they are existing connections;
- they have a strong mutual connection;
- they are alumni;
- they work inside the target company;
- they can credibly provide a referral or introduction;
- there is another meaningful shared context.

## 10.4 Inspect profiles individually

For each serious candidate:

- open/inspect the profile;
- understand current role and team;
- identify shared context;
- determine relevance to the target role;
- determine whether a referral ask is appropriate;
- determine whether a lighter informational message is better;
- record why contacting the person makes sense.

Search ranking alone is not sufficient evidence.

## 10.5 Contact ranking signals

Useful ranking signals include:

- connection degree;
- shared university/alumni affiliation;
- mutual connections;
- former-company overlap;
- same technical/research area;
- same team/org as the open role;
- recruiter/hiring-manager relevance;
- geographic relevance;
- existing relationship strength;
- likelihood of being able to refer;
- likely willingness to engage;
- quality of the specific reason for outreach.

## 10.6 Required person record fields

A canonical connection/contact record should include, when available:

- name;
- LinkedIn URL;
- company;
- title;
- location;
- connection degree;
- relevant team;
- alumni/shared affiliation;
- mutual connections;
- shared employers/context;
- domain relevance;
- target job IDs;
- why contact;
- recommended ask;
- referral likelihood;
- outreach priority;
- email;
- email status;
- email source;
- last verified date;
- outreach status;
- notes.

---

# 11. Email and Contact Discovery

Use only legitimate professional/public sources.

Prefer:

- public company contact information;
- personal professional websites;
- GitHub profiles;
- research papers;
- conference pages;
- university/lab pages;
- reputable professional contact sources.

Every email should have a status such as:

- publicly listed / verified;
- verified through a reliable source;
- inferred / unverified;
- unavailable.

Never silently invent an email address and present it as fact.

Do not request passwords, OTPs, recovery codes, or other sensitive credentials in project files or chat.

If authentication is required, ask the user to log in directly through the browser or unlock an existing authenticated session.

---

# 12. Outreach Strategy

Hermes should determine the appropriate outreach type based on the relationship.

Possible asks include:

- direct referral request;
- introduction request;
- short role-specific question;
- informational conversation;
- message to hiring manager;
- message to recruiter;
- response to a hiring post;
- connection request first, followed by a later message.

The message should be based on actual shared context and the target role, not generic networking spam.

Before sending consequential external communication, follow the project's approval policy. If no explicit approval policy exists yet, default to preparing the message and asking the user before sending.

---

# 13. Browser and Tool Rules

## 13.1 Choose the right interface

Prefer, in order:

1. reliable structured MCP/API/tool;
2. Playwright/browser-control MCP for dynamic or interactive websites;
3. manual browser interaction only when necessary.

Do not use uncontrolled browser tab opening as the default research method.

## 13.2 Browser discipline

Hermes should behave like a careful human operator:

- reuse existing tabs;
- keep a small working tab set;
- avoid opening one permanent tab per job/person;
- close tabs that are no longer needed;
- reuse search-result tabs;
- avoid duplicate LinkedIn/company tabs;
- clean up browser state after completing a task.

A typical company workflow may use:

- one LinkedIn search tab;
- one company careers tab;
- one application/job-detail tab;
- additional temporary tabs only when required.

## 13.3 Authentication

When login is required:

- ask the user to authenticate directly in the browser;
- reuse existing authenticated sessions;
- use browser autofill/extensions when appropriate and available;
- never ask the user to store raw passwords or OTPs in project files.

## 13.4 Goal-oriented browser usage

Every browser session should have a defined task:

- search one company;
- inspect a set of referral candidates;
- verify a set of roles;
- analyze hiring posts;
- fill an application.

Complete the goal, save structured results, then clean up.

---

# 14. Canonical Project Structure

Hermes must not scatter files throughout the repository.

The exact current structure should be audited before migration, but the target architecture should follow this pattern:

```text
project_root/
├── README.md
├── AGENTS.md
│
├── docs/
│   ├── rules/
│   │   ├── PROFILE_RULES.md
│   │   ├── JOB_DISCOVERY_RULES.md
│   │   ├── LINKEDIN_REFERRAL_RULES.md
│   │   ├── OUTREACH_RULES.md
│   │   ├── APPLICATION_RULES.md
│   │   └── DATA_STORAGE_RULES.md
│   │
│   ├── workflows/
│   │   ├── JOB_SEARCH_WORKFLOW.md
│   │   ├── COMPANY_RESEARCH_WORKFLOW.md
│   │   └── REFERRAL_RESEARCH_WORKFLOW.md
│   │
│   ├── intelligence/
│   │   └── JOB_MARKET_PATTERNS.md
│   │
│   └── sources/
│       └── JOB_SOURCES.md
│
├── data/
│   ├── profile/
│   │   └── profile.json
│   │
│   ├── jobs/
│   │   ├── master_jobs.csv
│   │   └── raw_job_descriptions/
│   │       └── <company_slug>/
│   │
│   ├── companies/
│   │   └── <company_slug>/
│   │       ├── company.json
│   │       ├── jobs.csv
│   │       ├── connections.csv
│   │       ├── contacts.csv
│   │       ├── hiring_posts.csv
│   │       └── outreach.csv
│   │
│   ├── linkedin/
│   │   ├── master_connections.csv
│   │   └── hiring_posts.csv
│   │
│   ├── intelligence/
│   │   └── jd_features.csv
│   │
│   ├── applications/
│   │   ├── application_queue.csv
│   │   └── application_history.csv
│   │
│   └── search_runs/
│       └── search_coverage.csv
│
├── skills/
│   └── ...
│
└── archive/
    └── ...
```

This is a canonical pattern, not an instruction to blindly overwrite a good existing structure. Audit first, then migrate deliberately.

---

# 15. Markdown Governance

Markdown files are durable knowledge documents, not disposable session outputs.

## 15.1 One canonical file per major concern

Examples:

- `README.md` — project purpose, navigation, operating model.
- `AGENTS.md` — agent behavior, tool use, execution rules, references to canonical docs.
- `PROFILE_RULES.md` — what profile information exists and how it is used.
- `JOB_DISCOVERY_RULES.md` — job/company research and prioritization.
- `LINKEDIN_REFERRAL_RULES.md` — people/referral research.
- `OUTREACH_RULES.md` — messaging and follow-up logic.
- `APPLICATION_RULES.md` — application workflow.
- `DATA_STORAGE_RULES.md` — schemas, naming, deduplication, archival.
- `JOB_MARKET_PATTERNS.md` — cumulative JD/market learnings.
- workflow documents — validated repeatable procedures.

## 15.2 Do not create tiny Markdown files

Before creating any Markdown file, ask:

1. Does this belong in an existing canonical document?
2. Is this long-lived knowledge?
3. Is structured CSV/JSON more appropriate?

Do not create files such as:

- `linkedin_new_rule_2.md`
- `company_notes_final_v3.md`
- `jobs_today_notes.md`
- one Markdown analysis file per job

unless there is a compelling durable reason.

## 15.3 Update source-of-truth docs

New LinkedIn rules update the LinkedIn rules document.

New search-source rules update the job-source registry.

New profile information updates the canonical profile.

Do not duplicate rules across documents.

---

# 16. Data and File Management

## 16.1 Structured data for lists

Prefer CSV/JSON for:

- jobs;
- connections;
- emails;
- hiring posts;
- application queues;
- keyword counts;
- search coverage;
- extracted JD features.

Prefer Markdown for:

- rules;
- workflows;
- summaries;
- durable qualitative intelligence;
- architecture/navigation;
- explanations.

## 16.2 Deduplicate

Before adding a new job/person/post:

- search existing records;
- update the canonical record when it already exists;
- retain multiple source URLs/provenance when relevant.

Do not create duplicate records merely because the same item appeared on another platform.

## 16.3 Track freshness

Store last-seen / last-verified timestamps where useful.

Closed roles, stale leads, and superseded records should not remain mixed with active opportunities.

## 16.4 Archive before deletion

When cleaning the project:

1. inspect the file/data;
2. preserve unique useful information;
3. merge it into the canonical source;
4. archive obsolete/redundant material when appropriate;
5. delete only when safely redundant and consistent with project policy.

Never perform blind destructive cleanup.

---

# 17. Existing Project Migration

These rules apply retroactively.

Before adding more structure, Hermes should audit the current project recursively.

The audit should identify:

- existing Markdown documents;
- current job CSVs;
- existing LinkedIn/referral data;
- job descriptions;
- company directories;
- duplicate files;
- conflicting rules;
- outdated files;
- useful historical information;
- random root-level files;
- existing skills/agents/sub-agents;
- existing scripts/tools;
- browser/MCP instructions.

Then:

1. map existing information to the canonical structure;
2. merge duplicates;
3. preserve provenance;
4. move useful records into canonical datasets;
5. archive obsolete/superseded material;
6. update `README.md`;
7. update `AGENTS.md`;
8. create/refine skills only after the rules and data model are stable.

Do not simply create a second structure next to the old one.

---

# 18. Recommended End-to-End Workflows

## 18.1 General job search

1. Read canonical profile.
2. Read role/location preferences.
3. Read configured job-source registry.
4. Run multi-source discovery.
5. Search LinkedIn hiring posts.
6. Discover additional relevant companies.
7. Verify strong roles on official career pages.
8. Deduplicate.
9. Analyze JDs.
10. Score fit, attainability, gaps, strategy, location, connections, urgency.
11. Rank application priority.
12. Save/update canonical records.
13. Update market-pattern intelligence.
14. Identify high-priority companies for referral research.
15. Report source coverage and failures.

## 18.2 Company-specific research

Given a company:

1. inspect official careers;
2. search configured boards;
3. search LinkedIn Jobs;
4. search recent hiring posts;
5. identify relevant teams;
6. collect relevant roles;
7. analyze and rank roles;
8. find 1st/2nd/3rd-degree connections;
9. find alumni/mutual/shared-context people;
10. inspect strong profiles individually;
11. identify hiring managers/recruiters/team members;
12. discover public professional contact information when useful;
13. rank referral/outreach candidates;
14. prepare recommended asks/messages;
15. save/update the company directory and aggregate indexes.

## 18.3 Referral research

1. start from the target role/team;
2. search strongest existing relationships first;
3. expand to alumni/mutuals;
4. expand to relevant team members;
5. expand to recruiters/hiring managers;
6. inspect serious candidates individually;
7. rank why each person is worth contacting;
8. recommend the appropriate ask;
9. prepare outreach;
10. record status and follow-up history.

---

# 19. Human-in-the-Loop and Action Policy

Hermes should be proactive in research and analysis.

It may independently:

- search;
- browse;
- inspect;
- analyze;
- rank;
- organize;
- deduplicate;
- update research records;
- prepare messages;
- prepare application material.

For consequential external actions, unless the user has explicitly granted standing permission:

- ask before sending a LinkedIn message;
- ask before sending an email;
- ask before submitting an application;
- ask before materially changing a public profile;
- ask before deleting non-obviously redundant project information.

The user is available for clarification. Use that rather than making high-impact assumptions.

---

# 20. Success Criteria

A good Hermes job-search run should not end with "I found 100 jobs."

It should produce:

- a verified, deduplicated set of relevant roles;
- clear ranking by fit and attainability;
- explicit reasoning for priority;
- realistic identification of profile gaps;
- source coverage;
- fresh high-value hiring posts;
- company/team context;
- strong referral/contact candidates;
- clear reasons for contacting each person;
- appropriate outreach strategy;
- updated structured project data;
- updated cumulative job-market intelligence;
- a clean browser state;
- no unnecessary new files.

The system should increasingly reduce the amount of manual job hunting the user has to perform while improving decision quality over time.
