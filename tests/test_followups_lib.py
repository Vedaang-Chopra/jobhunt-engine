"""TDD tests for scripts/followups_lib.py — follow-up rule engine (Task 2.2)."""

import datetime
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import followups_lib as flib  # noqa: E402

TODAY = datetime.date(2026, 8, 23)


def _row(**overrides):
    row = {
        "job_id": "acme_ai_eng_1",
        "company": "Acme",
        "status": "submitted",
        "date_submitted": "2026-08-20",
        "date_acknowledged": "",
    }
    row.update(overrides)
    return row


class FakeDF:
    """Minimal DataFrame stand-in with .columns and .to_dict."""

    def __init__(self, rows):
        self.rows = rows
        self.columns = sorted({key for r in rows for key in r}) if rows else []

    def to_dict(self, fmt=None):
        return [dict(r) for r in self.rows]


def _df(rows):
    return FakeDF(rows)


# ---------------------------------------------------------------- empty input

def test_empty_dataframe_returns_empty_list():
    assert flib.get_followups(_df([]), today=TODAY) == []


def test_none_like_empty_rows_returns_empty_list():
    assert flib.get_followups([], today=TODAY) == []


# ------------------------------------------------------------- schema checks

def test_missing_required_columns_raises():
    bad = _df([{"job_id": "x", "company": "Y"}])
    try:
        flib.get_followups(bad, today=TODAY)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
        assert "status" in str(exc) and "date_submitted" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_row_dicts_missing_columns_raise():
    try:
        flib.get_followups([{"job_id": "x", "company": "Y"}], today=TODAY)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


# ------------------------------------------------------------ nudge_recruiter

def test_nudge_after_seven_days_no_response():
    followups = flib.get_followups(
        _df([_row(date_submitted="2026-08-16", status="submitted")]),  # exactly 7
        today=TODAY,
    )
    assert len(followups) == 1
    f = followups[0]
    assert f["action"] == "nudge_recruiter"
    assert f["days_since"] == 7


def test_no_nudge_at_six_days():
    followups = flib.get_followups(
        _df([_row(date_submitted="2026-08-17", status="submitted")]),  # 6 days
        today=TODAY,
    )
    assert followups == []


def test_no_nudge_when_acknowledged():
    followups = flib.get_followups(
        _df([_row(date_submitted="2026-08-01",
                  date_acknowledged="2026-08-02")]),
        today=TODAY,
    )
    assert followups == []


def test_no_nudge_for_queued_or_other_statuses():
    rows = [
        _row(job_id="q1", status="queued"),
        _row(job_id="r1", status="rejected"),
        _row(job_id="o1", status="offer_received"),
    ]
    followups = flib.get_followups(_df(rows), today=TODAY)
    assert all(f["action"] != "nudge_recruiter" for f in followups)


# ---------------------------------------------------------------- prep_prompt

def test_prep_prompt_exactly_two_days_out():
    followups = flib.get_followups(
        _df([_row(status="interview_scheduled",
                  interview_date="2026-08-25")]),
        today=TODAY,
    )
    assert len(followups) == 1
    assert followups[0]["action"] == "prep_prompt"
    assert followups[0]["days_since"] == 2


def test_prep_prompt_day_of_interview():
    followups = flib.get_followups(
        _df([_row(interview_date="2026-08-23")]),
        today=TODAY,
    )
    assert len(followups) == 1
    assert followups[0]["action"] == "prep_prompt"
    assert followups[0]["days_since"] == 0


def test_no_prep_prompt_three_days_out():
    followups = flib.get_followups(
        _df([_row(interview_date="2026-08-26")]),
        today=TODAY,
    )
    assert followups == []


# ---------------------------------------------------------- respond_checklist

def test_respond_checklist_on_offer_status():
    followups = flib.get_followups(
        _df([_row(status="offer_received")]),
        today=TODAY,
    )
    assert len(followups) == 1
    f = followups[0]
    assert f["action"] == "respond_checklist"
    assert f["reason"]
    assert set(f) == {"job_id", "company", "action", "reason", "days_since"}


def test_respond_checklist_via_offer_date():
    followups = flib.get_followups(
        _df([_row(offer_date="2026-08-22")]),
        today=TODAY,
    )
    assert len(followups) == 1
    assert followups[0]["action"] == "respond_checklist"


# ------------------------------------------------------------------ structure

def test_result_fields_and_multiple_actions():
    rows = [
        _row(job_id="a1", company="Alpha",
             date_submitted="2026-07-01", status="submitted"),
        _row(job_id="b1", company="Beta", interview_date="2026-08-24"),
        _row(job_id="c1", company="Gamma", status="offer_received"),
        _row(job_id="d1", company="Delta"),  # no action due
    ]
    followups = flib.get_followups(_df(rows), today=TODAY)
    by_job = {f["job_id"]: f["action"] for f in followups}
    assert by_job == {
        "a1": "nudge_recruiter",
        "b1": "prep_prompt",
        "c1": "respond_checklist",
    }
    for f in followups:
        assert set(f) == {"job_id", "company", "action", "reason", "days_since"}


# ------------------------------------------------------------- summarize

def test_summarize_counts_by_action():
    followups = [
        {"action": "nudge_recruiter"},
        {"action": "nudge_recruiter"},
        {"action": "prep_prompt"},
        {"action": "respond_checklist"},
    ]
    counts = flib.summarize_followups(followups)
    assert counts == {
        "nudge_recruiter": 2,
        "prep_prompt": 1,
        "respond_checklist": 1,
    }


def test_summarize_empty():
    assert flib.summarize_followups([]) == {}
