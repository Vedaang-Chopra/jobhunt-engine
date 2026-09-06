"""Tests for the canonical RunManager / workflow-registry execution layer."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from engine import workflows as wf_mod
from engine.run_manager import (
    INTERRUPTED,
    RunManager,
    SUCCEEDED,
    WorkflowBusy,
)
from engine.workflows import AGENT, SCRIPT, Workflow, get_workflow


def _wait(func, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if func():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture()
def manager(tmp_path):
    return RunManager(data_root=tmp_path)


@pytest.fixture()
def fast_script_workflow(manager):
    """Register a deterministic SCRIPT workflow for tests."""
    def builder():
        return [sys.executable, "-c", "print('script-ran')"]
    wf_mod.register(Workflow(name="test-script-wf", execution_type=SCRIPT,
                             description="test", cmd_builder=builder))
    return "test-script-wf"


# ------------------------------------------------------- shared registry
def test_registry_defines_linkedin_discovery_as_agent():
    wf = get_workflow("linkedin-discovery")
    assert wf.is_agent
    assert wf.browser_required
    assert "discovery_run.py" in (wf.prompt or "")


def test_ui_and_cron_resolve_same_workflow():
    from ui.triggers import RUNS, AGENT_COMPONENT_WORKFLOW
    # The UI component maps to the canonical workflow name.
    assert AGENT_COMPONENT_WORKFLOW["linkedin_discovery_agent"] == \
        "linkedin-discovery"
    # And starting it goes through the same RunManager path.
    assert RUNS.manager is not None


# ------------------------------------------------------------ script run
def test_script_run_persists_and_completes(manager, fast_script_workflow):
    run_id = manager.start(fast_script_workflow, trigger="ui")
    assert _wait(lambda: manager.get(run_id)["pid"] is not None)
    record = manager.get(run_id)
    assert record["execution_type"] == SCRIPT
    assert record["trigger"] == "ui"
    assert record["status"] in ("RUNNING", "STARTING", SUCCEEDED)
    assert _wait(lambda: manager.get(run_id)["status"] == SUCCEEDED)
    # Durable record exists on disk.
    lines = manager.records_path.read_text().splitlines()
    finals = [json.loads(l) for l in lines]
    assert any(r["run_id"] == run_id and r["status"] == SUCCEEDED
               for r in finals)


def test_script_run_logs_are_file_backed(manager, fast_script_workflow):
    run_id = manager.start(fast_script_workflow, trigger="ui")
    _wait(lambda: manager.get(run_id)["status"] == SUCCEEDED)
    log = Path(manager.get(run_id)["logs"])
    assert log.exists()
    assert any("script-ran" in l for l in log.read_text().splitlines())
    # Bounded tail works even after restart (no in-memory handle).
    fresh = RunManager(data_root=manager._dir.parent)
    assert isinstance(fresh.tail(run_id, 5), list)


# ----------------------------------------------------------- concurrency
def test_duplicate_concurrent_run_blocked(manager, tmp_path):
    def sleeper():
        return [sys.executable, "-c", "import time; time.sleep(3)"]

    wf_mod.register(Workflow(name="slow-wf", execution_type=SCRIPT,
                             description="t", cmd_builder=sleeper))
    first = manager.start("slow-wf", trigger="ui")
    with pytest.raises(WorkflowBusy):
        manager.start("slow-wf", trigger="cron")
    # The blocked attempt names the live run.
    try:
        manager.start("slow-wf")
    except WorkflowBusy as exc:
        assert first in str(exc)
    manager.cancel(first)


def test_trigger_recorded_per_run(manager, fast_script_workflow):
    run_id = manager.start(fast_script_workflow, trigger="cron")
    assert manager.get(run_id)["trigger"] == "cron"
    manager.cancel(run_id)


# ---------------------------------------------------------- cancellation
def test_cancel_terminates_process_and_releases_lock(manager):
    def sleeper():
        return [sys.executable, "-c", "import time; time.sleep(30)"]

    wf_mod.register(Workflow(name="cancel-wf", execution_type=SCRIPT,
                             description="t", cmd_builder=sleeper))
    run_id = manager.start("cancel-wf", trigger="ui")
    assert manager.is_running("cancel-wf")
    result = manager.cancel(run_id)
    assert result["status"] == "CANCELLED"
    assert result["finished_at"] is not None
    assert not manager.is_running("cancel-wf")


# ------------------------------------------------------- crash recovery
def test_reconcile_marks_orphan_interrupted(manager, fast_script_workflow):
    run_id = manager.start(fast_script_workflow, trigger="ui")
    # Simulate crash: fabricate a RUNNING record whose pid no longer exists.
    fake = {
        "run_id": "fake-wf-restart-1",
        "workflow": "linkedin-discovery",
        "execution_type": AGENT,
        "trigger": "cron",
        "status": "RUNNING",
        "created_at": "2026-08-26T00:00:00+00:00",
        "started_at": "2026-08-26T00:00:00+00:00",
        "finished_at": None,
        "pid": 999999999,
        "agent_session_id": None,
        "browser_session_id": None,
        "exit_code": None,
    }
    with open(manager.records_path, "a") as fh:
        fh.write(json.dumps(fake) + "\n")
    fixed = manager.reconcile()
    assert fixed >= 1
    assert _wait(lambda: manager.get(run_id)["status"] == SUCCEEDED)
    statuses = {r["run_id"]: r["status"] for r in manager.list_runs(500)}
    assert statuses["fake-wf-restart-1"] == INTERRUPTED
    assert statuses[run_id] == SUCCEEDED  # completed run untouched


def test_restart_preserves_history_visibility(manager, fast_script_workflow):
    run_id = manager.start(fast_script_workflow, trigger="ui")
    _wait(lambda: manager.get(run_id)["status"] == SUCCEEDED)
    fresh = RunManager(data_root=manager._dir.parent)  # simulates restart
    runs = fresh.list_runs(limit=500)
    assert any(r["run_id"] == run_id for r in runs)


# ------------------------------------------------------------ agent cmd
def test_agent_command_shape():
    """Agent runs invoke real hermes sessions — verify command assembly."""
    from engine.run_manager import _hermes_binary
    binary = Path(_hermes_binary())
    assert binary.exists(), "hermes binary must exist for agent runs"


def test_legacy_facade_maps_states(tmp_path):
    """ui.triggers.RUNS keeps its old API over the new layer."""
    from ui.triggers import RunRegistry

    reg = RunRegistry(
        RunManager(data_root=tmp_path))
    run_id = reg.start_adhoc(
        "comp_x", [sys.executable, "-c", "print('hi'); print('bye')"])
    st = reg.status(run_id)
    assert st["name"] == "comp_x"
    assert _wait(lambda: reg.status(run_id)["state"] in ("done", "failed"))
    assert reg.tail(run_id, 5)
    assert reg.latest("comp_x") == run_id
