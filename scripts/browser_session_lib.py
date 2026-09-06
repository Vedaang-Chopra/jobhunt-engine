"""Canonical BrowserSessionManager for ALL Hermes browser automation.

This is the ONLY sanctioned way any Hermes workflow — cron job, scheduled job,
UI button trigger, manual agent run, or domain sweep — obtains a browser.
Do not call playwright launch APIs directly; do not open raw CDP sockets;
do not invent another profile directory.

Lifecycle implemented here:

    request browser
          |
    shared automation Chrome already serving CDP on :9333?
          |-- YES --> attach, reuse/create tab
          |
          NO --> start it ONCE via scripts/automation_chrome.sh
                 (canonical persistent user-data-dir
                  ~/.hermes/browser-profiles/job-hunt) and attach

Guarantees:
  * one persistent profile, never ephemeral, never per-run
  * never --isolated / incognito for auth-requiring workflows
  * at most one Chrome process against the profile: cross-process
    file lock (flock) with ownership metadata + stale-lock recovery
    guards both attach and fallback-launch paths
  * authentication-state inspection exposed as check_auth_state()
    with AUTHENTICATED / AUTH_REQUIRED / CHALLENGE_OR_2FA / UNKNOWN
  * run observability appended to <data_root>/browser_runs/run_log.jsonl
    (never logs cookies/tokens/profile contents)
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if str(os.path.join(REPO, "scripts")) not in sys.path:
    sys.path.insert(0, str(os.path.join(REPO, "scripts")))

try:
    from scripts import config_lib  # type: ignore
except ImportError:  # pragma: no cover - direct script execution
    import config_lib  # type: ignore

AUTOMATION_CDP_PORT = int(os.environ.get("JOBHUNT_CDP_PORT", "9333"))
LEGACY_CDP_PORTS: list[int] = []  # legacy :9222 path retired 2026-08-26
PROFILE_DIR = os.environ.get(
    "JOBHUNT_BROWSER_PROFILE",
    str(Path.home() / ".hermes" / "browser-profiles" / "job-hunt"),
)
AUTOMATION_SCRIPT = os.path.join(REPO, "scripts", "automation_chrome.sh")
LOCK_DIR = os.path.join(
    os.environ.get("JOBHUNT_HOME", str(config_lib.data_root())), "browser_runs"
)

# Authentication lifecycle states -------------------------------------------
AUTHENTICATED = "AUTHENTICATED"
AUTH_REQUIRED = "AUTH_REQUIRED"
CHALLENGE_OR_2FA = "CHALLENGE_OR_2FA"
UNKNOWN = "UNKNOWN"


def _cdp_ok(port: int) -> bool:
    """True only when the DevTools JSON discovery endpoint answers 200."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/version",
            headers={"Connection": "close"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 - any failure means unusable
        return False


class ProfileLock:
    """Cross-process advisory lock around profile acquisition.

    A lock file under <data_root>/browser_runs/ records ownership metadata
    (pid, host, command line, acquired-at). Stale locks — owner pid no longer
    alive — are recovered automatically. The flock is held only while
    acquiring/launching so concurrent cron jobs serialize their launch
    attempts instead of racing two Chrome processes into one profile.
    """

    def __init__(self, name: str = "profile.job-hunt.lock") -> None:
        os.makedirs(LOCK_DIR, exist_ok=True)
        self.path = os.path.join(LOCK_DIR, name)
        self._fh = None

    def __enter__(self) -> "ProfileLock":
        fh = open(self.path, "a+")
        self._fh = fh
        fcntl.flock(fh, fcntl.LOCK_EX)
        content = ""
        try:
            fh.seek(0)
            content = fh.read()
        except OSError:
            pass
        owner = {}
        try:
            owner = json.loads(content.strip() or "{}")
        except json.JSONDecodeError:
            pass
        if owner and not _pid_alive(owner.get("pid")):
            # stale lock metadata from a dead process: recover
            print(
                f"[browser] recovering stale profile lock "
                f"(dead owner pid {owner.get('pid')})",
                file=sys.stderr,
            )
        meta = {
            "pid": os.getpid(),
            "host": os.uname().nodename,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
            "cmd": sys.argv[:3] if sys.argv else [],
        }
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(json.dumps(meta))
        self._fh.flush()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()
        except Exception:  # noqa: BLE001
            pass
        return False


def _pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by someone else



def _profile_locked() -> bool:
    """True when the job-hunt profile directory holds a SingletonLock."""
    lock_path = os.path.join(PROFILE_DIR, "SingletonLock")
    return os.path.exists(lock_path)

def log_run(event: dict) -> None:
    """Append one observability event to browser_runs/run_log.jsonl."""
    try:
        os.makedirs(LOCK_DIR, exist_ok=True)
        event = dict(event)
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(os.path.join(LOCK_DIR, "run_log.jsonl"), "a") as fh:
            fh.write(json.dumps(event, default=str) + "\n")
    except Exception:  # noqa: BLE001 - logging must never break a run
        pass


def ensure_automation_chrome(timeout_s: int = 30) -> bool:
    """Start the shared automation Chrome if not already up. Idempotent."""
    if _cdp_ok(AUTOMATION_CDP_PORT):
        return True
    if not os.path.exists(AUTOMATION_SCRIPT):
        raise RuntimeError(f"automation script missing: {AUTOMATION_SCRIPT}")
    # Serialize launches across processes so two crons can't race two Chromes.
    with ProfileLock("chrome-launch.lock"):
        if _cdp_ok(AUTOMATION_CDP_PORT):  # re-check inside lock
            return True
        subprocess.run(
            ["bash", AUTOMATION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if _cdp_ok(AUTOMATION_CDP_PORT):
                return True
            time.sleep(1)
    return False


class BrowserSession:
    """Logged-in browser handle. Use as a context manager."""

    def __init__(self, playwright, browser, context, page, mode: str,
                 reused: bool = False) -> None:
        self._pw = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self.mode = mode  # 'cdp' or 'persistent'
        self.reused = reused
        self.run_meta: dict = {}

    # -- observability ------------------------------------------------------
    def log(self, action: str, **fields) -> None:
        log_run({"action": action, **self.run_meta, **fields})

    # -- new-tab helper (multi-task sharing of one browser) ------------------
    def new_page(self):
        """Create an additional tab in the shared context."""
        p = self.context.new_page()
        self.log("tab_opened", url=p.url)
        return p

    # -- authentication lifecycle -------------------------------------------
    def check_auth_state(self, site: str = "linkedin") -> str:
        """Inspect the current page semantically and classify auth state.

        Never retries, never bypasses challenges — detection only.
        """
        state, marker = classify_auth_state(self.page, site)
        self.log("auth_state", site=site, state=state, marker=marker)
        return state

    def close(self) -> None:
        try:
            if self.mode == "persistent":
                # Only tear down what we launched.
                self.context.close()
            else:
                # Never kill the shared automation Chrome; drop only our
                # Playwright-side connection so other tasks keep working.
                self.browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._pw.stop()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False


# --- semantic auth classification ------------------------------------------
LOGIN_MARKERS = ("/login", "authwall", "signin", "session-redirect")
CHALLENGE_MARKERS = ("checkpoint", "challenge", "verify", "two-factor",
                     "security verification", "unusual sign-in")


def classify_auth_state(page, site: str = "linkedin") -> tuple[str, str]:
    """Return (state, evidence_marker) from URL + visible page text."""
    url = ""
    text = ""
    try:
        url = (page.url or "").lower()
    except Exception:  # noqa: BLE001
        pass
    for marker in CHALLENGE_MARKERS:
        if marker in url:
            return CHALLENGE_OR_2FA, marker
    for marker in LOGIN_MARKERS:
        if marker in url:
            # challenge pages can also contain login words; challenge wins via
            # the earlier loop ordering only when present in URL, so re-check
            # body text before declaring plain AUTH_REQUIRED
            break
    try:
        text = (page.inner_text("body")[:4000]).lower()
    except Exception:  # noqa: BLE001
        text = ""
    for marker in CHALLENGE_MARKERS:
        if marker in text:
            return CHALLENGE_OR_2FA, marker
    for marker in LOGIN_MARKERS:
        if marker in url or marker in text:
            return AUTH_REQUIRED, marker
    if not url or url.startswith(("about:", "chrome:")):
        return UNKNOWN, "no page loaded"
    # Site-specific positive signals
    if site == "linkedin" and "linkedin.com" in url:
        if "/feed" in url or "mynetwork" in url or "/jobs/" in url \
                or "/search/results" in url or "/notifications" in url:
            return AUTHENTICATED, "in-app url"
    return UNKNOWN, f"no decisive signal at {url}"


def open_logged_in_session(headless: bool = False,
                           source: str = "unknown") -> BrowserSession:
    """Return a BrowserSession attached to the canonical logged-in browser.

    Resolution order:
      1. Attach over CDP to the shared automation Chrome on :9333,
         auto-starting it first when it isn't running.
      2. Fallback: persistent context directly on the job-hunt profile
         (only reachable while holding the profile lock, i.e. when the
         LaunchAgent could not bring Chrome up).

    Raises RuntimeError with an actionable message when nothing works.
    """
    from playwright.sync_api import sync_playwright  # deferred import

    launched_chrome = False
    if not _cdp_ok(AUTOMATION_CDP_PORT):
        ensure_automation_chrome()
        launched_chrome = True

    pw = sync_playwright().start()

    if _cdp_ok(AUTOMATION_CDP_PORT):
        last_exc: Exception | None = None
        for attempt in range(2):  # one retry: the attach handshake is flaky
            try:
                browser = pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{AUTOMATION_CDP_PORT}"
                )
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                sess = BrowserSession(pw, browser, ctx, page, "cdp",
                                      reused=not launched_chrome)
                sess.run_meta = {
                    "source": source,
                    "mode": "cdp",
                    "profile": PROFILE_DIR,
                    "browser_reused": sess.reused,
                }
                log_run({"action": "session_open", **sess.run_meta})
                return sess
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                print(
                    f"[browser] CDP attach on :{AUTOMATION_CDP_PORT} failed "
                    f"(attempt {attempt + 1}/2): {exc}",
                    file=sys.stderr,
                )
                time.sleep(1.5)

    # Last resort: persistent context on the canonical profile. Guarded by
    # the cross-process profile lock; refuses cleanly when another Chrome
    # holds the SingletonLock without exposing CDP.
    if not os.path.isdir(PROFILE_DIR):
        pw.stop()
        raise RuntimeError(
            f"No CDP endpoint on :{AUTOMATION_CDP_PORT} and no browser profile "
            f"at {PROFILE_DIR}. Run:\n"
            f"  bash {AUTOMATION_SCRIPT}"
        )
    singleton = os.path.join(PROFILE_DIR, "SingletonLock")
    if os.path.exists(singleton):
        pw.stop()
        raise RuntimeError(
            f"Profile {PROFILE_DIR} is held by another Chrome (SingletonLock) "
            f"without a CDP endpoint on :{AUTOMATION_CDP_PORT}. Quit that "
            f"Chrome or run: bash {AUTOMATION_SCRIPT}"
        )
    with ProfileLock():
        try:
            ctx = pw.chromium.launch_persistent_context(PROFILE_DIR, headless=headless)
        except Exception as exc:  # noqa: BLE001
            pw.stop()
            raise RuntimeError(
                f"Could not launch persistent context on {PROFILE_DIR}: {exc}. "
                f"Prefer the shared Chrome: bash {AUTOMATION_SCRIPT}"
            ) from exc
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        sess = BrowserSession(pw, None, ctx, page, "persistent", reused=False)
        sess.run_meta = {
            "source": source,
            "mode": "persistent",
            "profile": PROFILE_DIR,
            "browser_reused": False,
        }
        log_run({"action": "session_open", **sess.run_meta})
        return sess


# Back-compat alias used by older sweeps.
ensure_shared_browser = ensure_automation_chrome

