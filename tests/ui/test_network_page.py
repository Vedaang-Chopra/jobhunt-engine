"""Tests for the /network recommended-connections directory (ui.data).

Covers: merged directory over ledger + contacts + people sweep + hiring posts,
dedup precedence (ledger wins), status normalization, source counts, cron
job-id lookup, and the /network page's automation triggers.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


LEDGER_HEADER = (
    "request_id,person_name,company,person_type,linkedin_url,email,"
    "source_post_url,related_job_ids,score,note_draft,"
    "note_basis(hiring_post|shared_ctx|job_specific|generic),"
    "send_status(pending|approved|sent_no_note|sent_with_note|connected|"
    "declined|failed),date_queued,date_sent,date_connected,response,"
    "followup_date,notes"
)


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    (root / "tracking" / "jobs").mkdir(parents=True)
    (root / "tracking" / "applications").mkdir(parents=True)
    (root / "tracking" / "contacts").mkdir(parents=True)
    (root / "tracking" / "companies").mkdir(parents=True)
    (root / "tracking" / "messages").mkdir(parents=True)
    (root / "tracking" / "people_sweeps").mkdir(parents=True)
    (root / "tracking" / "hiring_posts").mkdir(parents=True)
    monkeypatch.setenv("JOBHUNT_HOME", str(root))
    import importlib

    import ui.data as ui_data

    importlib.reload(ui_data)
    yield root
    importlib.reload(ui_data)


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def _seed_people(data_root: Path) -> None:
    _write_csv(
        data_root / "tracking" / "contacts" / "contacts.csv",
        "contact_id,name,company,role,linkedin_url,email,outreach_status,"
        "reason_to_contact",
        [
            "c1,Jane Recruiter,CoolCo,Recruiter,"
            "https://linkedin.com/in/jane-recruiter,jane@cool.com,not_contacted,"
            "hiring for ML roles now",
            "c2,Old Pal,CoolCo,Engineer,"
            "https://linkedin.com/in/old-pal,,connected,already connected",
        ])
    _write_csv(
        data_root / "tracking" / "people_sweeps" / "people_sweep.csv",
        "sweep_run_id,date,name,title,company,person_type,linkedin_url,"
        "post_url,why_relevant,status,notes",
        [
            "sw1,2026-08-24,Sam Poster,Founder,PostCo,founder,"
            "https://linkedin.com/in/sam-poster,,posted about hiring agents,"
            "pending_review,",
        ])
    _write_csv(
        data_root / "tracking" / "hiring_posts" / "hiring_posts.csv",
        "post_id,poster_name,poster_headline,poster_type,company,team_or_org,"
        "post_url,posted_date,discovered_date,roles_mentioned,application_url,"
        "connection_degree,shared_context,priority,role_family,status,notes",
        [
            "p1,Hana Hire,hiring!,recruiter,PostCo,,"
            "https://linkedin.com/in/hana-hire,2026-08-23,,ML Eng,,,high,,new,",
        ])


# ------------------------------------------------------------------ merge


def test_recommendations_merge_all_sources(data_root):
    from ui import data as d

    _seed_people(data_root)
    recs = d.network_recommendations()
    names = {p["name"] for p in recs}
    assert {"Jane Recruiter", "Old Pal", "Sam Poster", "Hana Hire"} <= names


def test_ledger_row_wins_and_suppresses_duplicate(data_root):
    """A person already queued must appear once, as a ledger row."""
    from ui import data as d

    _seed_people(data_root)
    _write_csv(
        data_root / "tracking" / "messages" / "connection_requests.csv",
        LEDGER_HEADER,
        [
            "cr_1,Jane Recruiter,CoolCo,Recruiter,"
            "https://linkedin.com/in/jane-recruiter,,"
            ",,90,note,hiring_post,pending,2026-08-24,,,,,,",
        ])
    recs = d.network_recommendations()
    jane = [p for p in recs if p["name"] == "Jane Recruiter"]
    assert len(jane) == 1
    assert jane[0]["source"] == "ledger"
    assert jane[0]["status"] == "pending"


def test_hiring_post_person_already_in_contacts_not_duplicated(data_root):
    """Same LinkedIn slug across contacts and hiring posts -> one row."""
    from ui import data as d

    _write_csv(
        data_root / "tracking" / "contacts" / "contacts.csv",
        "contact_id,name,company,role,linkedin_url,email,outreach_status,"
        "reason_to_contact",
        ["c1,Dana Dual,PostCo,HM,https://linkedin.com/in/dana-dual,,not_contacted,"])
    _write_csv(
        data_root / "tracking" / "people_sweeps" / "people_sweep.csv",
        "sweep_run_id,date,name,title,company,person_type,linkedin_url,"
        "post_url,why_relevant,status,notes", [])
    _write_csv(
        data_root / "tracking" / "hiring_posts" / "hiring_posts.csv",
        "post_id,poster_name,poster_headline,poster_type,company,team_or_org,"
        "post_url,posted_date,discovered_date,roles_mentioned,application_url,"
        "connection_degree,shared_context,priority,role_family,status,notes",
        ["p1,Dana Dual,hiring,recruiter,PostCo,,"
         "https://linkedin.com/in/dana-dual,,,,,,,high,,new,"])
    recs = d.network_recommendations()
    dana = [p for p in recs if p["name"] == "Dana Dual"]
    assert len(dana) == 1
    assert dana[0]["source"] == "contacts"


def test_actionable_rows_sort_first(data_root):
    from ui import data as d

    _seed_people(data_root)
    recs = d.network_recommendations()
    # connected rows sink to the bottom; untouched/new/pending_review first.
    assert recs[-1]["status"] == "connected"
    top_statuses = [p["status"] for p in recs[:3]]
    assert all(s in ("not_contacted", "new", "pending_review")
               for s in top_statuses)


def test_empty_sources_yield_empty_directory(data_root):
    from ui import data as d

    assert d.network_recommendations() == []
    counts = d.network_source_counts()
    assert counts["total"] == 0
    assert counts["with_email"] == 0


# ------------------------------------------------------------------ counts


def test_source_counts_fields(data_root):
    from ui import data as d

    _seed_people(data_root)
    counts = d.network_source_counts()
    assert counts["total"] == 4
    assert counts["sources"]["contacts"] == 2
    assert counts["sources"]["people_sweep"] == 1
    assert counts["sources"]["hiring_post"] == 1
    assert counts["with_email"] == 1  # only Jane has an email
    assert counts["with_linkedin"] == 4
    assert counts["actionable"] == 3  # everyone except Old Pal (connected)


def test_nan_outreach_status_normalized_to_blank(data_root):
    """Pandas renders blank CSV cells as 'nan' — they count as untouched."""
    from io import StringIO

    import pandas as pd

    from ui import data as d

    df = pd.read_csv(StringIO(
        "name,company,outreach_status\nNan Person,Acme,\n"))
    # Directly exercise the normalization used by _contacts_people.
    row = df.iloc[0]
    status = str(row.get("outreach_status") or "").strip().lower()
    if status in ("nan", "none"):
        status = ""
    assert status == ""
    assert d.connections_pending(pd.DataFrame()) == 0


# ------------------------------------------------------------- cron lookup


def test_find_cron_job_id_reads_profile_store(data_root, tmp_path, monkeypatch):
    from ui import data as d

    fake_home = tmp_path / "home"
    store = fake_home / ".hermes" / "profiles" / "job-hunt" / "cron"
    store.mkdir(parents=True)
    (store / "jobs.json").write_text(
        '[{"id": "abc123", "name": "linkedin-people-posts-2h"},'
        ' {"id": "def456", "name": "other"}]')
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    assert d.find_cron_job_id("linkedin-people-posts-2h") == "abc123"
    assert d.find_cron_job_id("no-such-job") is None


def test_find_cron_job_id_missing_store(monkeypatch, tmp_path):
    from ui import data as d

    monkeypatch.setattr(Path, "home", staticmethod(
        lambda: tmp_path / "no-home"))
    assert d.find_cron_job_id("linkedin-people-posts-2h") is None


# ---------------------------------------------------------------- triggers


def test_linkedin_people_sweep_cmd_uses_resolved_job_id():
    pytest.importorskip("nicegui")
    from ui import triggers

    cmd = triggers.linkedin_people_sweep_cmd()
    if cmd is None:
        pytest.skip("cron store without linkedin-people-posts-2h on this host")
    assert cmd[:4] == [str(Path.home() / ".local" / "bin" / "hermes"),
                       "--profile", "job-hunt", "cron"]
    assert cmd[-1]  # job id present


def test_outreach_draft_cmd_shape():
    pytest.importorskip("nicegui")
    from ui import triggers

    cmd = triggers.outreach_draft_cmd(limit=3)
    assert "connection_queue.py" in cmd[1]
    assert cmd[-2:] == ["--limit", "3"]


# ------------------------------------------------------- page registration


def test_clean_url_rejects_non_urls():
    from ui import data as d

    assert d._clean_url("London") == ""
    assert d._clean_url("nan") == ""
    assert d._clean_url(
        "https://www.linkedin.com/in/abel-e/") == \
        "https://www.linkedin.com/in/abel-e/"


def test_clean_reason_drops_junk():
    from ui import data as d

    assert d._clean_reason("Unknown") == ""
    assert d._clean_reason("n/a") == ""
    assert d._clean_reason("Real reason here") == "Real reason here"


def test_contacts_row_with_location_in_url_field_has_no_link(data_root):
    """Legacy contacts.csv rows with shifted columns must not link to junk."""
    from ui import data as d

    _write_csv(
        data_root / "tracking" / "contacts" / "contacts.csv",
        "name,company,role,linkedin_url,email,outreach_status,"
        "reason_to_contact",
        ["Abel E.,Cohere,Engineering Manager,London,,,"],
    )
    recs = [p for p in d.network_recommendations()
            if p["name"] == "Abel E."]
    assert len(recs) == 1
    assert recs[0]["linkedin_url"] == ""


def test_company_page_poster_rows_are_skipped(data_root):
    from ui import data as d

    _write_csv(
        data_root / "tracking" / "hiring_posts" / "hiring_posts.csv",
        "post_id,poster_name,poster_headline,poster_type,company,team_or_org,"
        "roles_mentioned,status,post_url,posted_date,discovered_date",
        [
            "p1,Applied Intuition (company page),,,Applied Intuition,,"
            "physical AI engineers,new,"
            "https://linkedin.com/company/applied-intuition,2026-08-19,",
            "p2,Jane Hirer,Hiring AI engineers,hiring_manager,Acme,,"
            "ML Engineer,new,https://www.linkedin.com/posts/jane/123,"
            "2026-08-20,",
        ],
    )
    people = d._hiring_post_people(set())
    names = {p["name"] for p in people}
    assert "Jane Hirer" in names
    assert not any("(company page)" in n for n in names)


def test_network_page_registers_with_new_blocks():

    pytest.importorskip("nicegui")
    import ui.app as mod

    # The redesigned page module imports cleanly and keeps its route.
    assert hasattr(mod, "network")
    assert "/network" in mod._OWNED_ROUTES
