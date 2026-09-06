# Outreach Rules

**Source Authority:** This document consolidates outreach strategy from HERMES_JOB_HUNT_SYSTEM_RULES.md, messaging/outreach_policy.md, and the modular rule files in `docs/hermes_job_hunt_rules_modular/`

## 1. Approval Boundaries

### Currently Automatic (No Approval Needed)
- Identifying potential contacts at target companies
- Looking up publicly available professional information
- Drafting outreach messages (saved with `status=draft`)
- Preparing referral request drafts
- Updating contact/outreach tracking

### Currently Requires Approval
- Sending LinkedIn connection requests
- Sending LinkedIn messages/InMails
- Sending emails via Gmail
- Requesting referrals
- Any external-facing communication

### Switching to Automatic
User can promote any approval-required action to automatic by explicitly stating:
> "Allow automatic [action type]"

Example: "Allow automatic LinkedIn connection requests for Tier A jobs"

The change is recorded in `messaging/outreach_policy.md` with date and scope.

## 2. Who to Contact (Priority Order)

For each Tier A/B job, identify contacts in this order:
1. **Existing close connections** — people actually known (former colleagues, classmates)
2. **Existing LinkedIn connections** — already connected on LinkedIn
3. **Georgia Tech alumni at the company** — shared affiliation
4. **Team members** working on the relevant product/research area
5. **Hiring managers** for the specific role
6. **Recruiters** responsible for AI/ML hiring at the company
7. **Senior engineers/researchers** on the team (if no HM found)

### Contact Limits
- Maximum 3 people per company per role (do not spam an entire team)
- Maximum 1 recruiter + 1 team member + 1 connection/alumni per role
- If an existing connection exists at the company, always try them first
- Do not contact the same person about multiple different roles unless clearly relevant

## 3. Contact Research

For each target contact, record in `tracking/contacts/contacts.csv`:
- Name, company, role/title
- Relationship type (existing connection, GT alumni, team member, recruiter, HM, cold)
- LinkedIn URL
- Email (only if publicly available — do not guess or use email-finding services)
- Which job_id this contact is relevant to
- Reason to contact (specific and genuine)
- Any shared context (GT, shared company, shared research interest, mutual connection)

### Finding Contact Information

**Allowed Sources:**
- LinkedIn public profiles
- Company team/about pages
- Published papers/talks with author contact info
- Personal websites/blogs with contact info
- Conference speaker bios
- GitHub profiles with public email

**Not Allowed:**
- Email guessing (firstname@company.com patterns)
- Third-party email finder tools (Hunter.io, etc.)
- Scraping private information
- Purchasing contact lists

## 4. Message Guidelines

### General Rules
- Every message must reference a SPECIFIC role or team, never generic "opportunities"
- Every message must include a genuine reason to contact THAT person
- Messages must be concise: connection requests ≤300 chars, messages ≤150 words, emails ≤250 words
- No AI-generated filler phrases ("I hope this message finds you well", "I'm reaching out because")
- No mass-blast identical messages — each must be personalized
- Never claim a relationship that doesn't exist
- Never exaggerate skills or experience
- Include 1-2 concrete, relevant accomplishments from the candidate profile
- End with a small, clear ask (not "can you refer me?" — too presumptuous for first contact)

### Message Types & Templates

All templates in `messaging/templates/`:

| Type | Template | Use Case |
|------|----------|----------|
| Connection Request | `connection_request.md` | First contact on LinkedIn |
| Referral Request | `referral_request.md` | Asking for referral after connection |
| Cold Email | `cold_email.md` | Direct email to hiring manager/recruiter |
| Recruiter Message | `recruiter_message.md` | Responding to inbound or contacting recruiter |
| Hiring Manager | `hiring_manager_message.md` | Direct to hiring manager with application context |
| Follow-up | `followup.md` | Follow-up on unanswered outreach |

### Template Structures

**Connection Request (≤300 chars):**
```
[shared context] + [specific interest] + [brief value prop]
"Hi [Name] — fellow GT MSCS grad interested in the RE role on [team]. I work on agentic AI systems and built production agentic RAG at Fortinet. Would love to connect."
```

**Referral Request (existing connections only):**
```
[personal greeting] + [specific role] + [why you're a fit] + [clear ask]
Only send to people who genuinely know the candidate's work.
```

**Recruiter Message (≤100 words):**
```
[role reference] + [2-sentence pitch] + [ask for consideration]
```

**Hiring Manager Message:**
```
[specific role + team reference] + [relevant experience/research connection] + [1 concrete result] + [interest in the problem they're solving]
```

**Cold Email:**
```
Subject: [role + shared context]
[1 paragraph: who you are + specific fit]
[1 paragraph: what interests you about their work]
[clear ask]
Subject examples:
- "GT MSCS student — RE role on your RL post-training team"
- "Re: [their recent paper/talk/blog] — interested in [team] RE role"
```

**Follow-up:**
- Wait 5-7 business days before following up
- Maximum 1 follow-up per person (do not chase)
- Follow-up should add new information, not just repeat
- If no response after follow-up, mark as `no_response` and move on

## 5. Outreach Cadence

### Per Day
- Maximum 5 new connection requests (LinkedIn may flag more)
- Maximum 3 new direct messages
- Maximum 2 new cold emails

### Per Week
- Maximum 20 new outreach actions total
- Review all pending follow-ups
- Update outreach status for all active contacts

### Cooling Off
- If a company has not responded to 3 separate contacts, stop outreach to that company for 2 weeks
- If a person has not responded to 1 message + 1 follow-up, do not contact again

## 6. Tracking

All outreach tracked in `tracking/messages/outreach.csv`:

| Field | Description |
|-------|-------------|
| outreach_id | Stable identifier |
| contact_id | Links to contacts.csv |
| job_id | Links to jobs.csv |
| company | Company name |
| contact_name | Person's name |
| channel | linkedin_connection / linkedin_message / email |
| message_type | connection / referral / recruiter / hiring_manager / cold_email / followup |
| message_text | Full message content |
| status | draft / approved / sent / followup_due / followed_up / responded / no_response / referred / declined / connected |
| date_drafted | ISO date |
| date_approved | ISO date |
| date_sent | ISO date |
| followup_date | ISO date when follow-up due |
| response_date | ISO date |
| response_summary | Brief summary of response |
| notes | Additional context |

## 7. Anti-Spam Safeguards

Before sending any message, verify:
1. This person has not been contacted in the last 14 days
2. This company has not received more than 3 outreach messages this week
3. The message is genuinely personalized (not a template with name swapped)
4. The reason to contact is real and specific
5. The ask is reasonable for the relationship level

If any check fails, do not send. Flag for review.

## 8. Connection-Request Ledger (`tracking/messages/connection_requests.csv`)

All LinkedIn connection requests are tracked in a single auditable ledger,
managed by `scripts/connection_queue.py`. Rows are never deleted; statuses move
forward only (pending → approved → sent_* → connected/declined/failed); dates
are immutable once stamped.

### 18-column schema

| # | Column | Description |
|---|--------|-------------|
| 1 | request_id | Stable ID (`cr_<date>_<seq>`) |
| 2 | person_name | Full name |
| 3 | company | Company |
| 4 | person_type | recruiter/engineer/researcher/founder/leader/peer… |
| 5 | linkedin_url | Profile URL |
| 6 | email | Only if publicly listed (supports channel=email rows) |
| 7 | source_post_url | Hiring-post URL when basis=hiring_post |
| 8 | related_job_ids | Linked jobs.csv IDs |
| 9 | score | Contact-discovery ranking score |
| 10 | note_draft | Customized note text |
| 11 | note_basis(hiring_post\|shared_ctx\|job_specific\|generic) | Why this person |
| 12 | send_status(pending\|approved\|sent_no_note\|sent_with_note\|connected\|declined\|failed) | Ledger status |
| 13 | date_queued | ISO date |
| 14 | date_sent | ISO date |
| 15 | date_connected | ISO date |
| 16 | response | Response summary |
| 17 | followup_date | ISO follow-up due date |
| 18 | notes | Additional context |

Rows with an email value are channel=email outreach and obey the same
approval/record rules as LinkedIn sends.

### Note validator (`connection_queue.py validate_note`)
A draft is rejected unless ALL of:
- ≤300 characters;
- honest identity present: MS CS at Georgia Tech (GT token) + ~4.5 years of
  production ML experience at Fortinet;
- NO banned claims: RLHF / DPO / SFT must never appear (coursework-level
  literacy only — see profile evidence rules);
- role-interest expression present ("interested … connect");
- when `note_basis=hiring_post`: the person's specific post is referenced in
  the note AND `source_post_url` is populated.

### Send discipline
- **Approve-before-send**: only `approved` rows may be sent
  (`connection_queue.py approve REQUEST_ID`, then live send via
  `poster_connect_sweep.py`).
- **Record-sent-before-next-batch**: `draft` refuses to run while any queued
  request is still `approved` — the previous batch must be record-sent first.
- **≤25/day cap**: at most 25 sends per calendar day across the ledger.
- **Bare-connect fallback**: if no note box appears on LinkedIn, send the bare
  connection request and record `sent_no_note`.
- **Stop-on-warning**: any CAPTCHA, account-restriction/warning banner, or
  login wall aborts the ENTIRE run immediately; record state before stopping.