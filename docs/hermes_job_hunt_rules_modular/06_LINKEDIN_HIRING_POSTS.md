# LinkedIn Hiring Post Search Rules

## Principle
LinkedIn posts are a first-class job-discovery channel, **separate from LinkedIn Jobs**.
Search recent posts for signals such as:
- we're hiring
- join my team
- hiring research engineers
- looking for ML/AI engineers
- new roles on my team
- building the team
- hiring for AI/ML/research

**Critical distinction:** LinkedIn Jobs and LinkedIn Posts have different ranking algorithms and content formats. Never use the same query string for both surfaces.
- **Jobs**: fuzzy title+description match → use short, high-recall **title queries only** (e.g. `"AI engineer"`, `"software engineer machine learning"`); let `score_jobs_v2` filter via description signals.
- **Posts**: people write *"we're hiring! building post-training infra at X"*, never `"research engineer post-training"`. Queries must combine **hiring-intent phrases × domain keywords** (see `job_research/config/search_queries.yaml`).

Use semantic variations; do not depend on exact phrases.

## Filter-first navigation
Search posts through LinkedIn's search UI with its native filters applied, not a bare keyword query:
- **Content type filter**: Posts (not People/Jobs/Companies).
- **Date posted filter**: Past Week (extend to Past Month only when a sweep explicitly covers a longer horizon).
- **Sort**: Latest so the freshest hiring signals surface first.
- For company-specific sweeps add the company as a filter facet where offered.

Navigate like an agent: after applying each filter, read the result count and
active chips to confirm the filter registered before extracting posts; adjust
or re-apply in the UI if it did not. Record which filters were applied in the run log.

## For every relevant post capture
Poster, poster role, company, team/org if identifiable, post URL, recency, roles mentioned, application URL, whether poster is hiring manager/recruiter/founder/team member, connection degree, alumni/mutual/shared context, role fit, recommended next action.

## Priority boost
A recent hiring post from a hiring manager, team lead, relevant engineer/researcher, or team recruiter can be more valuable than a generic job-board listing because it creates a direct human path.

## Outreach
Do not automatically send. Prepare the appropriate response or connection strategy unless standing permission exists.