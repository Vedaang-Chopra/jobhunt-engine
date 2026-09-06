# Company Research Workflow

**Source Authority:** This document defines the canonical company research workflow per HERMES_JOB_HUNT_SYSTEM_RULES.md §18.2

## Overview

Given a target company, this workflow performs comprehensive research: jobs, people, intelligence, and outreach preparation.

---

## Inputs

- Company name/slug from `job_research/config/target-companies.yaml`
- Canonical profile (`profile_info/`)
- Existing company records in `tracking/companies/companies.csv` and `job_research/companies/<slug>/`

---

## Phase 1: Official Careers Inspection

1. Navigate to `career_url` from target-companies.yaml
2. Search/filter for relevant roles using `role-keywords.yaml`
3. For each relevant role:
   - Extract full job description
   - Save to `tracking/job_descriptions/active/`
   - Create/update record in `tracking/jobs/jobs.csv`
   - Classify role family
4. Capture career page structure, team pages, culture content

---

## Phase 2: Configured Job Board Search

For each configured board (Greenhouse, Lever, etc.):
1. Query board for company
2. Filter using role keywords
3. For each relevant role:
   - Verify against official career page (deduplicate)
   - Save to `tracking/job_descriptions/active/`
   - Update `tracking/jobs/jobs.csv` with additional source provenance

---

## Phase 3: LinkedIn Jobs Search

1. Search LinkedIn Jobs for company + role keywords
2. Filter by location preferences
3. For each relevant role:
   - Verify against official career page
   - Capture LinkedIn-specific data (applicant count, posting age, etc.)
   - Update canonical job record

---

## Phase 4: LinkedIn Hiring-Post Search

1. Search recent LinkedIn posts (last 14 days) from company employees
2. Search for hiring signals:
   - "we're hiring", "join my team", "hiring [role]", "new role on my team"
   - Team-specific language
3. For each relevant post:
   - Capture poster, role, team, date, URL
   - Classify poster: hiring manager, team member, recruiter, founder, other
   - Assess connection degree and mutual signals
   - Determine outreach appropriateness
   - Save to `job_research/companies/<slug>/hiring_posts.csv` and `.md`

---

## Phase 5: Team Identification

1. From job descriptions and hiring posts, identify target teams
2. Map teams to role families from config
3. Prioritize teams by:
   - Number of relevant openings
   - Alignment with candidate's strongest evidence (CAD, ATHENA, ARTEMIS, Fortinet)
   - Connection strength (existing contacts, alumni, mutuals)

---

## Phase 6: Role Collection & Analysis

1. Collect all roles for this company across all sources
2. Deduplicate by `job_id`
3. For each unique role:
   - Score fit, attainability, gaps, strategic value, location, connections, urgency
   - Assign overall priority (A/B/C)
   - Determine recommended resume variant
4. Save to `job_research/companies/<slug>/jobs.csv` and `jobs.md`
5. Update `_role-registry.md` with company's roles

---

## Phase 7: Connection Research (Referral Path)

Execute LinkedIn Referral Workflow (see `REFERRAL_RESEARCH_WORKFLOW.md`) for this company:
1. Search 1st-degree connections at company
2. Search 2nd-degree with mutual connections
3. Search GT alumni at company (schoolFilter=16818)
4. Search former coworkers / Fortinet overlap
5. Search team members on target teams
6. Search hiring managers for open roles
7. Search recruiters for AI/ML org
8. For each candidate:
   - Inspect profile individually
   - Determine relevance and outreach strategy
   - Assign priority (P0-P3)
   - Save to `tracking/contacts/contacts.csv` and `job_research/companies/<slug>/connections.csv`

---

## Phase 8: Public Contact Discovery

For high-priority contacts (P0, P1, hiring managers):
1. Check public sources for professional contact info:
   - Company team pages
   - Personal websites/blogs
   - Published papers/talks
   - GitHub profiles
   - Conference speaker bios
2. Record email with status (publicly_listed/verified/inferred/unavailable)
3. Never guess or use email-finding services

---

## Phase 9: Outreach Preparation

For each high-priority contact:
1. Select appropriate template from `messaging/templates/`
2. Personalize with specific shared context and target role
3. Save draft to `tracking/messages/outreach.csv` with `status=draft`
4. Present for approval (never auto-send)

---

## Phase 10: Company Intelligence Update

Update `job_research/companies/<slug>/company-intel.md` with:
- Fresh company overview
- Target teams and hiring status
- Key people (hiring managers, recruiters, connections)
- Email formats (verified)
- Application strategy
- Last search date

Update `tracking/companies/companies.csv` with:
- `last_checked` date
- `open_roles_count`
- `contacts_count`
- `status` (not_searched / intel_complete / jobs_found / connections_found / applied / backburner / ignored)

---

## Phase 11: Aggregate Index Updates

1. Update `_company-registry.md` with latest status
2. Update `job_research/config/target-companies.yaml` if new info (tier, teams, contacts)
3. Identify any new companies discovered during research

---

## Automation

### Scheduled
- Daily T1 scan (9 AM Mon-Fri)
- Daily T2 scan (10 AM Mon-Fri)
- Weekly referral refresh for active application companies (Mon 10 AM)

### On-Demand
- `company-deep-dive` — Full research for a specific company

---

## Output Deliverables

1. Updated `tracking/jobs/jobs.csv` with company's jobs
2. `job_research/companies/<slug>/jobs.md` and `.csv` — role analysis
3. `job_research/companies/<slug>/hiring_posts.md` and `.csv` — hiring signals
4. `job_research/companies/<slug>/connections.md` and `.csv` — people research
4. `job_research/companies/<slug>/company-intel.md` — company intelligence
5. `job_research/companies/<slug>/outreach-log.md` — outreach tracking
6. Updated `tracking/contacts/contacts.csv` — canonical contacts
7. Updated `tracking/messages/outreach.csv` — outreach drafts
8. Updated `tracking/companies/companies.csv` — company registry
9. Updated `_company-registry.md` and `_role-registry.md`