# Hermes Modular Rules Bootstrap Prompt

The job-hunt rules are split into focused files. Do not load every rule file into every worker.

First read:
- `00_README.md`
- `12_EXISTING_PROJECT_MIGRATION.md`
- `11_SUBAGENT_ORCHESTRATION.md`

Then audit the entire existing job-hunt project recursively.

Your task is to make the current project conform to these rules without creating a second parallel system.

1. Map existing files, data, agents, sub-agents, skills, scripts, and browser/MCP instructions to the canonical structure.
2. Merge duplicated/conflicting Markdown knowledge into the appropriate modular rule files.
3. Reorganize jobs, companies, LinkedIn connections/referrals, hiring posts, JD intelligence, applications, and search coverage into canonical structured datasets.
4. Update `README.md` and `AGENTS.md` so future Hermes sessions know exactly what source-of-truth files to use.
5. Create/refine specialized skills/workers described in `11_SUBAGENT_ORCHESTRATION.md`; each worker should receive only relevant rule files.
6. Prefer reliable MCP/API tools; use Playwright/browser-control MCP when actual browser interaction is required; keep tab usage minimal and reuse tabs.
7. Preserve useful information and provenance; archive superseded material before deleting anything non-trivial.
8. Ask me when an important assumption is unresolved.
9. Validate the full workflow on 1–2 representative companies before declaring the migration complete.

At completion report the canonical directory tree, files created/modified/merged/archived/deleted, workers/skills created or updated, validation performed, and unresolved questions.
