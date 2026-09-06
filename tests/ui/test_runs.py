"""Tests for the ui.runs background-run registry (Phase 4.1)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ui.runs import RunRegistry


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _wait(func, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if func():
            return True
        time.sleep(0.05)
    return False


def test_start_status_and_exit():
    reg = RunRegistry()
    run_id = reg.start("comp_a", _py("print('hello'); print('world')"))
    assert reg.status(run_id)["name"] == "comp_a"
    assert _wait(lambda: reg.status(run_id)["state"] == "done")
    st = reg.status(run_id)
    assert st["state"] == "done" and st["returncode"] == 0


def test_tail_streams_stdout():
    reg = RunRegistry()
    run_id = reg.start("comp_tail", _py("print('alpha'); print('beta')"))
    assert _wait(lambda: "beta" in reg.tail(run_id, 10))
    lines = reg.tail(run_id, 1)
    assert lines == ["beta"]
    assert len(reg.tail(run_id, 50)) >= 2


def test_duplicate_component_blocked_then_allowed_after_finish():
    reg = RunRegistry()
    first = reg.start("dup", _py("import time; time.sleep(3)"))
    with pytest.raises(RuntimeError):
        reg.start("dup", _py("print('nope')"))
    assert reg.cancel(first)["state"] == "cancelled"
    # After the live run is gone a new one may start.
    second = reg.start("dup", _py("print('ok')"))
    assert _wait(lambda: reg.status(second)["state"] == "done")
    assert reg.is_running("dup") is False


def test_cancel_kills_running_process():
    reg = RunRegistry()
    run_id = reg.start("killme", _py("import time; print('started', flush=True); time.sleep(30)"))
    assert _wait(lambda: "started" in reg.tail(run_id, 20))
    st = reg.cancel(run_id)
    assert st["state"] == "cancelled"
    assert not _wait(lambda: reg.status(run_id)["state"] == "running", timeout=1)


def test_failed_run_reports_failed_state():
    reg = RunRegistry()
    run_id = reg.start("fails", _py("raise SystemExit(3)"))
    assert _wait(lambda: reg.status(run_id)["state"] != "running")
    st = reg.status(run_id)
    assert st["state"] == "failed" and st["returncode"] == 3


def test_unknown_run_id_raises_and_tail_bounds_output():
    reg = RunRegistry()
    with pytest.raises(KeyError):
        reg.status("missing-999")
    run_id = reg.start("spam", _py(
        "print(('x'*80 + '\\n') * 5000, end='')"))
    assert _wait(lambda: reg.status(run_id)["state"] == "done")
    assert len(reg.tail(run_id, 5)) <= 5
