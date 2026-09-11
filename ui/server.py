"""Server lifecycle controls: start / stop / restart the UI server.

The UI runs on ``localhost:8080`` via ``start.sh`` / ``stop.sh`` at the repo
root. These helpers drive those scripts as *detached* processes so they keep
running even if this web app's process exits (which is exactly what happens
on Stop/Restart).
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("JOBHUNT_UI_PORT", "8080"))


def is_running() -> bool:
    """True when something accepts connections on the UI port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def _default_data_root() -> Path:
    """Default JOBHUNT_HOME for detached children: sibling data checkout
    (<container>/jobhunt-data) if present, else the repo-local fallback."""
    repo = Path(__file__).resolve().parent.parent
    sibling = repo.parent / "jobhunt-data"
    if sibling.is_dir():
        return sibling
    return repo / "jobhunt-data"


def _detached(cmd: list[str]) -> None:
    """Run a command fully detached so it survives this process exiting."""
    env = dict(os.environ)
    env.setdefault("JOBHUNT_HOME", str(_default_data_root()))
    subprocess.Popen(  # noqa: S603 - fixed internal scripts only
        cmd,
        cwd=str(REPO),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def start() -> None:
    """Start the UI server (no-op request if already running)."""
    _detached(["bash", str(REPO / "start.sh")])


def stop() -> None:
    """Stop the UI server. This web app's own process is killed too."""
    _detached(["bash", str(REPO / "stop.sh")])


def restart() -> None:
    """Stop then start again; start.sh refuses to double-start, so sequence."""
    script = (
        f'cd "{REPO}" && '
        f'"./stop.sh"; sleep 1; "./start.sh"'
    )
    _detached(["bash", "-c", script])
