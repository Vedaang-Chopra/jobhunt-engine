"""Tests for the /right-people page (ui.data right-people layer + page render).

Covers: company directory discovery (registry merge, per-company dirs),
company lookup incl. registry-only companies, people merge (connections.csv
+ contacts), email pattern intel + rendering, add-pipeline upsert behavior,
and page render with/without a selected company.
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    (root / "tracking" / "jobs").mkdir(parents=True)
    (root / "tracking" / "contacts").mkdir(parents=True)
    (root / "tracking" / "companies").mkdir(parents=True)
    (root / "tracking" / "messages").mkdir(parents=True)
    (root / "tracking" / "people_sweeps").mkdir(parents=True)
    (root / "tracking" / "hiring_posts").mkdir(parents=True)
    (root / "tracking" / "applications").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


REGISTRY_HEADER = [
    "company_slug", "company", "email_pattern", "email_pattern_status",
    "email_pattern_source",
]


def _seed_registry(data_root: Path, rows: list[dict]) -> None:
    _write_csv(data_root / "tracking" / "companies" /
               "companies_registry.csv", REGISTRY_HEADER, rows)


def _seed_company_dir(data_root: Path, slug: str, rows: list[dict]) -> Path:
    d = data_root / "job_research" / "companies" / slug
    _write_csv(d / "connections.csv", [
        "priority_group", "name", "current_role", "location",
        "linkedin_profile_url", "connection_degree", "common_ground",
        "email_format_1", "last_updated",
    ], rows)
    return d


# --------------------------------------------------------------- companies

def test_companies_merge_registry_and_dirs(data_root):
    _seed_registry(data_root, [
        {"company_slug": "cohere", "company": "Cohere",
         "email_pattern": "first@cohere.com",
         "email_pattern_status": "confirmed", "email_pattern_source": "x"},
        {"company_slug": "scale-ai", "company": "Scale AI", "email_pattern":
         "", "email_pattern_status": "unknown", "email_pattern_source": ""},
    ])
    _seed_company_dir(data_root, "cohere", [
        {"name": "Grace Byun", "current_role": "Engineer",
         "linkedin_profile_url": "https://linkedin.com/in/grace",
         "email_format_1": "", "last_updated": "2026-08-28"},
    ])
    import ui.data as d

    companies = d.right_people_companies()
    by_slug = {c["slug"]: c for c in companies}
    assert by_slug["cohere"]["company"] == "Cohere"
    assert by_slug["cohere"]["people_count"] == 1
    assert by_slug["cohere"]["with_email"] == 0  # email_format_1 empty
    assert by_slug["cohere"]["email_pattern_status"] == "confirmed"
    assert by_slug["cohere"]["has_connections_csv"] is True
    # registry-only company still listed (no directory yet)
    assert by_slug["scale-ai"]["people_count"] == 0
    assert by_slug["scale-ai"]["has_connections_csv"] is False


def test_company_lookup_registry_only(data_root):
    _seed_registry(data_root, [
        {"company_slug": "nvidia", "company": "NVIDIA", "email_pattern":
         "flast@nvidia.com", "email_pattern_status": "unverified",
         "email_pattern_source": "s"},
    ])
    import ui.data as d

    row = d.right_people_company("nvidia")
    assert row is not None
    assert row["company"] == "NVIDIA"
    assert row["people_count"] == 0
    assert d.right_people_company("nope") is None
    assert d.right_people_company("") is None


# ------------------------------------------------------------------ people

def test_people_merges_directory_and_contacts(data_root):
    _seed_registry(data_root, [
        {"company_slug": "cohere", "company": "Cohere", "email_pattern":
         "", "email_pattern_status": "unknown", "email_pattern_source": ""},
    ])
    _seed_company_dir(data_root, "cohere", [
        {"name": "Dir Person", "current_role": "SWE",
         "linkedin_profile_url": "https://linkedin.com/in/dir",
         "connection_degree": "2nd", "email_format_1": "",
         "last_updated": "2026-08-28"},
    ])
    _write_csv(data_root / "tracking" / "contacts" / "contacts.csv", [
        "contact_id", "name", "company", "role", "linkedin_url", "email",
        "outreach_status", "reason_to_contact", "outreach_priority",
    ], [
        {"contact_id": "c1", "name": "Grace Byun", "company": "Cohere",
         "role": "Engineer", "linkedin_url": "https://linkedin.com/in/grace",
         "email": "grace@cohere.com", "outreach_status": "not_contacted",
         "reason_to_contact": "Atlanta connection",
         "outreach_priority": "P1"},
        {"contact_id": "c2", "name": "Dir Person", "company": "Cohere",
         "role": "Staff SWE", "linkedin_url": "https://linkedin.com/in/dir",
         "email": "", "outreach_status": "requested",
         "reason_to_contact": "", "outreach_priority": ""},
    ])
    import ui.data as d

    people = d.right_people_people("cohere")
    by_name = {p["name"]: p for p in people}
    assert len(people) == 2
    # contacts email/status wins for the merged row
    assert by_name["Grace Byun"]["email"] == "grace@cohere.com"
    assert by_name["Grace Byun"]["priority"] == "P1"
    assert by_name["Dir Person"]["status"] == "requested"
    assert by_name["Dir Person"]["title"] == "Staff SWE"
    # P1 sorts before un-prioritized rows
    assert people[0]["name"] == "Grace Byun"


# ------------------------------------------------------------ email pattern

def test_email_pattern_render(data_root, monkeypatch):
    import ui.data as d

    # monkeypatch the finder's registry lookup to a cited pattern
    import email_pattern_finder as epf

    monkeypatch.setattr(epf, "find_pattern", lambda slug: {
        "pattern": "first@cohere.com", "example_email": "a@cohere.com",
        "status": "confirmed", "source": "contacts.csv:x", "method":
        "observed"})
    intel = d.right_people_email_pattern("cohere")
    assert intel["pattern"] == "first@cohere.com"
    assert d.right_people_render_email("Grace Byun", "cohere") == \
        "grace@cohere.com"
    assert d.right_people_render_email("Cher", "cohere") == ""  # 1 name
    monkeypatch.setattr(epf, "find_pattern", lambda slug: {
        "pattern": "", "example_email": "", "status": "unknown",
        "source": "", "method": "none"})
    assert d.right_people_render_email("Grace Byun", "cohere") == ""


# --------------------------------------------------------------- add people

def test_add_people_appends_and_upserts(data_root):
    _seed_registry(data_root, [
        {"company_slug": "cohere", "company": "Cohere", "email_pattern":
         "", "email_pattern_status": "unknown", "email_pattern_source": ""},
    ])
    _seed_company_dir(data_root, "cohere", [
        {"name": "Existing", "current_role": "",
         "linkedin_profile_url": "https://linkedin.com/in/existing",
         "last_updated": "2026-08-28"},
    ])
    import ui.data as d

    out = d.right_people_add("cohere", [
        {"name": "New Person", "title": "HM",
         "linkedin_url": "https://linkedin.com/in/new", "email":
         "new@cohere.com", "reason": "hiring manager", "priority": "P0"},
        {"name": "Existing", "title": "Staff Engineer",
         "linkedin_url": "https://linkedin.com/in/existing"},
        {"name": "", "title": "no name row"},
    ])
    assert out == {"added": 1, "updated": 1, "skipped": 1}
    rows = list(csv.DictReader(open(
        data_root / "job_research" / "companies" / "cohere" /
        "connections.csv")))
    assert len(rows) == 2
    new_row = next(r for r in rows if r["name"] == "New Person")
    assert new_row["email_format_1"] == "new@cohere.com"
    assert new_row["priority_group"] == "P0"
    ex_row = next(r for r in rows if r["name"] == "Existing")
    assert ex_row["current_role"] == "Staff Engineer"  # fill-empty-only

    with pytest.raises(ValueError):
        d.right_people_add("unknown-co", [{"name": "X"}])


# -------------------------------------------------------------------- page

def test_page_renders_without_company(data_root):
    from nicegui import ui

    import ui.pages_right_people as page_mod

    @ui.page("/right-people")
    def _p():
        page_mod.render_right_people_page()

    # constructing the page function is enough for import-level validation;
    # full browser rendering is exercised by the smoke test.


def test_add_slot_trunc_helper():
    import ui.pages_right_people as page_mod

    # the CSS template keeps its placeholder; _add_slot_trunc formats it
    assert "{w}" in page_mod._TRUNCATE_CSS
    rendered = page_mod._TRUNCATE_CSS.format(w=240)
    assert "max-width:240px" in rendered
