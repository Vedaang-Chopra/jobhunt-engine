"""Tests for the JD -> tailored resume + cover letter pipeline.

Covers scripts/tailor_from_jd.py helpers (spec loading, family diagnosis,
factuality gate, letter wrapper) and the ui/data.py package listing.
LLM calls are never made in tests.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    for sub in ("tracking/job_descriptions/active", "applications",
                "resume_custom/base_variants", "resume_custom/evidence",
                "resume_custom/rules", "profile_info"):
        (root / sub).mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import scripts.tailor_from_jd as tfj

    importlib.reload(tfj)
    yield root
    importlib.reload(tfj)


# ---------------------------------------------------------------------------
# spec loading (the UI contract)
# ---------------------------------------------------------------------------


def test_load_spec_url(tmp_path):
    from scripts.tailor_from_jd import load_spec

    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"url": "https://boards.greenhouse.io/acme/jobs/1",
                                "company": "Acme", "title": "MLE"}))
    ns = load_spec(str(spec))
    assert ns.url == "https://boards.greenhouse.io/acme/jobs/1"
    assert ns.company == "Acme" and ns.title == "MLE"


def test_load_spec_text_writes_temp_file(tmp_path):
    from scripts.tailor_from_jd import load_spec

    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"text": "x" * 300}))
    ns = load_spec(str(spec))
    assert ns.text_file and Path(ns.text_file).read_text() == "x" * 300


def test_load_spec_file(tmp_path):
    from scripts.tailor_from_jd import load_spec

    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"file": "/tmp/jd.md"}))
    ns = load_spec(str(spec))
    assert ns.jd_file == "/tmp/jd.md"


def test_load_spec_rejects_empty(tmp_path):
    from scripts.tailor_from_jd import load_spec

    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"company": "Acme"}))
    with pytest.raises(RuntimeError):
        load_spec(str(spec))


# ---------------------------------------------------------------------------
# family diagnosis + factuality gate
# ---------------------------------------------------------------------------


def test_diagnose_family_agentic(data_root):
    from scripts.tailor_from_jd import diagnose_family

    jd = ("We are hiring a research engineer to build multi-agent systems. "
          "You will design tool use and function calling orchestration with "
          "LangGraph for agentic workflows.")
    fam, hits = diagnose_family(jd)
    assert fam == "research_engineer_agentic"
    assert "agentic" in hits[fam]


def test_diagnose_family_ml_systems(data_root):
    from scripts.tailor_from_jd import diagnose_family

    jd = ("Own inference optimization and model serving on GPU clusters. "
          "Deep experience with vLLM, SLA/SLO ownership, latency routing.")
    fam, _ = diagnose_family(jd)
    assert fam == "ml_systems_inference"


def test_factuality_gate_catches_tier1(data_root):
    from scripts.tailor_from_jd import factuality_gate

    tex = "\\item{Built a 14-agent system with RLHF post-training}"
    violations = factuality_gate(tex)
    assert any("14-agent" in v for v in violations)
    assert any("RLHF" in v for v in violations)


def test_factuality_gate_passes_clean_tex(data_root):
    from scripts.tailor_from_jd import factuality_gate

    tex = ("\\item{Building a closed-loop agentic pipeline; reduced mean "
           "resolution time ~70%. Patent (Filed): PCT/IN2022/058026.}")
    assert factuality_gate(tex) == []


def test_factuality_gate_allows_qwen_lora_context(data_root):
    from scripts.tailor_from_jd import factuality_gate

    tex = "\\item{LoRA fine-tuning of Qwen2.5 (7B) decoders}"
    assert factuality_gate(tex) == []


# ---------------------------------------------------------------------------
# cover-letter wrapper
# ---------------------------------------------------------------------------


def test_letter_wrapper_strips_greeting_and_signature(data_root):
    from scripts.tailor_from_jd import _render_letter_tex

    body = ("Dear Hiring Manager,\n\nPara one.\n\nPara two.\n\n"
            "Sincerely,\nTest Candidate")
    tex = _render_letter_tex("ML Engineer", "Acme", body)
    paras = tex.split("\\letterPara{")[1:]
    # greeting and signature paragraphs must not survive into the template
    assert len(paras) == 2
    assert all("Sincerely" not in p.split("}")[0] for p in paras)
    assert "Dear Hiring Team at Acme," in tex


def test_extract_json_object_handles_fences(data_root):
    from scripts.tailor_from_jd import extract_json_object

    reply = '```json\n{"family": "ml_engineer", "p0": ["a"]}\n```'
    plan = extract_json_object(reply)
    assert plan["family"] == "ml_engineer"


def test_extract_json_object_nested(data_root):
    from scripts.tailor_from_jd import extract_json_object

    reply = 'prefix {"a": {"b": [1, 2]}, "c": "}"} trailing'
    plan = extract_json_object(reply)
    assert plan["c"] == "}"


# ---------------------------------------------------------------------------
# ui.data.list_tailored_packages
# ---------------------------------------------------------------------------


def test_list_tailored_packages(data_root, monkeypatch):
    import ui.data as ui_data

    importlib.reload(ui_data)
    # Package storage lives in the repo (all_custom_resumes/), not data_root;
    # point applications_dir at an isolated temp copy for this test.
    fake_dir = data_root / "all_custom_resumes_test"
    pkg = fake_dir / "acme_mle_20260823"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "resume.pdf").write_bytes(b"%PDF-1.4 fake")
    (pkg / "cover_letter.pdf").write_bytes(b"%PDF-1.4 fake")
    (pkg / "evaluation.md").write_text("# eval")
    monkeypatch.setattr(ui_data, "applications_dir",
                        lambda: fake_dir, raising=False)

    rows = ui_data.list_tailored_packages()
    assert len(rows) == 1
    row = rows[0]
    assert row["package"] == "acme_mle_20260823"
    assert row["cover_letter"] == "yes"
    assert row["evaluation"] == "yes"

    # folders without a compiled resume are not listed
    (data_root / "applications" / "incomplete_20260823").mkdir(exist_ok=True)
    assert len(ui_data.list_tailored_packages()) == 1


def test_list_tailored_packages_empty(data_root, monkeypatch):
    import ui.data as ui_data

    importlib.reload(ui_data)
    # isolate from real repo packages: point at an empty temp dir
    empty = data_root / "applications"
    monkeypatch.setattr(ui_data, "applications_dir",
                        lambda: empty, raising=False)
    assert ui_data.list_tailored_packages() == []
