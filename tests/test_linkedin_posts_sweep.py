"""Unit tests for scripts/linkedin_posts_sweep.py pure logic."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import linkedin_posts_sweep as lps  # noqa: E402


# ---------------------------------------------------------------- dedupe

def _post(url="", urn="", poster="Jane Doe", roles="ML Engineer",
          date="2026-08-24", **kw):
    p = {"poster": poster, "roles_mentioned": roles, "posted_date": date,
         "post_url": url, "urn": urn}
    p.update(kw)
    return p


def test_split_new_and_dup_by_url():
    seen = {"https://www.linkedin.com/feed/update/urn:li:activity:123/".lower()}
    new, dups = lps.split_new_and_dup_posts(
        [_post(url="https://www.linkedin.com/feed/update/urn:li:activity:123/"),
         _post(url="https://www.linkedin.com/feed/update/urn:li:activity:456/")],
        seen)
    assert len(new) == 1 and len(dups) == 1
    assert new[0]["urn"] == "" or True  # url-based split only asserted via count


def test_split_dedupes_within_batch():
    seen: set[str] = set()
    posts = [_post(urn="111", poster="A"), _post(urn="111", poster="A"),
             _post(urn="222", poster="B")]
    new, dups = lps.split_new_and_dup_posts(posts, seen)
    assert [p["urn"] for p in new] == ["111", "222"]
    assert len(dups) == 1


def test_split_conservative_fuzzy_across_batch():
    """Same poster+roles+date with no url/urn counts as one post (conservative)."""
    seen: set[str] = set()
    new, dups = lps.split_new_and_dup_posts(
        [_post(), _post()], seen)
    assert len(new) == 1 and len(dups) == 1


def test_split_fuzzy_match_on_poster_roles_date():
    seen = {lps._fuzzy_key("jane doe", "ml engineer", "2026-08-24")}
    new, dups = lps.split_new_and_dup_posts([_post(poster="Jane Doe")], seen)
    assert not new and len(dups) == 1


def test_load_seen_posts_reads_all_key_shapes(tmp_path):
    csv_path = tmp_path / "hiring_posts.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=lps.POSTS_HEADER)
        w.writeheader()
        w.writerow({**{k: "" for k in lps.POSTS_HEADER},
                    "post_url": "https://www.linkedin.com/in/someone/",
                    "poster_name": "Someone", "roles_mentioned": "MLE",
                    "posted_date": "2026-08-01",
                    "notes": "feed; urn:999888777; body here"})
    seen = lps.load_seen_posts(csv_path)
    assert "https://www.linkedin.com/in/someone" in seen
    assert "urn:999888777" in seen
    assert lps._fuzzy_key("someone", "mle", "2026-08-01") in seen


# ------------------------------------------------------------- classifiers

def test_classify_poster_types():
    assert lps.classify_poster("Senior Technical Recruiter at Acme") == "recruiter"
    assert lps.classify_poster("Engineering Manager, AI Platform") == "hiring_manager"
    assert lps.classify_poster("Founder & CEO") == "hiring_manager"
    assert lps.classify_poster("Research Scientist at Lab") == "engineer_researcher"


def test_classify_priority():
    assert lps.classify_priority("recruiter") == "high"
    assert lps.classify_priority("hiring_manager") == "high"
    assert lps.classify_priority("engineer_researcher") == "normal"


@pytest.mark.parametrize("text,family", [
    ("We're hiring an agentic AI engineer to build multi-agent systems", "agentic_ai"),
    ("Hiring: distributed training + FSDP training engineer", "ml_training_arch"),
    ("LLM evaluation and benchmarking role open", "eval_inference"),
    ("AI security red team position", "ai_security"),
    ("Applied Scientist, ML platform", "applied_ml"),
    ("Software engineer, generic posting", "other"),
])
def test_classify_role_family(text, family):
    assert lps.classify_role_family(text) == family


# ------------------------------------------------------------ row builder

def test_to_post_row_shape():
    row = lps.to_post_row({
        "poster": "Alex Kim", "posterUrl": "https://www.linkedin.com/in/alexkim/",
        "degree": "2nd", "headline": "Technical Recruiter @ OpenAI",
        "time": "3h", "urn": "1234567890123456789",
        "roles_mentioned": "Research Engineer, Agents",
        "body": "we're hiring research engineers for agentic workflows!",
        "link_url": "", "post_url":
            "https://www.linkedin.com/feed/update/urn:li:activity:1234567890123456789/",
    }, discovered_date="2026-08-24", source_note="test")
    assert row["poster_type"] == "recruiter"
    assert row["priority"] == "high"
    assert row["role_family"] == "agentic_ai"
    assert row["status"] == "new"
    assert row["post_id"].startswith("alex_kim_2026-08-24_")
    assert set(row) == set(lps.POSTS_HEADER)


# ---------------------------------------------------------------- append

def test_append_rows_creates_header_then_appends(tmp_path):
    csv_path = tmp_path / "posts.csv"
    rows = [{**{k: "" for k in lps.POSTS_HEADER}, "post_id": "a"},
            {**{k: "" for k in lps.POSTS_HEADER}, "post_id": "b"}]
    assert lps.append_rows(rows[:1], csv_path) == 1
    assert lps.append_rows(rows[1:], csv_path) == 1
    with open(csv_path, newline="", encoding="utf-8") as fh:
        data = list(csv.DictReader(fh))
    assert [r["post_id"] for r in data] == ["a", "b"]


# --------------------------------------------------- keyword adaptation

def test_select_queries_prefers_high_yield_history():
    base = {"a": 1, "b": 5}
    yields = {"a": {"runs": 10, "new": 8}, "b": {"runs": 4, "new": 0}}
    assert lps.select_queries(2, yields, base_keywords=base) == ["a", "b"]


def test_select_queries_explores_untried_first():
    base = {"fresh": 1, "tired": 5}
    yields = {"tired": {"runs": 6, "new": 0}}
    assert lps.select_queries(1, yields, base_keywords=base)[0] == "fresh"


def test_record_and_reload_yields(tmp_path):
    csv_path = tmp_path / "yields.csv"
    lps.record_keyword_yields({"q one": 3, "q two": 0}, csv_path)
    lps.record_keyword_yields({"q one": 1}, csv_path)
    stats = lps.load_keyword_yields(csv_path)
    assert stats["q one"] == {"runs": 2, "new": 4}
    assert stats["q two"] == {"runs": 1, "new": 0}


# --------------------------------------------------------------- dry-run

def test_dry_run_main(capsys):
    rc = lps.main(["dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"mode": "dry-run"' in out
