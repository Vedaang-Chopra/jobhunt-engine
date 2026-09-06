# User Guide — Running Everything From the UI

This guide is for using the system **entirely from the browser GUI**. No
terminal work is needed after the one-time install.

---

## 1. One-Time Setup (terminal, once only)

```bash
git clone git@github.com:Vedaang-Chopra/Job-Hunting.git
cd Job-Hunting
python3.9 -m venv .venv && source .venv/bin/activate
pip install -e .
export JOBHUNT_HOME="$(pwd)/jobhunt-data"   # your data lives in the repo's jobhunt-data/
python -m setup.wizard --apply             # creates folders + config.yaml skeleton
```

The wizard asks for:
- **Data directory** — where all your personal data goes (default `<repo>/jobhunt-data`)
- **Resume** — drop your resume file (or skip; you can upload it from the UI later)
- **LLM API keys** — OpenRouter and/or NVIDIA keys → written to `config.yaml` with `chmod 600`, never displayed again

## 2. Start the App (daily)

```bash
source .venv/bin/activate
export JOBHUNT_HOME="<repo>/jobhunt-data"   # or put this in your shell profile once
python -m ui.app
```

Open **http://localhost:8080**. That's it — everything below happens in the browser.

> Tip: add the two lines (`source ...` / `export ...`) to a small `start.sh`
> so daily startup is one command.

---

## 3. The Pages — What Each One Does

### Profile — *start here on first run*
Your identity to the whole system: scoring, resumes, and outreach all read
from what's on this page.

- **Build it by uploading anything**: drag files onto the upload card (PDF,
  DOCX, TXT, MD, YAML, CSV) or use **Paste text** for job descriptions,
  notes, old applications — anything.
- Every upload lands in a **Pending review** queue. The engine classifies it
  (resume / JD / notes), extracts emails, phones, skills, and companies.
- For each item choose:
  - **Accept** → merged into your profile YAML, tagged `unverified` until you
    confirm the claim is true (provenance rule: nothing becomes "verified"
    without evidence)
  - **Discard** → removed
- Edit any profile section directly with the inline editor (it validates
  YAML before saving — invalid edits are rejected with a message).

**First-day checklist:** upload your resume → Accept it → check the Skills
and Experience sections look right → paste in 2–3 job descriptions you like
and Accept them as preference signals.

### Dashboard
Daily landing page: fresh jobs found, queue depth, applications sent,
connections pending — plus a **Needs action** panel (nudge recruiters you've
waited ≥7 days on, prep for interviews within ≤2 days) and the freshness
chart.

### Jobs
Every discovered job, filterable by search box, fit tier, and priority.
Click any row for the full job description. This is your browse/search surface.

### Today's Queue
The engine's opinionated shortlist: **Fresh jobs** (new since last sweep),
**Top queue** (best fit × attainability), **Needing attention** (stale,
missing data). Buttons here let you run discovery sweeps yourself:

- **Run discovery** (with freshness-tier selector) — fetches new postings from configured boards
- **Freshness check** — re-verifies which known jobs are still open

### Pipeline
Your application Kanban: Saved → Preparing → Applied → Interviewing → Closed.
Drag isn't wired; change stage via the dropdown on each card — writes go
through the engine layer (which auto-schedules +7-day follow-ups when you mark
something Applied).

### Outreach
LinkedIn connection management with hard safety rails:
- Ledger of requests: pending → approved → sent
- You approve each batch; sends respect the **≤25/day cap** (progress meter shown)
- Nobody is ever contacted twice
- Drafts are read-only here — review them, then approve

### Analytics
Funnel view: applied → response → screen → interview → offer, weekly volume,
breakdowns by source board and resume version. Read-only; updates as the
tracking data grows.

### Company Research
Pick a company → see gathered intel beside its open jobs.

### Resume & Settings
- List of tailored resumes; tailor trigger for a selected job
- Settings shows which config keys are present/absent (**names only — values
  are never rendered**) and your data-root path
- LLM endpoint editor: change OpenRouter/NVIDIA base URLs, models, API keys;
  keys are write-only (type → save → never echoed back)

---

## 4. What the System Will NOT Do (by design)

- It never submits an application for you — Workday portals especially are manual
- It never sends LinkedIn messages/connection requests without your explicit approval
- It never marks a profile claim "verified" without you confirming evidence

## 5. Where Is My Data?

Everything personal lives under `$JOBHUNT_HOME` (default `<repo>/jobhunt-data`):
profile YAMLs, inbox uploads, tracking CSVs, `config.yaml` with your keys.
The code repo stays clean — back up that one folder and you've backed up
your entire job search.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| Port 8080 already in use | An older instance is running: `kill $(lsof -ti :8080)` then relaunch |
| Pages show empty tables | No data yet — run **Run discovery** from Today's Queue |
| Discovery returns nothing | Check LLM/board config in Settings; some boards rate-limit |
| Upload not extracted | PDFs need `pypdf` (`pip install pypdf`); text paste always works |
| Forgot whether wizard ran | Re-run `python -m setup.wizard` (dry-run default shows what it would do) |
