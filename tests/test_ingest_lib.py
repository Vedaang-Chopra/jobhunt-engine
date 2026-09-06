"""Tests for scripts/ingest_lib.py: extraction heuristics, inbox lifecycle,
collision-safe naming, YAML round-trip accept path, and discard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import ingest_lib  # noqa: E402


@pytest.fixture
def root(tmp_path):
    base = tmp_path / "data_root"
    (base / "tracking" / "companies").mkdir(parents=True)
    (base / "tracking" / "companies" / "companies.csv").write_text(
        "company\nFortinet\nAcme Corp\n", encoding="utf-8")
    return base


RESUME_TEXT = """Jane Doe
jane.doe@example.com | (415) 555-0132
SKILLS
Python, PyTorch, Kubernetes, AWS
WORK EXPERIENCE
Fortinet — Senior Engineer
EDUCATION
Georgia Tech, MS Computer Science
"""

JD_TEXT = """Senior ML Engineer
We are looking for a candidate with strong Python and Docker skills.
Responsibilities:
- Build data pipelines (Airflow, Spark)
Requirements:
- 5+ years experience
Apply now to join our team.
"""

NOTES_TEXT = """Note to self: follow up with recruiter.
TODO: tailor resume for Acme Corp role.
"""


def test_extract_entities_finds_emails_phones_skills(root):
    entities = ingest_lib.extract_entities(
        RESUME_TEXT, ingest_lib.known_companies(root))
    assert "jane.doe@example.com" in entities["emails"]
    assert entities["phones"]
    assert "python" in entities["skills"]
    assert "pytorch" in entities["skills"]
    assert "fortinet" in entities["companies"]


def test_classify_kind_resume_jd_notes(root):
    assert ingest_lib.classify_kind(RESUME_TEXT) == "resume"
    assert ingest_lib.classify_kind(JD_TEXT) == "jd"
    assert ingest_lib.classify_kind(NOTES_TEXT) == "notes"
    assert ingest_lib.classify_kind("random words only") == "unknown"


def test_extract_upload_returns_full_summary(root):
    result = ingest_lib.extract_upload(RESUME_TEXT, root)
    assert result["kind"] == "resume"
    assert result["suggested_section"] == "experience.yaml"
    assert result["raw_excerpt"].startswith("Jane Doe")
    assert result["needs_manual"] is False


def test_extract_upload_unknown_text_defaults_to_notes_section(root):
    result = ingest_lib.extract_upload("lorem ipsum dolor", root)
    assert result["kind"] == "unknown"
    assert result["suggested_section"] == "notes.yaml"


def test_pdf_without_pypdf_marks_needs_manual(root, tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ingest_lib, "_pdf_text", lambda p: None)
    result = ingest_lib.extract_upload(pdf, root)
    assert result["needs_manual"] is True
    assert result["kind"] == "unknown"


def test_docx_extraction_via_zip(root, tmp_path):
    import zipfile

    docx = tmp_path / "cv.docx"
    body = "<w:p><w:r><w:t>SKILLS Python PyTorch</w:t></w:r></w:p>"
    with zipfile.ZipFile(docx, "w") as zf:
        zf.writestr("word/document.xml", body)
    text, flags = ingest_lib.read_source(docx)
    assert flags == {}
    assert "SKILLS Python PyTorch" in text


def test_save_to_inbox_collision_gets_timestamp_suffix(root):
    first = ingest_lib.save_to_inbox("cv.txt", "v1", root)
    second = ingest_lib.save_to_inbox("cv.txt", "v2", root)
    assert first != second
    assert first.name == "cv.txt"
    assert second.stem.startswith("cv_")
    assert second.read_text(encoding="utf-8") == "v2"


def test_save_to_inbox_rejects_bad_suffix(root):
    target = ingest_lib.save_to_inbox("notes.exe", "hello", root)
    assert target.suffix == ".txt"


def test_process_upload_writes_meta_json(root):
    summary = ingest_lib.process_upload("jd.txt", JD_TEXT, root)
    meta = root / "profile_info" / "inbox" / (summary["path"] + ".meta.json")
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["kind"] == "jd"
    assert "python" in payload["entities"]["skills"]


def test_list_inbox_returns_pending_items(root):
    ingest_lib.process_upload("a.txt", RESUME_TEXT, root)
    items = ingest_lib.list_inbox(root)
    assert len(items) == 1
    assert items[0]["kind"] == "resume"


def test_accept_item_yaml_round_trip_with_unverified_provenance(root):
    ingest_lib.process_upload("resume_upload.txt", RESUME_TEXT, root)
    target = ingest_lib.accept_item("resume_upload.txt", root)
    assert target.name == "experience.yaml"
    import yaml

    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    entries = data["unverified_entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["provenance"] == "unverified"
    assert entry["source_file"] == "resume_upload.txt"
    assert "Jane Doe" in entry["content"]
    # Inbox is drained after acceptance.
    assert ingest_lib.list_inbox(root) == []


def test_accept_item_appends_to_existing_section(root):
    section = ingest_lib.profile_info_dir(root) / "experience.yaml"
    section.parent.mkdir(parents=True, exist_ok=True)
    section.write_text("experience:\n  - company: Fortinet\n", encoding="utf-8")
    ingest_lib.process_upload("n.txt", NOTES_TEXT, root)
    target = ingest_lib.accept_item("n.txt", root)
    assert target.name == "notes.yaml"
    import yaml

    data = yaml.safe_load(section.read_text(encoding="utf-8"))
    assert data["experience"][0]["company"] == "Fortinet"
    notes = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert len(notes["unverified_entries"]) == 1


def test_discard_item_removes_file_and_meta(root):
    summary = ingest_lib.process_upload("x.txt", "some notes", root)
    ingest_lib.discard_item(summary["path"], root)
    directory = root / "profile_info" / "inbox"
    assert not (directory / summary["path"]).exists()
    assert not (directory / (summary["path"] + ".meta.json")).exists()
    assert ingest_lib.list_inbox(root) == []


def test_validate_yaml_rejects_non_mapping():
    with pytest.raises(ValueError):
        ingest_lib.validate_yaml("- just\n- a\n- list\n")
    assert ingest_lib.validate_yaml("") == {}
    assert ingest_lib.validate_yaml("a: 1") == {"a": 1}
