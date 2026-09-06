"""Hybrid deterministic + LLM web-navigation agent.

Public API:
    GoalContract          — declarative bounds for a run
    observe               — deterministic page observation (a11y + text)
    execute_action        — validated Playwright action executor
    run                   — the GOAL->OBSERVE->DECIDE->EXECUTE loop
    llm_decide/parse_decision — LLM decision plumbing
"""

from .goal import GoalContract
from .observer import observe, summarize_observation
from .actions import execute_action, ActionRefused
from .agent import run, llm_decide, parse_decision, build_prompt

__all__ = [
    "GoalContract",
    "observe",
    "summarize_observation",
    "execute_action",
    "ActionRefused",
    "run",
    "llm_decide",
    "parse_decision",
    "build_prompt",
]
