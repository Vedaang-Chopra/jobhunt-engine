"""Unit tests for scripts/search_strategy/ontology.py (Task 1).

The ontology loader must derive ALL role/domain/seniority/location vocabulary
from the existing preference configs under ``<data_root>/job_research/config/``
— no second copy of keyword lists in code (TITLE_CANON excepted).
"""

from __future__ import annotations

import os
import sys

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from search_strategy.ontology import Ontology, TITLE_CANON, DATA_ROOT_DEFAULT


# ---------------------------------------------------------------------------
# Real-config loads (read-only against jobhunt-data via config_lib.data_root)
# ---------------------------------------------------------------------------

def test_loads_real_config():
    onto = Ontology.load()
    fams = onto.role_families()
    assert "agentic-ai" in fams
    assert fams["agentic-ai"].priority <= fams["post-training"].priority
    assert onto.primary_titles()
    assert onto.domain_terms("agentic-ai")
    assert onto.target_companies()
    assert onto.locations()


def test_no_duplication_of_keywords_file():
    onto = Ontology.load()
    # terms come FROM the yaml, not a second copy in code
    assert onto.source_files()[0].name == "role-keywords.yaml"


def test_title_canon_defined_once():
    assert TITLE_CANON == [
        "Research Engineer", "Research Scientist", "Applied Scientist",
        "ML Engineer", "AI Engineer", "LLM Engineer",
    ]
    onto = Ontology.load()
    titles = onto.primary_titles()
    for t in TITLE_CANON:
        assert t in titles


def test_primary_titles_include_yaml_title_like_keywords():
    onto = Ontology.load()
    # research-engineer family declares "research engineer"/"research scientist"
    # as primary keywords — they are title-like and must surface here.
    titles_lower = {t.lower() for t in onto.primary_titles()}
    assert "research engineer" in titles_lower
    assert "research scientist" in titles_lower
    # non-title keywords must NOT leak into the title vocabulary
    assert "langgraph" not in titles_lower


def test_adjacent_titles_share_a_family():
    onto = Ontology.load()
    adj = onto.adjacent_titles("Research Engineer")
    assert adj
    assert "Research Engineer" not in adj
    # Research Scientist shares the research-engineer/agentic families
    assert "Research Scientist" in adj
    # unknown title -> no adjacency invented
    assert onto.adjacent_titles("Astronaut") == []


def test_seniority_levels_from_config():
    onto = Ontology.load()
    levels = onto.seniority_levels()
    assert "Senior" in levels and "Staff" in levels


def test_locations_from_location_preferences():
    onto = Ontology.load()
    locs = onto.locations()
    assert any("United States" in l for l in locs)


def test_target_companies_from_target_companies_yaml():
    onto = Ontology.load()
    comps = onto.target_companies()
    assert len(comps) >= 5
    assert any("Anthropic" in c or "Cohere" in c for c in comps)


def test_domain_terms_unknown_family_raises():
    onto = Ontology.load()
    try:
        onto.domain_terms("no-such-family")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown family")


# ---------------------------------------------------------------------------
# Synthetic data_root (tmp dir) — never touches JOBHUNT_HOME
# ---------------------------------------------------------------------------

def _write_tmp_configs(tmp_path):
    cfg = tmp_path / "job_research" / "config"
    cfg.mkdir(parents=True)
    (cfg / "role-keywords.yaml").write_text(yaml.safe_dump({
        "role_families": {
            "alpha": {
                "name": "Alpha",
                "priority": 1,
                "primary_keywords": ["ml engineer", "vector db"],
                "seniority": ["Senior", "ML Engineer"],
                "locations": ["United States"],
            },
            "beta": {
                "name": "Beta",
                "priority": 2,
                "primary_keywords": ["research engineer", "evals"],
                "seniority": ["Staff"],
                "locations": ["Canada"],
            },
        },
    }))
    (cfg / "target-companies.yaml").write_text(yaml.safe_dump({
        "companies": [{"name": "Acme", "tier": "T1"}, {"company": "BetaCo"}],
    }))
    (cfg / "location-preferences.yaml").write_text(yaml.safe_dump({
        "location_tiers": {
            "tier_1_primary": {"name": "United States",
                               "cities": ["Atlanta", "Seattle"]},
        },
    }))
    return cfg


def test_load_with_explicit_data_root(tmp_path):
    _write_tmp_configs(tmp_path)
    onto = Ontology.load(data_root=tmp_path)
    assert set(onto.role_families()) == {"alpha", "beta"}
    assert onto.role_families()["alpha"].priority < onto.role_families()["beta"].priority
    assert onto.domain_terms("alpha") == ["ml engineer", "vector db"]
    assert sorted(onto.target_companies()) == ["Acme", "BetaCo"]
    assert "Atlanta" in onto.locations()
    names = [p.name for p in onto.source_files()]
    assert names == ["role-keywords.yaml", "target-companies.yaml",
                     "location-preferences.yaml"]


def test_missing_optional_files_are_tolerated(tmp_path):
    cfg = tmp_path / "job_research" / "config"
    cfg.mkdir(parents=True)
    (cfg / "role-keywords.yaml").write_text(yaml.safe_dump(
        {"role_families": {"only": {"priority": 1,
                                    "primary_keywords": ["llm engineer"]}}}))
    onto = Ontology.load(data_root=tmp_path)
    assert list(onto.role_families()) == ["only"]
    assert onto.target_companies() == []
    assert "LLM Engineer" in onto.primary_titles()


def test_data_root_default_resolves():
    from pathlib import Path
    assert isinstance(DATA_ROOT_DEFAULT, Path)
    assert DATA_ROOT_DEFAULT.name
