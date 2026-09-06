"""TDD tests for scripts/right_people.py — CLI shell (plan Task 6).

Sibling libs (right_people_lib, search_plan_lib, ...) may not be landed yet:
every test stubs the boundary. The CLI must import sibling libs lazily inside
functions, never at module top-level.
"""
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import right_people  # noqa: E402

FAKE_TARGET = {
    "kind": "company",
    "company": "Cohere",
    "company_slug": "cohere",
    "job": None,
    "jd_path": None,
}

FAKE_PLAN = [
    {
        "pass_id": 1,
        "family": "existing_1st",
        "tier": "1st",
        "url": "https://www.linkedin.com/search/results/people/?company=Cohere&network=%5B%22F%22%5D",
        "filters": {"currentCompany": "Cohere", "connectionDegree": "1st"},
        "verify": "chips+count",
        "expected_columns": ["name", "title", "location", "degree", "linkedin_url"],
    },
    {
        "pass_id": 2,
        "family": "gt_alumni",
        "tier": "alumni",
        "url": "https://www.linkedin.com/search/results/people/?company=Cohere&schoolFilter=16818",
        "filters": {"currentCompany": "Cohere", "schoolFilter": 16818},
        "verify": "chips+count",
        "expected_columns": ["name", "title", "location", "degree", "linkedin_url"],
    },
]


def _fake_resolve_and_plan(args):
    return dict(FAKE_TARGET), [dict(p) for p in FAKE_PLAN]


# ---------------------------------------------------------------- argparse --


def test_missing_both_flags_is_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc:
        right_people.parse_args([])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--company" in err and "--job-url" in err


def test_both_flags_is_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc:
        right_people.parse_args(
            ["--company", "Cohere", "--job-url", "https://jobs.example/x"]
        )
    assert exc.value.code == 2


def test_defaults():
    args = right_people.parse_args(["--company", "Cohere"])
    assert args.company == "Cohere"
    assert args.job_url is None
    assert args.live is False
    assert args.limit == 15
    assert args.cap == 12
    assert args.json is False
    assert args.queue_drafts is False


# ----------------------------------------------------------------- dry-run --


def test_dry_run_prints_table_and_writes_nothing(capsys, monkeypatch):
    monkeypatch.setattr(right_people, "_resolve_and_plan", _fake_resolve_and_plan)

    upsert_calls = []
    poison = types.ModuleType("upsert_lib")
    poison.upsert_contacts = lambda *a, **k: upsert_calls.append(a)
    monkeypatch.setitem(sys.modules, "upsert_lib", poison)

    rc = right_people.main(["--company", "Cohere"])
    out = capsys.readouterr().out

    assert rc == 0
    # human-readable table: header + both passes
    assert "pass_id" in out.lower() or "pass" in out.lower()
    assert "existing_1st" in out
    assert "gt_alumni" in out
    # filters summary visible
    assert "currentCompany" in out
    # no ledger/CSV writes were attempted
    assert upsert_calls == []


def test_dry_run_does_not_require_sibling_libs(monkeypatch, capsys):
    """Dry-run works purely from the monkeypatched boundary."""
    monkeypatch.setattr(right_people, "_resolve_and_plan", _fake_resolve_and_plan)
    rc = right_people.main(["--company", "Cohere"])
    assert rc == 0
    assert capsys.readouterr().out.strip()


# -------------------------------------------------------------------- json --


def test_json_prints_target_and_plan(capsys, monkeypatch):
    monkeypatch.setattr(right_people, "_resolve_and_plan", _fake_resolve_and_plan)
    rc = right_people.main(["--company", "Cohere", "--json"])
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert set(payload) == {"target", "plan"}
    assert payload["target"]["company"] == "Cohere"
    assert payload["target"]["company_slug"] == "cohere"
    assert payload["target"]["kind"] == "company"
    assert len(payload["plan"]) == 2
    assert payload["plan"][0]["family"] == "existing_1st"
    assert payload["plan"][1]["filters"]["schoolFilter"] == 16818


# --------------------------------------------------------- TargetNotFound --


def test_target_not_found_exits_1_with_stderr(capsys, monkeypatch):
    def _raise(args):
        raise right_people.TargetNotFound("no job row matches url https://x.example/nope")

    monkeypatch.setattr(right_people, "_resolve_and_plan", _raise)
    rc = right_people.main(["--job-url", "https://x.example/nope"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "not found" in captured.err.lower()
