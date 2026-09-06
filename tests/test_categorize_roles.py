"""Tests for scripts/categorize_roles.py and score_jobs_v2 --job-id subset.

LLM calls are never made in tests — llm_chat is stubbed via chat_fn.
"""

from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

JOBS_HEADER = [
    "job_id", "company", "title", "status", "date_updated", "role_family",
    "key_requirements", "matching_strengths", "main_gaps", "notes",
    "description_file",
]

TODAY = date.today().isoformat()


def write_jobs_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=JOBS_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def make_row(job_id, role_family="", title="ML Engineer",
             description_file="", status="open", company="Acme"):
    return {
        "job_id": job_id,
        "company": company,
        "title": title,
        "status": status,
        "date_updated": "2026-01-01" if role_family else "",
        "role_family": role_family,
        "key_requirements": "python, pytorch",
        "matching_strengths": "4 yrs production ML",
        "main_gaps": "no PhD",
        "notes": "",
        "description_file": description_file,
    }


@pytest.fixture()
def isolated_root(tmp_path, monkeypatch):
    """Isolated data root (mirrors tests/ui/test_data_states.py pattern)."""
    root = tmp_path / "data_root"
    root.mkdir()
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    yield root


@pytest.fixture()
def cr(isolated_root):
    import scripts.categorize_roles as mod
    return mod


def jobs_csv_path(root):
    return root / "tracking/jobs/jobs.csv"


# --- target selection -------------------------------------------------------


def test_select_targets_picks_blank_nan_unknown(cr):
    rows = [
        make_row("j1"),                                # blank
        make_row("j2", role_family="  "),              # whitespace
        make_row("j3", role_family="NaN"),             # nan
        make_row("j4", role_family="Unknown"),         # unknown
        make_row("j5", role_family="None"),            # none
        make_row("j6", role_family="applied_ml"),      # valid -> skip
    ]
    targets = cr.select_targets(rows)
    assert [r["job_id"] for r in targets] == ["j1", "j2", "j3", "j4", "j5"]


def test_select_targets_all_includes_valid(cr):
    rows = [make_row("j1"), make_row("j2", role_family="other")]
    assert [r["job_id"] for r in cr.select_targets(rows)] == ["j1"]
    assert [r["job_id"] for r in cr.select_targets(rows, force_all=True)] == \
        ["j1", "j2"]


def test_select_targets_job_id_filter_and_limit(cr):
    rows = [make_row(f"j{i}") for i in range(5)]
    picked = cr.select_targets(rows, job_id_filter={"j1", "j3"})
    assert [r["job_id"] for r in picked] == ["j1", "j3"]


def test_parse_job_ids_repeatable_and_comma_separated(cr):
    assert cr.parse_job_ids(["a,b", " c ", "", "d"]) == {"a", "b", "c", "d"}


# --- JD text building --------------------------------------------------------


def test_build_jd_text_extracts_body(isolated_root, cr):
    jd = isolated_root / "tracking/job_descriptions/active/x.md"
    jd.parent.mkdir(parents=True, exist_ok=True)
    jd.write_text(
        "# Header\n---\n## Full Job Description Text\npost-training rlhf body\n"
        "---\nfooter metadata\n")
    row = make_row("j1", description_file="tracking/job_descriptions/active/x.md")
    text = cr.build_jd_text(row, isolated_root)
    assert text == "post-training rlhf body"


def test_build_jd_text_falls_back_to_meta_columns(isolated_root, cr):
    row = make_row("j1", title="Inference Optimization Engineer")
    row["key_requirements"] = "vllm serving latency"
    text = cr.build_jd_text(row, isolated_root)
    assert "vllm serving latency" in text
    assert "Inference Optimization Engineer" in text


def test_build_jd_text_missing_file_is_empty(isolated_root, cr):
    row = make_row("j1", description_file="tracking/job_descriptions/active/gone.md")
    assert isinstance(cr.build_jd_text(row, isolated_root), str)


# --- vocab validation + fallback --------------------------------------------


def test_validate_family_reply(cr):
    assert cr.validate_family_reply("post_training") == "post_training"
    assert cr.validate_family_reply("  Agentic_AI. ") == "agentic_ai"
    assert cr.validate_family_reply(
        "The best fit is eval_inference.") == "eval_inference"
    assert cr.validate_family_reply("machine learning stuff") is None
    assert cr.validate_family_reply("") is None
    # 'not_otherwise' must not match bare token 'other' spuriously.
    assert cr.validate_family_reply("brotherly") is None


class RaisingChat:
    def __call__(self, messages, max_tokens=16, temperature=0.0):
        raise RuntimeError("no LLM provider responded")


def test_classify_job_llm_success(cr):
    def chat(messages, max_tokens=16, temperature=0.0):
        return "post_training\n"
    fam, method = cr.classify_job(make_row("j1"), "rlhf reward model", chat_fn=chat)
    assert (fam, method) == ("post_training", "llm")


def test_classify_job_invalid_then_retry_then_valid(cr):
    replies = iter(["I think it's machine learning.", "APPLIED_ML"])
    def chat(messages, max_tokens=16, temperature=0.0):
        return next(replies)
    fam, method = cr.classify_job(make_row("j1"), "production ml", chat_fn=chat)
    assert (fam, method) == ("applied_ml", "llm")


def test_classify_job_invalid_twice_falls_back_to_keywords(cr):
    calls = []
    def chat(messages, max_tokens=16, temperature=0.0):
        calls.append(1)
        return "definitely not a family"
    fam, method = cr.classify_job(
        make_row("j1", title="Post-training RLHF Research Engineer"),
        "post-training rlhf grpo reward model", chat_fn=chat)
    assert len(calls) == 2          # exactly one retry
    assert fam == "post_training"
    assert method == "keyword_fallback"


def test_classify_job_llm_down_keyword_only(cr):
    fam, method = cr.classify_job(
        make_row("j1", title="Agent Framework Engineer"),
        "agentic multi-agent tool use orchestration langgraph",
        chat_fn=RaisingChat())
    assert fam == "agentic_ai"
    assert method == "keyword_only"


def test_keyword_family_maps_to_jobs_vocab(cr):
    cases = {
        "we build agentic agents with langgraph orchestration": "agentic_ai",
        "frontier reasoning planning verifier long-horizon": "agent_reasoning",
        "production ml pipeline feature engineering experimentation": "applied_ml",
        "inference optimization vllm serving gpu cluster latency": "eval_inference",
        "post-training rlhf dpo sft preference reward model": "post_training",
        "data infrastructure analytics dashboards etl": "other",
    }
    for text, expected in cases.items():
        fam, _ = cr.keyword_family(text)
        assert fam == expected, text


# --- dry-run vs apply --------------------------------------------------------


def seed(root, extra_jd=None):
    if extra_jd:
        jd = root / "tracking/job_descriptions/active/a.md"
        jd.parent.mkdir(parents=True, exist_ok=True)
        jd.write_text("## Full Job Description Text\npost-training rlhf\n---\n")
    rows = [
        make_row("keep1", role_family="applied_ml"),
        make_row("blank1"),
        make_row("nan1", role_family="NaN"),
        make_row("unknown1", role_family="unknown"),
        make_row("arch1", status="archived"),
    ]
    write_jobs_csv(jobs_csv_path(root), rows)
    return rows


def read_rows(root):
    with open(jobs_csv_path(root), newline="") as f:
        return list(csv.DictReader(f))


def always_post_training(messages, max_tokens=16, temperature=0.0):
    return "post_training"


def test_dry_run_makes_no_file_changes(isolated_root, cr):
    seed(isolated_root, extra_jd=True)
    before = jobs_csv_path(isolated_root).read_bytes()
    buf = io.StringIO()
    with redirect_stdout(buf):
        summary = cr.run(jobs_csv=jobs_csv_path(isolated_root),
                         data_root=isolated_root,
                         sleep_s=0, chat_fn=always_post_training)
    assert jobs_csv_path(isolated_root).read_bytes() == before
    assert summary["total_targets"] == 3   # blank1, nan1, unknown1 (not archived)
    out = buf.getvalue()
    assert "-> post_training" in out
    assert "dry run" in out.lower()


def test_apply_updates_only_targeted_rows(isolated_root, cr):
    seed(isolated_root, extra_jd=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        summary = cr.run(jobs_csv=jobs_csv_path(isolated_root),
                         data_root=isolated_root, apply=True,
                         sleep_s=0, chat_fn=always_post_training)
    after = {r["job_id"]: r for r in read_rows(isolated_root)}
    assert set(after) == {"keep1", "blank1", "nan1", "unknown1", "arch1"}
    # Untouched rows verbatim.
    assert after["keep1"]["role_family"] == "applied_ml"
    assert after["keep1"]["date_updated"] == "2026-01-01"
    assert after["arch1"]["role_family"] == ""
    assert after["arch1"]["status"] == "archived"
    # Targeted rows updated + dated.
    for jid in ("blank1", "nan1", "unknown1"):
        assert after[jid]["role_family"] == "post_training"
        assert after[jid]["date_updated"] == TODAY
    assert summary["per_family"] == {"post_training": 3}
    assert summary["per_method"] == {"llm": 3}
    # All original columns preserved in header order.
    with open(jobs_csv_path(isolated_root), newline="") as f:
        header = csv.DictReader(f).fieldnames
    assert header == JOBS_HEADER


def test_apply_with_job_id_filter_only_touches_selected(isolated_root, cr):
    seed(isolated_root)
    buf = io.StringIO()
    with redirect_stdout(buf):
        summary = cr.run(jobs_csv=jobs_csv_path(isolated_root),
                         data_root=isolated_root, apply=True,
                         job_ids=["blank1"], sleep_s=0,
                         chat_fn=always_post_training)
    after = {r["job_id"]: r for r in read_rows(isolated_root)}
    assert after["blank1"]["role_family"] == "post_training"
    assert after["nan1"]["role_family"] == "NaN"     # untouched
    assert after["unknown1"]["role_family"] == "unknown"
    assert summary["total_targets"] == 1


def test_apply_respects_limit(isolated_root, cr):
    seed(isolated_root)
    buf = io.StringIO()
    with redirect_stdout(buf):
        summary = cr.run(jobs_csv=jobs_csv_path(isolated_root),
                         data_root=isolated_root, apply=True, limit=2,
                         sleep_s=0, chat_fn=always_post_training)
    after = {r["job_id"]: r for r in read_rows(isolated_root)}
    updated = [j for j, r in after.items() if r["role_family"] == "post_training"]
    assert len(updated) == 2
    assert summary["total_targets"] == 2


def test_no_provider_still_completes_with_keyword_fallback(isolated_root, cr,
                                                           capsys):
    seed(isolated_root)
    buf = io.StringIO()
    with redirect_stdout(buf):
        summary = cr.run(jobs_csv=jobs_csv_path(isolated_root),
                         data_root=isolated_root, apply=True, sleep_s=0,
                         chat_fn=RaisingChat())
    out = buf.getvalue()
    assert "falling back to keyword heuristic" in out
    assert summary["per_method"].get("keyword_only", 0) >= 1
    after = {r["job_id"]: r for r in read_rows(isolated_root)}
    assert all(after[j]["role_family"] in cr.VOCAB
               for j in ("blank1", "nan1", "unknown1"))


# --- score_jobs_v2 --job-id subset -------------------------------------------


@pytest.fixture()
def sjv(tmp_path, monkeypatch):
    """score_jobs_v2 reloaded against an isolated data root."""
    root = tmp_path / "sjv_root"
    (root / "job_research/config").mkdir(parents=True)
    (root / "job_research/config/scoring-config.yaml").write_text(
        "company_quality_priors: {}\n")
    (root / "job_research/data").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    sys.modules.pop("scripts.score_jobs_v2", None)
    sys.modules.pop("score_jobs_v2", None)
    try:
        import scripts.score_jobs_v2 as mod
        yield mod
    finally:
        sys.modules.pop("scripts.score_jobs_v2", None)


def test_should_score_restricts_subset(sjv):
    rows = [
        {"job_id": "a", "status": "open"},
        {"job_id": "b", "status": "archived"},
        {"job_id": "c", "status": "open"},
    ]
    # No filter: non-archived only (today's default behavior).
    assert [r["job_id"] for r in rows if sjv.should_score(r)] == ["a", "c"]
    # With filter: intersection of filter and non-archived.
    sel = sjv.parse_args(["--job-id", "a,c,d"])
    assert sel[1] == {"a", "c", "d"}
    assert [r["job_id"] for r in rows if sjv.should_score(r, sel[1])] == ["a", "c"]
    # Archived never scores even when explicitly listed.
    assert not sjv.should_score(rows[1], {"b"})
    # No ids -> no restriction.
    assert sjv.parse_args([])[1] is None
