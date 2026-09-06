#!/usr/bin/env python3
"""L1 LinkedIn portal sweep: saved-search registry + Playwright sweep.

Contract:
- CLI --dry-run prints the searches that would run (no browser).
- CLI --live runs via Playwright MCP: ONE tab, <=8 searches per run,
  scroll-pause extraction of job cards, no Easy-Apply clicks, tab closed after.
- Extraction rows -> normalize_job -> DedupIndex (loaded from all jobs.csv rows)
  -> scrutinize -> append NEW accepted rows to tracking/jobs/jobs.csv.
- One coverage line per search appended to tracking/search_runs/search_runs.csv.

Merge logic (build_registry, build_search_url, merge_extraction) is pure and
unit-tested in tests/test_portal_sweep.py.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sys
import time
from urllib.parse import urlencode

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from discovery_lib import (  # noqa: E402
    DedupIndex,
    normalize_job,
    normalize_source,
    scrutinize,
)

try:
    from scripts import config_lib
except ImportError:
    import config_lib
REGISTRY_PATH = str(config_lib.data_root() / "job_research" / "config" / "linkedin_saved_searches.yaml")
JOBS_CSV = str(config_lib.data_root() / "tracking" / "jobs" / "jobs.csv")
SEARCH_RUNS_CSV = os.path.join(REPO, "tracking", "search_runs", "search_runs.csv")
SEARCH_RUNS_HEADER = ["date", "search_id", "source", "results_seen", "new_rows", "rejected", "status"]

BASE_SEARCH_URL = "https://www.linkedin.com/jobs/search/"


# ---------------------------------------------------------------------------
# Pure registry / URL logic
# ---------------------------------------------------------------------------

def build_search_url(entry: dict, geos: dict, defaults: dict) -> str:
    """Build a LinkedIn jobs search URL from a registry entry."""
    params = {"keywords": entry["keywords"]}
    for geo_key in entry.get("geos", []):
        params.update(p.split("=", 1) for p in geos[geo_key]["params"])
    params["f_TPR"] = defaults["freshness_param"].split("=", 1)[1].replace("f_TPR=", "")
    # On-demand recency override (discovery_run.py --recency): bare r<seconds>.
    override = os.environ.get("LINKEDIN_F_TPR_OVERRIDE", "").strip()
    if override:
        params["f_TPR"] = override
    params["f_E"] = defaults["experience_param"].split("=", 1)[1].replace("f_E=", "")
    # f_TPR / f_E arrive as bare values; geos already carry key=value.
    clean = {}
    for k, v in params.items():
        if k in ("f_TPR", "f_E") and "=" in v:
            k, v = v.split("=", 1)
        clean[k] = v
    return BASE_SEARCH_URL + "?" + urlencode(clean, safe="(),%")


def build_registry(registry_path: str = REGISTRY_PATH) -> list[dict]:
    """Load the YAML registry and expand it into a flat search list."""
    with open(registry_path) as fh:
        cfg = yaml.safe_load(fh)
    searches: list[dict] = []
    for entry in cfg.get("base_searches", []):
        searches.append({**entry, "tier": "base", "company": None})
    c2_keyword = '("machine learning" OR "AI engineer" OR "research engineer")'
    for i, company in enumerate(cfg.get("c2_companies_uncovered_by_ats", []), start=1):
        searches.append(
            {
                "id": f"c2_{i:02d}_{company.lower().replace(' ', '_').replace('&', 'and').replace('(', '').replace(')', '').replace('/', '_')}",
                "tier": "c2",
                "family": "c2-company-filter",
                "keywords": c2_keyword,
                "geos": ["us_remote"],
                "company": company,
                # Company filter is applied as a URL param at live-run time
                # via the LinkedIn currentCompany facet; recorded here so the
                # sweep driver can attach it.
                "company_filter": company,
            }
        )
    return searches


def cap_searches(searches: list[dict], cap: int) -> list[dict]:
    """Round-robin base/c2 so both tiers get coverage within the cap."""
    base = [s for s in searches if s["tier"] == "base"]
    c2 = [s for s in searches if s["tier"] == "c2"]
    picked, bi, ci = [], 0, 0
    while len(picked) < cap and (bi < len(base) or ci < len(c2)):
        if bi < len(base):
            picked.append(base[bi]); bi += 1
        if len(picked) < cap and ci < len(c2):
            picked.append(c2[ci]); ci += 1
    return picked


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
    extraction: list[dict], dedup: DedupIndex, search_id: str, source: str = "linkedin"
) -> tuple[list[dict], list[dict], list[dict]]:
    """Normalize, dedup, and scrutinize raw extraction rows.

    Returns (new_accepted_rows, duplicate_rows, rejected_rows).
    """
    accepted, duplicates, rejected = [], [], []
    for raw in extraction:
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
            or normalize_source(raw.get("url") or "")
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
        row["notes"] = f"linkedin_sweep:{search_id}; flags={','.join(flags) or 'none'}"
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
            datetime.date.today().isoformat(), search_id, "linkedin",
            results_seen, new_rows, rejected, status,
        ])


# ---------------------------------------------------------------------------
# Live sweep driver (Playwright MCP)
# ---------------------------------------------------------------------------

# LinkedIn renders job cards with hashed class names and virtualized DOM
# (verified live 2026-08-24): the legacy CSS selectors below return zero
# cards. The reliable path is fetching /jobs/search-results/ inside the
# authenticated tab and splitting on the componentkey markers — each job id
# appears twice; the card payload sits after the SECOND occurrence.
_CARD_MARKER = 'componentkey="job-card-component-ref-'


def parse_search_results_html(html: str) -> list[dict]:
    """Parse one /jobs/search-results/ HTML page into extraction rows.

    Pure function (unit-tested): split on componentkey markers, take the
    segment AFTER the second occurrence of each id, strip tags, and read the
    text tokens in order (title, company, location, [salary], [alumni],
    [posted age]).
    """
    import html as html_mod

    if _CARD_MARKER not in html:
        return []
    parts = html.split(_CARD_MARKER)

    def _tokens(segment: str) -> list[str]:
        clean = re.sub(r"<style.*?</style>", " ", segment, flags=re.S)
        clean = re.sub(r"<svg.*?</svg>", " ", segment and clean, flags=re.S)
        # Head remnant: segment begins right after the previous marker, e.g.
        # '4418852774"><p>Title…'. Drop the leading '<id>">'.
        clean = re.sub(r'^\s*\d+"\s*>\s*', " ", clean)
        # Tail remnant: the segment is cut mid-tag at the next marker, leaving
        # an unterminated tag like '<button class="…" componentkey="job-card-'
        clean = re.sub(r"<[a-zA-Z!/][^>]*$", " ", clean)
        raw = re.split(r"<[^>]+>", clean)
        toks = []
        for tok in raw:
            tok = html_mod.unescape(re.sub(r"\s+", " ", tok)).strip()
            if len(tok) <= 2:
                continue
            # Drop attribute remnants (bare job ids, class dumps) left by the
            # split boundaries.
            if re.fullmatch(r"[\d\s\"'><=]+", tok):
                continue
            if "class=" in tok or "<" in tok:
                continue
            toks.append(tok)
        return toks

    rows: list[dict] = []
    seen_ids: set[str] = set()
    last_id: str | None = None

    def _emit(job_id: str, segment: str) -> None:
        if job_id in seen_ids:
            return
        toks = _tokens(segment)
        if not toks:
            return
        salary = next((t for t in toks if re.search(r"\$|K/yr|/hr\b", t)), "")
        alumni = next((t for t in toks if re.search(r"alumni work|connections work", t, re.I)), "")
        posted = next((t for t in toks if re.search(r"ago\.?$|^Posted$", t, re.I)), "")
        rows.append(
            {
                "title": toks[0],
                "company": toks[1] if len(toks) > 1 else "",
                "location": toks[2] if len(toks) > 2 else "",
                "salary": salary,
                "alumni": alumni,
                "posted_age": posted,
                "date_posted": posted,
                "source_id": job_id,
                "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
            }
        )
        seen_ids.add(job_id)

    for i in range(1, len(parts)):
        m = re.match(r"(\d+)", parts[i])
        if not m:
            continue
        job_id = m.group(1)
        if last_id is not None and job_id != last_id:
            _emit(last_id, parts[i - 1])
        last_id = job_id
    if last_id is not None:
        _emit(last_id, parts[-1])
    return rows


_FETCH_PAGE_JS = """
async ({baseQuery, start}) => {
    const r = await fetch('/jobs/search-results/?' + baseQuery + '&start=' + start,
                          {headers: {'accept': 'text/html'}});
    return {status: r.status, html: await r.text()};
}
"""


def _search_results_query(page_url: str) -> str | None:
    """Extract the query string of a /jobs/search-results/ URL, minus paging."""
    from urllib.parse import urlencode, urlparse, parse_qsl

    parsed = urlparse(page_url)
    if "/jobs/search-results/" not in parsed.path and "/jobs/search/" not in parsed.path:
        return None
    pairs = [(k, v) for k, v in parse_qsl(parsed.query) if k != "start"]
    return urlencode(pairs)


def extract_job_cards_live(page, pause_s: float, max_scrolls: int) -> list[dict]:
    """Fetch-based extraction of LinkedIn job cards (current DOM, verified
    live 2026-08-24). Fetches /jobs/search-results/ inside the authenticated
    tab, paginating via ``start``; falls back to legacy CSS selectors when the
    fetch path yields nothing (e.g. unexpected page shape).
    """
    base_query = _search_results_query(page.url)
    if base_query:
        # Map the scroll budget onto fetch pages (~25 cards/page); the old
        # default of 12 scrolls ≈ 3 result pages.
        max_pages = max(1, min(4, max_scrolls // 4))
        seen: dict[str, dict] = {}
        for page_no in range(max_pages):
            start = page_no * 25
            try:
                res = page.evaluate(_FETCH_PAGE_JS, {"baseQuery": base_query, "start": start})
            except Exception:
                break
            if not res or res.get("status") != 200:
                break
            fresh = 0
            for row in parse_search_results_html(res["html"]):
                if row["url"] not in seen:
                    seen[row["url"]] = row
                    fresh += 1
            if fresh == 0:
                break
            if page_no + 1 < max_pages:
                page.wait_for_timeout(int(pause_s * 1000))
        if seen:
            return list(seen.values())
    return _extract_job_cards_legacy(page, pause_s, max_scrolls)


def _extract_job_cards_legacy(page, pause_s: float, max_scrolls: int) -> list[dict]:
    """Scroll-pause extraction via pre-2026-08 LinkedIn CSS selectors.

    Kept as fallback: returns [] against the current hash-classed DOM.
    """
    seen: dict[str, dict] = {}
    for _ in range(max_scrolls):
        cards = page.query_selector_all("div.scaffold-layout__list > div > div > ul > li")
        for card in cards:
            try:
                a = card.query_selector("a.base-card__full-link, a.job-card-container__link")
                title_el = card.query_selector(".job-card-list__title, .base-search-card__title")
                company_el = card.query_selector(".job-card-container__primary-description, .base-search-card__subtitle, .artdeco-entity-lockup__subtitle")
                meta_el = card.query_selector(".job-card-container__metadata, .job-search-card__location, .artdeco-entity-lockup__caption li")
                age_el = card.query_selector(".job-card-container__listed-time, .job-search-card__listdate, time")
                if not (a and title_el):
                    continue
                url = (a.get_attribute("href") or "").split("?")[0]
                if not url or url in seen:
                    continue
                seen[url] = {
                    "title": title_el.get_attribute("aria-label") or title_el.inner_text().strip(),
                    "company": (company_el.inner_text().strip() if company_el else ""),
                    "location": (meta_el.inner_text().strip() if meta_el else ""),
                    "posted_age": (age_el.inner_text().strip() if age_el else ""),
                    "url": url,
                }
            except Exception:
                continue
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(int(pause_s * 1000))
    return list(seen.values())


def run_live(searches: list[dict], geos: dict, defaults: dict) -> int:
    """Live sweep in a LinkedIn-logged-in browser session.

    Attaches over CDP to the shared automation Chrome (:9333, see
    scripts/automation_chrome.sh) or falls back to a persistent context on
    the job-hunt profile. ONE new tab; closes it at the end.
    """
    from browser_session_lib import open_logged_in_session

    exit_code = 0
    entry = None
    with open_logged_in_session() as session:
        page = session.page
        try:
            for entry in searches:
                url = build_search_url(entry, geos, defaults)
                if entry.get("company_filter"):
                    url += "&companyFilter=" + entry["company_filter"].replace(" ", "%20")
                print(f"[live] {entry['id']} -> {url}")
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                if "/login" in page.url or "/authwall" in page.url:
                    raise RuntimeError(
                        "LinkedIn login wall hit even on the logged-in profile; "
                        "log in once at linkedin.com in the automation Chrome"
                    )
                extraction = extract_job_cards_live(
                    page, defaults["scroll_pause_seconds"], defaults["max_scrolls_per_search"]
                )
                dedup = load_dedup_index()
                accepted, duplicates, rejected = merge_extraction(
                    extraction, dedup, entry["id"]
                )
                append_jobs(accepted)
                log_search_run(entry["id"], len(extraction), len(accepted), len(rejected),
                               "ok" if extraction else "no_results")
                print(f"       seen={len(extraction)} new={len(accepted)} "
                      f"dup={len(duplicates)} rejected={len(rejected)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[live] ERROR: {exc}", file=sys.stderr)
            log_search_run(getattr(entry, "id", None) or (entry or {}).get("id", "?"), 0, 0, 0, f"error:{type(exc).__name__}")
            exit_code = 1
        finally:
            session.close()
    return exit_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="L1 LinkedIn saved-search portal sweep")
    ap.add_argument("--registry", default=REGISTRY_PATH)
    ap.add_argument("--dry-run", action="store_true", help="print searches that would run")
    ap.add_argument("--live", action="store_true", help="run the sweep via Playwright")
    ap.add_argument("--extraction-file", help="merge a JSON extraction fixture instead of browsing")
    ap.add_argument("--max-searches", type=int, default=None)
    args = ap.parse_args()

    with open(args.registry) as fh:
        cfg = yaml.safe_load(fh)
    geos, defaults = cfg["geos"], cfg["defaults"]
    cap = args.max_searches or defaults["max_searches_per_run"]
    searches = cap_searches(build_registry(args.registry), cap)

    if args.dry_run:
        print(f"Registry: {len(build_registry(args.registry))} searches defined; "
              f"capped run of {cap}:")
        for entry in searches:
            url = build_search_url(entry, geos, defaults)
            label = f" [{entry['company']}]" if entry.get("company") else ""
            print(f"  - {entry['id']}{label}\n      {url}")
        print("Dry run only: no pages visited, no rows written.")
        return 0

    if args.extraction_file:
        import json
        with open(args.extraction_file) as fh:
            extraction = json.load(fh)
        accepted, duplicates, rejected = merge_extraction(extraction, load_dedup_index(), "fixture")
        n = append_jobs(accepted)
        log_search_run("fixture", len(extraction), n, len(rejected), "ok")
        print(f"seen={len(extraction)} new={n} dup={len(duplicates)} rejected={len(rejected)}")
        return 0

    if args.live:
        return run_live(searches, geos, defaults)

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
