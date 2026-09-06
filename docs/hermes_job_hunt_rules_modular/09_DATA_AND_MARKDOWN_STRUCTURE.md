# Data and Markdown Structure Rules

## Principle
The filesystem is persistent project memory. Do not scatter files around the repository.

Before creating anything, ask whether it belongs in an existing CSV, company directory, canonical Markdown document, or aggregate index.

## Canonical pattern
```text
project_root/
├── README.md
├── AGENTS.md
├── docs/
│   ├── rules/
│   ├── workflows/
│   ├── intelligence/
│   └── sources/
├── data/
│   ├── profile/
│   ├── jobs/
│   ├── companies/
│   ├── linkedin/
│   ├── intelligence/
│   ├── applications/
│   └── search_runs/
├── skills/
└── archive/
```

## Company data pattern
```text
data/companies/<company_slug>/
├── company.json
├── jobs.csv
├── connections.csv
├── contacts.csv
├── hiring_posts.csv
└── outreach.csv
```

## Aggregate indexes
Maintain canonical cross-company datasets such as `master_jobs.csv`, `master_connections.csv`, `hiring_posts.csv`, `application_queue.csv`, `application_history.csv`, `jd_features.csv`, and `search_coverage.csv`.

## Markdown governance
One durable Markdown file per major concern. Do not create tiny notes, timestamped `.md` files for every run, one Markdown per job, or conflicting versions. Update canonical documents.

## Structured-data rule
Use CSV/JSON for jobs, people, contacts, posts, application queues, JD features, and search coverage. Use Markdown for rules, workflows, durable summaries/intelligence, architecture, and navigation.

## Deduplication/freshness
Search existing records before adding. Update canonical records and retain multiple sources instead of duplicating. Track last-seen/last-verified timestamps and move closed/stale/superseded data out of active sets.

## Archive before delete
Preserve unique information, merge it into canonical sources, then archive obsolete material before removal. Never do blind destructive cleanup.
