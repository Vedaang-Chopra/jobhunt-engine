"""Tests for scripts/connection_queue.py (Task 10)."""
import csv
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import connection_queue as cq  # noqa: E402


def _write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def make_env(tmp):
    contacts = tmp / "contacts.csv"
    posts = tmp / "posts.csv"
    reqs = tmp / "requests.csv"
    _write_csv(contacts, [
        "contact_id", "name", "company", "role", "relationship", "linkedin_url",
        "email", "job_id", "reason_to_contact", "shared_context",
        "outreach_status"], [
        ["c1", "Jane Recruiter", "CrowdStrike", "Recruiter", "2nd",
         "https://li/jane", "", "job_1", "ML roles open now", "",
         "not_contacted"],
        ["c2", "Old Friend", "CrowdStrike", "Engineer", "1st",
         "https://li/old", "", "job_1", "", "", "connected"],
    ])
    _write_csv(posts, ["post_id", "poster_name", "poster_headline",
                       "poster_type", "company", "team_or_org", "post_url",
                       "posted_date", "discovered_date", "roles_mentioned",
                       "application_url", "connection_degree", "shared_context",
                       "priority", "role_family", "status", "notes"], [
        ["p1", "Posty Poster", "hiring!", "recruiter", "CrowdStrike", "",
         "https://li/posty", "", "", "Sr Data Scientist ML", "", "2nd", "",
         "high", "", "new", ""],
    ])
    reqs.write_text(",".join(cq.HEADER) + "\n", encoding="utf-8")
    return contacts, posts, reqs


class TestNoteValidator(unittest.TestCase):
    def person(self, **kw):
        p = {"person_name": "Jane Recruiter", "company": "CrowdStrike",
             "person_type": "recruiter", "source_post_url": "https://li/posty",
             "_post_hint": "Sr Data Scientist ML"}
        p.update(kw)
        return p

    def test_valid_recruiter_note(self):
        note = cq.compose_note(self.person(), "job_specific")
        self.assertEqual([], cq.validate_note(note, "job_specific", self.person()))

    def test_too_long_rejected(self):
        errs = cq.validate_note("x" * 301 + " Georgia Tech Fortinet interested",
                                "generic", self.person())
        self.assertTrue(any("exceeds" in e for e in errs))

    def test_banned_claims_rejected(self):
        for word in ("RLHF", "DPO", "SFT", "rlhf"):
            note = (f"Hi - Georgia Tech MS CS with Fortinet production ML, "
                    f"hands-on {word} experience, interested in your roles.")
            self.assertTrue(any("banned" in e.lower() for e in
                                cq.validate_note(note, "generic", self.person())),
                            word)

    def test_hiring_post_requires_post_reference(self):
        note = "Hi Sam - Georgia Tech MS CS with Fortinet production ML, interested in your roles."
        p = self.person(_post_hint="", source_post_url="https://li/x")
        errs = cq.validate_note(note, "hiring_post", p)
        self.assertTrue(any("post" in e for e in errs))
        ok = note + " Saw your hiring post."
        self.assertEqual([], cq.validate_note(ok, "hiring_post",
                                              self.person()))

    def test_one_style_per_person_type(self):
        types = ["Recruiter", "Director, Engineering", "Cyber Intern (CS @ GT)",
                 "Founder & AI Engineer", "Senior Engineer"]
        styles = {cq.style_for(t) for t in types}
        self.assertEqual(len(styles), len(types))


class TestQueueFlow(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.contacts, self.posts, self.reqs = make_env(self.tmp)
        self._saved = (cq.CONTACTS_PATH, cq.POSTS_PATH, cq.REQ_PATH)

    def tearDown(self):
        cq.CONTACTS_PATH, cq.POSTS_PATH, cq.REQ_PATH = self._saved

    def use_env(self):
        cq.CONTACTS_PATH, cq.POSTS_PATH, cq.REQ_PATH = (
            self.contacts, self.posts, self.reqs)

    def test_draft_blocks_duplicates_from_contacts_and_queue(self):
        self.use_env()
        self.assertEqual(cq.main(["draft"]), 0)
        rows = cq.read_requests()
        names = [r["person_name"] for r in rows]
        self.assertNotIn("Old Friend", names)          # touched in contacts.csv
        rc2 = cq.main(["draft"])                       # second draft same batch
        rows2 = cq.read_requests()
        self.assertEqual(len(rows2), len(rows))        # no duplicate persons
        self.assertIn(rc2, (0, 1))                     # 1 = nothing new to queue

    def test_approve_before_send_interlock(self):
        self.use_env()
        cq.main(["draft"])
        rid = cq.read_requests()[0]["request_id"]
        rc = cq.main(["record-sent", rid])
        self.assertNotEqual(rc, 0)                     # blocked without approve
        self.assertEqual(cq.main(["approve", rid]), 0)
        self.assertEqual(cq.main(["record-sent", rid,
                                  "--state", "sent_with_note"]), 0)
        row = cq.read_requests()[0]
        self.assertTrue(row["date_sent"])

    def test_next_batch_blocked_until_record_sent(self):
        self.use_env()
        cq.main(["draft"])
        rid = cq.read_requests()[0]["request_id"]
        cq.main(["approve", rid])
        rc = cq.main(["draft"])                        # interlock fires
        self.assertEqual(rc, 2)
        self.assertEqual(cq.main(["record-sent", rid]), 0)
        # after record-sent the interlock lifts; pool may be exhausted
        self.assertNotEqual(cq.main(["draft"]), 2)

    def test_connected_requires_send(self):
        self.use_env()
        cq.main(["draft"])
        rid = cq.read_requests()[0]["request_id"]
        self.assertNotEqual(cq.main(["record-connected", rid]), 0)
        cq.main(["approve", rid])
        cq.main(["record-sent", rid])
        self.assertEqual(cq.main(["record-connected", rid]), 0)
        self.assertEqual(cq.main(["record-replied", rid,
                                  "--response", "referred!"]), 0)
        row = cq.read_requests()[0]
        self.assertEqual(row["response"], "referred!")


if __name__ == "__main__":
    unittest.main()
