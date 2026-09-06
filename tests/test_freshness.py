"""Tests for scripts/freshness_check.py — tiered re-verification policy."""
import csv
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from freshness_check import (  # noqa: E402
    assign_tier,
    compute_row_updates,
    days_since,
    http_url_expired,
    load_rows,
    today_utc,
)


def make_row(score="70", status="open", last_checked=None, date_posted=None,
             url="https://boards.greenhouse.io/acme/jobs/123", source="greenhouse",
             stale_flag="", **extra):
    row = {
        "job_id": "j1",
        "company": "Acme",
        "title": "Engineer",
        "job_url": url,
        "canonical_application_url": "",
        "source": source,
        "date_posted": date_posted or "2026-08-01",
        "status": status,
        "priority_v2": score,
        "last_checked": last_checked or "",
        "stale_flag": stale_flag,
    }
    row.update(extra)
    return row


class TestTierAssignment(unittest.TestCase):
    def test_score_68_plus_is_weekly(self):
        self.assertEqual(assign_tier(75.5), "weekly")
        self.assertEqual(assign_tier(68.0), "weekly")

    def test_score_55_to_67_is_biweekly(self):
        self.assertEqual(assign_tier(67.9), "biweekly")
        self.assertEqual(assign_tier(55.0), "biweekly")

    def test_score_below_55_is_stale(self):
        self.assertEqual(assign_tier(54.9), "stale")
        self.assertEqual(assign_tier(23.3), "stale")

    def test_missing_score_is_stale(self):
        self.assertEqual(assign_tier(None), "stale")
        self.assertEqual(assign_tier(""), "stale")


class TestReferenceDate(unittest.TestCase):
    def test_prefers_newest_of_updated_posted(self):
        row = make_row(date_posted="2026-08-01")
        row["date_updated"] = "2026-08-10"
        self.assertEqual(compute_row_updates.__globals__["reference_date"](row),
                         "2026-08-10")

    def test_falls_back_to_date_discovered(self):
        """Rows without posted/updated still start their freshness clock."""
        row = make_row()
        row["date_posted"] = ""
        row["date_updated"] = ""
        row["date_discovered"] = "2026-05-01"
        ref = compute_row_updates.__globals__["reference_date"](row)
        self.assertEqual(ref, "2026-05-01")
        # >90d past discovery -> expiry due under the standard policy
        updates = compute_row_updates(row, today=date(2026, 8, 23))
        self.assertEqual(updates.get("status"), "expired")


class TestDaysSince(unittest.TestCase):
    def test_days_since_parses_iso(self):
        today = today_utc()
        self.assertEqual(days_since(today.isoformat(), today), 0)
        self.assertEqual(days_since((today - timedelta(days=7)).isoformat(), today), 7)

    def test_empty_or_bad_date_returns_none(self):
        self.assertIsNone(days_since("", today_utc()))
        self.assertIsNone(days_since("not-a-date", today_utc()))


class TestStalePolicy(unittest.TestCase):
    """score < 55 -> stale_flag after 30 days unchecked."""

    def test_not_stale_when_recently_checked(self):
        recent = (today_utc() - timedelta(days=10)).isoformat()
        updates = compute_row_updates(make_row(score="40", last_checked=recent))
        self.assertFalse(updates.get("stale_flag", ""))
        self.assertNotIn("status", updates)  # no expiry

    def test_stale_flag_after_30_days_unchecked(self):
        old = (today_utc() - timedelta(days=30)).isoformat()
        updates = compute_row_updates(make_row(score="40", last_checked=old))
        self.assertTrue(updates["stale_flag"])

    def test_stale_flag_when_never_checked_and_old_posted(self):
        # never checked: use date_posted as the reference clock
        old = (today_utc() - timedelta(days=45)).isoformat()
        updates = compute_row_updates(make_row(score="40", last_checked=None,
                                               date_posted=old))
        self.assertTrue(updates["stale_flag"])

    def test_high_score_job_overdue_weekly_check_gets_last_checked_updated(self):
        overdue = (today_utc() - timedelta(days=8)).isoformat()
        row = make_row(score="70", last_checked=overdue)
        updates = compute_row_updates(row, http_expired=False)
        self.assertIn("last_checked", updates)


class TestAutoArchive(unittest.TestCase):
    """status=expired after 90 days past posted/updated date; row kept."""

    def test_expired_after_90_days_past_posted(self):
        old = (today_utc() - timedelta(days=91)).isoformat()
        updates = compute_row_updates(make_row(date_posted=old))
        self.assertEqual(updates["status"], "expired")

    def test_not_expired_within_90_days(self):
        recent = (today_utc() - timedelta(days=60)).isoformat()
        updates = compute_row_updates(make_row(date_posted=recent,
                                               last_checked=recent))
        self.assertNotIn("status", updates)

    def test_already_expired_stays_expired(self):
        updates = compute_row_updates(
            make_row(status="expired", date_posted=(today_utc() - timedelta(days=200)).isoformat()))
        self.assertEqual(updates["status"], "expired")

    def test_uses_date_updated_when_newer(self):
        # posted long ago but updated recently -> not expired
        updates = compute_row_updates(make_row(
            date_posted=(today_utc() - timedelta(days=200)).isoformat(),
            date_updated=(today_utc() - timedelta(days=5)).isoformat()))
        self.assertNotIn("status", updates)


class TestHttpCheck(unittest.TestCase):
    def test_404_means_expired(self):
        self.assertTrue(http_url_expired(404))

    def test_410_means_expired(self):
        self.assertTrue(http_url_expired(410))

    def test_200_ok(self):
        self.assertFalse(http_url_expired(200))

    def test_other_client_errors_are_not_expiry(self):
        self.assertFalse(http_url_expired(403))


class TestWriteBackByIdentity(unittest.TestCase):
    def test_load_rows_preserves_identity_and_write_back_targets_correct_rows(self):
        import freshness_check
        tmp = REPO / ".tmp_test_jobs.csv"
        rows = [
            make_row(job_id="a", score="70", status="open"),
            make_row(job_id="b", score="30", status="open",
                     last_checked=(today_utc() - timedelta(days=31)).isoformat()),
            make_row(job_id="c", score="60", status="open"),
        ]
        fieldnames = list(rows[0].keys())
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                r2 = {k: v for k, v in r.items() if k in fieldnames}
                w.writerow(r2)
        try:
            loaded = load_rows(tmp)
            by_id = {r["job_id"]: r for r in loaded}
            by_id["b"]["stale_flag"] = "true"
            by_id["b"]["last_checked"] = today_utc().isoformat()
            freshness_check.write_rows(tmp, loaded)
            reloaded = {r["job_id"]: r for r in load_rows(tmp)}
            self.assertEqual(reloaded["b"]["stale_flag"], "true")
            self.assertEqual(reloaded["a"]["status"], "open")  # untouched
            self.assertEqual(len(load_rows(tmp)), 3)  # rows kept, never deleted
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
