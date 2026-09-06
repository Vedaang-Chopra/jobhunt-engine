"""Unit tests for linkedin_recommended_sweep merge logic (fixture extraction ->
normalized rows -> dedup vs existing -> scrutinize -> recommendation_rank in
notes). No browser, no live calls, no writes to canonical CSVs."""

import copy
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import linkedin_recommended_sweep as sweep  # noqa: E402


def _fixture():
    path = os.path.join(REPO, "tests", "fixtures", "linkedin_recommended_fixture.json")
    with open(path) as fh:
        data = json.load(fh)
    for i, card in enumerate(data, start=1):
        card.setdefault("recommendation_rank", i)
    return data


def test_merge_normalizes_rows():
    extraction = _fixture()
    accepted, duplicates, rejected = sweep.merge_extraction(extraction, sweep.DedupIndex())
    # card 3 shares card 1's URL (dup), card 5 has empty title (rejected),
    # Bangalore card is scrutinize-rejected; cards 1 and 2 are accepted.
    assert len(accepted) == 2
    assert accepted[0]["title"] == "AI Agent Engineer"
    assert accepted[0]["company"] == "Acme Intelligence"
    assert accepted[0]["source"] == "l2_recommended"
    assert len(duplicates) == 1
    assert rejected and any("missing_required_field" in r.get("flags", []) for r in rejected)


def test_recommendation_rank_stamped_into_notes():
    extraction = _fixture()
    accepted, _, _ = sweep.merge_extraction(extraction, sweep.DedupIndex())
    # Novum Labs card is fixture rank 2.
    novum = next(r for r in accepted if r["company"] == "Novum Labs")
    assert "recommendation_rank=2" in novum["notes"]
    assert novum["notes"].startswith("l2_recommended;")


def test_dedup_against_existing_index():
    extraction = [card for card in _fixture() if card["title"] == "Research Engineer, Post-Training"]
    dedup = sweep.DedupIndex()
    first, _, _ = sweep.merge_extraction(copy.deepcopy(extraction), dedup)
    assert len(first) == 1
    second, dups, _ = sweep.merge_extraction(copy.deepcopy(extraction), dedup)
    assert second == []
    assert len(dups) == 1


def test_scrutinize_filters_unsupported_location():
    extraction = [
        {"recommendation_rank": 7,
         "title": "Senior Data Scientist",
         "company": "Outsourcia",
         "location": "Bangalore, India",
         "posted_age": "1 day ago",
         "url": "https://www.linkedin.com/jobs/view/4100000003"},
    ]
    accepted, dups, rejected = sweep.merge_extraction(extraction, sweep.DedupIndex())
    assert accepted == [] and dups == []
    assert len(rejected) == 1
    assert "flags" in rejected[0]


def test_explicit_rank_overrides_position():
    extraction = [_fixture()[1]]
    extraction[0]["recommendation_rank"] = 42
    accepted, _, _ = sweep.merge_extraction(extraction, sweep.DedupIndex())
    assert "recommendation_rank=42" in accepted[0]["notes"]


def test_log_search_run_uses_header_and_source(tmp_path):
    runs_csv = str(tmp_path / "runs.csv")
    sweep.log_search_run("l2_recommended", 5, 1, 2, "ok", runs_csv=runs_csv)
    import csv
    with open(runs_csv) as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == sweep.SEARCH_RUNS_HEADER
    assert rows[1][2] == "l2_recommended"
    assert rows[1][3] == "5"
