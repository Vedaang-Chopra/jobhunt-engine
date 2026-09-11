# Notion Job Application Tracker - Database Template

Create this database in Notion, then share it with your MCP integration.

## Database Properties

| Property Name | Type | Options / Description |
|---------------|------|----------------------|
| **Company** | Title | Company name |
| **Role** | Select | Software Engineer, Senior SWE, Staff Engineer, Engineering Manager, Data Scientist, ML Engineer, DevOps, SRE, Product Manager, Designer, Other |
| **Status** | Select | 🔍 Researching, 📝 Preparing, 🚀 Applied, 📞 Phone Screen, 💻 Technical Interview, 👥 Onsite/Final, 🤝 Offer, ✅ Accepted, ❌ Rejected, 💤 Ghosted, 📅 Withdrawn |
| **Priority** | Select | 🔥 High, ⭐ Medium, 💡 Low, 🧊 Backburner |
| **Job URL** | URL | Direct link to job posting |
| **Application Date** | Date | When you applied |
| **Location** | Select | San Francisco, New York, Seattle, Austin, Remote, London, Berlin, Toronto, Other |
| **Work Type** | Select | Onsite, Hybrid, Remote |
| **Salary Range** | Text | e.g., "$150k-$200k + equity" |
| **Source** | Select | LinkedIn, Indeed, Company Site, Referral, Recruiter, Job Board, Other |
| **Recruiter** | Text | Recruiter name + contact |
| **Hiring Manager** | Text | If known |
| **Referral** | Person | Internal referrer (Notion user) |
| **Next Action** | Text | What you need to do next |
| **Next Action Due** | Date | Deadline for next action |
| **Interview Dates** | Date (multiple) | Scheduled interview dates |
| **Interview Notes** | Text | Quick notes per round |
| **Tech Stack** | Multi-select | React, Python, Go, Kubernetes, AWS, etc. |
| **Company Size** | Select | Startup (<50), Growth (50-500), Mid (500-5k), Large (5k-50k), Enterprise (50k+) |
| **Industry** | Select | FinTech, HealthTech, EdTech, AI/ML, SaaS, E-commerce, Crypto, Gaming, Other |
| **Notes** | Text | General notes, research links |
| **Resume Version** | Text | Which resume version used |
| **Cover Letter** | Files & media | Attach tailored cover letter |
| **Offer Details** | Text | Base, equity, bonus, benefits (when offered) |
| **Created** | Created time | Auto |
| **Last Updated** | Last edited time | Auto |

## Views to Create

### 1. Kanban by Status (Default)
- Group by **Status**
- Show: Company, Role, Priority, Next Action Due
- Sort: Priority (High first), then Application Date

### 2. Table - Active Applications
- Filter: Status NOT in [Accepted, Rejected, Withdrawn, Ghosted]
- Sort: Next Action Due (ascending)

### 3. Calendar - Interview Schedule
- Date property: **Interview Dates**
- Show: Company, Role, Status

### 4. List - Follow-ups Needed
- Filter: Next Action Due <= Today AND Status NOT in [Accepted, Rejected, Withdrawn]
- Sort: Next Action Due

### 5. Gallery - Company Research
- Group by **Company**
- Show: Role, Status, Tech Stack, Industry, Notes
- Filter: Has Notes or Company Research

### 6. Board - By Priority
- Group by **Priority**
- Show: Company, Role, Status, Next Action

## Sample Notion MCP Commands

Once configured, you can use these via Hermes:

```
# Create new application entry
"Create a Notion page in my Job Tracker database for my application to Stripe - Senior Backend Engineer. Set status to Applied, priority High, source LinkedIn, application date today."

# Update status
"Update the Stripe application status to Phone Screen and set next action to 'Prepare for system design interview' due Friday."

# Add interview
"Add interview date 2026-01-15 10:00 for Stripe application. Add note: 'System design with hiring manager'."

# Get pipeline summary
"Query my Job Tracker for all applications with status Applied or Phone Screen. Show company, role, status, next action due."

# Company research
"Search for existing company page for 'Stripe' in my Job Tracker. If exists, show me the notes and tech stack."
```

## Notion Integration Setup

1. Go to https://www.notion.so/my-integrations
2. Click "New Integration"
3. Name: "Hermes Job Hunt"
4. Select workspace
5. Copy **Internal Integration Token** (starts with `ntn_`)
6. In your Job Tracker database → Share → Invite → select your integration
7. Add token to Hermes config: `NOTION_API_KEY: "ntn_..."`

## Database ID

After creating, get the database ID from URL:
`https://www.notion.so/your-workspace/Job-Tracker-<DATABASE_ID>?v=...`

The DATABASE_ID is the 32-char string after the last dash.