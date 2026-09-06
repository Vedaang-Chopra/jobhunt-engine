"""Tests for scripts/config_lib.py — data root precedence and config loading."""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import config_lib  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("JOBHUNT_HOME", raising=False)


@pytest.fixture()
def clean_pointer(monkeypatch, tmp_path):
    """Isolate each test from the real repo config.yaml and env var."""
    monkeypatch.delenv("JOBHUNT_HOME", raising=False)
    monkeypatch.setattr(config_lib, "POINTER_FILE", tmp_path / "absent_config.yaml")
    monkeypatch.setattr(config_lib, "REPO_ROOT", tmp_path / "legacy_root")
    (tmp_path / "legacy_root").mkdir()


def test_env_var_takes_precedence(monkeypatch, tmp_path):
    custom = tmp_path / "custom_home"
    custom.mkdir()
    monkeypatch.setenv("JOBHUNT_HOME", str(custom))
    assert config_lib.data_root() == custom


def test_env_var_overrides_pointer_file(monkeypatch, tmp_path):
    pointer = tmp_path / "pointer.yaml"
    pointer.write_text("data_root: /some/other/place\n", encoding="utf-8")
    monkeypatch.setattr(config_lib, "POINTER_FILE", pointer)
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path / "env_home"))
    (tmp_path / "env_home").mkdir()
    assert config_lib.data_root() == tmp_path / "env_home"


def test_pointer_file_used_when_no_env(monkeypatch, tmp_path):
    target = tmp_path / "data_home"
    target.mkdir()
    pointer = tmp_path / "config.yaml"
    pointer.write_text(f"data_root: {target}\n", encoding="utf-8")
    monkeypatch.setattr(config_lib, "POINTER_FILE", pointer)
    assert config_lib.data_root().resolve() == target.resolve()


def test_pointer_file_relative_path_resolved(monkeypatch, tmp_path):
    pointer = tmp_path / "config.yaml"
    pointer.write_text("data_root: relative_data\n", encoding="utf-8")
    monkeypatch.setattr(config_lib, "POINTER_FILE", pointer)
    assert config_lib.data_root() == Path("relative_data")


def test_malformed_pointer_falls_back_to_legacy(clean_pointer, monkeypatch, tmp_path, caplog):
    pointer = tmp_path / "config.yaml"
    pointer.write_text(": : not: valid: yaml:\n  - [", encoding="utf-8")
    monkeypatch.setattr(config_lib, "POINTER_FILE", pointer)
    with caplog.at_level(logging.WARNING):
        assert config_lib.data_root() == tmp_path / "legacy_root" / "jobhunt-data"
    assert any("Could not parse" in r.message for r in caplog.records)


def test_pointer_without_data_root_key_falls_back(clean_pointer, monkeypatch, tmp_path):
    pointer = tmp_path / "config.yaml"
    pointer.write_text("other_key: value\n", encoding="utf-8")
    monkeypatch.setattr(config_lib, "POINTER_FILE", pointer)
    assert config_lib.data_root() == tmp_path / "legacy_root" / "jobhunt-data"


def test_legacy_default_is_repo_parent(clean_pointer):
    # With no env and no pointer file, falls back to REPO_ROOT/jobhunt-data
    # (the repo-local data dir — never the repo root itself, so run outputs
    # and personal data cannot leak into the code tree).
    import config_lib as _c

    assert config_lib.data_root() == _c.REPO_ROOT / "jobhunt-data"
    assert _c.REPO_ROOT.name == "legacy_root"


def test_agent_helpers_layout_follows_data_root(monkeypatch, tmp_path):
    # DATA_DIR/JOBS_DIR derive from config_lib.data_root() (post-isolation contract).
    (tmp_path / "job_research" / "data").mkdir(parents=True)
    (tmp_path / "tracking" / "job_descriptions" / "active").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path))
    import importlib
    from scripts import config_lib, agent_helpers

    importlib.reload(config_lib)
    importlib.reload(agent_helpers)
    assert str(agent_helpers.DATA_DIR).startswith(str(tmp_path))
    assert str(agent_helpers.JOBS_DIR).startswith(str(tmp_path))
    monkeypatch.delenv("JOBHUNT_HOME")
    importlib.reload(config_lib)  # restore for other tests


def test_load_config_missing_returns_empty_dict(clean_pointer):
    assert config_lib.load_config() == {}


def test_load_config_reads_data_root_config(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text(
        "llm:\n  endpoint: http://localhost:1234\n", encoding="utf-8"
    )
    monkeypatch.setenv("JOBHUNT_HOME", str(home))
    assert config_lib.load_config() == {"llm": {"endpoint": "http://localhost:1234"}}


def test_load_config_malformed_yaml_warns_and_returns_empty(monkeypatch, tmp_path, caplog):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("key: [unclosed\n  bad:: :\n", encoding="utf-8")
    monkeypatch.setenv("JOBHUNT_HOME", str(home))
    with caplog.at_level(logging.WARNING):
        assert config_lib.load_config() == {}
    assert any("Malformed YAML" in r.message for r in caplog.records)


def test_load_config_non_mapping_yaml_returns_empty(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    monkeypatch.setenv("JOBHUNT_HOME", str(home))
    assert config_lib.load_config() == {}
