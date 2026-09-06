"""Tests for Task 9: contact discovery (scripts/contact_discovery.py)."""

import csv
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import referral_lib as rl


def _tmp_csv(path, header, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return str(path)


POSTER_HEADER = [
    "post_id", "poster_name", "poster_headline", "poster_type", "company",
    "post_url", "posted_date", "application_url", "connection_degree",
    "shared_context",
]
CONTACT_HEADER = [
    "contact_id", "name", "company", "role", "relationship", "linkedin_url",
    "shared_context", "outreach_status",
]


def poster(name="Ada Lovelace", ptype="hiring_manager", company="Acme",
           posted=None, degree="", context=""):
    return {
        "post_id": f"{name.lower().replace(' ', '_')}_p",
        "poster_name": name,
        "poster_headline": "HM at Acme" if ptype == "hiring_manager" else "",
        "poster_type": ptype,
        "company": company,
        "post_url": "https://example.com/post",
        "posted_date": posted or date.today().isoformat(),
        "application_url": "",
        "connection_degree": degree,
        "shared_context": context,
    }


def contact(name="Bob Ray", company="Acme", rel="2nd", status="not_contacted",
            url=""):
    return {
        "contact_id": name.lower().replace(" ", "_"),
        "name": name,
        "company": company,
        "role": "Recruiter" if rel else "",
        "relationship": rel,
        "linkedin_url": url,
        "shared_context": "",
        "outreach_status": status,
    }


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.posts = _tmp_csv(Path(self.tmp) / "posts.csv", POSTER_HEADER, [])
        self.contacts = _tmp_csv(Path(self.tmp) / "contacts.csv",
                                 CONTACT_HEADER, [])

    def score(self, **kw):
        return rl.score_candidate({**{
            "source": "", "poster_type": "", "relationship": "",
            "gt_alumni": False, "shared_context": "", "posted_date": "",
            "linkedin_url": "",
        }, **kw})

    def test_type_scores(self):
        self.assertEqual(
            self.score(source="hiring_posts", poster_type="hiring_manager"),
            rl.SCORE_HM_POSTER)
        self.assertEqual(self.score(poster_type="recruiter"), rl.SCORE_RECRUITER)
        self.assertEqual(self.score(poster_type="engineer_researcher"),
                         rl.SCORE_ENGINEER)

    def test_first_degree_beats_stranger_recruiter(self):
        first_deg = self.score(relationship="1st")
        stranger_recruiter = self.score(poster_type="recruiter")
        self.assertGreater(first_deg, stranger_recruiter)
        self.assertEqual(first_deg, rl.SCORE_FIRST_DEGREE)

    def test_bonus_stack(self):
        base = self.score()
        gt = self.score(gt_alumni=True)
        ctx = self.score(shared_context="Georgia Tech CS; Atlanta")
        fresh = self.score(posted_date=date.today().isoformat())
        old = self.score(posted_date=(date.today() - timedelta(days=30))
                         .isoformat())
        self.assertEqual(gt, base + rl.SCORE_GT_ALUMNI)
        self.assertEqual(ctx, base + rl.SCORE_SHARED_CONTEXT)
        self.assertEqual(fresh, base + rl.SCORE_JOB_FRESH)
        self.assertEqual(old, base)

    def test_reason_from_evidence_only(self):
        cand = {
            "name": "Ada", "company": "Acme", "source": "hiring_posts",
            "poster_type": "hiring_manager", "relationship": "1st",
            "shared_context": "Both at Georgia Tech",
            "post_url": "https://x.com/p", "headline": "HM at Acme",
        }
        reason = rl.compose_reason(cand)
        self.assertIn("hiring post", reason.lower())
        self.assertIn("1st-degree", reason.lower())
        self.assertIn("georgia tech", reason.lower())

    def test_reason_no_invention(self):
        # With zero evidence beyond identity, reason stays minimal/factual.
        reason = rl.compose_reason({"name": "X", "company": "Y"})
        self.assertNotIn("georgia tech", reason.lower())


class TestDedupGuard(unittest.TestCase):
    def test_slug_dedupe(self):
        a = {"name": "Ada Lovelace", "company": "Acme",
             "linkedin_url": "https://www.linkedin.com/in/ada-lovelace/"}
        b = {"name": "A. Lovelace", "company": "Acme",
             "linkedin_url": "https://linkedin.com/in/ada-lovelace"}
        merged = rl.dedup_candidates([a, b])
        self.assertEqual(len(merged), 1)

    def test_fuzzy_name_company_dedupe(self):
        a = {"name": "Ada Lovelace", "company": "Acme"}
        b = {"name": "Ada  Lovelace", "company": "acme inc."}
        merged = rl.dedup_candidates([a, b])
        self.assertEqual(len(merged), 1)

    def test_distinct_people_kept(self):
        a = {"name": "Ada Lovelace", "company": "Acme"}
        b = {"name": "Bob Ray", "company": "Acme"}
        self.assertEqual(len(rl.dedup_candidates([a, b])), 2)


class TestDiscoveryPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        today = date.today().isoformat()

        def reg_row(slug, company):
            r = dict.fromkeys(rl.REGISTRY_COLUMNS, "")
            r.update({"company_slug": slug, "company": company,
                      "status": "active"})
            return r

        self.registry = _tmp_csv(
            Path(self.tmp) / "registry.csv", rl.REGISTRY_COLUMNS,
            [reg_row("acme", "Acme"), reg_row("beta", "Beta Corp")])
        self.posts = _tmp_csv(
            Path(self.tmp) / "posts.csv", POSTER_HEADER,
            [poster(name="Ada Lovelace", ptype="hiring_manager", company="Acme",
                    posted=today, context="Georgia Tech alum"),
             poster(name="Cara Diaz", ptype="recruiter", company="Beta Corp")])
        self.contacts = _tmp_csv(
            Path(self.tmp) / "contacts.csv", CONTACT_HEADER,
            [contact(name="Bob Ray", company="Acme", rel="1st"),
             # already-contacted people who must NEVER surface again:
             contact(name="Ada Lovelace", company="Acme", rel="1st",
                     status="requested",
                     url="https://www.linkedin.com/in/ada-lovelace/"),
             contact(name="Dan Wu", company="Acme", rel="2nd",
                     status="connected")])

    def discover(self, slug, **kw):
        kw.setdefault("registry_path", self.registry)
        kw.setdefault("posts_path", self.posts)
        kw.setdefault("contacts_path", self.contacts)
        kw.setdefault("live_linkedin", False)
        kw.setdefault("web_search_fn", None)
        return rl.discover_contacts(slug, **kw)

    def test_ranked_merge_and_order(self):
        ranked = self.discover("acme")
        self.assertTrue(ranked)
        scores = [c["score"] for c in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        names = {c["name"] for c in ranked}
        self.assertIn("Bob Ray", names)

    def test_already_contacted_never_surfaced(self):
        ranked = self.discover("acme")
        names = {(c["name"], (c.get("outreach_status") or "").lower())
                 for c in ranked}
        blocked = {"requested", "connected", "contacted", "responded"}
        for _, status in names:
            self.assertNotIn(status, blocked)
        self.assertNotIn("Ada Lovelace", {c["name"] for c in ranked})
        self.assertNotIn("Dan Wu", {c["name"] for c in ranked})

    def test_hm_poster_outranks_plain_contact(self):
        # Ada is requested -> suppressed; Cara only exists for beta.
        ranked = self.discover("acme")
        self.assertEqual(ranked[0]["name"], "Bob Ray")

    def test_slug_resolution_via_registry(self):
        ranked = self.discover("ACME Corp")   # non-canonical input
        self.assertTrue(ranked)
        ranked2 = self.discover("nope_xyz")
        self.assertEqual(ranked2, [])

    def test_web_search_source_merged(self):
        def fake_web(query):
            if "talent acquisition" in query.lower():
                return [{"name": "Erin Fox", "company": "Acme",
                         "role": "Talent Acquisition",
                         "source": "web_search",
                         "evidence": ["web search: talent acquisition Acme"]}]
            return []

        ranked = self.discover("acme", web_search_fn=fake_web)
        self.assertIn("Erin Fox", {c["name"] for c in ranked})
        erin = next(c for c in ranked if c["name"] == "Erin Fox")
        self.assertEqual(erin["score"], rl.SCORE_RECRUITER)

    def test_every_candidate_has_reason(self):
        ranked = self.discover("acme", web_search_fn=lambda q: [])
        for c in ranked:
            self.assertTrue(c["reason_to_contact"].strip())


class TestCLI(unittest.TestCase):
    def test_cli_runs(self):
        import subprocess
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        proc = subprocess.run(
            [sys.executable, str(repo / "scripts" / "contact_discovery.py"),
             "--help"],
            capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--company", proc.stdout)


if __name__ == "__main__":
    unittest.main()
