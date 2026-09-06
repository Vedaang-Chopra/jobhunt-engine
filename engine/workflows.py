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

#: Prompt for linkedin-discovery — extracted verbatim from the canonical cron
#: definition (discovery-linkedin, every 2h) so UI-triggered runs execute the
#: IDENTICAL agent workflow. Do not fork this prompt per trigger.
LINKEDIN_DISCOVERY_PROMPT = (
    "LinkedIn discovery sweep (trigger: {trigger}). "
    f"cd '{REPO}'. First run: "
    "~/.hermes/hermes-agent/venv/bin/python scripts/discovery_run.py "
    "--sources l1,l2 — it will report 'needs interactive session' if "
    "headless. THEN attempt the real sweep yourself using the Playwright MCP "
    "browser (persistent logged-in Chrome profile is already configured — "
    "never type passwords; if a login wall appears, stop and report): run "
    "ONE LinkedIn jobs sweep per the linkedin-job-sweep skill (guest API + "
    "logged-in fetch methods, scripts/linkedin_guest_sweep.py exists as "
    "reference), normalize results through scripts/discovery_lib.py, dedupe "
    "against tracking/jobs/jobs.csv, append new rows, log to "
    "tracking/search_runs/search_runs.csv. Keep it to ONE tab, ≤8 searches, "
    "close the tab after. If LinkedIn shows CAPTCHA/warning, stop "
    "immediately and note it. Report new-jobs count."
)


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
    # ---------------------------------------------------- agent workflows
    "linkedin-discovery": Workflow(
        name="linkedin-discovery",
        execution_type=AGENT,
        description="Logged-in LinkedIn jobs sweep via Hermes agent "
                    "(canonical discovery-linkedin workflow).",
        prompt=LINKEDIN_DISCOVERY_PROMPT,
        browser_required=True,
        persistent_browser_profile="job-hunt-automation",
    ),
    # Future migrations register here with the same shape:
    #   linkedin-hiring-posts, linkedin-feed-discovery, wellfound-discovery.

    # ---------------------------------------------------- script workflows
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
