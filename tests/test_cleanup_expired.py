"""Tests for scripts/cleanup_expired.py — dry-run-by-default cleanup pass."""
import csv
import importlib
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

ce = importlib.import_module("cleanup_expired")  # noqa: E402

FAKE_TODAY = date(2026, 8, 23)

FIELDS = [
    "job_id", "company", "title", "job_url", "canonical_application_url",
    "source", "date_posted", "date_updated", "status", "priority_v2",
    "last_checked", "last_verified", "stale_flag",
]


def make_row(job_id="j1", status="open", date_posted=None,
             last_checked="", source="greenhouse", **extra):
    row = {
        "job_id": job_id,
        "company": "Acme",
        "title": "Engineer",
        "job_url": "https://boards.greenhouse.io/acme/jobs/123",
        "canonical_application_url": "",
        "source": source,
        "date_posted": date_posted or (FAKE_TODAY - timedelta(days=10)).isoformat(),
        "date_updated": "",
        "status": status,
        "priority_v2": "70",
        "last_checked": last_checked,
        "last_verified": "",
        "stale_flag": "",
    }
    row.update(extra)
    return {k: row.get(k, "") for k in FIELDS}


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


class CleanupTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cleanup_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # Patch the clock exactly like test_freshness.py pins today.
        self._orig_today = ce.today_utc
        ce.today_utc = lambda: FAKE_TODAY
        self.addCleanup(setattr, ce, "today_utc", self._orig_today)
        # Point data_root() at tmp so run reports land in the sandbox.
        env_patcher = unittest.mock.patch.dict(
            "os.environ", {"JOBHUNT_HOME": str(self.tmp)})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        self.jobs_csv = self.tmp / "jobs.csv"

    def read_rows(self) -> dict:
        return {r["job_id"]: r for r in ce.load_rows(self.jobs_csv)}

    def run_main(self, *argv):
        return ce.main(["--jobs-csv", str(self.jobs_csv), *argv])


class TestCleanupDryRunByDefault(CleanupTestCase):
    def _fixture(self):
        rows = [
            make_row("old_open", date_posted=(FAKE_TODAY - timedelta(days=120)).isoformat()),
            make_row("fresh_open", date_posted=(FAKE_TODAY - timedelta(days=10)).isoformat(),
                     last_checked=(FAKE_TODAY - timedelta(days=1)).isoformat()),
            make_row("already_expired", status="expired",
                     date_posted=(FAKE_TODAY - timedelta(days=200)).isoformat(),
                     last_checked="2026-01-01"),
        ]
        write_csv(self.jobs_csv, rows)

    def test_no_flags_is_dry_run_and_does_not_modify_file(self):
        self._fixture()
        before = self.jobs_csv.read_bytes()
        rc = self.run_main()  # NO flags at all besides --jobs-csv
        self.assertEqual(rc, 0)
        self.assertEqual(self.jobs_csv.read_bytes(), before)
        rows = self.read_rows()
        self.assertEqual(rows["old_open"]["status"], "open")
        self.assertEqual(rows["fresh_open"]["status"], "open")
        self.assertEqual(rows["already_expired"]["status"], "expired")
        self.assertEqual(rows["already_expired"]["last_checked"], "2026-01-01")

    def test_explicit_dry_run_does_not_modify_file(self):
        self._fixture()
        before = self.jobs_csv.read_bytes()
        rc = self.run_main("--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(self.jobs_csv.read_bytes(), before)


class TestApplyTransitions(CleanupTestCase):
    def _fixture(self):
        rows = [
            make_row("old_open", date_posted=(FAKE_TODAY - timedelta(days=91)).isoformat()),
            make_row("fresh_open", date_posted=(FAKE_TODAY - timedelta(days=10)).isoformat(),
                     last_checked=(FAKE_TODAY - timedelta(days=1)).isoformat()),
            make_row("already_expired", status="expired",
                     date_posted=(FAKE_TODAY - timedelta(days=200)).isoformat(),
                     last_checked="2026-01-01"),
        ]
        write_csv(self.jobs_csv, rows)

    def test_apply_expires_old_row_only(self):
        self._fixture()
        rc = self.run_main("--apply")
        self.assertEqual(rc, 0)
        rows = self.read_rows()
        self.assertEqual(len(rows), 3)  # rows never deleted
        self.assertEqual(rows["old_open"]["status"], "expired")
        self.assertEqual(rows["old_open"]["last_checked"], FAKE_TODAY.isoformat())
        self.assertEqual(rows["fresh_open"]["status"], "open")
        self.assertEqual(rows["fresh_open"]["last_checked"],
                         (FAKE_TODAY - timedelta(days=1)).isoformat())
        # terminal rows untouched — nothing stamped
        self.assertEqual(rows["already_expired"]["status"], "expired")
        self.assertEqual(rows["already_expired"]["last_checked"], "2026-01-01")

    def test_apply_writes_report_json(self):
        self._fixture()
        rc = self.run_main("--apply")
        self.assertEqual(rc, 0)
        rpath = (self.tmp / "execution_results" / "cleanup_reports"
                 / f"cleanup_expired_{FAKE_TODAY.isoformat()}.json")
        self.assertTrue(rpath.is_file(), rpath)
        report = json.loads(rpath.read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "apply")
        self.assertEqual(report["changed_job_ids"], ["old_open"])
        self.assertIn("expired_by_age", report["totals_by_action"])
        self.assertIn("greenhouse", report["by_source"])

    def test_dry_run_report_records_mode(self):
        self._fixture()
        self.run_main()
        rpath = (self.tmp / "execution_results" / "cleanup_reports"
                 / f"cleanup_expired_{FAKE_TODAY.isoformat()}.json")
        report = json.loads(rpath.read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["changed_job_ids"], ["old_open"])


class TestCliContract(CleanupTestCase):
    def test_dry_run_and_apply_are_mutually_exclusive(self):
        write_csv(self.jobs_csv, [make_row()])
        with self.assertRaises(SystemExit):
            self.run_main("--dry-run", "--apply")


if __name__ == "__main__":
    unittest.main()
