# LinkedIn Referral Rules

**Source Authority:** This document consolidates LinkedIn referral and connection research rules from HERMES_JOB_HUNT_SYSTEM_RULES.md, linkedin/LINKEDIN_STRATEGY.md, and the modular rule files in `docs/hermes_job_hunt_rules_modular/`

## 1. Objective

When given a company or role, find people who provide a credible path to:
- Referral
- Introduction
- Hiring-team contact
- Role/team insight
- Useful professional conversation

Do not dump the first employees returned by LinkedIn. Use judgment.

## 2. Search Hierarchy

Inspect in priority order:
1. **1st-degree connections** — existing relationships
2. **2nd-degree connections** — mutual connections available
3. **3rd-degree connections** — weaker but still reachable
4. **Active hiring posters** — people at the company who regularly post hiring/referral content ("we're hiring", "ask me for referrals", "connect with me"); LinkedIn activity level is a first-class ranking signal
5. **Georgia Tech alumni** — shared affiliation is a strong signal
6. **Former coworkers / former-company overlap** — Fortinet, internship connections
7. **Mutual connections** — named mutuals are the strongest connection signal
8. **People in the relevant research/engineering domain** — agentic AI, evaluation, VLM routing
9. **People on the specific team** — hiring manager, team members
10. **Hiring managers** — for the specific role
11. **Recruiters** — responsible for the relevant organization
12. **People with shared project/research/domain context** — paper co-authors, conference speakers
13. **Strong cross-country personal/professional connections** — India, Canada networks

### People-search filter rule (mandatory)
Execute the hierarchy through LinkedIn's native people-search filters, not bare keyword queries (see `docs/hermes_job_hunt_rules_modular/05_LINKEDIN_REFERRALS.md` § People-search filter rule):
- Apply the **Connection degree** filter per tier: 1st pass → 2nd pass.
- Pin results with the **Current company** filter; narrow by **Location** (US/Remote-US first).
- Navigate like an agent: read active chips + result count after every filter change, verify each tier's filters registered before collecting names, paginate beyond page 1.
- Record applied filters alongside the contact-research output.

### Active hiring posters (detail)
For every serious contact search:
- Search the target company's recent LinkedIn posts for hiring/referral language and record who authors them.
- During profile inspection, check each candidate's recent activity: posting frequency and any hiring/referral posts.
- Record activity level and observed hiring posts in the contact record; use them in "reason to contact" and shape the ask around their post (e.g., replying to their referral invitation).
- Prioritize active posters over inactive contacts when relevance is comparable — an active poster who invites outreach is often a better referral path than a closer-degree connection who never posts.

## 3. Geography for People Search

For U.S. roles, prefer U.S.-based people when all else is equal.

However, do not discard strong people in India, Toronto, Europe, or elsewhere if:
- They are existing connections
- They have a strong mutual connection
- They are alumni
- They work inside the target company
- They can credibly provide a referral or introduction
- There is another meaningful shared context

## 4. Profile Inspection Required

For each serious candidate:
- Open/inspect the profile
- Understand current role and team
- Identify shared context
- Determine relevance to the target role
- Determine whether a referral ask is appropriate
- Determine whether a lighter informational message is better
- Record why contacting the person makes sense

Search ranking alone is not sufficient evidence.

## 5. Contact Ranking Signals

Useful ranking signals (weight appropriately):
- Connection degree (1st > 2nd > 3rd)
- Shared university/alumni affiliation (Georgia Tech = highest)
- Mutual connections (named mutuals = high value)
- Former-company overlap (Fortinet = high value)
- Same technical/research area (agentic AI, evaluation, VLM routing)
- Same team/org as the open role
- Recruiter/hiring-manager relevance
- Geographic relevance (US-based for US roles)
- Existing relationship strength
- Likelihood of being able to refer
- Likely willingness to engage
- Quality of the specific reason for outreach

## 6. Required Person Record Fields

A canonical connection/contact record in `tracking/contacts/contacts.csv` must include:

| Field | Description |
|-------|-------------|
| contact_id | Stable identifier: `{company_slug}_{name_slug}_{sequence}` |
| name | Full name |
| company | Company name |
| role | Current title |
| relationship | 1st/2nd/3rd/alumni/mutual/team/hiring_manager/recruiter |
| linkedin_url | Full LinkedIn profile URL |
| email | Only if publicly listed/verified |
| job_id | Target job ID(s) this contact is relevant to |
| reason_to_contact | Specific, genuine rationale |
| shared_context | GT alumni, Fortinet, mutual connection, project overlap |
| domain_relevance | How their work relates to target role |
| referral_likelihood | high/medium/low/none |
| outreach_priority | P0 (immediate) / P1 (this week) / P2 (soon) / P3 (if needed) |
| outreach_status | not_contacted / connection_sent / connected / message_sent / responded / referred / declined / no_response |
| email_status | publicly_listed / verified / inferred / unavailable |
| email_source | Source of email if available |
| last_verified_date | ISO date of last profile verification |
| notes | Additional context |

## 7. Priority Grouping (P0-P3)

| Group | Description | Action |
|-------|-------------|--------|
| **P0** | Existing 1st connections | Message directly TODAY |
| **P1** | 2nd degree with mutual connections | Connect with mutual reference |
| **P2** | 2nd degree no mutuals | Connect with strong rationale |
| **P3** | 3rd+ degree | Cold outreach / peer referral path only if exceptional |

## 8. Browser Discipline

For LinkedIn research:
- Reuse existing tabs (one search tab, one profile tab, one company tab)
- Avoid opening one permanent tab per person
- Close tabs no longer needed
- Clean up browser state after completing a company workflow

Typical company workflow uses:
- One LinkedIn search tab
- One company careers tab
- One application/job-detail tab
- Additional temporary tabs only when required

## 9. Authentication

When LinkedIn login required:
- Ask user to authenticate directly in browser
- Reuse existing authenticated sessions
- Use browser autofill/extensions when appropriate
- Never store raw passwords or OTPs in project files

## 10. Integration with Job Discovery

Referral research triggers:
- When a job scores fit ≥ 4 (Tier A/B)
- When application enters queue
- Weekly refresh for companies with active applications
- On-demand for company deep-dives

Referral output feeds into:
- `tracking/contacts/contacts.csv` — canonical contact database
- `messaging/templates/` — personalized outreach drafts
- `tracking/messages/outreach.csv` — outreach history

## 11. Company Registry and Automated Contact Discovery

### Company registry
- The canonical company registry (`tracking/companies/companies_registry.csv`,
  seeded by `scripts/referral_lib.py` from open jobs in `jobs.csv` and
  contacts in `contacts.csv`) is the input
  to automated referral research: one row per company with slug, tier, ATS
  coverage, and open-job/contact counts.
- Run `python scripts/referral_lib.py` to (re)seed registry counts from
  `jobs.csv` / `contacts.csv`; counts go stale between reseeds, so reseed
  before relying on them.

### Ranked contact discovery (`scripts/contact_discovery.py`)
- `python3 scripts/contact_discovery.py --company <slug> [--top N] [--live-linkedin]`
  ranks people for one company; omitting `--company` iterates all active
  registry companies with a per-company cap.
- Source trust order: hiring-post posters → existing tracked contacts →
  [optional live LinkedIn] → web-search fallback.
- Each candidate gets a numeric score combining the §5 ranking signals
  (degree, GT alumni, mutuals, Fortinet overlap, domain/team relevance,
  poster activity); output is a ranked list with `reason_to_contact` citing
  verifiable evidence (post URLs, roles, shared context).
- People already touched (contacts.csv `outreach_status` in
  requested/connected/contacted/responded) or already queued in
  `connection_requests.csv` are excluded — never contact anyone twice.

## 12. Never-Contact-Twice Interlock

Before any connection request is queued or sent, both stores are checked:
1. `tracking/contacts/contacts.csv` — skip if `outreach_status` indicates the
   person was already touched (requested / connected / contacted / responded).
2. `tracking/messages/connection_requests.csv` — skip if a request row already
   exists for that person (name-key match), regardless of status.

This interlock is enforced in `contact_discovery.py` (candidate pool) and
`connection_queue.py draft` (queued keys). No exceptions without explicit user
instruction recorded in the ledger notes.