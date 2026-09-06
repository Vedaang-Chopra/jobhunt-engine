# Sequential Execution Prompt — Productization 002
# Paste as first message to any executing agent (Pi or Hermes subagent).

You are executing a pre-planned feature implementation for the job-applications repo.
Read docs/tasks/002_productization_ui_onboarding.md and execute tasks in phase order.

## PRE-FLIGHT
1. Confirm task file non-empty; find your assigned task (subagent letter in parens).
2. Read ~/agent-governance/AGENTS.md, project AGENTS.md, docs/ai_context/*.md, AGENT_EXECUTION_LOG.md.
3. Never modify files outside your task's listed File(s).

## RULES
- Verify each task with pytest before marking [x]; max 2 fix attempts then stop and report.
- Commit per completed task: `git commit -m "agent: <task id> <description>"`.
- At SYNC POINTS: do not proceed unless all prior-group verifies passed.
- Long sweeps/LLM calls: no secrets printed, no raw curl for LLMs (openai SDK only).
- Destructive ops preview-first with explicit --apply.
- On completion: write Change Report + AGENT_EXECUTION_LOG entry + update session_state.md.
