"""Resilient provider-chain LLM client for the search-strategy layer.

Walks the provider chain from ``web_nav_agent._llm_config_fallback.llm_config()``
(openrouter -> nvidia -> custom, priority-ordered) using OpenAI-compatible SDK
clients. A provider attempt is retried on the *next* entry when it fails with a
retryable provider failure (HTTP 429, timeout, connection error) or returns an
empty/short completion (< ``MIN_CHARS`` chars — some models return empty text
under small token budgets; the 4000-token default mitigates this). The first
successful non-empty completion is returned.

No raw HTTP here: every call goes through the ``openai`` SDK client built by
:meth:`build_client`. Tests inject fake clients via the ``clients`` parameter.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from web_nav_agent._llm_config_fallback import llm_config
except ImportError:  # pragma: no cover - alternate import root
    try:
        from scripts.web_nav_agent._llm_config_fallback import llm_config
    except ImportError:
        llm_config = None

MIN_CHARS = 50
DEFAULT_TEMPERATURE = 0.4
DEFAULT_MAX_TOKENS = 4000


class AllProvidersFailedError(RuntimeError):
    """Raised when every provider in the chain failed; message carries the
    per-provider error summary."""

    def __init__(self, errors: list[str], reason: str = ""):
        lines = ["All LLM providers failed."]
        if reason:
            lines.append(f"Reason: {reason}")
        if errors:
            lines.append("Per-provider summary:")
            lines.extend(f"  - {e}" for e in errors)
        super().__init__("\n".join(lines))
        self.errors = list(errors)


# --- retryability classification ----------------------------------------------


def is_retryable_failure(exc: BaseException) -> bool:
    """True for HTTP 429, timeout, connection errors (duck-typed so tests can
    use plain exception objects without importing openai)."""
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    names = {type(exc).__name__.lower(),
             str(getattr(exc, "__name__", "")).lower()}
    if any(tok in n for n in names for tok in
           ("ratelimit", "timeout", "connection")):
        return True
    text = str(exc).lower()
    return any(tok in text for tok in ("rate limit", "timed out", "timeout",
                                       "connection error", "connection reset"))


def _describe_error(exc: BaseException) -> str:
    """One-line provider-error description used in failure summaries."""
    name = getattr(exc, "__name__", None) or type(exc).__name__
    status = getattr(exc, "status_code", None)
    suffix = f" (HTTP {status})" if status else ""
    return f"{name}{suffix}: {str(exc)[:200]}"


def _is_short_completion(text: str) -> bool:
    return len((text or "").strip()) < MIN_CHARS


# --- client construction -------------------------------------------------------


def build_client(entry: dict):
    """Build one OpenAI-compatible client for a single llm_config() entry."""
    from openai import OpenAI

    return OpenAI(base_url=entry["base_url"], api_key=entry["key"])


def _attempts_from_config(entries=None):
    """Expand config entries into per-(client, model) attempts, priority order."""
    entries = entries if entries is not None else (llm_config() if llm_config else [])
    attempts = []
    for entry in entries:
        client = build_client(entry)
        models = entry.get("models") or []
        name = entry.get("name") or "provider"
        for model in models:
            attempts.append({
                "client": client,
                "model": model,
                "label": f"{name}/{model}",
            })
    return attempts


def _attempts_from_clients(clients):
    """Wrap injected clients; label/model read off duck-typed attributes."""
    attempts = []
    for i, client in enumerate(clients):
        model = getattr(client, "model_name", None)
        label = getattr(client, "provider_label", None) or f"client-{i}"
        attempts.append({"client": client, "model": model, "label": label})
    return attempts


# --- public API ----------------------------------------------------------------


def chat(messages: list[dict],
         temperature: float = DEFAULT_TEMPERATURE,
         max_tokens: int = DEFAULT_MAX_TOKENS,
         clients: list | None = None) -> str:
    """Run a chat completion against the provider chain; return the first
    successful non-empty (>={MIN_CHARS} char) completion text.

    ``clients`` allows dependency injection of pre-built (or fake) clients in
    tests; when omitted the chain comes from ``llm_config()``.
    """
    attempts = (_attempts_from_clients(clients) if clients is not None
                else _attempts_from_config())
    if not attempts:
        raise AllProvidersFailedError([], reason="no providers configured")

    errors: list[str] = []
    for attempt in attempts:
        client = attempt["client"]
        kwargs = {"messages": messages,
                  "temperature": temperature,
                  "max_tokens": max_tokens}
        if attempt["model"]:
            kwargs["model"] = attempt["model"]
        try:
            response = client.chat.completions.create(**kwargs)
            text = ""
            choices = getattr(response, "choices", None)
            if choices:
                text = getattr(choices[0].message, "content", None) or ""
            if _is_short_completion(text):
                errors.append(
                    f"{attempt['label']}: short/empty completion "
                    f"({len(text.strip())} chars < {MIN_CHARS})")
                continue
            return text.strip()
        except Exception as exc:  # noqa: BLE001 - classify then fall through
            if is_retryable_failure(exc):
                errors.append(f"{attempt['label']}: {_describe_error(exc)}")
                continue
            raise AllProvidersFailedError(
                errors + [f"{attempt['label']}: non-retryable "
                          f"{_describe_error(exc)}"],
                reason="non-retryable provider error") from exc

    raise AllProvidersFailedError(errors)


def llm_judge_fn(**chat_kwargs):
    """Convenience adapter: returns a callable(messages)->str usable as an
    injected judge/LLM dependency by planner/evaluator modules."""
    def call(messages: list[dict]) -> str:
        return chat(messages, **chat_kwargs)
    return call
