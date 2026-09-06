"""RunManager: canonical execution + run-record layer.

Every workflow run — whether triggered by the NiceGUI UI, a Hermes cron, or
manually — goes through here. It resolves the workflow from
``engine.workflows`` (single definition), enforces workflow-level and
browser-profile concurrency, persists durable run records to
``<data_root>/runs/runs.jsonl`` + per-run log files, and supports both:

  SCRIPT_RUN → subprocess.Popen (deterministic scripts)
  AGENT_RUN  → a REAL Hermes agent session via
               ``hermes --profile job-hunt -z "<workflow prompt>" --cli``.
               The child's stdout is watched for the session id so the run
               record carries ``agent_session_id``. No fake agents.

Run state survives UI refreshes and NiceGUI restarts: on startup,
``reconcile()`` re-attaches live children by pid or marks orphans FAILED
(INTERRUPTED). Logs are file-backed with a bounded in-memory tail.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import signal
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    from scripts import config_lib
except ImportError:  # direct script-style invocation
    import config_lib  # type: ignore[no-redef]

from engine.workflows import AGENT, SCRIPT, get_workflow

RUNS_DIR_NAME = "runs"
MAX_TAIL_LINES = 2000

# Status vocabulary
QUEUED = "QUEUED"
STARTING = "STARTING"
RUNNING = "RUNNING"
WAITING_FOR_AUTH = "WAITING_FOR_AUTH"
WAITING_FOR_USER = "WAITING_FOR_USER"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
INTERRUPTED = "INTERRUPTED"

LIVE_STATES = {QUEUED, STARTING, RUNNING, WAITING_FOR_AUTH, WAITING_FOR_USER}

_HERMES_BINARIES = [
    Path.home() / ".local" / "bin" / "hermes",
    Path("/usr/local/bin/hermes"),
]
_SESSION_ID_RE = re.compile(r"\b(\d{8}_\d{6}_[0-9a-f]{6})\b")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hermes_binary() -> str:
    for candidate in _HERMES_BINARIES:
        if candidate.exists():
            return str(candidate)
    return "hermes"


class RunHandle:
    """In-memory bookkeeping for one run (mirrors the persisted record)."""

    def __init__(self, record: dict):
        self.record = record
        self.proc: Optional[subprocess.Popen] = None
        self.lines: deque = deque(maxlen=MAX_TAIL_LINES)
        self.lock = threading.Lock()


class WorkflowBusy(RuntimeError):
    """Raised when a workflow already has a live run."""


class RunManager:
    def __init__(self, data_root: Optional[Path] = None):
        if data_root is None:
            data_root = Path(config_lib.data_root())
        self._dir = Path(data_root) / RUNS_DIR_NAME
        self._dir.mkdir(parents=True, exist_ok=True)
        self._records_path = self._dir / "runs.jsonl"
        self._handles: Dict[str, RunHandle] = {}
        self._lock = threading.RLock()
        self._seq = itertools.count(1)
        self.reconcile()

    # ------------------------------------------------------------ storage
    @property
    def records_path(self) -> Path:
        return self._records_path

    def _append_record(self, record: dict) -> None:
        with self._lock:
            with open(self._records_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _log_file(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.log"

    def _append_log(self, run_id: str, line: str) -> None:
        handle = self._handles.get(run_id)
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        stamped = f"[{stamp}] {line}"
        with open(self._log_file(run_id), "a", encoding="utf-8") as fh:
            fh.write(stamped + "\n")
        if handle is not None:
            with handle.lock:
                handle.lines.append(stamped)

    # ------------------------------------------------------------- lookup
    def _load_records(self) -> List[dict]:
        if not self._records_path.exists():
            return []
        out = []
        for raw in self._records_path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out

    def _live_run_for(self, workflow: str) -> Optional[str]:
        for run_id in reversed(list(self._handles)):
            handle = self._handles.get(run_id)
            if handle and handle.record["workflow"] == workflow \
                    and handle.record["status"] in LIVE_STATES:
                return run_id
        return None

    def get(self, run_id: str) -> dict:
        handle = self._handles.get(run_id)
        if handle is None:
            raise KeyError(f"unknown run_id: {run_id}")
        return dict(handle.record)

    def list_runs(self, limit: int = 50) -> List[dict]:
        """Newest-first view of all runs (in-memory first, then history)."""
        seen: Dict[str, dict] = {}
        for record in self._load_records():
            seen[record["run_id"]] = record
        for handle in self._handles.values():
            seen[handle.record["run_id"]] = dict(handle.record)
        runs = sorted(seen.values(), key=lambda r: r["created_at"],
                      reverse=True)
        return runs[:limit]

    def latest(self, workflow: str) -> Optional[str]:
        for record in reversed(self.list_runs(limit=500)):
            if record["workflow"] == workflow:
                return record["run_id"]
        return None

    def is_running(self, workflow: str) -> bool:
        return self._live_run_for(workflow) is not None

    def tail(self, run_id: str, n_lines: int = 100) -> List[str]:
        handle = self._handles.get(run_id)
        if handle is not None:
            with handle.lock:
                lines = list(handle.lines)
            return lines[-max(n_lines, 0):]
        log = self._log_file(run_id)
        if log.exists():
            lines = log.read_text(encoding="utf-8").splitlines()
            return lines[-max(n_lines, 0):]
        return []

    # -------------------------------------------------------------- start
    def start(self, workflow: str, trigger: str = "ui",
              params: Optional[dict] = None) -> str:
        wf = get_workflow(workflow)
        with self._lock:
            live = self._live_run_for(workflow)
            if live:
                raise WorkflowBusy(
                    f"'{workflow}' already running ({live}); duplicate "
                    "execution prevented")
            run_id = (f"{workflow}-{time.strftime('%Y%m%d-%H%M%S')}-"
                      f"{next(self._seq)}")
            record = {
                "run_id": run_id,
                "workflow": workflow,
                "execution_type": wf.execution_type,
                "trigger": trigger,
                "params": params or {},
                "status": STARTING,
                "created_at": _utcnow_iso(),
                "started_at": _utcnow_iso(),
                "finished_at": None,
                "agent_session_id": None,
                "browser_session_id":
                    wf.persistent_browser_profile if wf.browser_required
                    else None,
                "pid": None,
                "exit_code": None,
                "current_goal": wf.description,
                "current_action": "starting",
                "logs": str(self._log_file(run_id)),
                "result": None,
                "error": None,
            }
            handle = RunHandle(record)
            self._handles[run_id] = handle
            self._append_record(record)
            self._append_log(run_id, f"run started "
                                     f"(trigger={trigger}, type={wf.execution_type})")

        threading.Thread(target=self._launch, args=(handle, wf),
                         daemon=True).start()
        return run_id

    def _launch(self, handle: RunHandle, wf) -> None:
        run_id = handle.record["run_id"]
        try:
            # Respect a cancel that landed before the spawn happened.
            with handle.lock:
                if handle.record["status"] not in LIVE_STATES:
                    return
                cmd = (
                    [_hermes_binary(), "--profile", "job-hunt",
                     "-z", wf.prompt.format(trigger="ui"), "--cli"]
                    if wf.is_agent else [str(c) for c in wf.cmd_builder()])
            proc = subprocess.Popen(  # noqa: S603 - fixed internal commands
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(Path(__file__).resolve().parents[1]),
                start_new_session=True,
            )
            with handle.lock:
                if handle.record["status"] not in LIVE_STATES:
                    # Cancelled between spawn and attach: kill the orphan.
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        proc.terminate()
                    return
                handle.proc = proc
                handle.record["pid"] = proc.pid
            self._update(handle, status=RUNNING, pid=proc.pid,
                         current_action="executing")
            self._pump(handle)
        except Exception as exc:  # noqa: BLE001 - launch must not crash caller
            self._update(handle, status=FAILED,
                         error=f"launch failed: {exc}",
                         finished_at=_utcnow_iso())

    # --------------------------------------------------------------- pump
    def _pump(self, handle: RunHandle) -> None:
        run_id = handle.record["run_id"]
        proc = handle.proc
        session_id = None
        try:
            stdout = proc.stdout if proc is not None else None
            if stdout is not None:
                for line in stdout:
                    line = line.rstrip("\n")
                    if line:
                        self._append_log(run_id, line)
                        if session_id is None:
                            match = _SESSION_ID_RE.search(line)
                            if match:
                                session_id = match.group(1)
                                self._update(handle,
                                             agent_session_id=session_id)
                                self._append_log(run_id,
                                                 f"agent session: {session_id}")
            returncode = proc.wait() if proc is not None else -1
        except Exception:  # noqa: BLE001
            returncode = proc.poll() if proc is not None else -1
            if returncode is None:
                returncode = -1
        with handle.lock:
            record = handle.record
            record["exit_code"] = returncode
            if record["status"] == CANCELLED:
                pass  # cancel() owns terminal state
            elif returncode == 0:
                record["status"] = SUCCEEDED
            else:
                record["status"] = FAILED
            record["finished_at"] = _utcnow_iso()
            final = dict(record)
        self._append_record(final)

    # ------------------------------------------------------------- update
    def _update(self, handle: RunHandle, **fields) -> None:
        with handle.lock:
            handle.record.update(fields)

    def set_status(self, run_id: str, status: str,
                   current_action: Optional[str] = None) -> dict:
        handle = self._get(run_id)
        fields = {"status": status}
        if current_action is not None:
            fields["current_action"] = current_action
        self._update(handle, **fields)
        self._append_log(run_id, f"status → {status}")
        return self.get(run_id)

    # ------------------------------------------------------------- cancel
    def cancel(self, run_id: str, timeout: float = 5.0) -> dict:
        handle = self._get(run_id)
        with handle.lock:
            if handle.record["status"] not in LIVE_STATES:
                return self.get(run_id)
            handle.record["status"] = CANCELLED
            proc = handle.proc
        self._append_log(run_id, "cancel requested")
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    proc.kill()
                proc.wait(timeout=timeout)
            self._append_log(run_id, f"process stopped (exit {proc.returncode})")
        with handle.lock:
            record = handle.record
            record["finished_at"] = _utcnow_iso()
            if proc is not None:
                record["exit_code"] = proc.returncode
            final = dict(record)
        self._append_record(final)
        return final

    # --------------------------------------------------------- reconcile
    def reconcile(self) -> int:
        """Crash/restart recovery: reattach live pids, fail orphans."""
        fixed = 0
        for record in self._load_records():
            if record["run_id"] in self._handles:
                continue
            if record["status"] not in LIVE_STATES:
                # Recreate completed handles lazily? Not needed; history only.
                continue
            run_id = record["run_id"]
            pid = record.get("pid")
            alive = False
            proc = None
            if pid:
                try:
                    os.kill(pid, 0)
                    alive = True
                    # Reattach: adopt without owning pipes.
                    proc = subprocess.Popen.__new__(subprocess.Popen)
                    proc.pid = pid
                    proc.returncode = None
                    proc.stdout = None
                except OSError:
                    alive = False
            handle = RunHandle(dict(record))
            handle.proc = proc
            self._handles[run_id] = handle
            if alive:
                self._append_log(run_id, "reconciled after restart: process "
                                         "still alive; reattached")
                threading.Thread(target=self._reap_adopted,
                                 args=(handle,), daemon=True).start()
            else:
                record.update(status=INTERRUPTED,
                              error="interrupted by restart; process gone",
                              finished_at=_utcnow_iso())
                handle.record = record
                self._append_record(dict(record))
                self._append_log(run_id, "reconciled after restart: process "
                                         "gone → INTERRUPTED")
                fixed += 1
        return fixed

    def _reap_adopted(self, handle: RunHandle) -> None:
        run_id = handle.record["run_id"]
        pid = handle.record.get("pid")
        if pid is None:
            return
        while True:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(2)
        with handle.lock:
            record = handle.record
            if record["status"] in LIVE_STATES:
                record["status"] = INTERRUPTED
                record["error"] = "process exited during detached period"
                record["finished_at"] = _utcnow_iso()
                self._append_record(dict(record))
        self._append_log(run_id, "detached process exited → reconciled")

    # ------------------------------------------------------------- helper
    def _get(self, run_id: str) -> RunHandle:
        handle = self._handles.get(run_id)
        if handle is None:
            raise KeyError(f"unknown run_id: {run_id}")
        return handle


MANAGER: Optional[RunManager] = None
_MANAGER_LOCK = threading.Lock()


def get_manager() -> RunManager:
    global MANAGER
    with _MANAGER_LOCK:
        if MANAGER is None:
            MANAGER = RunManager()
        return MANAGER
