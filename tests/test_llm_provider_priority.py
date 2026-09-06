"""Tests for multi-provider LLM priority ordering (llm_config in tailor_from_jd)
and the priority field in update_llm_providers / llm_provider_config (ui.data)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import tailor_from_jd  # noqa: E402
from ui import data as data_layer  # noqa: E402


def _with_providers(monkeypatch, providers: dict):
    def fake_load():
        return {"llm": {"providers": providers}}
    monkeypatch.setattr(tailor_from_jd.config_lib, "load_config", fake_load)


# --- engine chain ordering ----------------------------------------------------


def test_default_order_openrouter_first(monkeypatch):
    _with_providers(monkeypatch, {
        "openrouter": {"api_key": "k1"},
        "nvidia": {"api_key": "k2"},
    })
    chain = tailor_from_jd.llm_config()
    assert [c["name"] for c in chain] == ["openrouter", "nvidia"]


def test_explicit_priority_overrides_defaults(monkeypatch):
    _with_providers(monkeypatch, {
        "openrouter": {"api_key": "k1", "priority": 2},
        "nvidia": {"api_key": "k2", "priority": 1},
    })
    chain = tailor_from_jd.llm_config()
    assert [c["name"] for c in chain] == ["nvidia", "openrouter"]
    assert chain[0]["priority"] == 1


def test_providers_without_key_are_skipped(monkeypatch):
    _with_providers(monkeypatch, {
        "openrouter": {},                      # no key
        "nvidia": {"api_key": "k2"},
        "custom": {"api_key": "k3", "base_url": "http://x/v1", "model": "m"},
    })
    chain = tailor_from_jd.llm_config()
    assert [c["name"] for c in chain] == ["nvidia", "custom"]


def test_custom_without_endpoint_or_model_is_dropped(monkeypatch):
    _with_providers(monkeypatch, {
        "custom": {"api_key": "k3"},           # unusable
        "nvidia": {"api_key": "k2"},
    })
    chain = tailor_from_jd.llm_config()
    assert [c["name"] for c in chain] == ["nvidia"]


def test_unparsable_priority_falls_back_to_builtin_rank(monkeypatch):
    _with_providers(monkeypatch, {
        "openrouter": {"api_key": "k1", "priority": "soon"},
        "nvidia": {"api_key": "k2"},
    })
    chain = tailor_from_jd.llm_config()
    assert [c["name"] for c in chain] == ["openrouter", "nvidia"]


# --- settings-page persistence -------------------------------------------------


@pytest.fixture()
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    root.mkdir()
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    return root


def test_update_llm_providers_persists_priority(isolated_root):
    data_layer.update_llm_providers({
        "openrouter": {"api_key": "sk-or-test", "priority": "1"}})
    view = data_layer.llm_provider_config()
    assert view["openrouter"]["priority"] == 1
    # nvidia untouched -> empty-string priority in the view layer
    assert view["nvidia"]["priority"] == ""


def test_update_llm_providers_rejects_bad_priority(isolated_root):
    with pytest.raises(ValueError):
        data_layer.update_llm_providers({"nvidia": {"priority": "high"}})
    with pytest.raises(ValueError):
        data_layer.update_llm_providers({"nvidia": {"priority": "0"}})


def test_priority_blank_leaves_existing_value(isolated_root):
    data_layer.update_llm_providers({"nvidia": {"priority": "3"}})
    data_layer.update_llm_providers({"nvidia": {"base_url": ""}})
    view = data_layer.llm_provider_config()
    assert view["nvidia"]["priority"] == 3
