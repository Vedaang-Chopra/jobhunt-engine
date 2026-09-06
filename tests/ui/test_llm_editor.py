"""Tests for the Settings LLM endpoint editor backend (Phase 4.4)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from ui import data as data_layer


def _isolate_data_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "data_root"
    root.mkdir(exist_ok=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    return root


def test_update_creates_config_chmod_600(tmp_path, monkeypatch):
    root = _isolate_data_root(tmp_path, monkeypatch)
    result = data_layer.update_llm_providers({
        "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                       "model": "anthropic/claude",
                       "api_key": "sk-or-test"},
    })
    path = root / "config.yaml"
    assert Path(result["path"]) == path
    assert path.is_file()
    assert (os.stat(path).st_mode & 0o777) == 0o600

    raw = yaml.safe_load(path.read_text())
    node = raw["llm"]["providers"]["openrouter"]
    assert node["api_key"] == "sk-or-test"
    assert node["model"] == "anthropic/claude"


def test_saved_config_picked_up_by_load_config_and_never_rendered(tmp_path, monkeypatch):
    _isolate_data_root(tmp_path, monkeypatch)
    data_layer.update_llm_providers({
        "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1",
                   "model": "meta/llama-3", "api_key": "nvapi-secret"},
    })
    # Next load_config() call sees the saved values.
    raw = data_layer.config_lib.load_config()
    assert raw["llm"]["providers"]["nvidia"]["base_url"] == \
        "https://integrate.api.nvidia.com/v1"

    # The read-only view exposes only has_api_key — never the key itself.
    view = data_layer.llm_provider_config()
    assert view["nvidia"]["has_api_key"] is True
    flat = str(view)
    assert "nvapi-secret" not in flat


def test_blank_fields_preserve_existing_values(tmp_path, monkeypatch):
    _isolate_data_root(tmp_path, monkeypatch)
    data_layer.update_llm_providers({
        "custom": {"base_url": "https://old.example/v1", "model": "m1",
                   "api_key": "key1"},
    })
    data_layer.update_llm_providers({
        "custom": {"base_url": "", "model": "m2", "api_key": ""},
    })
    raw = data_layer.config_lib.load_config()
    node = raw["llm"]["providers"]["custom"]
    assert node["base_url"] == "https://old.example/v1"
    assert node["model"] == "m2"
    assert node["api_key"] == "key1"


def test_blank_base_url_on_preset_resets_to_default(tmp_path, monkeypatch):
    _isolate_data_root(tmp_path, monkeypatch)
    data_layer.update_llm_providers({
        "openrouter": {"base_url": "https://proxy.example/v1", "model": "m1",
                       "api_key": "key1"},
    })
    data_layer.update_llm_providers({
        "openrouter": {"base_url": "", "model": "", "api_key": ""},
    })
    raw = data_layer.config_lib.load_config()
    node = raw["llm"]["providers"]["openrouter"]
    # Preset semantics: blank endpoint means "back to the fixed default";
    # model/key blanks preserve what was there.
    assert node["base_url"] == \
        data_layer.LLM_PROVIDER_DEFAULTS["openrouter"]["base_url"]
    assert node["model"] == "m1"
    assert node["api_key"] == "key1"


def test_existing_other_keys_survive_edit(tmp_path, monkeypatch):
    root = _isolate_data_root(tmp_path, monkeypatch)
    (root / "config.yaml").write_text(yaml.safe_dump({
        "job_search": {"keywords": ["ml"], "locations": ["Austin"]},
        "llm": {"api_key": "legacy"},
    }))
    data_layer.update_llm_providers({
        "nvidia": {"model": "nim/model"},
    })
    raw = data_layer.config_lib.load_config()
    assert raw["job_search"]["locations"] == ["Austin"]
    assert raw["llm"]["api_key"] == "legacy"
    assert raw["llm"]["providers"]["nvidia"]["model"] == "nim/model"


def test_preset_providers_fall_back_to_default_endpoint(tmp_path, monkeypatch):
    _isolate_data_root(tmp_path, monkeypatch)
    data_layer.update_llm_providers({"openrouter": {}})
    raw = data_layer.config_lib.load_config()
    assert raw["llm"]["providers"]["openrouter"]["base_url"] == \
        data_layer.LLM_PROVIDER_DEFAULTS["openrouter"]["base_url"]

    # An explicit override still wins over the default.
    data_layer.update_llm_providers({
        "openrouter": {"base_url": "https://proxy.example/v1"}})
    raw = data_layer.config_lib.load_config()
    assert raw["llm"]["providers"]["openrouter"]["base_url"] == \
        "https://proxy.example/v1"


def test_custom_provider_has_no_endpoint_fallback(tmp_path, monkeypatch):
    _isolate_data_root(tmp_path, monkeypatch)
    data_layer.update_llm_providers({"custom": {}})
    raw = data_layer.config_lib.load_config()
    node = raw["llm"]["providers"]["custom"]
    assert "base_url" not in node  # nothing fabricated for custom

    # Only set once the user actually provides one.
    data_layer.update_llm_providers({
        "custom": {"base_url": "http://192.168.1.8:9000/v1",
                   "model": "local-model"}})
    raw = data_layer.config_lib.load_config()
    assert raw["llm"]["providers"]["custom"]["base_url"] == \
        "http://192.168.1.8:9000/v1"
    assert raw["llm"]["providers"]["custom"]["model"] == "local-model"


def test_provider_registry_covers_all_three(tmp_path, monkeypatch):
    view = data_layer.llm_provider_config()
    assert set(view.keys()) == {"openrouter", "nvidia", "custom"}
    assert set(data_layer.LLM_PROVIDERS) == set(view.keys())
