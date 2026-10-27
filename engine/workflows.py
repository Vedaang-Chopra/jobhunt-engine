"""Workflow Registry: each workflow is defined exactly ONCE.

A workflow declares HOW it executes (agent vs script), what it does, and its
concurrency/browser requirements. Cron, the NiceGUI UI, and manual CLI
invocation all resolve through this registry via
``engine.run_manager.RunManager`` — there are no separate "UI" and "cron"
implementations of the same workflow.

AGENT_RUN  → a real Hermes agent session (``hermes --profile job-hunt -z …``),
             which uses browser/terminal tools and the shared persistent
             Chrome profile (scripts/browser_session_lib / automation Chrome
             on :9333). The UI never launches its own browser.
SCRIPT_RUN → a deterministic subprocess (python scripts/<name>.py).

Browser-requiring workflows must keep ``browser_required`` true so RunManager
enforces single ownership of the shared logged-in profile.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional

REPO = Path(__file__).resolve().parents[1]

AGENT = "agent"
SCRIPT = "script"

#: LinkedIn Jobs discovery is intentionally a SCRIPT workflow: deterministic
#: query selection, extraction, and hard filtering must not depend on an LLM.


def _py(name: str) -> str:
    return str(sys.executable or "python3")


def _script(name: str) -> str:
    return str(REPO / "scripts" / name)


class Workflow:
    """One canonical workflow definition."""

    def __init__(self, name: str, execution_type: str, description: str,
                 prompt: Optional[str] = None,
                 cmd_builder=None,
                 browser_required: bool = False,
                 persistent_browser_profile: Optional[str] = None):
        self.name = name
        self.execution_type = execution_type  # AGENT | SCRIPT
        self.description = description
        self.prompt = prompt
        self.cmd_builder = cmd_builder          # -> list[str] for SCRIPT runs
        self.browser_required = browser_required
        self.persistent_browser_profile = persistent_browser_profile

    @property
    def is_agent(self) -> bool:
        return self.execution_type == AGENT


WORKFLOWS: Dict[str, Workflow] = {
    # ---------------------------------------------------- script workflows
    "linkedin-discovery": Workflow(
        name="linkedin-discovery",
        execution_type=SCRIPT,
        description="Deterministic dual-path LinkedIn Jobs discovery.",
        cmd_builder=lambda: [_py("x"), _script("linkedin_job_sweep.py"), "--live"],
        browser_required=True,
        persistent_browser_profile="job-hunt-automation",
    ),
    # Future migrations register here with the same shape:
    #   linkedin-hiring-posts, linkedin-feed-discovery, wellfound-discovery.

    "resume-scorer": Workflow(
        name="resume-scorer",
        execution_type=SCRIPT,
        description="ATS score deterministic pass.",
        cmd_builder=lambda: [_py("x"), _script("ats_check.py"), "--help"],
    ),
    "csv-deduplication": Workflow(
        name="csv-deduplication",
        execution_type=SCRIPT,
        description="Dedupe/normalize CSV outputs.",
        cmd_builder=lambda: [_py("x"), _script("ingest_linkedin_sweep.py")],
    ),
}


def get_workflow(name: str) -> Workflow:
    wf = WORKFLOWS.get(name)
    if wf is None:
        raise KeyError(f"unknown workflow: {name}")
    return wf


def register(workflow: Workflow) -> None:
    WORKFLOWS[workflow.name] = workflow
