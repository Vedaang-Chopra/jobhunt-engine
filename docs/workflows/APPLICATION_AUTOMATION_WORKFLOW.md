# Application Automation Workflow

**Status:** Stage 1-4 built and tested on synthetic form; live validation pending.
**Created:** 2026-08-22
**Origin:** Built from the user's Simplify Copilot extension data + config.

## Overview

When the user says "apply" for a job, the pipeline runs:

```
job id -> fit check -> tailored resume -> form fill plan -> [APPROVAL GATE] -> submit
```

## Components

| Component | Path | Role |
|-----------|------|------|
| Answer bank | `profile_info/preferences/application_answers.yaml` | Canonical auto-fill values; `ASK_USER` never auto-fills |
| Field matcher | `scripts/match_application_fields.py` | Label -> answer key classification (3 tiers) |
| Pipeline driver | `scripts/apply_pipeline.py` | Orchestrates stages, enforces approval gate |
| Question bank | `execution_results/simplify_questions_extract.json` | 181 real labels the user answered before |
| ATS selector reference | `job_research/platform/apply_automation/simplify_ats_reference.json` | Simplify's per-ATS selectors, submit/success paths, aliases |
| Extractor | `scripts/extract_simplify_answers.py` | Re-extract extension storage snapshot |

## Matching tiers

1. **Gate first**: work-auth, sponsorship, EEO, salary questions ALWAYS pause for
   the user, even if previously answered.
2. **Observed answer bank**: exact/fuzzy match against the 181 answered labels.
3. **Rules**: regex derived from Simplify's fieldNameAliases + observed labels.
4. **Unmatched** -> ASK_USER.

## Fill stage protocol (agent-driven)

1. Open the application URL (Playwright MCP per browser rules).
2. Extract all visible field labels + types ->
   `execution_results/apply_runs/<job_id>_fields.json`.
3. Run `python3 scripts/apply_pipeline.py <job_id> --url <url>` to print the plan.
4. Ask the user only the `[ASK]` items; save their phrased answers back into the
   answer bank when they are reusable.
5. Fill `AUTO_FILL` fields via Playwright. Upload resume PDF from the
   application dir.
6. STOP. Show the user the fully-filled form state. Submission happens only on
   explicit user confirmation (per 10_OUTREACH_AND_APPLICATIONS.md).

## Hard rules

- Never submit without explicit per-application user approval.
- Never auto-fill: passwords, government IDs, salary expectations, legal
  attestations, EEO demographics.
- Work-authorization answers depend on role start date vs OPT timing — always
  confirm phrasing with the user once per company, then cache.
- Values come only from `profile_info/` verified facts. No invention.

## Provenance

Simplify Copilot extension v3.0.11 (`pbanhockgagggenencehbnadejlgchfc`),
LevelDB storage snapshot + remoteConfig.json extracted 2026-08-22. The
extension's saved question-answer pairs seeded the observed bank; its remote
config provided per-ATS selector patterns used as prior art for field matching.
