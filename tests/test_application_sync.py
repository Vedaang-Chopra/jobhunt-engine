#!/usr/bin/env python3
"""Unit tests for scripts/application_sync.py transition logic (Task 6)."""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import application_sync as sync  # noqa: E402


def app_row(**over):
    row = {
        "application_id": "a1", "job_id": "j1", "company": "Acme",
        "role": "ML Engineer", "job_url": "https://boards.example.com/acme/jobs/1",
        "status": "queued", "resume_variant": "", "referral_contact": "",
        "date_queued": "2026-08-01", "date_resume_ready": "",
        "date_submitted": "", "date_acknowledged": "",
        "date_last_status_change": "", "current_stage": "queued",
        "rejection_reason": "", "follow_up_date": "", "notes": "",
    }
    row.update(over)
    return row


TODAY = datetime.date(2026, 8, 23)


class TestMarkStatus(unittest.TestCase):
    def test_queued_to_submitted_sets_dates(self):
        r = app_row()
        changes = sync.mark_status(r, "submitted", TODAY)
        self.assertEqual(r["status"], "submitted")
        self.assertEqual(r["date_submitted"], "2026-08-23")
        self.assertEqual(r["date_last_status_change"], "2026-08-23")
        self.assertIn("status queued -> submitted", changes)

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):
            sync.mark_status(app_row(), "offer_accepted", TODAY)

    def test_lifecycle_requires_submitted_first(self):
        for bad in ("acknowledged", "rejected", "interview", "withdrawn"):
            with self.assertRaises(ValueError, msg=bad):
                sync.mark_status(app_row(status="queued"), bad, TODAY)

    def test_cannot_resubmit_after_withdrawal(self):
        with self.assertRaises(ValueError):
            sync.mark_status(app_row(status="withdrawn"), "submitted", TODAY)

    def test_acknowledged_fills_date_once(self):
        r = app_row(status="submitted", date_submitted="2026-08-10")
        sync.mark_status(r, "acknowledged", TODAY)
        self.assertEqual(r["date_acknowledged"], "2026-08-23")

    def test_rejection_requires_reason(self):
        with self.assertRaises(ValueError):
            sync.mark_status(app_row(status="submitted"), "rejected", TODAY)

    def test_rejection_records_reason(self):
        r = app_row(status="submitted", date_submitted="2026-08-10")
        sync.mark_status(r, "rejected", TODAY, reason="role filled")
        self.assertEqual(r["rejection_reason"], "role filled")
        self.assertEqual(r["date_last_status_change"], "2026-08-23")

    def test_interview_sets_followup_plus7d(self):
        r = app_row(status="submitted")
        sync.mark_status(r, "interview", TODAY)
        self.assertEqual(r["follow_up_date"], "2026-08-30")

    def test_current_stage_tracks_status(self):
        r = app_row(status="submitted")
        sync.mark_status(r, "interview", TODAY)
        self.assertEqual(r["current_stage"], "interview")


class TestPortalClassification(unittest.TestCase):
    def test_404_is_possibly_closed(self):
        self.assertEqual(sync.classify_portal_check(
            "https://x/j/1", {"code": 404, "final_url": "https://x/j/1"}),
            "possibly_closed")

    def test_redirect_to_listing_root_possibly_closed(self):
        self.assertEqual(sync.classify_portal_check(
            "https://x/jobs/12345",
            {"code": 302, "final_url": "https://x/jobs"}),
            "possibly_closed")

    def test_403_login_walled_needs_manual(self):
        self.assertEqual(sync.classify_portal_check(
            "https://x/j/1", {"code": 403, "final_url": "https://x/j/1"}),
            "needs_manual")

    def test_redirect_to_login_needs_manual(self):
        self.assertEqual(sync.classify_portal_check(
            "https://x/j/1",
            {"code": 302,
             "final_url": "https://x/login?redirect=/j/1"}),
            "needs_manual")

    def test_network_error_ambiguous_needs_manual(self):
        self.assertEqual(sync.classify_portal_check(
            "https://x/j/1", {"code": "error:URLError", "final_url": ""}),
            "needs_manual")

    def test_200_ok(self):
        self.assertEqual(sync.classify_portal_check(
            "https://x/j/1", {"code": 200, "final_url": "https://x/j/1"}),
            "ok")

    def test_add_note_preserves_existing_and_status_untouched(self):
        r = app_row(status="submitted", notes="tier A")
        sync.add_note(r, "possibly_closed (HTTP 404)")
        self.assertIn("tier A", r["notes"])
        self.assertIn("possibly_closed", r["notes"])
        self.assertEqual(r["status"], "submitted")


class TestFollowups(unittest.TestCase):
    def test_14day_no_acknowledgment_selected(self):
        rows = [
            app_row(job_id="old", status="submitted",
                    date_submitted="2026-08-01"),
            app_row(job_id="recent", status="submitted",
                    date_submitted="2026-08-20"),
            app_row(job_id="acked", status="submitted",
                    date_submitted="2026-08-01", date_acknowledged="2026-08-05"),
            app_row(job_id="rejected", status="rejected",
                    date_submitted="2026-08-01"),
        ]
        cands = sync.followup_candidates(rows, TODAY)
        self.assertEqual([c["job_id"] for c in cands], ["old"])
        self.assertEqual(cands[0]["_days_waiting"], 22)

    def test_draft_mentions_company_and_role_and_does_not_send(self):
        draft = sync.draft_followup({"role": "ML Engineer", "company": "Acme",
                                     "date_submitted": "2026-08-01"})
        self.assertIn("Acme", draft)
        self.assertIn("ML Engineer", draft)
        self.assertIn("2026-08-01", draft)


if __name__ == "__main__":
    unittest.main()
