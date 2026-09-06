#!/usr/bin/env python3
"""L2 LinkedIn recommended-jobs sweep.

Contract:
- CLI --dry-run prints the pipeline plan against the bundled fixture
  extraction (no browser, no writes to canonical CSVs).
- CLI --live opens ONE Playwright tab on the logged-in LinkedIn
  Jobs -> Recommended page, scroll-pause extracts job cards (no
  Easy-Apply clicks), and closes the tab in a finally block.
- Extraction rows -> normalize_job -> DedupIndex (from all jobs.csv rows)
  -> scrutinize -> append NEW accepted rows to tracking/jobs/jobs.csv with
  `recommendation_rank` stamped into the notes column.
- One coverage line appended to tracking/search_runs/search_runs.csv
  (header created if the file is missing), source=l2_recommended.

Merge logic (merge_extraction) is pure and unit-tested in
tests/test_recommended_sweep.py.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

try:
    from scripts import config_lib
except ImportError:
    import config_lib
from discovery_lib import (  # noqa: E402
    DedupIndex,
    normalize_job,
    normalize_source,
    scrutinize,
)

JOBS_CSV = str(config_lib.data_root() / "tracking" / "jobs" / "jobs.csv")
SEARCH_RUNS_CSV = os.path.join(REPO, "tracking", "search_runs", "search_runs.csv")
SEARCH_RUNS_HEADER = ["date", "search_id", "source", "results_seen", "new_rows", "rejected", "status"]
FIXTURE_PATH = os.path.join(REPO, "tests", "fixtures", "linkedin_recommended_fixture.json")
SOURCE = "l2_recommended"
SEARCH_ID = "l2_recommended"
RECOMMENDED_URL = "https://www.linkedin.com/jobs/recommended/"


# ---------------------------------------------------------------------------
# Merge logic: extraction rows -> normalized -> deduped -> scrutinized
# ---------------------------------------------------------------------------

def load_dedup_index(jobs_csv: str = JOBS_CSV) -> DedupIndex:
    idx = DedupIndex()
    if not os.path.exists(jobs_csv):
        return idx
    with open(jobs_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            idx.add(row)
    return idx


def merge_extraction(
    extraction: list[dict], dedup: DedupIndex, search_id: str = SEARCH_ID,
    source: str = SOURCE,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Normalize, dedup, and scrutinize raw recommended-jobs cards.

    Each input card carries an optional ``recommendation_rank`` (1-based card
    order); it is stamped into the notes column of accepted rows.

    Returns (new_accepted_rows, duplicate_rows, rejected_rows).
    """
    accepted, duplicates, rejected = [], [], []
    for rank, raw in enumerate(extraction, start=1):
        try:
            row = normalize_job(
                {
                    "title": raw.get("title"),
                    "company": raw.get("company"),
                    "url": raw.get("url"),
                    "location": raw.get("location") or "",
                    "date_posted": raw.get("date_posted") or "",
                    "source_id": raw.get("source_id") or "",
                }
            )
        except ValueError:
            rejected.append({**raw, "flags": ["missing_required_field"]})
            continue
        # Source provenance: explicit source wins; otherwise derive from the
        # job URL; sweep-level "linkedin" as last resort (never blank).
        row["source"] = (
            source
            or normalize_source(row.get("job_url") or "")
            or "linkedin"
        )
        is_dup, _matched = dedup.seen_before(row)
        if is_dup:
            duplicates.append(row)
            continue
        verdict, flags = scrutinize(row)
        if verdict != "accept":
            rejected.append({**row, "flags": flags})
            continue
        rec_rank = raw.get("recommendation_rank") or rank
        row["notes"] = (
            f"{search_id}; recommendation_rank={rec_rank}; "
            f"flags={','.join(flags) or 'none'}"
        )
        accepted.append(row)
        dedup.add(row)
    return accepted, duplicates, rejected


def append_jobs(rows: list[dict], jobs_csv: str = JOBS_CSV) -> int:
    if not rows:
        return 0
    fieldnames = list(rows[0].keys())
    if os.path.exists(jobs_csv):
        with open(jobs_csv, newline="", encoding="utf-8") as fh:
            fieldnames = next(csv.reader(fh))
    new_file = not os.path.exists(jobs_csv)
    os.makedirs(os.path.dirname(jobs_csv), exist_ok=True)
    with open(jobs_csv, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def log_search_run(search_id: str, results_seen: int, new_rows: int, rejected: int,
                   status: str, runs_csv: str = SEARCH_RUNS_CSV) -> None:
    new_file = not os.path.exists(runs_csv)
    os.makedirs(os.path.dirname(runs_csv), exist_ok=True)
    with open(runs_csv, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(SEARCH_RUNS_HEADER)
        writer.writerow([
            datetime.date.today().isoformat(), search_id, SOURCE,
            results_seen, new_rows, rejected, status,
        ])


def load_extraction(path: str = FIXTURE_PATH) -> list[dict]:
    """Load an extraction JSON (fixture in dry-run; live output uses same shape)."""
    with open(path) as fh:
        data = json.load(fh)
    for i, card in enumerate(data, start=1):
        card.setdefault("recommendation_rank", i)
    return data


# ---------------------------------------------------------------------------
# Live sweep driver (Playwright MCP contract: one tab, no Easy-Apply clicks)
# ---------------------------------------------------------------------------

def extract_recommended_cards_live(page, pause_s: float = 1.5, max_scrolls: int = 5) -> list[dict]:
    """Scroll-pause extraction of cards from the logged-in Recommended page.

    Selectors verified live 2026-08-25 against the hash-classed DOM: cards
    are ``div.job-card-container`` (the wrapping ``li`` carries only hash
    classes), title anchor is ``a.job-card-container__link`` (its class list
    also contains 'disabled', so match on the stable suffix), company in
    ``.artdeco-entity-lockup__subtitle``, location inside
    ``ul.job-card-container__metadata-wrapper``.
    """
    seen: dict[str, dict] = {}
    rank = 0
    for _ in range(max_scrolls):
        cards = page.query_selector_all("div.job-card-container")
        for card in cards:
            try:
                a = card.query_selector("a.job-card-container__link")
                title_el = card.query_selector(
                    ".job-card-list__title, .artdeco-entity-lockup__title"
                )
                company_el = card.query_selector(
                    ".job-card-container__primary-description, "
                    ".artdeco-entity-lockup__subtitle"
                )
                meta_el = card.query_selector(
                    ".job-card-container__metadata li, "
                    "ul.job-card-container__metadata-wrapper li, "
                    ".artdeco-entity-lockup__caption li"
                )
                age_el = card.query_selector(".job-card-container__listed-time, time")
                if not a:
                    continue
                url = (a.get_attribute("href") or "").split("?")[0]
                if not url or not url.startswith("/jobs/"):
                    continue
                title_text = (
                    (title_el.inner_text().strip() if title_el else "")
                    or (a.get_attribute("aria-label") or "").strip()
                )
                if not title_text or url in seen:
                    continue
                rank += 1
                seen[url] = {
                    "recommendation_rank": rank,
                    "title": title_text,
                    "company": company_el.inner_text().strip() if company_el else "",
                    "location": meta_el.inner_text().strip() if meta_el else "",
                    "posted_age": age_el.inner_text().strip() if age_el else "",
                    "url": url,
                }
            except Exception:
                continue
        # Scroll only; never click any card / Easy-Apply button.
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(int(pause_s * 1000))
    return list(seen.values())


def run_live(max_scrolls: int = 5) -> int:
    """Live sweep in a LinkedIn-logged-in browser session.

    Attaches over CDP to the shared automation Chrome (:9333, see
    scripts/automation_chrome.sh) or falls back to a persistent context on
    the job-hunt profile. ONE new tab; closed in finally.
    """
    from browser_session_lib import open_logged_in_session

    exit_code = 0
    results_seen = 0
    with open_logged_in_session() as session:
        page = session.page  # the tab this run drives
        try:
            print(f"[live] opening {RECOMMENDED_URL}")
            page.goto(RECOMMENDED_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if "/login" in page.url or "/authwall" in page.url:
                raise RuntimeError("not logged in to LinkedIn; run inside logged-in session")
            extraction = extract_recommended_cards_live(page, max_scrolls=max_scrolls)
            results_seen = len(extraction)
            dedup = load_dedup_index()
            accepted, duplicates, rejected = merge_extraction(extraction, dedup)
            append_jobs(accepted)
            log_search_run(SEARCH_ID, results_seen, len(accepted), len(rejected),
                           "ok" if extraction else "no_results")
            print(f"[live] seen={results_seen} new={len(accepted)} "
                  f"dup={len(duplicates)} rejected={len(rejected)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[live] ERROR: {exc}", file=sys.stderr)
            log_search_run(SEARCH_ID, results_seen, 0, 0, f"error:{type(exc).__name__}")
            exit_code = 1
        finally:
            session.close()
    return exit_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_dry_run() -> int:
    extraction = load_extraction()
    dedup = load_dedup_index()
    accepted, duplicates, rejected = merge_extraction(extraction, dedup)
    print(f"[dry-run] source={SOURCE} search_id={SEARCH_ID} fixture={os.path.basename(FIXTURE_PATH)}")
    print(f"[dry-run] extraction cards: {len(extraction)}")
    print(f"[dry-run] would accept {len(accepted)}, skip {len(duplicates)} duplicates, "
          f"{len(rejected)} rejected")
    for row in accepted:
        print(f"  + {row['company']} | {row['title']} | {row['location']} | notes={row['notes']!r}")
    for row in duplicates:
        print(f"  = DUP {row['company']} | {row['title']} | {row['job_url']}")
    for row in rejected:
        flags = ",".join(row.get("flags", []))
        print(f"  - REJ ({flags}) {row.get('company')} | {row.get('title') or '<missing>'}")
    print("[dry-run] no CSVs were modified.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L2 LinkedIn recommended-jobs sweep")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="run merge logic against the fixture; no browser, no writes")
    mode.add_argument("--live", action="store_true", help="logged-in Playwright sweep of Jobs->Recommended (one tab)")
    args = parser.parse_args(argv)
    if args.dry_run:
        return run_dry_run()
    return run_live()


if __name__ == "__main__":
    sys.exit(main())
