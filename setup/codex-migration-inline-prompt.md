# INLINE PROMPT — Codex subscription cutover on Linux laptop

Copy everything below the line into a fresh Hermes session on the Linux laptop. It is fully self-contained.

---

You are migrating this machine's Hermes job-hunt system from NVIDIA/OpenRouter models to the user's ChatGPT/Codex subscription (provider `openai-codex`, OAuth). Follow these steps IN ORDER and report a done/not-done verdict with evidence after each phase. Do not skip the smoke tests.

## Context (verified on the Mac, 2026-09-10)

- Provider `openai-codex` authenticates via OAuth device-code login to ChatGPT's Codex backend (`https://chatgpt.com/backend-api/codex`). No API key.
- Model matrix VERIFIED LIVE on this subscription:
  - `gpt-5.6-terra` — ✅ works (use for COMPLEX tasks)
  - `gpt-5.6-luna` — ✅ works (use for SIMPLE tasks — DEFAULT)
  - `gpt-6-astra` — ✅ works but user chose NOT to use it
  - `gpt-5.5` — listed in catalog, untested
  - `gpt-5.4-mini` — ❌ HTTP 400 "not supported when using Codex with a ChatGPT account"
  - `gpt-5.3-codex` — ❌ HTTP 400, same error
- Correct invocation shape: `--provider openai-codex --model gpt-5.6-luna` (passing `openai-codex/gpt-5.6-luna` as a bare `--model` to nvidia endpoint gives 404s — the slash-form only belongs in `model.default` / aliases).
- Fallback safety: keep `nvidia/nemotron-3-super-120b-a12b` in `fallback_model` so any Codex rate-cap/5xx never stalls a cron. If nvidia is missing from fallback chain on this machine, add it back.
- Known pitfall: `hermes config set model.default openai-codex/gpt-5.6-luna` is required — setting only `model.provider` + `model.name` left a stale nvidia default and caused silent nemotron routing. After config, ALWAYS verify with a live run + log grep (step 3).
- The Mac reference config (working) is: `model.default: openai-codex/gpt-5.6-luna`, `model.provider: openai-codex`, `model.base_url: ''` (cleared), `model.name: ''` (cleared), aliases terra/luna/nemotron, fallback = nvidia nemotron.
- Canonical cron fleet: 8 jobs per `setup/CRON_JOBS_LINUX.md` in the jobhunt-engine repo. Pilot = the LinkedIn hiring-post monitor (`lhp_*` run_id, skill `linkedin-hiring-post-monitor`).

## Phase 1 — Auth (one-time, needs the user)

1. Check: `hermes auth list | grep codex`. If `openai-codex` already exists, skip to Phase 2.
2. Run `hermes auth add openai-codex` INTERACTIVELY (user's own terminal, not background). It prints a device code + URL `https://auth.openai.com/codex/device`.
3. Tell the user to enter the code within ~10 minutes — the poller times out at 15 min and the code expires; a late sign-in does NOT save the token (this failed twice on 2026-09-10 via SSH because sign-in happened too late).
4. On success it prints `Added openai-codex OAuth credential #1`. Verify: `hermes auth list | grep codex` shows an oauth entry.

## Phase 2 — Config (both profiles that exist: `job-hunt-fresh` and `job-hunt`)

For EACH profile (`hermes --profile <name>` or equivalent), run:

```bash
hermes config set model.provider openai-codex
hermes config set model.default openai-codex/gpt-5.6-luna
hermes config set model.base_url ""
hermes config set model.name ""
hermes config set model.aliases.terra "openai-codex/gpt-5.6-terra"
hermes config set model.aliases.luna "openai-codex/gpt-5.6-luna"
hermes config set model.aliases.nemotron "nvidia/nemotron-3-super-120b-a12b"
```

Then ensure the fallback chain still contains nvidia nemotron (`hermes fallback list`). If not: `hermes fallback add` (interactive picker) or edit `fallback_model` in config.yaml to:

```yaml
fallback_model:
  - provider: nvidia
    model: nvidia/nemotron-3-super-120b-a12b
    key_env: NVIDIA_API_KEY
```

Do NOT touch openrouter keys — they stay as dormant credentials.

## Phase 3 — Smoke test (MUST pass before any cron work)

```bash
hermes chat -q "Reply OK"
grep "API call #1" ~/.hermes/profiles/<active-profile>/logs/agent.log | tail -1
```

PASS = line reads `model=gpt-5.6-luna provider=openai-codex` with NO "Fallback activated" line after it.
Also test terra: `hermes chat -q "Reply OK" --provider openai-codex --model gpt-5.6-terra` → same log check.
If you see `model=nvidia/nemotron` in the API-call line, the default did not land — re-check `model.default` value and stale `model.base_url`/`model.name` keys, then re-test.

## Phase 4 — Pilot: LinkedIn hiring-post monitor

1. Identify the pilot cron in `hermes cron list` (name contains discovery/linkedin posts; run_id prefix `lhp_`).
2. Ensure its job uses the profile default (no per-job model override pinning it to nvidia — if it has one, change it to alias `luna`, or `terra` if the job does heavy reasoning).
3. Fire ONE manual run (`hermes cron run <job_id>`).
4. Verify, with evidence:
   - agent.log newest lines show `provider=openai-codex` (luna or terra), no unexpected fallback
   - the run's digest/output was produced normally (no truncation/refusal weirdness vs. previous nvidia runs)
   - `jobhunt-data/tracking/search_runs/search_runs.csv` got a new `lhp_*` row with correct 9-column schema
   - if the run scrapes LinkedIn: feed pass worked and any new posts were classified + appended to `tracking/hiring_posts/hiring_posts.csv` without duplicate post_ids
5. Run it one more time to confirm repeatability.

## Phase 5 — Roll out to remaining crons (one at a time, lightest first)

For each of the remaining 7 crons: check for per-job model overrides. Simple/classification/digest jobs → alias `luna` (or leave on profile default). Heavy reasoning jobs (deep discovery, resume tailoring, JD intelligence) → alias `terra`. Cheapest/simplest batch jobs may stay on `nemotron` if the user wants to conserve subscription quota.

After each flip: fire one manual run, check the log line for `provider=openai-codex` and normal output, then move to the next. If a job fails on Codex (rate cap 429/usage limit), leave that job on nemotron, note it, and continue — do not block the fleet.

## Phase 6 — Report

Final message must include: config diff summary per profile, smoke-test log lines, pilot run verdict (with CSV/log evidence), list of crons flipped vs. left on nvidia, and any Codex rate-limit events seen.

## Rollback (if everything breaks)

```bash
hermes config set model.provider nvidia
hermes config set model.default nvidia/nemotron-3-ultra-550b-a55b   # this machine's previous default
hermes config set model.base_url https://integrate.api.nvidia.com/v1
```

(Previous defaults before this migration: `nvidia/nemotron-3-ultra-550b-a55b` on job-hunt-fresh; verify from config.yaml backup/git before rolling back.)
