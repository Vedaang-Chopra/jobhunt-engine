"""Tests for the Profile page (/profile): section loading, empty states,
render smoke, and the edit-validation wrapper (ui/pages_profile.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import ingest_lib  # noqa: E402


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    base = tmp_path / "data_root"
    (base / "profile_info").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(base))
    return base


def test_load_sections_empty_root(data_root):
    from ui.pages_profile import load_sections

    assert load_sections(data_root) == []


def test_load_sections_reads_yaml_files_excluding_inbox(data_root):
    (data_root / "profile_info" / "skills.yaml").write_text(
        "skills:\n  - python\n", encoding="utf-8")
    inbox = data_root / "profile_info" / "inbox"
    inbox.mkdir()
    (inbox / "pending.yaml").write_text("junk: true", encoding="utf-8")
    from ui.pages_profile import load_sections

    sections = dict(load_sections(data_root))
    assert list(sections) == ["skills"]
    assert "python" in sections["skills"]


def test_load_sections_ignores_missing_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path / "nope"))
    from ui.pages_profile import load_sections

    assert load_sections() == []


EMPTY_STATE_TEXT = "Upload documents or paste text"


def test_render_profile_empty_state_smoke(data_root):
    """With no profile YAML the page renders its guidance message."""
    pytest.importorskip("nicegui")
    from nicegui import ui

    from ui.pages_profile import EMPTY_STATES, render_profile

    assert any(EMPTY_STATE_TEXT in msg for msg in EMPTY_STATES.values())

    with ui.column():
        render_profile()  # must not raise on an empty profile


def test_render_profile_with_section_smoke(data_root):
    pytest.importorskip("nicegui")
    from nicegui import ui

    (data_root / "profile_info" / "skills.yaml").write_text(
        "skills:\n  - python\n", encoding="utf-8")
    from ui.pages_profile import render_profile

    with ui.column():
        render_profile()  # must not raise with a real section


def test_edit_wrapper_validates_then_writes(data_root, monkeypatch):
    """The Save handler path: valid YAML writes back; invalid is rejected."""
    pytest.importorskip("nicegui")
    import yaml as yaml_mod
    from nicegui import ui

    notified: list[tuple[str, object]] = []
    monkeypatch.setattr(
        ui, "notify", lambda msg="", **kw: notified.append((str(msg), kw.get("type"))))

    saved: dict[str, str] = {}
    write_calls = {"n": 0}

    def fake_write(path, text):
        path.write_text(text, encoding="utf-8")
        write_calls["n"] += 1

    class Area:
        def __init__(self, value):
            self.value = value

    from ui.pages_profile import make_save_handler

    handler_valid = make_save_handler("skills", Area("skills:\n  - rust\n"),
                                      notify=ui.notify, write=fake_write,
                                      base_dir=data_root / "profile_info")
    handler_valid()
    assert write_calls["n"] == 1
    reloaded = ingest_lib.load_yaml(
        data_root / "profile_info" / "skills.yaml")
    assert reloaded == {"skills": ["rust"]}
    assert any(t == "positive" for _, t in notified)

    before = write_calls["n"]
    handler_invalid = make_save_handler("skills", Area("skills: [unclosed"),
                                        notify=ui.notify, write=fake_write,
                                        base_dir=data_root / "profile_info")
    handler_invalid()
    assert write_calls["n"] == before  # nothing written
    assert yaml_mod.safe_load(
        (data_root / "profile_info" / "skills.yaml").read_text()) == {
            "skills": ["rust"]}  # file unchanged
    assert any(t == "negative" for _, t in notified)


def test_save_handler_with_confirm_defers_write_until_confirmed(
        data_root, monkeypatch):
    """With a confirm callable, nothing is written until on_confirm fires."""
    pytest.importorskip("nicegui")
    from nicegui import ui

    notified: list[tuple[str, object]] = []
    monkeypatch.setattr(
        ui, "notify", lambda msg="", **kw: notified.append((str(msg), kw.get("type"))))

    write_calls: list[tuple[object, str]] = []

    def fake_write(path, text):
        write_calls.append((path, text))

    class Area:
        def __init__(self, value):
            self.value = value

    from ui.pages_profile import make_save_handler

    captured: list[dict] = []

    def fake_confirm(**kwargs):
        captured.append(kwargs)  # do NOT invoke on_confirm — dialog "open"

    target = data_root / "profile_info" / "skills.yaml"
    handler = make_save_handler(
        "skills", Area("skills:\n  - rust\n"), notify=ui.notify,
        write=fake_write, base_dir=data_root / "profile_info",
        confirm=fake_confirm)
    handler()

    assert not target.exists()          # nothing written yet
    assert write_calls == []            # write fn NOT called
    assert len(captured) == 1
    kwargs = captured[0]
    assert kwargs["title"] == "Save section skills"
    assert "Writes" in kwargs["body"]
    assert str(target) in kwargs["body"]
    assert "+skills:" in kwargs["body"] or "- original" in kwargs["body"] \
        or "+++" in kwargs["body"]      # a diff preview is present
    assert kwargs["on_confirm"] is not None

    # User confirms -> only then does the write happen.
    kwargs["on_confirm"]()
    assert len(write_calls) == 1
    assert any(t == "positive" for _, t in notified)


def test_save_handler_invalid_yaml_skips_confirm(data_root, monkeypatch):
    """Invalid YAML never reaches the confirm dialog nor the writer."""
    pytest.importorskip("nicegui")
    from nicegui import ui

    notified: list[tuple[str, object]] = []
    monkeypatch.setattr(
        ui, "notify", lambda msg="", **kw: notified.append((str(msg), kw.get("type"))))

    class Area:
        value = "skills: [unclosed"

    from ui.pages_profile import make_save_handler

    confirm_calls: list = []
    handler = make_save_handler(
        "skills", Area(), notify=ui.notify, write=lambda p, t: (_ for _ in ()).throw(
            AssertionError("write must not run")),
        base_dir=data_root / "profile_info", confirm=lambda **kw: confirm_calls.append(kw))
    handler()
    assert confirm_calls == []
    assert any(t == "negative" for _, t in notified)


def test_diff_preview_truncated_and_fenced():
    """_diff_preview yields a short unified diff; helper exists for reuse."""
    from ui.pages_profile import _diff_preview

    original = "\n".join(f"- item {i}" for i in range(40))
    new_text = "\n".join(f"- changed {i}" for i in range(40))
    diff = _diff_preview(original, new_text)
    assert diff.startswith("---")
    assert "…" in diff  # truncated marker present
    assert _diff_preview("a: 1\n", "a: 1\n") == "(no textual differences)"
