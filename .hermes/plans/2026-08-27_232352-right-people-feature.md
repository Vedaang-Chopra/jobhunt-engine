# "Right People" Feature Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** One feature: give a **company name** OR a **job URL** → find, inspect, rank, and record all the right people to connect with (1st/2nd/3rd connections, GT alumni, active hiring posters, team members, hiring managers, recruiters) at that company — per the codified referral/browser/data rules.

**Architecture:** A new orchestrating CLI (`scripts/right_people.py`) that resolves the target (company slug or job record), builds a filter-first LinkedIn people-search plan (reusing `people_sweep.py` query families), executes it through the canonical browser session (`browser_session_lib.py` + `web_nav_agent`), runs mandatory per-person profile inspection + activity check, scores/ranks with the REFERRAL_RESEARCH_WORKFLOW weights, and upserts the canonical CSVs (`contacts.csv`, per-company `connections.csv`, `people_sweep.csv`, `search_runs.csv`). Pure logic (target resolution, query plan, scoring, dedup/upsert) is separated into `scripts/right_people_lib.py` so everything except the browser step is pytest-testable.

**Tech Stack:** Python 3 (repo venv), pytest, csv stdlib, existing `config_lib` (path registry), `browser_session_lib` v2 (Chrome CDP :9333), Playwright MCP for live runs, optional LLM via `tailor_from_jd.llm_config()` chain (openrouter→nvidia) for JD team/manager extraction and profile inspection notes.

---

## 0. Rules the feature must obey (verified from the repo)

Read and enforced throughout:

1. **`docs/hermes_job_hunt_rules_modular/05_LINKEDIN_REFERRALS.md`** — search hierarchy (1st → 2nd → 3rd → active hiring posters → GT alumni → former coworkers → mutuals → domain → team → hiring managers → recruiters → shared research); **people-search filter rule** (native filters: connection degree per pass, current company, location, keywords — never bare keyword search; verify chips + result count after every filter change; paginate past page 1); **active hiring posters are a first-class ranking signal**; **individual profile inspection is mandatory** for every serious candidate; required contact record fields.
2. **`docs/rules/LINKEDIN_REFERRAL_RULES.md` + memory (user directive)** — connection degree is not enough: **activity matters**; check each candidate's recent posting activity; prioritize active posters when relevance is comparable.
3. **`docs/hermes_job_hunt_rules_modular/08_BROWSER_AND_TOOLS.md`** — filter-first search rule (mandatory; record applied filters in `tracking/search_runs/search_runs.csv`); interface preference (MCP/API → Playwright → manual); **mandatory browser tests** (pytest for pure logic first, then one live smoke test per workflow change with evidence — real row counts, never claims); tab discipline; auth: ask user, never store secrets; never mark an unsearched source as searched.
4. **`docs/hermes_job_hunt_rules_modular/09_DATA_AND_MARKDOWN_STRUCTURE.md`** — CSV persistence, no new DB; company data pattern (`job_research/companies/<slug>/connections.csv`); aggregate indexes; dedup-before-add, `last_verified` timestamps; archive before delete.
5. **`docs/hermes_job_hunt_rules_modular/10_OUTREACH_AND_APPLICATIONS.md`** — right ask per situation; no generic spam; referral logic (not every employee); email labels (public/verified | verified | inferred/unverified | unavailable); **human approval boundary — never auto-send** anything.
6. **`docs/hermes_job_hunt_rules_modular/11_SUBAGENT_ORCHESTRATION.md`** — Referral Research Worker pattern; parent dedupes/ranks/writes canonical files only; workers don't invent structure.
7. **`docs/workflows/REFERRAL_RESEARCH_WORKFLOW.md`** — the 9-phase canonical workflow and the **weighted ranking model** (degree 1st=10/2nd=6/3rd=3; mutuals +5 each max 15; GT +8; Fortinet overlap +6; same team +10; hiring manager +15; same domain +8; US +5; known personally +5; can-refer +10) plus P0–P3 priority bands and per-situation recommended asks.
8. **Geography rule (`01_PROFILE_AND_PREFERENCES.md` / `discovery_lib.scrutinize`)** — US-wide + Remote-US; other regions only when relationship strength is exceptional.
9. **Profile rules** — always GT email for any outreach identity; facts from `profile_info/` (GT, Fortinet RAC/agentic RAG, SD-WAN anomaly-detection patent) are the shared-context source; never invent accomplishments.
10. **Existing interlocks** — `people_sweep.py` never-twice dedup vs `contacts.csv` + prior sweep rows (BLOCKED_STATUSES = requested/connected/contacted/responded); `connection_queue.py` forward-only ledger; filter chips verification before extraction.

---

## 1. Current context / assumptions

- Repo: `/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting` (data root = `<repo>/jobhunt-data`, via `config_lib.data_root()`).
- Existing reusable pieces (verified present):
  - `scripts/config_lib.py` — canonical paths: `contacts_csv`, `people_sweep_csv`, `hiring_posts_csv`, `search_runs_csv`, `jobs_csv`.
  - `scripts/people_sweep.py` — 4 query families (`a_hiring_posts`, `b_recruiters`, `c_company_people`, `d_gt_alumni`), normalize + dedup; **browser extraction is agent-driven** by design.
  - `scripts/connection_queue.py` — connection-request ledger (draft/approve/record-sent).
  - `scripts/referral_lib.py` — company registry, `resolve_company_slug()`, `score_candidate()`, `dedup_candidates()`.
  - `scripts/browser_session_lib.py` v2 + `scripts/web_nav_agent/` — canonical browser infra (Chrome :9333, auth-state check).
  - `tracking/jobs/jobs.csv` — 47 columns incl. `company_slug`, `job_url`, `description_file`, `role_family`, `networking_priority`.
  - `tracking/contacts/contacts.csv` — 23 columns (verified header above).
- Company dirs live at `jobhunt-data/job_research/companies/<slug>/` (some currently lack `connections.csv` — the feature creates it on first write with the schema below).
- Assume LinkedIn is authenticated in the shared Chrome profile; if `check_auth_state` fails, the run pauses and asks the user (rule 08 Authentication).
- Feature is research + ranking + draft-prep only. **Sending stays behind the human approval boundary**; the farthest the feature goes autonomously is queueing connection-request drafts via `connection_queue.py draft`.

---

## 2. Proposed approach

One entry point, five stages:

```
right_people.py --company "Scale AI"        # company mode
right_people.py --job-url <url>             # job mode (JD-aware targeting)
right_people.py --job-url <url> --live      # actually browse LinkedIn (default: plan-only dry run)
```

1. **Resolve target** — company mode → slug via `referral_lib.resolve_company_slug`; job mode → row from `jobs.csv` by URL (fuzzy fallback on canonical_application_url), pull `description_file` JD → LLM extract: team/org name, hiring manager hints, recruiter hints, role keywords, domain terms.
2. **Build search plan** — pure function emits an ordered list of filter-first search passes (degree tier × company filter × location × keywords × schoolFilter=16818), each pass recording the exact UI filters it must set and how to verify registration (chips + result count). Extends `people_sweep.FAMILIES` — do not fork the schema.
3. **Execute live** (Playwright MCP through `browser_session_lib`) — navigate → apply filters → verify chips/count → paginate → extract rows → append raw finds to `people_sweep.csv`; log every pass to `search_runs.csv` with filters applied (rule 08).
4. **Inspect + score** — for each serious candidate (deduped, not already requested/connected): profile inspection (confirm company/role/team, shared context, recent activity/hiring posts), then score with the weighted model + activity bonus; assign P0–P3 and recommended ask per the workflow table.
5. **Write canonical outputs + queue drafts** — upsert `contacts.csv` (dedup by linkedin_url/name+company, refresh `last_verified`), write per-company `connections.csv`, emit a ranked Markdown summary, and optionally stage P0/P1 into `connection_queue` as pending drafts (never sent).

## 3. New / modified files

- Create: `scripts/right_people_lib.py` (pure logic: target resolution, plan builder, scoring, dedup/upsert, JD hint extraction contract)
- Create: `scripts/right_people.py` (CLI + browser-execution orchestration, agent-driven like `people_sweep.py`)
- Create: `tests/test_right_people_lib.py`, `tests/test_right_people_cli.py`
- Modify: `scripts/people_sweep.py` — only if a shared helper (normalize/dedup) needs exporting; no behavior change
- Data (created on demand): `jobhunt-data/job_research/companies/<slug>/connections.csv`
- Docs (same-change rule): repo `README.md` map + `session_state.md` update at the end

## 4. Canonical schemas (exact)

`job_research/companies/<slug>/connections.csv` header:

```csv
contact_id,name,linkedin_url,company,title,location,degree,relevant_team,alumni_shared_affiliation,mutuals,shared_context,activity_level,hiring_post_urls,target_job_ids,reason_to_contact,recommended_ask,referral_likelihood,outreach_priority,email,email_status,source,outreach_status,last_verified
```

- `degree`: `1st|2nd|3rd|unknown`
- `activity_level`: `active_poster|active|inactive|unknown`
- `outreach_priority`: `P0|P1|P2|P3`
- `email_status`: `public/verified|verified|inferred/unverified|unavailable` (rule 10)
- `contact_id`: `<slug>_<seq>` pattern, matching existing `cohere_001` convention.

---

## 5. Step-by-step plan (TDD, bite-sized, commit per task)

### Task 1: Target resolver (company slug or job record)

**Files:** Create `scripts/right_people_lib.py`; Test `tests/test_right_people_lib.py`

**Step 1 — failing tests**

```python
def test_resolve_company(tmp_path):
    assert resolve_target("--company", "Scale AI", repo=tmp_path)["kind"] == "company"

def test_resolve_job_from_jobs_csv(tmp_path, monkeypatch):
    # seed jobs.csv with one row whose job_url matches
    t = resolve_target("--job-url", "https://jobs.eu.lever.co/scale/abc", repo=tmp_path)
    assert t["kind"] == "job" and t["company_slug"] == "scale-ai"
    assert t["job"]["role_family"]  # pulled from the row

def test_resolve_job_unknown_url_raises():
    with pytest.raises(TargetNotFound):
        resolve_target("--job-url", "https://x.example/nope", repo=tmp_path)
```

**Step 2:** `pytest tests/test_right_people_lib.py -v` → FAIL (module missing)

**Step 3 — implement** `resolve_target(flag, value, repo=None) -> dict`: company mode delegates to `referral_lib.resolve_company_slug`; job mode loads `config_lib.path("jobs_csv")`, exact match on `job_url` then `canonical_application_url`, then fuzzy title+company match; returns `{"kind", "company", "company_slug", "job": row|None, "jd_path": description_file|None}`.

**Step 4:** pytest → PASS. **Step 5:** `git commit -m "feat(right-people): target resolver for company/job-url"`

### Task 2: JD intelligence hints (job mode only)

**Files:** `scripts/right_people_lib.py`; `tests/test_right_people_lib.py`

**Step 1 — failing tests** for `extract_jd_hints(jd_text) -> {"team": str|None, "manager_hints": [..], "recruiter_hints": [..], "keywords": [..], "domain_terms": [..]}`: regex-based extraction of "reports to", "hiring manager", "team:", title keywords (ML Engineer, Applied Scientist, Recruiter…), and domain terms (agentic AI, evaluation, VLM routing…). LLM fallback (`tailor_from_jd.llm_config()` chain) is a separate wrapper `llm_jd_hints()` — tested only for contract (monkeypatched client), never called in unit tests.

**Step 2:** FAIL → **Step 3:** implement regex pass + wrapper → **Step 4:** PASS → **Step 5:** `git commit -m "feat(right-people): JD hint extraction"`

### Task 3: Filter-first search plan builder

**Files:** `scripts/right_people_lib.py`; `tests/test_right_people_lib.py`

**Step 1 — failing tests** for `build_search_plan(target, hints=None) -> list[dict]`. Each pass: `{"pass_id", "family", "tier", "url", "filters": {...}, "verify": "chips+count", "expected_columns"}`. Order mirrors rule 05 hierarchy:

| # | family | filters |
|---|--------|---------|
| 1 | `existing_1st` | currentCompany + connection degree=1st |
| 2 | `existing_2nd` | currentCompany + degree=2nd (+mutuals sort) |
| 3 | `existing_3rd` | currentCompany + degree=3rd |
| 4 | `hiring_posts` | company Posts search: "we're hiring"/"refer me", date-posted ≤ 30d, content type=posts |
| 5 | `gt_alumni` | currentCompany + schoolFilter=16818 |
| 6 | `former_coworkers` | currentCompany + keywords "Fortinet" |
| 7 | `team_members` | currentCompany + keywords from JD hints (titles) |
| 8 | `hiring_managers` | currentCompany + keywords Manager/Lead/Director + JD domain |
| 9 | `recruiters` | currentCompany + keywords Recruiter/Talent + AI/ML |
| 10 | `university_recruiters` | currentCompany + University/Campus/Early Career |

Job mode injects `hints["keywords"]` into passes 7–9; company mode uses role-agnostic defaults from `people_sweep.build_queries()`. Location filter = US/Remote-US (rule 8). Assert: every pass has non-empty `filters`; no pass is keyword-only (rule: never bare keyword search).

**Step 2:** FAIL → **Step 3:** implement → **Step 4:** PASS → **Step 5:** commit `feat(right-people): filter-first search plan`

### Task 4: Scoring + ranking (workflow weights + activity rule)

**Files:** `scripts/right_people_lib.py`; `tests/test_right_people_lib.py`

**Step 1 — failing tests** for `score_person(p) -> (score:int, priority:str, ask:str)` implementing REFERRAL_RESEARCH_WORKFLOW weights exactly (1st=10/2nd=6/3rd=3; mutuals +5 ea max 15; GT +8; Fortinet +6; same team +10; HM +15; domain +8; US +5; known +5; can-refer +10) **plus**: `activity_level=="active_poster" and hiring_post_urls` → +6 and tiebreak advantage (per LINKEDIN_REFERRAL_RULES + rule 05). P0 = 1st connection; P1 = 2nd+mutuals or GT+mutuals; P2 = strong alignment no mutuals; P3 = 3rd+exceptional or recruiters-only-path. `recommended_ask` per the Phase-6 table. Parametrize ≥10 cases including: active-poster 2nd beats inactive 2nd with equal relevance; recruiter never above P1 unless nothing else.

**Step 2:** FAIL → **Step 3:** implement → **Step 4:** PASS → **Step 5:** commit `feat(right-people): weighted scoring + P0-P3 bands`

### Task 5: Dedup + canonical upserts

**Files:** `scripts/right_people_lib.py`; `tests/test_right_people_lib.py`

**Step 1 — failing tests** for `upsert_contacts(findings) -> {"added": n, "updated": n, "skipped_dup": n}`:
- reuse `people_sweep` never-twice semantics: skip if `outreach_status ∈ {requested, connected, contacted, responded}` in `contacts.csv` or prior `people_sweep.csv` rows;
- match by `linkedin_url`, fallback normalized name+company (reuse `referral_lib._fuzzy_same`);
- update-in-place refreshes `last_verified`, never duplicates rows;
- creates per-company `connections.csv` with exact header from §4 if absent;
- appends run row to `people_sweep.csv` with `sweep_run_id`.

**Step 2:** FAIL → **Step 3:** implement → **Step 4:** PASS → **Step 5:** commit `feat(right-people): dedup + canonical upserts`

### Task 6: CLI shell (plan-only dry run default)

**Files:** Create `scripts/right_people.py`; Test `tests/test_right_people_cli.py`

**Step 1 — failing test:** `--company "Cohere"` (no `--live`) prints the resolved target + ordered search plan as a table, writes **nothing**; exit 0. `--json` emits machine-readable plan. Missing both flags → argparse error.

**Step 2:** FAIL → **Step 3:** implement argparse (`--company | --job-url`, `--live`, `--limit N`, `--json`, `--queue-drafts`) wiring Tasks 1–5 → **Step 4:** PASS → **Step 5:** commit `feat(right-people): CLI dry-run`

### Task 7: Live execution pass (browser, agent-driven)

**Files:** `scripts/right_people.py` (execution section)

Live mode per pass: use `browser_session_lib` (Chrome :9333, `check_auth_state` first; if unauthenticated → pause and ask user, rule 08). Via Playwright MCP: navigate → apply native filters in UI (URL params allowed only as mirrors of UI filters) → **read chips + result count and record them** → paginate → extract person rows (name/title/location/degree/URL) → append to `people_sweep.csv`. Log every pass to `search_runs.csv` (`filters_applied`, chips observed, rows extracted, page reachable). Tab discipline: one LinkedIn search tab reused; close temp tabs. If a pass fails/blocked → record failure in `search_runs.csv`, continue other passes, never mark searched (rule 08).

Verification (evidence, not claims): run `--company "Cohere" --live --limit 12`; report real per-pass row counts + chips observed; spot-check ≥3 extracted profiles exist at their URLs.

Commit: `feat(right-people): live LinkedIn execution with filter verification`

### Task 8: Profile inspection + activity check pass

**Files:** `scripts/right_people.py` (inspection section)

For each serious candidate from Task 7 (cap `--limit`): open profile → confirm current company/role/team; identify shared context (GT/Fortinet/mutuals/domain — facts only from `profile_info/`); **check recent activity**: posting frequency + any hiring/referral posts (record `activity_level`, `hiring_post_urls`); assign email label `unavailable` unless a verified public source exists (rule 10). LLM-assisted summarization allowed via the standard provider chain; **recorded facts must come from the page**, never the model's imagination.

Verification: run inspection on 3 Cohere candidates from Task 7; confirm each `connections.csv` row has non-empty `shared_context` or explicit `unknown`, and `activity_level` set.

Commit: `feat(right-people): mandatory profile inspection + activity signal`

### Task 9: Ranked report + optional draft queueing

**Files:** `scripts/right_people.py` (output section)

Emit ranked Markdown summary (P0→P3, score, ask, reason, activity) to stdout and to `job_research/companies/<slug>/connections_report.md` (durable per-company artifact, not a timestamped note — rule 09). With `--queue-drafts`: stage P0/P1 into `connection_queue.py draft` ledger as `pending` only. **No message is ever sent autonomously** (rule 10 approval boundary).

Verification: report shows the exact ranked list matching `connections.csv` rows; `connection_requests.csv` gains `pending` rows only when flag passed.

Commit: `feat(right-people): ranked report + human-gated draft queue`

### Task 10: Live smoke test, docs, session state

Per rule 08 mandatory browser tests: one full live run each for company mode (`--company "Scale AI" --live --limit 10`) and job mode (`--job-url <a current pipeline job> --live --limit 10`); record evidence (row counts, chips, verification spot-checks) into `search_runs.csv`. Update repo `README.md` map + `session_state.md` in the same change. Final commit: `docs: right-people feature map + session state`

---

## 6. Tests / validation summary

- **Unit:** `pytest tests/test_right_people_lib.py tests/test_right_people_cli.py -v` — resolver, JD hints, plan builder (no keyword-only passes), scoring table, dedup/upsert interlocks, CLI dry-run. Must pass before any live run.
- **Live smoke (evidence):** per-pass row counts + observed filter chips recorded in `tracking/search_runs/search_runs.csv`; ≥3 extracted profiles verified at their LinkedIn URLs; `people_sweep.csv` run row appended; no duplicate rows in `contacts.csv` after a repeat run (idempotency check).
- **Safety checks:** zero outbound messages in any mode without explicit user send; `connection_requests.csv` rows only ever `pending` from this feature.

## 7. Risks / tradeoffs / open questions

- **LinkedIn scrape fragility** — DOM changes break extraction; mitigated by chip/count verification and per-pass failure logging, but expect periodic selector repair.
- **Rate limits** — many filter passes per company; mitigated by `--limit`, tab reuse, and running passes sequentially.
- **JD hints quality** — regex pass is cheap but shallow; LLM fallback uses the openrouter→nvidia chain which can 429/slow-start; feature must complete with regex-only hints if LLM unavailable.
- **3rd-degree data sparsity** — LinkedIn hides names at 3rd degree more often; plan treats those as `unknown` degree, P3 ceiling.
- **Open questions:** (a) Should job mode also auto-trigger when a new job enters the pipeline (cron tie-in to weekly Mon-10AM referral refresh)? (b) Should `mutuals` be fetched per-person (slow) or only for P1-boundary candidates? (c) Default `--limit` per pass — 15?
