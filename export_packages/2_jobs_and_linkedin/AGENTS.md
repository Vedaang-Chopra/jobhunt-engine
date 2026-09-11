# LinkedIn Subsystem — Agent Rules

**Parent:** Root `AGENTS.md` → This file contains only local additions.

## Scope

This subsystem owns LinkedIn profile optimization, connection research, networking strategy, and referral outreach. It consumes facts from `profile_info/` and job data from `tracking/jobs/jobs.csv` and `tracking/companies/companies.csv`.

## Canonical Assets

- **Profile strategy:** `linkedin/LINKEDIN_STRATEGY.md` (headline, about, experience, skills, projects, education)
- **Referral workflow:** `docs/workflows/REFERRAL_RESEARCH_WORKFLOW.md`
- **Referral rules:** `docs/rules/LINKEDIN_REFERRAL_RULES.md`
- **Contact database:** `tracking/contacts/contacts.csv`
- **Outreach tracking:** `tracking/messages/outreach.csv`
- **Modular Rule Source:** `docs/hermes_job_hunt_rules_modular/` (01_PROFILE_AND_PREFERENCES.md, 05_LINKEDIN_REFERRALS.md, 06_LINKEDIN_HIRING_POSTS.md, 08_BROWSER_AND_TOOLS.md)

## Operational Rules

1. **Profile content derives from `profile_info/`** — headline options, about section, experience entries, skills list, and projects all reference canonical facts.
2. **Unverified skills are excluded** — `profile_info/skills/skills.md` and `profile_info/resume_fact_bank.yaml` banned lists define what NOT to claim on LinkedIn.
3. **Company research feeds networking** — for each target company in `tracking/companies/companies.csv`, research contacts and save to `tracking/contacts/contacts.csv`.
4. **Outreach uses `messaging/templates/`** — connection requests, referral requests, cold emails, and follow-ups use shared templates, not LinkedIn-specific copies.
5. **Connection status tracked in `tracking/contacts/contacts.csv`** — `outreach_status` field tracks: `not_contacted`, `connection_sent`, `connected`, `message_sent`, `responded`, `referred`, `declined`, `no_response`.
6. **Search hierarchy** — 1st degree → 2nd with mutuals → GT alumni → former coworkers → team members → hiring managers → recruiters → domain peers.
7. **Geography** — For US roles, prefer US-based people; don't discard strong India/Canada/Europe connections if meaningful shared context exists.
8. **Profile inspection required** — For each serious candidate: open profile, understand role/team, identify shared context, determine relevance, determine appropriate ask, record rationale.
9. **Browser discipline** — Reuse tabs, keep small working set, clean up after company workflow.

## Workflows

### Referral Research Workflow (`docs/workflows/REFERRAL_RESEARCH_WORKFLOW.md`)
1. Start from target role/team
2. Search strongest existing relationships first (1st connections)
3. Expand to alumni/mutuals (GT alumni = high priority)
4. Expand to relevant team members
5. Expand to hiring managers/recruiters
6. Inspect serious candidates individually
7. Rank by composite priority (P0-P3)
8. Recommend appropriate ask
9. Prepare outreach using shared templates
10. Record status and follow-up history

### Profile Optimization
- Update headline based on active target role family
- About section mirrors `profile_info/profile.md` executive summary
- Experience section mirrors `profile_info/experience/`
- Skills section uses verified skills from `profile_info/skills/skills.md`
- Pin projects from `LINKEDIN_STRATEGY.md` (Malware_Analysis, Which-VLM-Router, Edge-Glass, RL_Soccer_project)

## Data Outputs

| Output | Location | Format |
|--------|----------|--------|
| Contact database | `tracking/contacts/contacts.csv` | CSV |
| Outreach history | `tracking/messages/outreach.csv` | CSV |
| Per-company connections | `job_research/companies/<slug>/connections.csv` | CSV |
| Per-company connections narrative | `job_research/companies/<slug>/connections.md` | Markdown |
| Per-company outreach log | `job_research/companies/<slug>/outreach-log.md` | Markdown |
| Profile strategy | `linkedin/LINKEDIN_STRATEGY.md` | Markdown |

## Integration Points

- **Job Research** — Triggers referral research when Tier A/B job found
- **Tracking** — Reads `tracking/jobs/jobs.csv` for target roles, writes contacts/outreach
- **Messaging** — Uses templates from `messaging/templates/`
- **Profile Info** — Reads canonical facts for profile content and outreach personalization

## Automation

### Scheduled (from `job_research/config/search-schedule.yaml`)
- Weekly referral refresh for companies with active applications (Mon 10 AM)

### On-Demand
- `company-deep-dive` → triggers full referral research for company
- New Tier A/B job added to pipeline → triggers referral research for that company/role