"""Deterministic page observation via Playwright accessibility snapshot.

No CSS-selector scraping for content understanding: the a11y tree + body
innerText are the only page-understanding signals handed to the LLM.
"""

from __future__ import annotations

MAX_A11Y_NODES = 150
TEXT_HEAD_CHARS = 3000

_INTERACTIVE_ROLES = {
    "button", "link", "textbox", "searchbox", "combobox", "checkbox",
    "radio", "menuitem", "tab", "option", "switch", "slider",
}
_KEEP_ROLES = _INTERACTIVE_ROLES | {"heading"}

try:
    from browser_session_lib import classify_auth_state
except ImportError:  # pragma: no cover - standalone use without repo scripts
    def classify_auth_state(page, site="linkedin"):
        return ("UNKNOWN", "browser_session_lib unavailable")


def _condense_a11y(snapshot, cap: int = MAX_A11Y_NODES) -> list[dict]:
    """Flatten a Playwright page.accessibility.snapshot() tree."""
    out: list[dict] = []
    seen: set[tuple] = set()

    def walk(node):
        if node is None or len(out) >= cap:
            return
        role = (node.get("role") or "").lower()
        name = (node.get("name") or "").strip()
        value = (node.get("value") or "").strip()
        key = (role, name, value)
        interesting = (
            role in _KEEP_ROLES
            or (node.get("children") is None and (name or value))
        )
        if interesting and key not in seen:
            seen.add(key)
            entry = {"role": role}
            if name:
                entry["name"] = name[:120]
            if value and role in _INTERACTIVE_ROLES:
                entry["text"] = value[:120]
            out.append(entry)
        for child in node.get("children") or []:
            walk(child)
            if len(out) >= cap:
                return

    walk(snapshot)
    return out


def _a11y_outline_fallback(page) -> list[dict]:
    """Last-resort outline from body text headings when the tree fails."""
    try:
        text = page.inner_text("body")
    except Exception:
        return [{"role": "error", "name": "a11y extraction failed"}]
    entries = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            entries.append({"role": "text", "name": line[:120]})
        if len(entries) >= MAX_A11Y_NODES:
            break
    return entries or [{"role": "empty", "name": "no readable text"}]


def observe(page, session=None, site: str = "linkedin") -> dict:
    """Observe ``page`` deterministically. Never raises for page issues."""
    obs: dict = {}
    try:
        obs["url"] = page.url
    except Exception:
        obs["url"] = ""
    try:
        obs["title"] = page.title()
    except Exception:
        obs["title"] = ""

    outline: list[dict] | None = None
    try:
        snapshot = page.accessibility.snapshot(interesting_only=True)
        outline = _condense_a11y(snapshot)
    except Exception:
        outline = None
    if not outline:
        outline = _a11y_outline_fallback(page)
    obs["a11y_outline"] = outline

    try:
        obs["visible_text_head"] = (page.inner_text("body") or "")[:TEXT_HEAD_CHARS]
    except Exception:
        obs["visible_text_head"] = ""

    auth_state = "UNKNOWN"
    try:
        state, _marker = classify_auth_state(page, site=site)
        auth_state = state
    except Exception:
        pass
    obs["auth_state"] = auth_state

    if session is not None:
        try:
            session.log("observe", url=obs["url"], title=obs["title"][:100],
                        nodes=len(obs["a11y_outline"]), auth=auth_state)
        except Exception:
            pass
    return obs


def summarize_observation(obs: dict, max_nodes: int = 40) -> str:
    """Compact one-line-ish summary used in LLM history windows."""
    nodes = "; ".join(
        f"{n.get('role', '?')}:{n.get('name', '')[:60]}"
        for n in obs.get("a11y_outline", [])[:max_nodes]
    )
    return f"url={obs.get('url', '')} title={obs.get('title', '')[:80]} a11y=[{nodes}]"
