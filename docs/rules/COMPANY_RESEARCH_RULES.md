# Company Research Rules

**Source Authority:** This document consolidates company research rules from HERMES_JOB_HUNT_SYSTEM_RULES.md and the modular rule files in `docs/hermes_job_hunt_rules_modular/`

## 1. Goal

Determine where meaningful AI work exists and where the candidate has the strongest strategic positioning.

## 2. Evaluate Teams, Not Only Brands

For each company consider relevant teams, actual technical/research work, current hiring, role quality, location, technical overlap, candidate advantage, referral paths, company selectivity, and strategic career value.

## 3. Useful Company Taxonomy

- Frontier AI Lab
- Big Tech AI
- AI-Native Startup
- Enterprise AI
- AI Infrastructure
- Semiconductor / Inference
- Robotics / Autonomy
- CAD / Design / Manufacturing AI
- Security AI
- Multimodal / Vision
- Developer Tools / Coding Agents
- Other Research-Heavy Technology

## 4. Strategic Advantage Questions

- Does prior work experience create an edge?
- Is this a competitor or adjacent company to a past employer?
- Are there Georgia Tech alumni or strong mutuals?
- Is there overlap with CAD/design research?
- Is there overlap with AI/security or agentic/reasoning work?
- Is there an unusually credible story for this company/team?

## 5. Company-Specific Search

When given company names, inspect every official career page, search LinkedIn Jobs, search recent LinkedIn hiring posts, inspect relevant external sources, identify relevant teams, then find referral/contact paths.

## 6. Persistence

Each company should have canonical company data plus roles, connections, contacts, hiring posts, outreach/application status, and last-researched information. Do not create free-form note files without a durable need.

## 7. Company Data Structure

Per-company data lives in `job_research/companies/<slug>/`:
- `company-intel.md` — Company intelligence narrative
- `jobs.csv` / `jobs.md` — Roles found at this company
- `connections.csv` / `connections.md` — LinkedIn connections/contacts
- `hiring_posts.csv` — LinkedIn hiring posts
- `outreach-log.md` — Outreach tracking

Aggregate indexes:
- `job_research/companies/_company-registry.md` — Registry of all researched companies
- `tracking/companies/companies.csv` — Canonical company CSV with tiering, H-1B status, sector, size