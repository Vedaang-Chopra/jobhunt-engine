"""GoalContract: declarative bounds for a web-navigation run.

Plain class (no pydantic), loadable from a dict or YAML file.
"""

from __future__ import annotations

import fnmatch
from urllib.parse import urlparse

DEFAULT_PROHIBITED = [
    "submit application",
    "send message",
    "post",
    "comment",
    "modify settings",
]

DEFAULT_ALLOWED_ACTIONS = [
    "navigate", "click", "type", "scroll", "press_key", "wait",
    "extract", "done",
]


class GoalContract:
    """What the agent may do, where, and for how long."""

    def __init__(self, description: str = "",
                 success_conditions: list | None = None,
                 stop_conditions: list | None = None,
                 allowed_actions: list | None = None,
                 prohibited_actions: list | None = None,
                 max_actions: int = 40,
                 max_seconds: int = 600,
                 allowed_domains: list | None = None):
        self.description = description or ""
        self.success_conditions = list(success_conditions or [])
        self.stop_conditions = list(stop_conditions or [])
        self.allowed_actions = list(allowed_actions or DEFAULT_ALLOWED_ACTIONS)
        self.prohibited_actions = [p.lower() for p in
                                   (prohibited_actions
                                    if prohibited_actions is not None
                                    else DEFAULT_PROHIBITED)]
        self.max_actions = int(max_actions)
        self.max_seconds = int(max_seconds)
        self.allowed_domains = list(allowed_domains or [])

    # ------------------------------------------------------------------ load

    @classmethod
    def from_dict(cls, data: dict) -> "GoalContract":
        data = dict(data or {})
        return cls(
            description=data.get("description", ""),
            success_conditions=data.get("success_conditions"),
            stop_conditions=data.get("stop_conditions"),
            allowed_actions=data.get("allowed_actions"),
            prohibited_actions=data.get("prohibited_actions"),
            max_actions=data.get("max_actions", 40),
            max_seconds=data.get("max_seconds", 600),
            allowed_domains=data.get("allowed_domains"),
        )

    @classmethod
    def from_yaml(cls, path) -> "GoalContract":
        import yaml
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)

    def to_prompt_text(self) -> str:
        lines = [f"GOAL: {self.description}"]
        if self.success_conditions:
            lines.append("Success when: " + "; ".join(self.success_conditions))
        if self.stop_conditions:
            lines.append("Stop when: " + "; ".join(self.stop_conditions))
        lines.append("Allowed actions: " + ", ".join(self.allowed_actions))
        if self.prohibited_actions:
            lines.append("NEVER: " + ", ".join(self.prohibited_actions))
        if self.allowed_domains:
            lines.append("Allowed domains: " + ", ".join(self.allowed_domains))
        return "\n".join(lines)

    # -------------------------------------------------------------- validate

    @staticmethod
    def _domain_allowed(url: str, patterns: list[str]) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            # file:// and about:blank etc. — only allowed when no domain
            # restrictions are configured.
            scheme = urlparse(url).scheme.lower()
            return scheme in ("file", "about", "data") or not scheme
        return any(fnmatch.fnmatch(host, "*" + p.lstrip(".").lower())
                   for p in patterns)

    def validate_action(self, action: dict) -> tuple[bool, str]:
        """Return (ok, reason). Deterministic guardrail — no LLM involved."""
        if not isinstance(action, dict) or not action.get("type"):
            return False, "malformed action: missing 'type'"
        atype = str(action["type"]).lower().strip()
        if atype not in {a.lower() for a in self.allowed_actions}:
            return False, f"action type '{atype}' is not in allowed_actions"
        low = atype.replace("_", " ").replace("-", " ")
        for banned in self.prohibited_actions:
            b = banned.lower().strip()
            if not b:
                continue
            if b == low or b in low:
                return False, f"action '{atype}' is prohibited by goal ({b})"
        if atype == "navigate":
            url = str(action.get("url") or "")
            if not url:
                return False, "navigate requires 'url'"
            if self.allowed_domains and \
                    not self._domain_allowed(url, self.allowed_domains):
                return False, (f"navigate target '{url}' is outside "
                               f"allowed_domains {self.allowed_domains}")
        if atype == "wait":
            try:
                secs = float(action.get("seconds", 1))
            except (TypeError, ValueError):
                return False, "wait requires numeric 'seconds'"
            if secs <= 0 or secs > 10:
                return False, "wait seconds must be in (0, 10]"
        return True, ""
