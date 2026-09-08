# AGENTS_SETUP_PROMPT.md — Paste This Into Hermes on the New Linux Laptop

Copy everything below the line into a fresh Hermes session on the target
machine. It gives the agent complete, self-contained instructions.

---

You are setting up my job-hunt automation system on this new Linux laptop.
Everything you need is in the repository at `SETUP_ON_LINUX.md` (in the repo
root) — read it fully first, then execute it phase by phase. Follow it
exactly; it encodes hard-won lessons (repo-root data dumps, cron path
drift, dual-machine write conflicts).

Context you must know:

1. **Two repos.** `git@github.com:Vedaang-Chopra/jobhunt-engine.git` is the
   PUBLIC engine (this repo). `git@github.com:Vedaang-Chopra/jobhunt-data-private.git`
   is my PRIVATE data (job registry, resumes, application answers, API keys
   in `jobhunt-data/config.yaml`). Never commit personal data to the engine
   repo; `tests/test_output_hygiene.py` enforces this — if it fails, fix the
   writer to use `config_lib.path(...)`, never move data back into the repo.

2. **My identity is config-driven**, not hardcoded: it lives in the
   `identity:` block of `jobhunt-data/config.yaml` and is read via
   `config_lib.identity()`. Never hardcode name/email/phone anywhere.

3. **Run outputs go under the data root** (`<repo>/jobhunt-data/execution_results/...`),
   registered in `scripts/config_lib.py` PATHS. Never write reports,
   digests, sweep payloads or fill plans to the repo root.

4. **The 8 Hermes cron jobs (the duplicate `morning-job-digest` was removed 2026-09-08; canonical fleet is in `setup/CRON_JOBS_LINUX.md`)** live in `~/.hermes/profiles/job-hunt/cron/jobs.json`
   (copied from my Mac). Their prompts contain the OLD Mac repo path and the
   old macOS venv python — recreate them from `setup/CRON_JOBS_LINUX.md` (single source of truth, with `{{REPO}}`/`{{PY}}` placeholders), or rewrite them with
   `setup/migrate_cron_paths.py --to-repo "$HOME/git/jobhunt-engine" --apply`.
   Every job is pinned to provider `nvidia`, model
   `nvidia/nemotron-3-super-120b-a12b` — do not change this; unpinned jobs
   hard-skip on config drift (`[drift_skip]`).

5. **Browser automation**: one shared automation Chrome on CDP port 9333
   (systemd unit `jobhunt-automation-chrome`, script
   `scripts/automation_chrome.sh`, profile `~/.hermes/browser-profiles/job-hunt`).
   Sweeps attach over CDP; never launch competing Chrome instances or use
   the user's normal Chrome profile.

6. **I must do the LinkedIn login myself** in the automation Chrome window.
   After that, verify CDP answers on 127.0.0.1:9333 before running any
   LinkedIn sweep.

7. **Cutover discipline**: the old Mac's cron jobs must be PAUSED before
   any cron fires here (both machines writing the same tracking CSVs
   corrupts the registry). Ask me to confirm the Mac is paused before Phase 7.

    Cron creation on this machine: paste each job from `setup/CRON_JOBS_LINUX.md`
    with `{{REPO}}`/`{{PY}}` substituted. All jobs start `enabled: false`; enable
    only after the Phase 6 verification gate passes.

8. **Verification before declaring done**: pytest suite green,
   `hermes doctor` healthy, `hermes cron list` shows 8 jobs with zero
   `/Users/` references in jobs.json, CDP :9333 answers, `ops-health` cron
   run completes with status ok, `jobhunt-ui` systemd unit active.

9. **Daily flow after setup**: `./scripts/sync_data.sh push` before leaving
   this machine / `pull` after arriving on the other. One machine is
   authoritative per time window.

10. **Rules files**: read `AGENTS.md` at the repo root and the modular rules
    under `docs/hermes_job_hunt_rules_modular/` before changing job-discovery,
    scoring, outreach or resume logic. `CRON_MANIFEST.md` documents the cron
    fleet and the failure playbook.

Execute Phase 1 → 6 autonomously (stopping only for sudo prompts and the
LinkedIn login), show me a checkpoint with pass/fail evidence after each
phase, then ask me to pause the Mac crons before doing Phase 7.

    Cron creation on this machine: paste each job from `setup/CRON_JOBS_LINUX.md`
    with `{{REPO}}`/`{{PY}}` substituted. All jobs start `enabled: false`; enable
    only after the Phase 6 verification gate passes.
