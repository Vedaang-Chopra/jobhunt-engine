# Spec 004 — Resume Customization Agent

**Status:** Draft for user review
**Owner:** resume_custom subsystem
**Depends on:** `resume_custom/rules/*` (all authority files), `base_variants/`, `profile_info/`

## 1. Problem

Resume customization is currently executed by ad-hoc session prompting against
`rules/SMALL_LLM_CHECKLIST.md`. There is no explicit agent design, no structured
hand-off between reasoning stages, and no enforced artifact contract (see empty
`plan.json` in `tessera_labs_ai_engineer_20260824`). This spec defines a staged
agent where each stage has one job, a typed input/output, and a deterministic
verifier — so an LLM never does a job a script can do.

## 2. Non-negotiable invariants (inherited, restated)

- I1 Formatting is NEVER generated: agent copies a locked `base_variants/base_*.tex`
  skeleton; `resume_style.sty` md5 `175a177e` is frozen; layout fixes are content-only.
- I2 Facts come ONLY from `EVIDENCE_LIBRARY.md` blocks (+ fact bank / accomplishments).
  One bullet draws from exactly ONE evidence block. No cross-block synthesis inside a bullet.
- I3 Banned/X-tier terms never appear (grep gate, binary).
- I4 Numbers/dates/status verbs are immutable strings copied verbatim from evidence.
- I5 Every JD keyword gets a disposition row; zero silent omissions.
- I6 Human hard stops: post-training stretch family, page exception, unresolvable P0,
  any request to use a banned term → ask the user.

## 3. Architecture — five stages, three of them scripted

```
                       JD text (+ optional URL)
                                │
┌───────────────────────────────────────────────────────────┐
│ S0 EXTRACT (script)      fetch/clean JD → jd.json         │
│ S1 PLAN (LLM #1)         classify + map + select → plan.json
│ S2 VERIFY-PLAN (script)  schema + invariant checks        │
│ S3 DRAFT (LLM #2)        fill skeleton → resume.tex       │
│ S4 QA LOOP (scripts)     factuality grep · compile ×2 ·   │
│                          orphan detector → fix or fail    │
│ S5 EVALUATE (LLM #3)     evaluation.md tables             │
└───────────────────────────────────────────────────────────┘
```

Key principle: **S1 and S3 are separate LLM calls with separate prompts.** The
planner reasons about WHAT to include; the drafter only rewrites prose around
already-selected facts. A small model can draft reliably if it never has to select;
a planner can be judged purely on its JSON.

### S0 — Extract (deterministic)
Input: JD URL or pasted text.
Output: `jd.json` `{ company, role, url, responsibilities[], qualifications[],
raw_text_sha256 }`.
No LLM. If extraction fails → stop, ask user to paste full text (never plan from partial).

### S1 — Plan (LLM call #1) → `plan.json`
The ONLY stage that makes selection decisions. Prompt contains:
- JD responsibilities + qualifications (from jd.json, not raw dump)
- Family classification table (checklist Step 1) + ROLE_FAMILIES section-order map
- Evidence library INDEX ONLY: block name + 1-line summary + family tags per block
  (~20 lines), not full bullets — keeps context small and forces lookup discipline
- KEYWORD_BANK tiers for the candidate families
Required output schema:

```json
{
  "family": "research_engineer_agentic",
  "seniority": "mid|senior|staff",
  "p0": [{"requirement": "...", "jd_quote": "..."}],
  "p1": [...], "p2": [...],
  "keyword_dispositions": [
    {"keyword": "LangGraph", "tier": "U", "disposition": "integrated",
     "evidence_block": "CAD Code Generation Pipeline"}
  ],
  "featured_blocks": [
    {"block": "Fortinet — Agentic RAG Diagnostics", "target_section": "industry",
     "why": "covers P0#1,#3", "bullet_count": 3},
    {"block": "CAD Code Generation Pipeline", "target_section": "research",
     "why": "covers P0#2", "bullet_count": 2}
  ],
  "omitted_blocks": [{"block": "CERBERUS", "reason": "no P0 coverage"}],
  "section_order": ["header","research","industry","education","skills"],
  "page_target": 1,
  "skills_rows": [
    {"category": "Agentic AI", "source_keywords": ["..."], "trace": "integrated+listed"}
  ],
  "header_tagline": {"angle": "production agentic systems", "themes": ["eval","orchestration"]}
}
```

Selection policy encoded in prompt:
- Featured projects: rank blocks by weighted P0-keyword coverage; take top-k such
  that total bullets fit page_target (default k≤4 blocks, ≤3 bullets each);
  every included block must cover ≥1 P0; omissions recorded with reason (I5 spirit).
- Skills: rows built ONLY from Integrated/Listed dispositions + verified systems tools;
  max 5 rows; coursework line copied verbatim from Rules §7.1.

### S2 — Verify plan (deterministic script)
Checks: JSON schema valid; every disposition resolves to an existing block/bank tier;
no X-tier keyword dispositioned anywhere; every featured block covers ≥1 P0;
section_order matches family default; page_target within family policy.
On failure: ONE bounded retry with the validator's error list appended. Second failure →
stop and surface to user. Output on success: validated plan + the FULL TEXT of the
selected evidence blocks extracted from EVIDENCE_LIBRARY.md into `selected_evidence.md`.

### S3 — Draft (LLM call #2) → `resume.tex`
Prompt contains ONLY: base skeleton .tex (chosen by section_order), selected_evidence.md,
plan.json keyword_dispositions, bullet-writing rules (BULLET_PATTERNS.md condensed),
and these freedom tiers — stated explicitly in the prompt:

| Element | Freedom |
|---|---|
| Header contact/education lines | ZERO — copy skeleton verbatim |
| Header tagline | Rewriting allowed; themes fixed by plan; facts only from featured blocks |
| Section titles/order | Fixed by plan |
| Employer/date/GPA lines | ZERO — copy verbatim |
| Project/role bullets | Emphasis-swap toward Integrated keywords; numbers/dates/status verbs verbatim (I4); single-block provenance (I2); verb form per project status |
| Skills rows | Category labels free; contents = plan's skills_rows only |

Drafting loop: produce full .tex in one shot (small models degrade on incremental edits).

### S4 — QA gate (deterministic scripts, in order)
1. Factuality grep (banned patterns) → any hit: auto-remove phrase if mechanical,
   else bounce to S3 with the hit list (max 2 bounces).
2. Number audit: every numeral in .tex must appear in selected_evidence.md.
3. Compile pdflatex ×2; require 0 Overfull/Underfull.
4. Phase K orphan detector (`awk 'NF<=2'`); fixes = re-word content only.
5. Page count vs plan.page_target.
All five must pass before S5. Failures after 2 repair rounds → human.

### S5 — Evaluate (LLM call #3) → `evaluation.md`
Fills the four mandatory rubric tables from plan.json + qa logs (mostly transcription,
not judgment): role diagnosis w/ counts, requirement map w/ match strength, fact-trace
(bullet ↔ block ID), keyword disposition table. Plus numeric dashboard + ≥1 honest criticism.
Then scripted: KEYWORD_BANK maintenance update (new F-tier terms), git commit per application.

## 4. Deliverables when implemented

```
resume_custom/agent/
├── prompts/
│   ├── plan_system.md        # S1 prompt template (versioned, reviewed here)
│   ├── draft_system.md       # S3 prompt template
│   └── evaluate_system.md    # S5 prompt template
├── run.py                    # orchestrator: S0→S5, enforces retries/hard-stops
├── verify_plan.py            # S2
├── qa_gates.py               # S4 (grep, numbers, compile, orphans, pages)
└── schemas/plan.schema.json
```
Output dir unchanged: `applications/{company}_{role}_{YYYYMMDD}/` +
`plan.json` + `jd.json` retained for auditability.

## 5. Model guidance
Planner (S1) benefits most from strong reasoning — use primary chain
(openrouter→nvidia fallback). Drafter (S3) is mechanical enough for smaller models but
needs ≥4000 max_tokens (stealth/ox-alpha returns empty below ~4000). All calls via
proper SDK clients; never raw HTTP.

## 6. Page-fit policy (explicit repair ladder)

Page target default = 1 (2 only for research-heavy families per ROLE_FAMILIES).
When S4 compile shows overflow (pages > target), apply repairs IN THIS ORDER,
one rung at a time, recompiling between each:
1. Trim/shorten P2-driven bullets first (P0/P1 bullets untouched).
2. Compress any bullet >3 rendered lines to ≤2 by emphasis-swap (facts immutable).
3. Merge Fortinet composite block variants (drop least-P0-relevant sub-bullet).
4. Compress Skills rows (merge categories, drop L-tier rows first — U/F stay).
5. Drop the lowest-ranked featured block (update plan.json omitted_blocks w/ reason).
NEVER: edit resume_style.sty, shrink font below 10pt, use \\ or \\mbox hacks,
drop Education, alter numbers/dates.
If still overflowing after rung 5 → hard stop, ask user (page exception decision).

## 7. Final LaTeX polish stage (S4.5, scripted + bounded LLM)

After content QA passes, one formatting-only pass over resume.tex using the base
skeleton as spacing reference: \\vspace values, itemize topsep/itemsep, section
breaks. Content strings must be byte-identical before/after (diff-checked);
only whitespace/layout macros may change. Re-run compile + orphan detector after.

## 8. ATS round-trip check (S4 addition)

After final PDF: `pdftotext -layout resume.pdf -` must yield —
- name + email present and adjacent
- no merged/garbled column tokens (spot-check employer lines)
- every U-tier keyword present in extracted text
Failure = LaTeX ligature/formatting issue → fix in .tex, recompile.

## 9. Within-section ordering rule

Bullets inside a section ordered by: (a) weighted P0 coverage desc, ties broken by
(b) recency (end date desc). Sections ordered by family map. Featured blocks
ordered by total P0 coverage desc.

## 10. Regeneration path

S5 evaluation scoring below rubric threshold, or any criticism naming a
fixable-at-draft flaw → orchestrator offers ONE regeneration: S3 re-draft with
S5's criticism appended as constraints. Max 1 regen per application; second
failure → human review of evaluation.md.

## 11. Human checkpoints

- CP1 (after S2): user approves plan.json — featured projects, angle, dispositions.
  Cheap gate: changing course here costs seconds.
- CP2 (after S4.5): user sees rendered PNG + evaluation summary before anything
  is marked ready-to-submit. Nothing is submitted without CP2 approval.

## 12. Cross-application variation

Orchestrator reads prior plans in applications/*/plan.json (last 30 days):
if ≥2 recent plans share the same family AND ≥2 identical featured blocks,
planner prompt receives that list and MUST rotate at least one featured block
(next-ranked by coverage) unless the dropped block was sole cover of a P0.
Prevents identical resumes landing at multiple companies.

## 13. Tagline quality bar

Header tagline: 1–3 themes separated by en-dashes; each theme maps to ≥1 featured
block; contains ≥1 U-tier keyword; ≤2 rendered lines; no banned terms; states
positioning (e.g. "production", "research") consistent with family balance.
Drafter produces 3 candidates in S3 output comment; S2-style check picks the
first passing all constraints (no extra LLM call).

## 14. Cover-letter stage (CL1–CL4)

Cover letters are generated by the same pipeline, reusing S1's plan.json —
no separate planning call. Authority: `rules/COVER_LETTER_RULES.md` (four
`\letterPara{}` paragraphs, ≤250 words, banned-term blocklist, fact-grounding
via `claims_from_bank`). Locked `resume_style.sty` reused; never edited.

```
CL1 PLAN-REUSE (script)   project plan.json → letter brief:
                          top-3 P0 requirements, featured-block one-liners,
                          company/role from jd.json
CL2 DRAFT (LLM call #4)   four paragraphs per COVER_LETTER_RULES contract;
                          hook from JD title/team; evidence paragraph maps
                          top-3 P0s to selected evidence facts verbatim-metric;
                          why-this-company from research file if present else
                          JD-derived ONLY (never invent findings)
CL3 QA (scripts)          word count ≤250 (hard fail) · banned-term grep ·
                          metric phrases string-match selected_evidence.md /
                          fact bank · compile ×2, 0 warnings
CL4 OUTPUT                cover_letter.tex/.pdf alongside resume in the
                          application dir; CP2 shows both together
```

Freedom tiers for CL2: hook + close = free prose within facts; evidence
paragraph = metrics must string-match evidence/fact bank; why-this-company =
research-file or JD text only. Same hard stops as resume (post-training
stretch → ask user). One regeneration allowed on CL3/CP2 failure, mirroring §10.

## 15. Out of scope (later)
Multi-JD batching, UI integration (spec 002/003).
