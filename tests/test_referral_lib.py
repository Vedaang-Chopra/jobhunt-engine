"""TDD tests for scripts/referral_lib.py — company registry (Task 8)."""

import csv
import datetime
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import referral_lib as rlib  # noqa: E402

EXPECTED_HEADER = [
    "company_slug", "company", "careers_url", "ats_platform",
    "email_pattern", "email_pattern_status", "email_pattern_source",
    "jobs_open_count", "top_job_ids", "contacts_count", "contacts_by_type",
    "referral_coverage", "status", "last_updated", "notes",
]


def _write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


JOBS_HEADER = ["job_id", "company", "status", "fit_score", "priority_v2", "company_slug"]
CONTACTS_HEADER = ["contact_id", "name", "company", "relationship", "company_slug"]


class ReferralLibTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.registry = self.tmp / "companies_registry.csv"
        self.jobs = self.tmp / "jobs.csv"
        self.contacts = self.tmp / "contacts.csv"
        self.seed_inputs()

    def seed_inputs(self):
        _write_csv(self.jobs, JOBS_HEADER, [
            {"job_id": "j1", "company": "Alpha Labs", "status": "open",
             "fit_score": "80", "priority_v2": "50.1", "company_slug": "alpha_labs"},
            {"job_id": "j2", "company": "Alpha Labs", "status": "open",
             "fit_score": "90", "priority_v2": "70.5", "company_slug": "alpha_labs"},
            {"job_id": "j3", "company": "Alpha Labs", "status": "closed",
             "fit_score": "99", "priority_v2": "99.0", "company_slug": "alpha_labs"},
            {"job_id": "j4", "company": "Beta Inc", "status": "open",
             "fit_score": "10", "priority_v2": "5.0", "company_slug": "beta_inc"},
            {"job_id": "j5", "company": "Gamma Co", "status": "closed",
             "fit_score": "10", "priority_v2": "5.0", "company_slug": "gamma_co"},
        ])
        _write_csv(self.contacts, CONTACTS_HEADER, [
            {"contact_id": "c1", "name": "A", "company": "Alpha Labs",
             "relationship": "1st", "company_slug": "alpha_labs"},
            {"contact_id": "c2", "name": "B", "company": "alpha labs",
             "relationship": "2nd", "company_slug": ""},
            {"contact_id": "c3", "name": "C", "company": "Gamma Co",
             "relationship": "1st", "company_slug": "gamma_co"},
        ])

    # --- schema -------------------------------------------------------
    def test_schema_header_exact(self):
        self.assertEqual(rlib.REGISTRY_COLUMNS, EXPECTED_HEADER)

    def test_write_and_read_roundtrip(self):
        rows = rlib.seed_registry(str(self.jobs), str(self.contacts))
        rlib.write_registry(rows, str(self.registry))
        with open(self.registry) as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, EXPECTED_HEADER)
            data = list(reader)
        self.assertEqual(len(data), 2)

    # --- seeding ------------------------------------------------------
    def test_seed_one_row_per_open_company(self):
        rows = {r["company_slug"]: r for r in rlib.seed_registry(
            str(self.jobs), str(self.contacts))}
        self.assertEqual(set(rows), {"alpha_labs", "beta_inc"})
        self.assertNotIn("gamma_co", rows)  # only closed jobs -> excluded

    def test_seed_counts_and_top_jobs(self):
        rows = {r["company_slug"]: r for r in rlib.seed_registry(
            str(self.jobs), str(self.contacts))}
        alpha = rows["alpha_labs"]
        self.assertEqual(alpha["jobs_open_count"], "2")
        # j3 is closed and must not appear; order by priority_v2 desc
        self.assertEqual(alpha["top_job_ids"].split(";"), ["j2", "j1"])
        self.assertEqual(alpha["company"], "Alpha Labs")

    def test_seed_contacts_merge(self):
        rows = {r["company_slug"]: r for r in rlib.seed_registry(
            str(self.jobs), str(self.contacts))}
        import json
        alpha = rows["alpha_labs"]
        self.assertEqual(alpha["contacts_count"], "2")
        by_type = json.loads(alpha["contacts_by_type"])
        self.assertEqual(by_type, {"1st": 1, "2nd": 1})
        beta = rows["beta_inc"]
        self.assertEqual(beta["contacts_count"], "0")
        self.assertEqual(beta["referral_coverage"], "none")

    def test_referral_coverage_levels(self):
        rows = {r["company_slug"]: r for r in rlib.seed_registry(
            str(self.jobs), str(self.contacts))}
        self.assertEqual(rows["alpha_labs"]["referral_coverage"], "strong")   # has 1st
        beta = next(r for r in rlib.seed_registry(str(self.jobs), str(self.contacts))
                    if r["company_slug"] == "beta_inc")
        self.assertEqual(beta["referral_coverage"], "none")
        # weak: contacts but no 1st
        _write_csv(self.contacts, CONTACTS_HEADER, [
            {"contact_id": "c9", "name": "Z", "company": "Beta Inc",
             "relationship": "2nd", "company_slug": "beta_inc"}])
        beta2 = next(r for r in rlib.seed_registry(str(self.jobs), str(self.contacts))
                     if r["company_slug"] == "beta_inc")
        self.assertEqual(beta2["referral_coverage"], "weak")

    def test_defaults_and_timestamp(self):
        rows = rlib.seed_registry(str(self.jobs), str(self.contacts))
        r = rows[0]
        self.assertIn(r["email_pattern_status"],
                      ("unverified", "confirmed", "guessed", "unknown"))
        self.assertEqual(r["email_pattern_status"], "unknown")
        self.assertEqual(r["status"], "active")
        datetime.date.fromisoformat(r["last_updated"])

    def test_top_job_ids_capped_at_five(self):
        rows_j = [{"job_id": f"j{i}", "company": "Delta", "status": "open",
                   "fit_score": str(i), "priority_v2": str(float(i)),
                   "company_slug": "delta"} for i in range(10)]
        _write_csv(self.jobs, JOBS_HEADER, rows_j)
        _write_csv(self.contacts, CONTACTS_HEADER, [])
        rows = {r["company_slug"]: r for r in rlib.seed_registry(
            str(self.jobs), str(self.contacts))}
        ids = rows["delta"]["top_job_ids"].split(";")
        self.assertEqual(len(ids), 5)
        self.assertEqual(ids, ["j9", "j8", "j7", "j6", "j5"])

    # --- row access / update ------------------------------------------
    def make_registry(self):
        rows = rlib.seed_registry(str(self.jobs), str(self.contacts))
        rlib.write_registry(rows, str(self.registry))

    def test_registry_row_for_hit_and_miss(self):
        self.make_registry()
        row = rlib.registry_row_for("alpha_labs", registry_path=str(self.registry))
        self.assertIsInstance(row, dict)
        self.assertEqual(row["company"], "Alpha Labs")
        self.assertIsNone(rlib.registry_row_for("nope_inc", registry_path=str(self.registry)))

    def test_registry_row_for_auto_creates_file_from_defaults(self):
        row = rlib.registry_row_for("alpha_labs", jobs_path=str(self.jobs),
                                    contacts_path=str(self.contacts),
                                    registry_path=str(self.registry))
        self.assertTrue(self.registry.exists())
        self.assertEqual(row["jobs_open_count"], "2")

    def test_update_preserves_unknown_columns(self):
        self.make_registry()
        with open(self.registry, "a", newline="") as f:
            pass
        # manually add an extra column + value to alpha's row
        with open(self.registry, newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames + ["custom_col"]
            data = list(reader)
        for r in data:
            if r["company_slug"] == "alpha_labs":
                r["custom_col"] = "keepme"
        _write_csv(self.registry, fields, data)

        ok = rlib.update_company_row("alpha_labs", {"notes": "hello", "custom_col": None},
                                     registry_path=str(self.registry))
        self.assertTrue(ok)
        row = rlib.registry_row_for("alpha_labs", registry_path=str(self.registry))
        self.assertEqual(row["notes"], "hello")
        self.assertEqual(row["custom_col"], "keepme")

    def test_update_missing_row_returns_false(self):
        self.make_registry()
        self.assertFalse(rlib.update_company_row(
            "ghost", {"notes": "x"}, registry_path=str(self.registry)))

    def test_update_ignores_unknown_field_names(self):
        self.make_registry()
        self.assertFalse(rlib.update_company_row(
            "alpha_labs", {"not_a_real_column": "x"}, registry_path=str(self.registry)))


if __name__ == "__main__":
    unittest.main()
