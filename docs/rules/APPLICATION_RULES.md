# Application Rules

**Source Authority:** This document consolidates application workflow rules from HERMES_JOB_HUNT_SYSTEM_RULES.md, messaging/application_policy.md, and tracking/AGENTS.md

## 1. Scope

This system is responsible for:
- Identifying jobs that should receive applications
- Preparing application handoffs for the Resume Customization system
- Tracking application status
- Identifying when follow-ups are appropriate

This system is NOT responsible for:
- Writing or customizing resumes (handled by `resume_custom/`)
- Writing cover letters (handled by resume system or manually)
- Submitting applications (requires user approval)

## 2. Application Triggers

A job enters the application queue when:
- It is Tier A or Tier B (fit score ≥ 65)
- It has been verified as still open (status = "open")
- It has not already been applied to (check `tracking/applications/applications.csv`)
- It does not have a hard blocker (PhD required, no sponsorship, etc.)

Tier C jobs (50-64) enter the queue only if:
- User explicitly requests it
- OR networking has identified a strong referral path
- OR the role has unique strategic value

## 3. Application Handoff Format

For every job entering the application queue, create a handoff in `tracking/applications/applications.csv` with full context:

### Required Fields
| Field | Description |
|-------|-------------|
| application_id | Stable identifier (same as job_id) |
| job_id | Links to tracking/jobs/jobs.csv |
| company | Company name |
| role | Full role title |
| job_url | Original job posting URL |
| status | queued / resume_ready / ready_to_submit / submitted / acknowledged / screening / interviewing / offered / rejected / withdrawn / no_response / expired |
| resume_variant | Agentic / Eval_Inference / Applied_ML / Agent_Reasoning / RL_Post_Training |
| referral_contact | Contact ID from contacts.csv if referral secured |
| date_queued | ISO date |
| date_resume_ready | ISO date |
| date_submitted | ISO date |
| date_acknowledged | ISO date |
| date_last_status_change | ISO date |
| current_stage | Current pipeline stage |
| rejection_reason | If rejected, reason if provided |
| follow_up_date | Next follow-up due date |
| notes | Additional context |

### Handoff Content (for Resume Customization)
The resume system needs:
1. **Full Job Description** — Complete JD text
2. **Fit Analysis Summary** — 3-5 bullet points on why this is a good fit
3. **Critical Resume Keywords** — Keywords from JD that MUST appear in tailored resume
4. **Most Relevant Candidate Experience** — Ranked list of experiences/projects most relevant
5. **Possible Gaps** — Skills/experience JD asks for that candidate lacks or has thin evidence for
6. **Recommended Resume Variant** — Which base variant to start from
7. **Networking Status** — Any contacts identified, outreach sent, referrals obtained
8. **H-1B Sponsor Status** — Known/Unknown with notes

## 4. Application Status Tracking

All applications tracked in `tracking/applications/applications.csv`.

### Status Values & Transitions

```
queued → resume_ready → ready_to_submit → submitted → acknowledged → screening → interviewing → offered
                              ↓                    ↓              ↓            ↓           ↓
                           (rejected)          (rejected)    (rejected)   (rejected)  (rejected/withdrawn)
                              ↓
                          expired (job closed before submit)
                              ↓
                          no_response (30 days no response)
```

### Status Definitions
- `queued` — Handoff prepared, ready for resume customization
- `resume_ready` — Tailored resume completed by resume system
- `ready_to_submit` — Everything prepared, awaiting user approval to submit
- `submitted` — Application submitted
- `acknowledged` — Received confirmation email/portal acknowledgment
- `screening` — Recruiter screen scheduled or in progress
- `interviewing` — In interview process (phone, technical, onsite)
- `offered` — Received offer
- `rejected` — Received rejection
- `withdrawn` — Candidate withdrew
- `no_response` — No response after 30 days
- `expired` — Job posting removed before application submitted

## 5. Application Priority

Within the queue, prioritize applications by:
1. Fit tier (A before B before C)
2. Whether a referral is available (referred applications first)
3. Posting recency (newer postings first — they may close sooner)
4. Company tier from profile preferences (T1 > T2 > T3 > T4)
5. Strategic career value

## 6. Follow-up Policy

After application submission:
- **Day 7**: If no acknowledgment, check application portal for status
- **Day 14**: If no response and a contact exists at the company, consider a polite check-in (via outreach system)
- **Day 30**: If no response, mark as `no_response`
- **If rejected**: Record the rejection, note any feedback received, analyze for patterns

## 7. Volume Targets

Based on market analysis (2-5% cold application response rate, higher with referrals):
- **Target**: 10-15 applications per week
- **Minimum**: 5 applications per week
- **Mix**: At least 30% should have a referral or networking contact attached
- **Quality floor**: Only apply to Tier A/B jobs (Tier C selectively)

## 8. Application Tracking Metrics

Weekly metrics to track (record in execution_results/):
- Applications submitted this week
- Applications with referrals vs. cold
- Response rate (any response / total submitted)
- Interview conversion rate
- Time from submission to first response
- Rejection reasons (if provided)
- Which resume variant was used

These metrics inform ongoing strategy adjustments.

## 9. Resume Variant Selection

| Role Family | Resume Template | When to Use |
|-------------|-----------------|-------------|
| Agentic AI / Applied AI Research | `base_agentic_ai.tex` | Agentic, multi-agent, tool use, LangGraph, function calling |
| LLM Evaluation / Inference Research | `base_eval_inference.tex` | Evaluation, benchmarking, vLLM, inference optimization, serving |
| ML Engineering / Applied Scientist | `base_applied_ml.tex` | Production ML, MLOps, pipelines, training, serving, Kubernetes |
| Applied AI / Applied Scientist | `base_applied_ml.tex` | Production ML, end-to-end, business impact, product ML |
| Research Engineer (Frontier) | `base_agent_reasoning.tex` | Reasoning, planning, SWE-bench, coding agents, reflection, supervisor-worker |
| Post-Training / RL | `base_agent_reasoning.tex` | Valid target family. Deep-specialization requirements lower attainability; transferable ML/research/systems strength raises it. Resume must obey factuality rules (no unverified RLHF/DPO/SFT claims) — see ROLE_FIT_RULES.md §2 |

## 10. Job Description Lifecycle

Individual job-description files are temporary working artifacts in `tracking/job_descriptions/active/`.

Before an application is marked `submitted`:
1. Verify that the canonical job row in `tracking/jobs/jobs.csv` contains the complete description and integrity metadata (`full_description_hash`)
2. Append the record to the appropriate monthly job-description archive in `tracking/job_descriptions/archive/YYYY-MM/`
3. Remove the individual active copy

Lifecycle cleanup must support `--dry-run` and require explicit `--apply` mode.