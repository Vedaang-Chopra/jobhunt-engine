"""Tests for scripts/poster_connect_sweep.py (Task 11)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import connection_queue as cq  # noqa: E402
import poster_connect_sweep as pcs  # noqa: E402

POSTS_HEADER = ["post_id", "poster_name", "poster_headline", "poster_type",
                "company", "team_or_org", "post_url", "posted_date",
                "discovered_date", "roles_mentioned", "application_url",
                "connection_degree", "shared_context", "priority",
                "role_family", "status", "notes"]


def write_posts(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POSTS_HEADER)
        w.writeheader()
        for r in rows:
            full = {k: "" for k in POSTS_HEADER}
            full.update(r)
            w.writerow(full)


@pytest.fixture
def env(tmp_path):
    posts = tmp_path / "hiring_posts.csv"
    reqs = tmp_path / "connection_requests.csv"
    with reqs.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(cq.HEADER)
    return posts, reqs


BASE = dict(post_id="p1", poster_name="Jane Recruiter", poster_type="recruiter",
            company="Acme", post_url="https://linkedin.com/in/jane/",
            roles_mentioned="ML Engineer", priority="high", status="new")


def test_queue_rows_created_from_fixture(env):
    posts, reqs = env
    write_posts(posts, [BASE])
    people, _ = pcs.poster_people(posts, reqs)
    assert len(people) == 1
    assert people[0]["source_post_url"] == BASE["post_url"]
    rows, skipped = pcs.build_queue_rows(people)
    assert not skipped
    person0, row = rows[0]
    assert set(row) == set(cq.HEADER)
    assert row[cq.HEADER[10]] == "hiring_post"
    assert row["source_post_url"] == BASE["post_url"]
    assert row[cq.STATUS_COL] == "pending"
    assert row["note_draft"]  # composed note present and valid


def test_connected_and_already_queued_excluded(env):
    posts, reqs = env
    write_posts(posts, [dict(BASE, status="connected"),
                        dict(BASE, post_id="p2", poster_name="Bob Builder")])
    # Bob already queued in requests ledger.
    existing = {k: "" for k in cq.HEADER}
    existing.update({"request_id": "cr_x", "person_name": "Bob Builder"})
    cq.write_requests([existing], reqs)
    people, _ = pcs.poster_people(posts, reqs)
    assert people == []


def test_recruiter_hm_priority_ordering(env):
    posts, _ = env
    write_posts(posts, [
        dict(BASE, post_id="p_eng", poster_name="Zed Engineer",
             poster_type="engineer_researcher", priority="high"),
        dict(BASE, post_id="p_rec", poster_name="Alice Recruiter",
             poster_type="recruiter", priority="normal"),
        dict(BASE, post_id="p_hm", poster_name="Carl Manager",
             poster_type="hiring_manager", priority="normal"),
    ])
    people, _ = pcs.poster_people(posts, None)
    names = [p["person_name"] for p in people]
    assert names.index("Alice Recruiter") < names.index("Zed Engineer")
    assert names.index("Carl Manager") < names.index("Zed Engineer")
    assert all(p["_high_priority"] for p in people[:2])


def test_daily_cap_25(env):
    posts, reqs = env
    write_posts(posts, [dict(BASE, post_id=f"p{i}",
                             poster_name=f"Person {i}")
                        for i in range(30)])
    people, sent_today = pcs.poster_people(posts, reqs)
    quota = max(0, pcs.MAX_DAILY_SENDS - sent_today)
    batch = people[:quota]
    assert pcs.MAX_DAILY_SENDS == 25
    assert len(batch) == 25
    # With 5 already sent today the cap leaves only 20 slots.
    today = cq.today_iso()
    existing = []
    for i in range(5):
        r = {k: "" for k in cq.HEADER}
        r.update({"request_id": f"cr_s{i}", "person_name": f"Sent {i}",
                  "date_sent": today})
        r[cq.STATUS_COL] = "sent_no_note"
        existing.append(r)
    cq.write_requests(existing, reqs)
    people2, sent2 = pcs.poster_people(posts, reqs)
    assert sent2 == 5
    assert max(0, pcs.MAX_DAILY_SENDS - sent2) == 20
    assert len(people2[:max(0, pcs.MAX_DAILY_SENDS - sent2)]) == 20


def test_dry_run_prints_without_side_effects(env, capsys):
    posts, reqs = env
    write_posts(posts, [
        dict(BASE),
        dict(BASE, post_id="p2", poster_name="Zed Engineer",
             poster_type="engineer_researcher", priority="low"),
    ])
    before = reqs.read_bytes()
    rc = pcs.main(["--dry-run", "--posts-path", str(posts),
                   "--requests-path", str(reqs)])
    out = capsys.readouterr().out
    assert rc == 0
    assert reqs.read_bytes() == before          # no ledger mutation
    assert "DRY-RUN" in out
    assert "INTENDED ACTIONS" in out
    assert "open profile https://linkedin.com/in/jane/" in out
    assert "sent_with_note" in out
    assert "Zed Engineer" in out                # both people listed
    assert out.index("Jane Recruiter") < out.index("Zed Engineer")  # priority


def test_live_requires_injected_driver(env):
    posts, reqs = env
    assert pcs.main(["--live", "--posts-path", str(posts),
                     "--requests-path", str(reqs)]) == 2


def test_live_stop_on_warning(env, capsys, monkeypatch, tmp_path):
    posts, reqs = env
    write_posts(posts, [])
    # Two approved rows.
    rows = []
    for name in ("A One", "B Two"):
        person = {"person_name": name, "company": "Acme",
                  "person_type": "recruiter",
                  "linkedin_url": "https://x/", "email": "",
                  "source_post_url": "https://p/",
                  "_role_hint": "ML roles", "_post_hint": "your hiring post",
                  "_score": 80, "_basis": "hiring_post"}
        r, sk = pcs.build_queue_rows([person])
        assert not sk
        person0, row0 = r[0]
        row0[cq.STATUS_COL] = "approved"
        rows.append(row0)
    cq.write_requests(rows, reqs)
    calls = []

    def fake_driver(row, note):
        calls.append(row["person_name"])
        if row["person_name"] == "B Two":
            return pcs.SendResult(ok=False, used_note=False,
                                  warning="CAPTCHA challenge detected")
        return pcs.SendResult(ok=True, used_note=True)

    monkeypatch.setattr(pcs.cq, "REQ_PATH", reqs)
    results = pcs.live_send(fake_driver, cq.read_requests(reqs), reqs)
    out = capsys.readouterr().out
    assert "STOP-ON-WARNING" in out
    assert calls[-1] == "B Two"                 # aborted on warning
    assert len(results) == 2
    statuses = {r["person_name"]: r[cq.STATUS_COL]
                for r in cq.read_requests(reqs)}
    assert statuses["A One"] == "sent_with_note"
