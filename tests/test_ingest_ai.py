"""Tests for scripts/ingest_ai.py: LLM placement proposals, YAML merge,
apply-with-provenance, and heuristic fallback."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import ingest_ai  # noqa: E402
from scripts import ingest_lib  # noqa: E402


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    base = tmp_path / "data_root"
    (base / "profile_info").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(base))
    return base


def _no_llm(monkeypatch):
    monkeypatch.setattr(ingest_ai.tfj, "llm_config", lambda: [])


def test_propose_placement_falls_back_without_llm(data_root, monkeypatch):
    _no_llm(monkeypatch)
    proposal = ingest_ai.propose_placement("resume.txt",
                                           "Work experience ... skills python")
    assert proposal["engine"] == "heuristic"
    assert proposal["target_file"].endswith(".yaml")
    assert proposal["yaml_snippet"] == ""


def test_propose_placement_empty_text(data_root, monkeypatch):
    _no_llm(monkeypatch)
    proposal = ingest_ai.propose_placement("empty.txt", "   ")
    assert proposal["confidence"] == 0.0


def test_propose_placement_uses_llm_json(data_root, monkeypatch):
    good = ('{"section": "experience", "confidence": 0.9, '
            '"rationale": "roles listed", "yaml": "roles:\\n  - company: Acme"}')
    monkeypatch.setattr(ingest_ai.tfj, "llm_config",
                        lambda: [{"name": "fake"}])
    monkeypatch.setattr(ingest_ai.tfj, "llm_chat",
                        lambda messages, temperature=0.4: f"```json\n{good}\n```")
    proposal = ingest_ai.propose_placement("offer.txt", "some text")
    assert proposal["engine"] == "llm"
    assert proposal["section"] == "experience"
    assert "Acme" in proposal["yaml_snippet"]
    assert proposal["confidence"] == pytest.approx(0.9)


def test_propose_placement_rejects_bad_section_and_yaml(data_root,
                                                        monkeypatch):
    calls = {"n": 0}

    def fake_chat(messages, temperature=0.4):
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"section": "hobbies", "yaml": "a: 1"}'
        return '{"section": "skills", "yaml": "[not a mapping]"}'

    monkeypatch.setattr(ingest_ai.tfj, "llm_config",
                        lambda: [{"name": "fake"}])
    monkeypatch.setattr(ingest_ai.tfj, "llm_chat", fake_chat)
    p1 = ingest_ai.propose_placement("x.txt", "text")
    p2 = ingest_ai.propose_placement("y.txt", "text")
    assert p1["engine"] == "heuristic" and "unknown section" in p1["rationale"]
    assert p2["engine"] == "heuristic" and "invalid" in p2["rationale"]


def test_merge_yaml_deep_merge_appends_lists():
    existing = "skills:\n  - python\ncount: 1\n"
    snippet = "skills:\n  - rust\ncount: 2\nnew_key: hello\n"
    merged, added = ingest_ai.merge_yaml(existing, snippet)
    doc = yaml.safe_load(merged)
    assert doc["skills"] == ["python", "rust"]
    assert doc["count"] == 2          # scalar overwrite
    assert doc["new_key"] == "hello"
    assert any("new_key" in p for p in added)
    with pytest.raises(ValueError):
        ingest_ai.merge_yaml("", "- just\n- a list\n")


def test_apply_proposal_writes_with_provenance_and_clears_inbox(
        data_root, monkeypatch):
    _no_llm(monkeypatch)
    ingest_lib.process_upload("note.txt", "Company: Fortinet role ML engineer")
    source = data_root / "profile_info" / "inbox" / "note.txt"
    text = source.read_text(encoding="utf-8")
    proposal = {
        "name": "note.txt",
        "section": "notes",
        "target_file": "notes.yaml",
        "confidence": 0.5,
        "rationale": "test",
        "yaml_snippet": yaml.safe_dump({"items": [{"text": text[:200]}]}),
        "engine": "heuristic",
        "error": None,
    }
    target = ingest_ai.apply_proposal(proposal, data_root)
    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert doc["items"][0]["text"]
    assert doc["_ai_ingest"][0]["provenance"] == "unverified"
    assert not source.exists()
    # second apply appends provenance entries rather than clobbering
    ingest_lib.process_upload("note.txt", "more text")
    ingest_ai.apply_proposal({**proposal}, data_root)
    doc2 = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert len(doc2["_ai_ingest"]) == 2


def test_cli_main_dry_run(data_root, monkeypatch, capsys):
    _no_llm(monkeypatch)
    ingest_lib.process_upload("thing.txt", "todo: follow up on referral")
    rc = ingest_ai.main(["--item", "thing.txt"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"engine": "heuristic"' in out


def test_cli_main_missing_item(data_root, monkeypatch, capsys):
    _no_llm(monkeypatch)
    assert ingest_ai.main(["--item", "nope.txt"]) == 1
