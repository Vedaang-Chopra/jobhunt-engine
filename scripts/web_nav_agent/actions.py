"""Deterministic action executor through the Playwright sync API."""

from __future__ import annotations

from .observer import observe


class ActionRefused(Exception):
    """Raised when a GoalContract prohibits an action."""


def _resolve_locator(page, params: dict):
    """Resolve a locator from ref (role+name), selector, or text."""
    role = params.get("role")
    name = params.get("name") or params.get("ref")
    if role:
        loc = page.get_by_role(role, name=name, exact=False)
        if name is None:
            loc = page.get_by_role(role)
        return loc
    if params.get("selector"):
        return page.locator(params["selector"])
    if name:
        return page.get_by_text(name, exact=False)
    raise ValueError("click/type/extract needs 'ref' (role/name) or 'selector'")


def execute_action(page, action: dict, goal=None, session=None,
                   timeout_ms: int = 8000) -> dict:
    """Execute one validated action; return a result dict.

    Caller (agent.py) validates against GoalContract BEFORE calling this;
    as defense-in-depth we re-validate when a goal is supplied.
    """
    atype = str(action.get("type", "")).lower().strip()
    if goal is not None:
        ok, reason = goal.validate_action(action)
        if not ok:
            session and session.log("action_refused", type=atype, reason=reason)
            return {"type": atype, "status": "REFUSED", "error": reason}

    result: dict = {"type": atype}
    try:
        if atype == "navigate":
            page.goto(action["url"], wait_until="domcontentloaded",
                      timeout=timeout_ms * 2)
            result["status"] = "OK"
        elif atype == "click":
            loc = _resolve_locator(page, action)
            loc.first.click(timeout=timeout_ms)
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            result["status"] = "OK"
        elif atype == "type":
            loc = _resolve_locator(page, action)
            loc.first.fill(str(action.get("text", "")), timeout=timeout_ms)
            result["status"] = "OK"
        elif atype == "scroll":
            direction = str(action.get("direction", "down")).lower()
            amount = int(action.get("amount", 600))
            page.evaluate(
                "([dy]) => window.scrollBy(0, dy)",
                [amount if direction == "down" else -abs(amount)],
            )
            result["status"] = "OK"
        elif atype == "press_key":
            page.keyboard.press(str(action.get("key", "Enter")))
            result["status"] = "OK"
        elif atype == "wait":
            import time
            time.sleep(min(float(action.get("seconds", 1)), 10.0))
            result["status"] = "OK"
        elif atype == "extract":
            loc = _resolve_locator(page, action)
            result["value"] = loc.first.inner_text(timeout=timeout_ms)[:2000]
            result["status"] = "OK"
        else:
            result["status"] = "UNKNOWN_TYPE"
            result["error"] = f"no executor for action type '{atype}'"
    except Exception as exc:  # noqa: BLE001 — report, don't crash the loop
        result["status"] = "FAILED"
        result["error"] = f"{type(exc).__name__}: {exc}"

    if atype == "done":
        # done() is a control-flow signal handled by agent.py; nothing to do.
        pass
    else:
        try:
            result["observation"] = observe(page, session=session)
        except Exception as exc:  # noqa: BLE001
            result["observation"] = {"url": "", "title": "",
                                     "a11y_outline": [], "visible_text_head": "",
                                     "auth_state": "UNKNOWN",
                                     "observe_error": str(exc)}
    session and session.log("action", **{k: result.get(k)
                                         for k in ("type", "status", "error")})
    return result
