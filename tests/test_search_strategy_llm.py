"""Tests for the resilient provider-chain LLM client (scripts/search_strategy/llm.py).

Unit tests inject fake clients — no network is ever hit.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from search_strategy.llm import AllProvidersFailedError, chat  # noqa: E402


# --- fakes ---------------------------------------------------------------------


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _ProviderError(Exception):
    """Duck-typed stand-in for openai APIStatus/Timeout/Connection errors."""

    def __init__(self, status_code=None, name="APIStatusError", msg="boom"):
        super().__init__(msg)
        self.status_code = status_code
        self.__name__ = name


class _CompletionsApi:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        self._owner.calls.append(kwargs)
        behavior = self._owner.behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        if isinstance(behavior, type) and issubclass(behavior, Exception):
            raise behavior("timed out")
        return _Response(behavior)


class _ChatApi:
    def __init__(self, owner):
        self.completions = _CompletionsApi(owner)


class FakeClient:
    """Mimics an OpenAI SDK client. Each create() pops the next behavior:
    a str (completion text), an Exception instance, or an Exception class.
    """

    def __init__(self, behaviors, label="fake", model="fake-model"):
        self.provider_label = label
        self.model_name = model
        self.behaviors = list(behaviors)
        self.calls = []

    @property
    def chat(self):
        return _ChatApi(self)


LONG = "This is a perfectly adequate completion that easily exceeds fifty characters."
SHORT = "too short"


def fake_client(text=LONG, label="fake", behaviors=None):
    return FakeClient(behaviors if behaviors is not None else [text], label=label)


# --- unit tests ----------------------------------------------------------------


def test_primary_success_returns_text():
    out = chat([{"role": "user", "content": "hi"}], clients=[fake_client()])
    assert out == LONG.strip()


def test_rate_limit_on_primary_falls_through_to_secondary():
    primary = fake_client(label="openrouter",
                          behaviors=[_ProviderError(429, "RateLimitError")])
    secondary = fake_client(label="nvidia")
    out = chat([], clients=[primary, secondary])
    assert out == LONG.strip()
    assert len(primary.calls) == 1          # one attempt, then moved on
    assert len(secondary.calls) == 1


def test_timeout_and_connection_errors_are_retryable():
    for err in (
        _ProviderError(None, "APITimeoutError"),
        _ProviderError(None, "APIConnectionError"),
    ):
        primary = fake_client(label="a", behaviors=[err])
        secondary = fake_client(label="b")
        out = chat([], clients=[primary, secondary])
        assert out == LONG.strip()
        assert len(secondary.calls) == 1


def test_short_completion_treated_as_failure_next_provider_used():
    primary = fake_client(SHORT, label="flaky")     # < 50 chars
    secondary = fake_client(label="solid")
    out = chat([], clients=[primary, secondary])
    assert out == LONG.strip()
    assert len(secondary.calls) == 1


def test_all_fail_raises_with_summary():
    clients = [
        fake_client(label="p0", behaviors=[_ProviderError(429, "RateLimitError")]),
        fake_client(SHORT, label="p1"),
    ]
    with pytest.raises(AllProvidersFailedError) as ei:
        chat([], clients=clients)
    msg = str(ei.value)
    # per-provider error summary present
    assert "p0" in msg and ("429" in msg or "rate" in msg.lower())
    assert "p1" in msg and ("short" in msg.lower() or "50" in msg)


def test_messages_temperature_max_tokens_forwarded():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    client = fake_client()
    chat(msgs, temperature=0.2, max_tokens=1234, clients=[client])
    kwargs = client.calls[0]
    assert kwargs["messages"] == msgs
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 1234


def test_default_forwarded_values():
    client = fake_client()
    chat([{"role": "user", "content": "u"}], clients=[client])
    kwargs = client.calls[0]
    assert kwargs["temperature"] == 0.4
    assert kwargs["max_tokens"] == 4000


# --- integration shape (skipped without NVIDIA_API_KEY) -------------------------

try:
    from web_nav_agent._llm_config_fallback import llm_config as _llm_config
except ImportError:  # pragma: no cover - alternate import root
    try:
        from scripts.web_nav_agent._llm_config_fallback import (
            llm_config as _llm_config,
        )
    except ImportError:
        _llm_config = None


@pytest.mark.skipif(
    _llm_config is None or not os.environ.get("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set; integration-shape check skipped silently",
)
def test_llm_config_chain_has_at_least_one_entry():
    entries = _llm_config()
    assert isinstance(entries, list) and len(entries) >= 1
