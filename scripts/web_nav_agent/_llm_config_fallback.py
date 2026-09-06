"""Fallback accessor for the canonical LLM provider chain.

Delegates to ``config_lib.llm_config()`` — the single source of truth used by
tailor_from_jd, resume_agent.common, and search_strategy/llm.py. This shim
remains so importing tailor_from_jd itself is never required (its module-level
imports can fail in stripped-down environments); ``config_lib`` has no heavy
dependencies.
"""

from __future__ import annotations

import config_lib  # noqa: F401  (repo scripts dir on sys.path via agent.py)


def llm_config() -> list[dict]:
    """Canonical provider chain via :func:`config_lib.llm_config`."""
    return config_lib.llm_config()
