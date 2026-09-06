"""Layer 3 run registry — now a thin adapter over the canonical RunManager.

All runs (UI, cron, manual) execute through ``engine.run_manager.RunManager``,
which owns workflow resolution, persistence, concurrency, and cancellation.
This module keeps the historical component-level API (``RUNS.start/status/
tail/latest/is_running/cancel``) so existing pages keep working unchanged,
and adds the agent-workflow entry point.

Exactly ONE live run per workflow is allowed — enforced by the RunManager at
workflow level, not by button state, so cron-triggered runs also block
duplicate UI launches.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, List, Optional

from nicegui import ui

from ui.components import page_timer
from engine.run_manager import (
    RunManager,
    WorkflowBusy,
    get_manager,
)

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable or "python3"

TIER_ORDER = ["A", "B", "C", "D", "E"]

# Component -> button label.
COMPONENT_LABELS = {
    "discovery": "Run discovery",
    "freshness": "Run freshness check",
    "people_sweep": "Run people sweep (plan)",
    "poster_connect_sweep": "Run poster connect sweep (plan)",
    "linkedin_live_sweep": "Collect LinkedIn jobs now",
    "linkedin_ingest": "Ingest last LinkedIn sweep",
    "linkedin_people_sweep": "Sweep LinkedIn for people now",
    "outreach_draft": "Draft next connection batch",
    "resume_tailor": "Tailor resume",
}

#: Legacy component name -> canonical workflow name. Components listed here
#: route through their canonical AGENT workflow instead of raw subprocesses.
AGENT_COMPONENT_WORKFLOW = {
    "linkedin_discovery_agent": "linkedin-discovery",
}


def script(name: str) -> str:
    """Absolute path to a scripts/ CLI."""
    return str(REPO / "scripts" / name)


def discovery_cmd(tier: str) -> List[str]:
    cmd = [PYTHON, script("discovery_run.py"), "--dry-run"]
    if tier:
        cmd += ["--min-tier", tier]
    return cmd


def freshness_cmd() -> List[str]:
    return [PYTHON, script("freshness_check.py"), "--dry-run"]


def freshness_live_cmd() -> List[str]:
    """Live freshness pass: reseed referral registry, then verify/expiry."""
    return [PYTHON, script("freshness_check.py"), "--live"]


def career_ops_sweep_cmd() -> List[str]:
    """Full career-ops sweep: node scan.mjs -> import -> rescore."""
    return [PYTHON, script("career_ops_sweep.py")]


def career_ops_import_cmd() -> List[str]:
    """Import-only career-ops pass (reuse the last scan-history)."""
    return [PYTHON, script("career_ops_sweep.py"), "--no-scan"]


def wellfound_cmd() -> Optional[List[str]]:
    """Run the Wellfound daily crawler resolved from the path registry."""
    try:
        from scripts import config_lib
    except ImportError:
        import config_lib  # type: ignore[no-redef]
    wf = config_lib.path("wellfound_crawler")
    if not Path(wf).exists():
        return None
    return [PYTHON, str(wf)]


def linkedin_portal_live_cmd() -> List[str]:
    """Live logged-in LinkedIn portal sweep (source l1)."""
    return [PYTHON, script("linkedin_portal_sweep.py"), "--live"]


def linkedin_recommended_live_cmd() -> List[str]:
    """Live logged-in LinkedIn 'recommended jobs' sweep (source l2)."""
    return [PYTHON, script("linkedin_recommended_sweep.py"), "--live"]


def people_sweep_cmd(limit: int = 12) -> List[str]:
    return [PYTHON, script("people_sweep.py"), "--dry-run",
            "--limit", str(max(1, int(limit)))]


def poster_connect_sweep_cmd() -> List[str]:
    # Dry mode is the read-only queue build; sends stay live-only + capped.
    return [PYTHON, script("poster_connect_sweep.py"), "--dry-run"]


def linkedin_live_sweep_cmd() -> List[str]:
    """Live (non-dry-run) LinkedIn guest-API collection sweep."""
    return [PYTHON, script("linkedin_guest_sweep.py")]


def linkedin_ingest_cmd() -> List[str]:
    """Ingest the newest sweep JSON into tracking/jobs/jobs.csv."""
    return [PYTHON, script("ingest_linkedin_sweep.py")]


def linkedin_people_sweep_cmd() -> Optional[List[str]]:
    """Fire the background LinkedIn people+hiring-posts cron immediately.

    DEPRECATED path kept only until linkedin-hiring-posts migrates to an
    agent workflow; returns None when the cron job cannot be resolved.
    """
    from ui import data as data_layer

    job_id = data_layer.find_cron_job_id("linkedin-people-posts-2h")
    if not job_id:
        return None
    hermes_bin = Path.home() / ".local" / "bin" / "hermes"
    binary = str(hermes_bin) if hermes_bin.exists() else "hermes"
    return [binary, "--profile", "job-hunt", "cron", "run", job_id]


def outreach_draft_cmd(limit: int = 8) -> List[str]:
    """Draft the next connection-request batch (writes ledger `pending` rows)."""
    return [PYTHON, script("connection_queue.py"), "draft",
            "--limit", str(max(1, int(limit)))]


def tailor_cmd(job_id: str) -> List[str]:
    return [PYTHON, script("apply_pipeline.py"), str(job_id)]


def tailor_spec_cmd(spec_path: str) -> List[str]:
    """Tailor resume + cover letter directly from a JD spec JSON."""
    return [PYTHON, script("tailor_from_jd.py"), "--spec-file", str(spec_path)]


class RunRegistry:
    """Backward-compatible facade over the canonical RunManager."""

    def __init__(self, manager: Optional[RunManager] = None) -> None:
        self._manager = manager or get_manager()

    @property
    def manager(self) -> RunManager:
        return self._manager

    def start(self, name: str, cmd_list: Optional[List[str]] = None) -> str:
        """Start component ``name``; returns the run_id.

        If ``name`` maps to a canonical agent workflow, launch that workflow;
        otherwise wrap the given command as an ad-hoc SCRIPT run registered
        under the legacy component name.
        """
        workflow = AGENT_COMPONENT_WORKFLOW.get(name)
        if workflow:
            return self.start_workflow(workflow, trigger="ui")
        if cmd_list is None:
            raise ValueError(f"component '{name}' has no command")
        return self.start_adhoc(name, cmd_list)

    def start_adhoc(self, name: str, cmd_list: List[str]) -> str:
        """Register a legacy command as a tracked SCRIPT run."""
        from engine.workflows import Workflow, register

        key = f"adhoc:{name}"
        try:
            from engine.workflows import get_workflow as _get
            _get(key)
        except KeyError:
            def _builder(cmd=tuple(cmd_list)):
                return list(cmd)
            register(Workflow(name=key, execution_type="script",
                              description=f"Legacy UI component '{name}'.",
                              cmd_builder=_builder))
        return self._manager.start(key, trigger="ui")

    def start_workflow(self, workflow: str, trigger: str = "ui") -> str:
        return self._manager.start(workflow, trigger=trigger)

    # -- read API ----------------------------------------------------------
    LEGACY_STATE = {
        "QUEUED": "running", "STARTING": "running", "RUNNING": "running",
        "WAITING_FOR_AUTH": "running", "WAITING_FOR_USER": "running",
        "SUCCEEDED": "done", "FAILED": "failed", "CANCELLED": "cancelled",
        "INTERRUPTED": "interrupted",
    }

    @classmethod
    def _legacy_state(cls, status: str) -> str:
        return cls.LEGACY_STATE.get(status, status.lower())

    def status(self, run_id: str) -> dict:
        record = self._manager.get(run_id)
        return {
            "run_id": record["run_id"],
            "name": record["workflow"].removeprefix("adhoc:"),
            "state": self._legacy_state(record["status"]),
            "returncode": record["exit_code"],
        }

    def cancel(self, run_id: str) -> dict:
        record = self._manager.cancel(run_id)
        return {
            "run_id": record["run_id"],
            "name": record["workflow"],
            "state": self._legacy_state(record["status"]),
            "returncode": record["exit_code"],
        }

    def tail(self, run_id: str, n_lines: int = 50) -> List[str]:
        lines = self._manager.tail(run_id, n_lines)
        return [line.split("] ", 1)[-1] if "] " in line else line
                for line in lines]

    def latest(self, name: str) -> Optional[str]:
        for record in self._manager.list_runs(limit=500):
            if record["workflow"].removeprefix("adhoc:") == name:
                return record["run_id"]
        return None

    def is_running(self, name: str) -> bool:
        for record in self._manager.list_runs(limit=500):
            if record["workflow"].removeprefix("adhoc:") != name:
                continue
            if record["status"] in ("QUEUED", "STARTING", "RUNNING",
                                    "WAITING_FOR_AUTH", "WAITING_FOR_USER"):
                return True
        return False


RUNS = RunRegistry()


class AgentWorkflowPanel:
    """Button + status + log panel bound to one CANONICAL agent workflow.

    Unlike RunPanel this never builds a local command — it asks the shared
    RunManager to start the real Hermes agent session, so UI and cron runs
    are indistinguishable apart from the recorded trigger.
    """

    def __init__(self, workflow: str, label: Optional[str] = None):
        self.workflow = workflow
        self.manager = get_manager()
        with ui.row().classes("w-full items-center q-gutter-sm"):
            self.button = ui.button(
                label or f"Run {workflow}",
                icon="smart_toy",
                on_click=self._start,
            )
            self.status_label = ui.label("").classes("text-caption text-grey")
        with ui.expansion("Logs", icon="terminal").classes("w-full"):
            self.log_label = ui.label("(no output yet)").classes(
                "text-caption").style(
                "white-space: pre-wrap; font-family: monospace; "
                "user-select: text")
        self.timer = page_timer(1.0, self.refresh)
        self.refresh()

    def _start(self) -> None:
        try:
            run_id = self.manager.start(self.workflow, trigger="ui")
            ui.notify(f"started agent run {run_id}", type="positive")
        except WorkflowBusy as exc:
            ui.notify(str(exc), type="warning")
        except KeyError as exc:
            ui.notify(str(exc), type="negative")
        self.refresh()

    def refresh(self) -> None:
        if self.timer.is_deleted or self.button.is_deleted \
                or self.status_label.is_deleted or self.log_label.is_deleted:
            return
        latest = None
        running = False
        st_txt = ""
        for record in self.manager.list_runs(limit=200):
            if record["workflow"] != self.workflow:
                continue
            if latest is None:
                latest = record
            if record["status"] in ("QUEUED", "STARTING", "RUNNING",
                                    "WAITING_FOR_AUTH", "WAITING_FOR_USER"):
                running = True
            break
        if running:
            self.button.disable()
        else:
            self.button.enable()
        if latest is None:
            self.status_label.set_text("")
            self.log_label.set_text("(no output yet)")
            return
        status = latest["status"]
        session = latest.get("agent_session_id") or "—"
        self.status_label.set_text(
            f"{latest['run_id']} · {status} · agent {session} "
            f"(trigger: {latest['trigger']})")
        lines = self.manager.tail(latest["run_id"], 300)
        if lines:
            self.log_label.set_text("\n".join(lines))
        elif status == "RUNNING":
            self.log_label.set_text("(waiting for output…)")


class RunPanel:
    """Button + status line + expanding log panel bound to one component."""

    def __init__(self, component: str,
                 cmd_builder: Callable[[], Optional[List[str]]]) -> None:
        self.component = component
        self.cmd_builder = cmd_builder
        with ui.row().classes("w-full items-center q-gutter-sm"):
            self.button = ui.button(
                COMPONENT_LABELS.get(component, f"Run {component}"),
                on_click=self._start,
            )
            self.status_label = ui.label("").classes("text-caption text-grey")
        with ui.expansion("Logs", icon="terminal").classes("w-full"):
            self.log_label = ui.label("(no output yet)").classes(
                "text-caption").style(
                "white-space: pre-wrap; font-family: monospace; "
                "user-select: text")
        self.timer = page_timer(1.0, self.refresh)
        self.refresh()

    def _cmd(self) -> Optional[List[str]]:
        try:
            return self.cmd_builder()
        except Exception as exc:  # noqa: BLE001 - surface builder errors inline
            ui.notify(f"cannot build command: {exc}", type="negative")
            return None

    def _start(self) -> None:
        cmd = self._cmd()
        if not cmd:
            return
        try:
            RUNS.start(self.component, cmd)
        except WorkflowBusy as exc:
            ui.notify(str(exc), type="warning")
        self.refresh()

    def refresh(self) -> None:
        if self.timer.is_deleted or self.button.is_deleted \
                or self.status_label.is_deleted or self.log_label.is_deleted:
            return  # panel was cleared from the page; stop touching dead elements
        run_id = RUNS.latest(self.component)
        if run_id is None:
            self.button.enable()
            self.status_label.set_text("")
            self.log_label.set_text("(no output yet)")
            return
        st = RUNS.status(run_id)
        if st["state"] == "running":
            self.button.disable()
        else:
            self.button.enable()
        rc = st.get("returncode")
        rc_txt = "" if rc is None else f" (exit {rc})"
        self.status_label.set_text(f"{run_id}: {st['state']}{rc_txt}")
        lines = RUNS.tail(run_id, 300)
        if lines:
            self.log_label.set_text("\n".join(lines))
        elif st["state"] == "running":
            self.log_label.set_text("(waiting for output…)")
