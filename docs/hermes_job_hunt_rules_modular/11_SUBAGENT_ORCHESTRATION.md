# Sub-Agent Orchestration Rules

## Goal
Use specialized workers to reduce hallucination and context overload. Do not ask every sub-agent to do everything.

## Recommended workers
### Job Discovery Worker
Reads profile + job discovery + role scoring. Finds candidate roles and source coverage.

### LinkedIn Jobs Worker
Reads profile + discovery + browser rules. Searches LinkedIn Jobs.

### Hiring Post Worker
Reads profile + hiring-post + browser rules. Finds recent direct hiring signals.

### Company Career Page Worker
Reads profile + company research + discovery + browser rules. Verifies official openings and relevant teams.

### External Job Board Worker
Reads profile + job discovery/source rules. Searches configured third-party platforms.

### Referral Research Worker
Reads profile + LinkedIn referral + browser rules. Returns ranked people with reasons/paths.

### JD Intelligence Worker
Reads profile + JD intelligence + role scoring. Extracts features, patterns, and candidate gaps.

### Ranking/Deduplication Worker
Reads role scoring + data rules. Produces one canonical ranked job set.

### Outreach Worker
Reads profile + referral data + outreach rules. Produces recommended asks and draft messages.

## Parent Hermes responsibilities
1. define bounded tasks;
2. give each worker only relevant rules;
3. collect structured outputs;
4. deduplicate and resolve conflicts;
5. make final rankings;
6. write only to canonical files;
7. report source coverage/failures.

## Structural rule
Sub-agents must not independently invent new directory structures or canonical rule files. Structural changes belong to the orchestrator unless explicitly delegated.

## Parallelization rule
Parallelize by source or responsibility, not by running several agents over the exact same source without a reason.
