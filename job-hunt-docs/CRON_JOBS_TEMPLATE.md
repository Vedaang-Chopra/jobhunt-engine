# Cron Jobs for Automated Job Hunting

Set up these cron jobs in Hermes to automate your job search workflow.

## Quick Setup Commands

### 1. Daily Job Board Scan (9 AM)
```bash
hermes cronjob create \
  --name "daily-job-search" \
  --schedule "0 9 * * *" \
  --prompt "Search LinkedIn and Indeed for 'Senior Software Engineer' OR 'Staff Engineer' OR 'Engineering Manager' roles in San Francisco Bay Area (remote OK). Filter for postings from last 24 hours. For each new posting: 1) Check if company already in Notion Job Tracker, 2) If new, create entry with status 'Researching', 3) Research company (news, tech stack, Glassdoor, funding), 4) Save top 5 matches to Notion with research notes, 5) Draft tailored cover letter for top 3 matches using docx skill." \
  --skills "linkedin,indeed,notion,web-search,docx,humanizer,grounded-citations"
```

### 2. Weekly Pipeline Review (Monday 9 AM)
```bash
hermes cronjob create \
  --name "weekly-pipeline-review" \
  --schedule "0 9 * * 1" \
  --prompt "Weekly job hunt review: 1) Query Notion Job Tracker for all active applications (not Accepted/Rejected/Withdrawn), 2) Identify applications with no activity > 7 days - draft follow-up emails, 3) Identify upcoming interviews this week - create prep docs with company research and STAR answers, 4) Check for expiring deadlines (referrals, take-homes), 5) Update priority rankings based on new info, 6) Generate summary report with metrics: applications sent, response rate, interview conversion, time in each stage." \
  --skills "notion,email-inbox-triage,weekly-review-planning,grounded-citations,web-search"
```

### 3. Daily Follow-up Check (10 AM)
```bash
hermes cronjob create \
  --name "daily-followup-check" \
  --schedule "0 10 * * *" \
  --prompt "Check Notion Job Tracker for applications where 'Next Action Due' is today or overdue. For each: 1) If follow-up email needed, draft and send via email-inbox-triage, 2) If interview prep needed, create prep document, 3) If take-home due, check status, 4) Update Next Action Due to next logical step. Log all actions taken." \
  --skills "notion,email-inbox-triage,docx"
```

### 4. Company News Monitor (Daily 8 AM)
```bash
hermes cronjob create \
  --name "company-news-monitor" \
  --schedule "0 8 * * *" \
  --prompt "Monitor target companies for material news: 1) Get list of companies from Notion Job Tracker (unique companies from active applications + 'Researching' stage), 2) For each company, search news from last 24h (funding, layoffs, product launches, earnings, leadership changes, acquisitions), 3) If material news found, update Notion company page with summary and link, 4) If negative news (layoffs, hiring freeze), flag application priority as 'Backburner', 5) If positive news (funding, growth), consider boosting priority." \
  --skills "competitor-news-monitor,notion,grounded-citations,web-search"
```

### 5. Resume/Cover Letter Refresh (Monthly 1st, 9 AM)
```bash
hermes cronjob create \
  --name "monthly-docs-refresh" \
  --schedule "0 9 1 * *" \
  --prompt "Monthly document refresh: 1) Review master resume - update with new projects, metrics, skills from last month, 2) Update master cover letter template with recent achievements, 3) Generate 3 role-specific resume variants (Backend, Full Stack, ML/Engineering), 4) Save all versions to filesystem (job-hunt-docs/resumes/), 5) Update Notion with current resume version for each active application." \
  --skills "docx,filesystem,notion,humanizer"
```

### 6. Interview Prep Generator (On-demand via trigger)
```bash
hermes cronjob create \
  --name "interview-prep-generator" \
  --schedule "0 0 * * *" \
  --prompt "This job only runs when triggered. When run with context 'company=X role=Y': 1) Search for X interview process, common questions for Y role, 2) Research X's tech stack, architecture, culture, 3) Generate interview prep doc in Obsidian with: company overview, tech deep-dive, behavioral questions (STAR), technical questions, system design topics, questions to ask interviewer, 4) Save to job-hunt-docs/interview-prep/X-Y-$(date).md" \
  --skills "web-search,grounded-citations,obsidian,arxiv"
```

## Management Commands

```bash
# List all cron jobs
hermes cronjob list

# Run a job manually (for testing)
hermes cronjob run --job_id <id> --prompt "test context: company=Stripe role=Senior Backend Engineer"

# Pause a job
hermes cronjob pause --job_id <id>

# Resume a job
hermes cronjob resume --job_id <id>

# Update a job
hermes cronjob update --job_id <id> --schedule "0 9 * * *" --prompt "new prompt"

# Delete a job
hermes cronjob remove --job_id <id>

# View job output/logs
hermes cronjob log --job_id <id>
```

## Advanced: Chained Jobs

Job B runs after Job A completes, using Job A's output:

```bash
# Job A: Collect job postings
hermes cronjob create \
  --name "collect-jobs" \
  --schedule "0 9 * * *" \
  --prompt "Search LinkedIn/Indeed for new postings. Output JSON array of {company, role, url, description, date_posted} to workspace/collected_jobs.json" \
  --skills "linkedin,indeed"

# Job B: Process & enrich (runs after A via context_from)
hermes cronjob create \
  --name "enrich-jobs" \
  --schedule "0 9 * * *" \
  --context_from "collect-jobs" \
  --prompt "Read collected_jobs.json from previous job. For each job: research company, check Notion for duplicates, create/enrich Notion entries. Output summary." \
  --skills "notion,web-search,grounded-citations"
```

## Delivery Options

```bash
# Deliver to current chat (default)
hermes cronjob create --name "x" --schedule "..." --prompt "..." --deliver "origin"

# Also deliver to Telegram
hermes cronjob create --name "x" --schedule "..." --prompt "..." --deliver "origin,telegram:-1001234567890"

# Save locally only (no delivery)
hermes cronjob create --name "x" --schedule "..." --prompt "..." --deliver "local"
```

## Tips

1. **Test first**: Run with `hermes cronjob run --job_id <id>` before scheduling
2. **Use context_from**: Chain jobs for multi-step workflows
3. **Set continuity**: For monitoring jobs, use `continuity=true` to dedupe
4. **Limit toolsets**: Use `enabled_toolsets` to reduce token usage
5. **Workdir**: Set `workdir` to your job-hunt project for project context files