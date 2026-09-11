# Job Hunt MCP Servers Reference

Complete reference for all MCP servers configured for job hunting with Hermes Agent.

## Quick Start

1. Run the setup script: `~/setup_job_hunt_mcp.sh`
2. Edit `~/.hermes/config.yaml` and add the `mcp_servers:` section
3. Replace all placeholder tokens with your actual API keys
4. Restart Hermes Agent

---

## MCP Server Categories

### 🎯 Job Search & Career Platforms

| Server | Package | Purpose | Key Features |
|--------|---------|---------|--------------|
| **career-compass** | `career-compass-mcp` | AI career co-pilot | Resume tailoring, job pipeline, interview prep, offer evaluation |
| **workopia** | `@shuang_workopia/workopia-mcp` | Job search + resume builder | Job search, resume builder, career advisor |
| **kynver-career** | `@kynver-app/mcp-career` | Job search tools | Basic job search functionality |

### 💼 LinkedIn Automation

| Server | Package | Purpose | Auth Required |
|--------|---------|---------|---------------|
| **linkedin** | `@pullapi/linkedin-scraper-mcp` | **RECOMMENDED** - Job search, profiles, company pages | Optional: `LINKEDIN_COOKIE` |
| **linkedin-micro-x** | `@micro-x-ai/mcp-linkedin` | Job search, job detail, posting | Unknown |
| **linkydy** | `linkydy-mcp` | Prospecting via Chrome extension | Requires Linkydy extension |

> **Recommendation**: Use `@pullapi/linkedin-scraper-mcp` as primary. Add `LINKEDIN_COOKIE` (li_at value from browser devtools) for authenticated access.

### 🔍 Job Board Scrapers

| Server | Package | Purpose |
|--------|---------|---------|
| **indeed** | `@pullapi/indeed-scraper-mcp` | Indeed job search, job details, company profiles |

### 🏢 Enterprise ATS (Optional)

| Server | Package | Purpose | Config Required |
|--------|---------|---------|-----------------|
| **workday** | `@mindstone/mcp-server-workday` | Workday HCM (Fortune 500 companies) | `WORKDAY_TENANT`, `WORKDAY_USERNAME`, `WORKDAY_PASSWORD` |

> Only enable if you frequently apply to Workday-powered career portals.

### 📋 Application Tracking & CRM

| Server | Package | Purpose | Auth Required |
|--------|---------|---------|---------------|
| **notion** | `@notionhq/notion-mcp-server` | **RECOMMENDED** - Notion databases for CRM | `NOTION_API_KEY` |
| **google-sheets** | *deprecated* | Spreadsheet tracking | Use `google-workspace` skill instead |
| **airtable** | *not available as MCP* | Airtable base tracking | Use Airtable REST API directly |

> **Recommendation**: Notion for rich CRM with relations. Use `google-workspace` Hermes skill for Sheets/Calendar/Gmail.

### 📄 Document Management

| Server | Package | Purpose | Path |
|--------|---------|---------|------|
| **filesystem** | `@modelcontextprotocol/server-filesystem` | Local resume/cover letter library | `~/job-hunt-docs` |

### 🌐 Web Research & Browser Automation

| Server | Package | Purpose | Use Cases |
|--------|---------|---------|-----------|
| **playwright** | `@playwright/mcp` | Full browser automation | Greenhouse, Lever, Workday portals; any site |
| **web-search** | `@modelcontextprotocol/server-brave-search` | Web search API | Company research, salary data, interview questions |
| **memory** | `@modelcontextprotocol/server-memory` | Knowledge graph memory | Persistent research context across sessions |
| **sequential-thinking** | `@modelcontextprotocol/server-sequential-thinking` | Structured problem solving | Complex interview prep, offer evaluation |

> **Playwright** is the most powerful - can automate ANY job application portal.

### 📅 Calendar & Scheduling

Use the `google-workspace` Hermes skill for Calendar, Gmail, Sheets, Docs instead of deprecated MCP packages.

### 💻 GitHub (Tech Roles)

Use GitHub CLI (`gh`) or REST API directly. The `@modelcontextprotocol/server-github` MCP package is deprecated.

### 🕐 Utilities

| Server | Package | Purpose |
|--------|---------|---------|
| **time** | `@guanxiong/mcp-server-time` | Timezone conversion for remote interviews |

---

## Complete Config Template

Copy this into `~/.hermes/config.yaml` under the root level:

```yaml
mcp_servers:
  # === JOB SEARCH & APPLICATION TRACKING ===
  career-compass:
    command: "npx"
    args: ["-y", "career-compass-mcp"]
    timeout: 120

  workopia:
    command: "npx"
    args: ["-y", "@shuang_workopia/workopia-mcp"]
    timeout: 120

  kynver-career:
    command: "npx"
    args: ["-y", "@kynver-app/mcp-career"]
    timeout: 120

  # === LINKEDIN AUTOMATION ===
  linkedin:
    command: "npx"
    args: ["-y", "@pullapi/linkedin-scraper-mcp"]
    timeout: 120
    # env:
    #   LINKEDIN_COOKIE: "li_at=YOUR_COOKIE_HERE"

  # === INDEED JOB SEARCH ===
  indeed:
    command: "npx"
    args: ["-y", "@pullapi/indeed-scraper-mcp"]
    timeout: 120

  # === APPLICATION TRACKING & CRM ===
  notion:
    command: "npx"
    args: ["-y", "@notionhq/notion-mcp-server"]
    timeout: 60
    env:
      NOTION_API_KEY: "ntn_YOUR_NOTION_TOKEN_HERE"

  # === DOCUMENT MANAGEMENT ===
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/vedaangchopra/job-hunt-docs"]
    timeout: 30

  # === WEB RESEARCH & SCRAPING ===
  playwright:
    command: "npx"
    args: ["-y", "@playwright/mcp"]
    timeout: 180

  web-search:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
    timeout: 30
    env:
      BRAVE_API_KEY: "YOUR_BRAVE_API_KEY_HERE"

  # Memory & reasoning (bonus)
  memory:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-memory"]
    timeout: 60

  sequential-thinking:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    timeout: 60

  # === UTILITIES ===
  time:
    command: "npx"
    args: ["-y", "@guanxiong/mcp-server-time"]
    timeout: 30
```

---

## Tool Naming Convention

MCP tools are prefixed: `mcp_{server_name}_{tool_name}`

Examples:
- `mcp_linkedin_search_jobs`
- `mcp_notion_create_page`
- `mcp_playwright_navigate`
- `mcp_web_search_search`
- `mcp_filesystem_read_file`
- `mcp_memory_read_graph`

---

## Required API Keys Setup

### 1. Notion API Key
1. Go to https://www.notion.so/my-integrations
2. Create new integration
3. Copy "Internal Integration Token" (starts with `ntn_`)
4. Share your Notion pages/databases with the integration

### 2. Google Services (via google-workspace skill)
The `google-workspace` Hermes skill handles Gmail, Calendar, Sheets, Docs natively.
Configure in `~/.hermes/config.yaml` or via `hermes setup`.

### 3. Brave Search API
1. Go to https://brave.com/search/api/
2. Sign up for free tier (2000 queries/month)
3. Copy API key

### 4. LinkedIn Cookie (Optional)
1. Log into LinkedIn in browser
2. Open DevTools → Application → Cookies → linkedin.com
3. Find `li_at` cookie value
4. Add to config: `LINKEDIN_COOKIE: "li_at=YOUR_VALUE"`

---

## Hermes Skills for Job Hunting

These skills are already available in your Hermes installation:

### Core Productivity
- `obsidian` - Job search vault
- `notion` - CRM databases
- `airtable` - Application tracking
- `xlsx` - Excel tracking
- `google-workspace` - Gmail, Sheets, Docs, Calendar (REPLACES deprecated MCP packages)
- `weekly-review-planning` - Weekly pipeline review
- `session-librarian` - Organize sessions by company

### Research
- `competitor-news-monitor` - Track target companies
- `blogwatcher` - Monitor career pages
- `grounded-citations` - Verified company research
- `arxiv` - Research papers for ML/research roles
- `maps` - Office locations, commute

### Communication
- `email-inbox-triage` - Recruiter emails
- `himalaya` - Terminal email
- `imessage` - SMS follow-ups (macOS)
- `xurl` - Twitter/X networking

### Documents
- `docx` - Tailored resumes/cover letters
- `pdf` - Application PDFs
- `ocr-and-documents` - Extract from scans
- `nano-pdf` - Natural language PDF edits
- `humanizer` - Authentic cover letters
- `claude-design` - Portfolio sites

### Automation
- `browser-automation` - Scrape job boards
- `computer-use` - Drive desktop portals
- `cronjob` - Scheduled monitoring

---

## Example Workflows

### Daily Job Search (via cronjob)
```bash
# Create a cron job that runs daily at 9 AM
cronjob create \
  --name "daily-job-search" \
  --schedule "0 9 * * *" \
  --prompt "Search LinkedIn and Indeed for 'Senior Software Engineer' roles in San Francisco. Save new postings to Notion database with company research. Draft tailored cover letters for top 3 matches."
```

### Company Research
```
"Use mcp_web_search_search to research [Company Name] - find recent news, funding, tech stack, Glassdoor reviews, and interview process. Save to Notion company page."
```

### Application Pipeline
```
"Create a new Notion database entry for my application to [Company] - [Role]. Include job description, tailored resume version, cover letter, application date, and follow-up reminders."
```

### Interview Prep
```
"Use mcp_web_search_search to find [Company] interview questions for [Role]. Create interview prep document in Obsidian with STAR format answers."
```

---

## Troubleshooting

### "MCP SDK not available"
```bash
# Use the Hermes venv Python
/Users/vedaangchopra/.hermes/venv/bin/python -m pip install mcp
```

### "Failed to connect to MCP server"
- Check command exists: `which npx`
- Check package exists: `npm view @pullapi/linkedin-scraper-mcp`
- Increase `connect_timeout` in config

### Tools not appearing
- Restart Hermes completely
- Check startup logs for connection messages
- Verify YAML indentation in config.yaml

### LinkedIn rate limiting
- Add delays between requests
- Use `LINKEDIN_COOKIE` for authenticated session
- Consider Linkydy extension for human-like browsing

---

## Security Notes

- **Never commit API keys to git**
- Store secrets in `~/.hermes/.env` or use config `env:` section
- Hermes filters env vars passed to MCP subprocesses
- Error messages auto-redact credential patterns

---

## Maintenance

```bash
# Update all MCP packages
npm update -g

# Check Hermes MCP status
hermes chat -q "List all available MCP tools"

# Re-discover tools after config change
# (Requires full Hermes restart)
```