# Referral Research Workflow

**Source Authority:** This document defines the canonical referral research workflow per HERMES_JOB_HUNT_SYSTEM_RULES.md §18.3

## Overview

Given a target role/team at a company, this workflow finds and ranks people who can provide referrals, introductions, or useful conversations.

---

## Inputs

- Target company from `tracking/companies/companies.csv`
- Target role(s) from `tracking/jobs/jobs.csv` and `job_research/companies/<slug>/jobs.md`
- Canonical profile (`profile_info/`) for shared context identification

---

## Phase 1: Start from Target Role/Team

1. Identify the specific team/org for the target role
2. Note hiring manager if known (from hiring posts or job description)
3. Note recruiter if known
4. Define the technical domain (agentic AI, evaluation, VLM routing, etc.)

---

## Phase 2: Search Strongest Existing Relationships First

### 2.1 1st-Degree Connections
- Search LinkedIn People with native filters: `currentCompany=[company_id]` +
  Connection degree = 1st; verify the filter chips registered before collecting
  names
- For each 1st connection:
  - Inspect profile
  - Determine if they know candidate's work well enough for referral
  - If yes → P0 (message directly TODAY)
  - If weak connection → P1 (connect with context)

### 2.2 Existing LinkedIn Connections (Any Degree)
- Review all existing connections at company
- Prioritize those in relevant teams or with hiring influence

---

## Phase 3: Expand to Alumni/Mutuals

### 3.1 Georgia Tech Alumni
- Search: `currentCompany=[company_id]` + `schoolFilter=16818`
- For each GT alum:
  - Inspect profile (grad year, program, current role)
  - Note mutual connections
  - Assess relevance to target team
  - Assign priority (P1 if mutuals, P2 if no mutuals)

### 3.2 Former Coworkers / Fortinet Overlap
- Search for Fortinet alumni at target company
- Search for former internship colleagues
- These are high-trust connections even if 2nd/3rd degree

### 3.3 Mutual Connections (Named)
- For 2nd-degree connections, always note mutual connections by name
- Named mutuals are the strongest connection signal
- Reference mutual by name in connection request

---

## Phase 4: Expand to Relevant Team Members

### 4.1 Target Team Members
- Search for people on the specific team (from job descriptions, hiring posts)
- Filter by relevant titles: Research Engineer, ML Engineer, Applied Scientist, Engineering Manager
- Assess technical alignment (agentic AI, evaluation, VLM routing, etc.)

### 4.2 Hiring Managers
- Identify from:
  - Job descriptions ("hiring manager", "reports to")
  - Hiring posts (poster with "hiring manager", "leading the team")
  - LinkedIn search: `currentCompany=[company_id]` + title contains "Manager", "Lead", "Director" + relevant keywords
- These are high-value but approach carefully

---

## Phase 5: Expand to Recruiters/Hiring Managers

### 5.1 AI/ML Recruiters
- Search: `currentCompany=[company_id]` + title contains "Recruiter", "Talent", "Recruiting" + "AI", "ML", "Engineering"
- Prioritize by location (US-based for US roles)
- Note: recruiters can submit referrals but rarely provide technical insight

### 5.2 University Recruiters
- Search: `currentCompany=[company_id]` + title contains "University", "Campus", "Early Career"
- Relevant for new grad / MS roles

---

## Phase 6: Inspect Serious Candidates Individually

For each candidate from Phases 2-5:

### Required Inspection
- Open/inspect full LinkedIn profile
- Understand current role, team, tenure
- Identify specific shared context:
  - Same university (GT = highest)
  - Same former company (Fortinet)
  - Mutual connections (name them)
  - Same research domain (papers, projects, conferences)
  - Same technical area (agentic AI, evaluation, VLM)
  - Geographic overlap
  - Personal connection (same city, shared hobby, etc.)

### Determine Outreach Strategy
| Situation | Recommended Ask |
|-----------|-----------------|
| Strong 1st connection, knows your work | Direct referral request |
| 1st connection, knows you casually | Introduction to hiring manager/team |
| GT alum with mutuals | Connection request + referral ask after connecting |
| GT alum no mutuals | Connection request + informational chat ask |
| Team member (2nd/3rd) | Connection request + specific technical question |
| Hiring manager | Connection request + specific interest in their team's work |
| Recruiter | Direct message with role reference + 2-sentence pitch |

### Record Decision
Update `tracking/contacts/contacts.csv` with:
- `outreach_priority` (P0/P1/P2/P3)
- `referral_likelihood` (high/medium/low/none)
- `reason_to_contact` (specific, genuine)
- `recommended_ask` (referral / intro / informational / question)
- `shared_context` (GT, Fortinet, mutual: [names], domain: [area])

---

## Phase 7: Rank Referral/Outreach Candidates

Sort by composite priority:
1. **P0** — Existing 1st connections (message TODAY)
2. **P1** — 2nd degree with named mutuals + strong domain relevance
3. **P1** — GT alumni with mutuals
4. **P2** — 2nd degree no mutuals but strong domain/GT alignment
5. **P2** — GT alumni no mutuals
6. **P3** — 3rd degree + exceptional rationale only
7. **P3** — Recruiters (if no better path exists)

### Ranking Signals (Weighted)
- Connection degree (1st=10, 2nd=6, 3rd=3)
- Named mutual connections (+5 each, max 15)
- GT alumni (+8)
- Fortinet/former company overlap (+6)
- Same team as target role (+10)
- Hiring manager for target role (+15)
- Same research domain (+8)
- US-based for US role (+5)
- Existing relationship strength (+5 if known personally)
- Likelihood of being able to refer (+10 if hiring manager/team lead)

---

## Phase 8: Prepare Outreach

For each ranked candidate:
1. Select template from `messaging/templates/`
2. Personalize with:
   - Specific shared context (name mutual, GT program, Fortinet project)
   - Target role title and team
   - 1-2 concrete relevant accomplishments
   - Clear, small ask appropriate to relationship
3. Save to `tracking/messages/outreach.csv` with `status=draft`
4. Present for approval

---

## Phase 9: Record Status & Follow-up History

Track in `tracking/messages/outreach.csv`:
- `status` progression: draft → approved → sent → followup_due → followed_up → responded/referred/declined/no_response
- `response_summary` for responses
- `followup_date` for pending follow-ups

Track in `tracking/contacts/contacts.csv`:
- `outreach_status` updated to match

---

## Automation

### Scheduled
- Weekly referral refresh for companies with active applications (Mon 10 AM)

### On-Demand
- Triggered when new Tier A/B job added to pipeline
- Triggered for `company-deep-dive`

---

## Output Deliverables

1. Updated `tracking/contacts/contacts.csv` with new/updated contacts
2. Updated `job_research/companies/<slug>/connections.csv` and `.md`
3. `tracking/messages/outreach.csv` with draft/approved/sent messages
4. `job_research/companies/<slug>/outreach-log.md` with narrative log
5. Ranked list of referral targets with recommended asks