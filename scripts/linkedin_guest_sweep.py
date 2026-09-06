#!/usr/bin/env python3
"""LinkedIn guest-API sweep: profile-guided queries, US + past-week filter.
Dedupes against tracking/jobs/jobs.csv by source_id and company+title.
Writes execution_results/linkedin_sweep_<date>.json"""
import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import config_lib
except ImportError:
    import config_lib
JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
OUT_DIR = config_lib.path("execution_results_dir")
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    # Guided (profile: AI research/applied, post-training, agents, evals)
    "Research Engineer Machine Learning",
    "AI Research Scientist",
    "Post-Training LLM",
    "LLM Fine-Tuning Engineer",
    "AI Agent Engineer",
    "Applied Scientist AI",
    "Machine Learning Engineer LLM",
    "LLM Evaluation Research",
]
BASE = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        "?keywords={kw}&location=United%20States&f_TPR=r604800&start={start}")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

CARD_RE = re.compile(r'<div class="base-card.*?(?=<div class="base-card|</ol>)', re.S)

# Planned-query filter-key -> guest-API URL param mapping.
RECENCY_SECONDS = {"day": 86400, "week": 604800, "month": 2592000}
GEO_IDS = {"us": "103644278", "us_remote": "103644278"}


def build_arg_parser():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planned-json", default=None,
                        help="Path to a planner output file ({\"queries\": [...]} "
                             "or bare list of PlannedQuery dicts). When given, "
                             "iterates those rows instead of the static QUERIES.")
    return parser


def filters_to_params(filters):
    """Map PlannedQuery filter keys onto guest-API URL params.

    Unknown keys are ignored safely. Returns a dict of URL query params.
    """
    filters = filters or {}
    params = {}
    geo = str(filters.get("geo", "")).strip().lower()
    if geo:
        if geo.startswith("geo:"):
            params["geoId"] = geo.split(":", 1)[1]
        else:
            params["location"] = "United States"
            if geo in GEO_IDS:
                params["geoId"] = GEO_IDS[geo]
    recency = str(filters.get("recency", "")).strip().lower()
    if recency in RECENCY_SECONDS:
        params["f_TPR"] = f"r{RECENCY_SECONDS[recency]}"
    exp = str(filters.get("experience", "")).strip()
    if re.fullmatch(r"[0-9]+(,[0-9]+)*", exp):
        params["f_E"] = exp
    return params


def resolve_query_rows(args):
    """Return the rows to sweep: planned dicts when --planned-json is set,
    otherwise the static QUERIES list unchanged (byte-for-byte legacy path)."""
    path = getattr(args, "planned_json", None)
    if not path:
        return list(QUERIES)
    try:
        from scripts.search_strategy.exec_jobs import parse_planned_json
    except ImportError:
        from search_strategy.exec_jobs import parse_planned_json
    return parse_planned_json(path)


def _log_memory(query, family, filters, found, new):
    """Append one SearchMemory QueryRecord; never raises."""
    try:
        try:
            from scripts.search_strategy.memory import QueryRecord, SearchMemory
        except ImportError:
            from search_strategy.memory import QueryRecord, SearchMemory
        mem = SearchMemory(root=config_lib.data_root())
        mem.append(QueryRecord(
            mode="jobs",
            query=query,
            family=family or "",
            filters_json=json.dumps(filters or {}),
            results_inspected=found,
            relevant_results=new,
            new_results=new,
            duplicate_results=max(found - new, 0),
        ))
    except Exception as exc:
        print(f"  !! search-memory append failed q={query!r}: {exc}")


def parse_cards(page_html):
    jobs = []
    for block in CARD_RE.findall(page_html):
        m = re.search(r'href="[^"]*/jobs/view/([^/?"]+)', block)
        if not m:
            continue
        sid = m.group(1)
        num_id = sid.rsplit("-", 1)[-1] if sid.rsplit("-", 1)[-1].isdigit() else sid
        title = re.search(r'<h3[^>]*>\s*(.*?)\s*</h3>', block, re.S)
        comp = re.search(r'<h4[^>]*>\s*(.*?)\s*</h4>', block, re.S)
        loc = re.search(r'job-search-card__location[^>]*>\s*(.*?)\s*<', block, re.S)
        t = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        t2 = re.search(r'<time[^>]*>\s*(.*?)\s*</time>', block, re.S)
        jobs.append({
            "source_id": num_id,
            "title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else "",
            "company": html.unescape(re.sub(r"<[^>]+>", "", comp.group(1))).strip() if comp else "",
            "location": html.unescape(re.sub(r"<[^>]+>", "", loc.group(1))).strip() if loc else "",
            "date_posted_raw": t.group(1)[:10] if t else "",
            "posted_rel": html.unescape(re.sub(r"<[^>]+>", "", t2.group(1))).strip() if t2 else "",
            "url": f"https://www.linkedin.com/jobs/view/{num_id}/",
        })
    return jobs


def existing_keys():
    keys = set()
    with open(JOBS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            keys.add(row.get("source_id", "").lower())
            keys.add(row.get("job_id", "").lower())
            if row.get("company") and row.get("title"):
                keys.add((row["company"].lower().replace(" ", "_") + "|" +
                          row["title"].lower().replace(" ", "_")))
    return keys


def _row_query(row):
    return row if isinstance(row, str) else str(row.get("query", ""))


def _row_filters(row):
    return {} if isinstance(row, str) else (row.get("filters") or {})


def _row_family(row):
    return "" if isinstance(row, str) else str(row.get("family", "") or "")


def run_sweep(rows):
    seen = existing_keys()
    all_jobs = {}
    per_query = {}
    for row in rows:
        q = _row_query(row)
        filters = _row_filters(row)
        family = _row_family(row)
        params = {"keywords": q, "location": "United States",
                  "f_TPR": "r604800"}
        params.update(filters_to_params(filters))
        qs = urllib.parse.urlencode(params)
        found = 0
        new = 0
        for start in (0, 25):
            url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                   f"?{qs}&start={start}")
            req = urllib.request.Request(url, headers=HEADERS)
            try:
                body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
            except Exception as e:
                print(f"  !! fetch failed q={q!r} start={start}: {e}")
                break
            cards = parse_cards(body)
            new = 0
            for j in cards:
                key = j["company"].lower().replace(" ", "_") + "|" + j["title"].lower().replace(" ", "_")
                j["dup_of_existing"] = (j["source_id"].lower() in seen) or (key in seen)
                if j["source_id"] not in all_jobs:
                    all_jobs[j["source_id"]] = j
                if not j["dup_of_existing"]:
                    new += 1
            found += len(cards)
            if len(cards) < 10:  # no more pages
                break
            time.sleep(2)
        per_query[q] = {"cards": found, "new": new}
        print(f"{q}: cards={found} new={new}")
        _log_memory(q, family, filters, found, new)
        time.sleep(2)

    fresh = [j for j in all_jobs.values() if not j["dup_of_existing"]]
    dups = [j for j in all_jobs.values() if j["dup_of_existing"]]
    out = OUT_DIR / f"linkedin_sweep_{date.today().isoformat()}.json"
    out.write_text(json.dumps({"per_query": per_query, "fresh": fresh, "duplicates": dups}, indent=2))
    print(f"\nTOTAL cards={len(all_jobs)} fresh={len(fresh)} dupes={len(dups)}")
    print(f"Wrote {out}")


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    run_sweep(resolve_query_rows(args))


if __name__ == "__main__":
    main()
