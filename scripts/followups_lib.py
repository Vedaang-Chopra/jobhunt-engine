"""Follow-up rule engine (Task 2.2).

Pure functions that derive follow-up actions from the applications tracking
table. Accepts any DataFrame-like or row-dict sequence so the module works
with or without pandas.

Rules:
- applied >= 7 days ago with no response -> ``nudge_recruiter``
- interview scheduled within <= 2 days   -> ``prep_prompt``
- offer received                          -> ``respond_checklist``
"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

REQUIRED_COLUMNS = ("job_id", "company", "status", "date_submitted")

NO_RESPONSE_STATUSES = {"submitted", "applied"}
NUDGE_AFTER_DAYS = 7
PREP_WITHIN_DAYS = 2


def _get_columns(apps_df: Any) -> list:
    """Return the column names of a DataFrame-like object."""
    if hasattr(apps_df, "columns"):
        return [str(c) for c in apps_df.columns]
    return []


def _iter_rows(apps_df: Any):
    """Yield dict rows from a DataFrame-like object or a sequence of dicts."""
    if hasattr(apps_df, "to_dict"):
        yield from apps_df.to_dict("records")
        return
    for row in apps_df:
        if isinstance(row, dict):
            yield row
        else:
            # Named-tuple-like / Series rows
            yield dict(row)


def _parse_date(value) -> datetime.date | None:
    """Parse an ISO 8601 date (YYYY-MM-DD); return None on blank/invalid."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def _row_get(row: dict, key: str):
    value = row.get(key)
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def get_followups(apps_df: Any, today: datetime.date | None = None) -> list[dict]:
    """Derive follow-up actions from application rows.

    Args:
        apps_df: DataFrame-like object (or iterable of dicts) with the
            required columns.
        today: Reference date for day computations; defaults to the real
            current date. Inject for deterministic behavior.

    Returns:
        List of {job_id, company, action, reason, days_since} dicts.

    Raises:
        ValueError: if required columns are missing.
    """
    if today is None:
        today = datetime.date.today()
    elif isinstance(today, datetime.datetime):
        today = today.date()

    columns = _get_columns(apps_df)
    if columns:
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise ValueError(f"missing required columns: {missing}")

    followups: list[dict] = []
    for idx, row in enumerate(_iter_rows(apps_df)):
        if not columns:
            missing = [c for c in REQUIRED_COLUMNS if c not in row]
            if missing:
                raise ValueError(
                    f"row {idx}: missing required columns: {missing}"
                )
        job_id = _row_get(row, "job_id")
        company = _row_get(row, "company") or ""
        status = (_row_get(row, "status") or "").lower()
        submitted = _parse_date(_row_get(row, "date_submitted"))
        days_since = (today - submitted).days if submitted else None

        # Rule 1: applied >= NUDGE_AFTER_DAYS ago, still no response.
        if (
            days_since is not None
            and days_since >= NUDGE_AFTER_DAYS
            and status in NO_RESPONSE_STATUSES
            and _row_get(row, "date_acknowledged") is None
        ):
            followups.append({
                "job_id": job_id,
                "company": company,
                "action": "nudge_recruiter",
                "reason": f"applied {days_since} days ago with no response",
                "days_since": days_since,
            })

        # Rule 2: interview coming up within PREP_WITHIN_DAYS days.
        interview_date = _parse_date(_row_get(row, "interview_date"))
        if interview_date is not None:
            until_interview = (interview_date - today).days
            if -1 <= until_interview <= PREP_WITHIN_DAYS:
                followups.append({
                    "job_id": job_id,
                    "company": company,
                    "action": "prep_prompt",
                    "reason": f"interview scheduled in {until_interview} days",
                    "days_since": until_interview,
                })

        # Rule 3: offer received — respond.
        offer_status = status == "offer_received"
        has_offer_date = _parse_date(_row_get(row, "offer_date")) is not None
        if offer_status or has_offer_date:
            followups.append({
                "job_id": job_id,
                "company": company,
                "action": "respond_checklist",
                "reason": "offer received; response checklist due",
                "days_since": days_since,
            })

    return followups


def summarize_followups(followups: list[dict]) -> dict:
    """Count follow-ups by action type."""
    return dict(Counter(f.get("action", "") for f in followups))
