#!/usr/bin/env python3
"""Complete LinkedIn guest API sweep: fetch, parse, normalize, gate, dedupe, append."""
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
import discovery_lib as d

JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
SRC_DIR = config_lib.path("execution_results_dir")
SRC_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
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
    if not JOBS_CSV.exists():
        return keys
    with open(JOBS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            keys.add(row.get("source_id", "").lower())
            keys.add(row.get("job_id", "").lower())
            if row.get("company") and row.get("title"):
                keys.add((row["company"].lower().replace(" ", "_") + "|" +
                          row["title"].lower().replace(" ", "_")))
    return keys


def fetch_query(q, start=0):
    params = {"keywords": q, "location": "United States", "f_TPR": "r604800", "start": str(start)}
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        return body
    except Exception as e:
        print(f"  !! fetch failed q={q!r} start={start}: {e}")
        return ""


def main():
    seen = existing_keys()
    all_jobs = {}
    per_query = {}
    gated_out = 0
    accepted = 0

    for q in QUERIES:
        print(f"\n=== Query: {q} ===")
        found = 0
        new = 0
        for start in (0, 25):
            body = fetch_query(q, start)
            if not body:
                break
            cards = parse_cards(body)
            if not cards:
                break
            found += len(cards)
            for j in cards:
                key = j["company"].lower().replace(" ", "_") + "|" + j["title"].lower().replace(" ", "_")
                j["dup_of_existing"] = (j["source_id"].lower() in seen) or (key in seen)
                if j["source_id"] not in all_jobs:
                    all_jobs[j["source_id"]] = j
                if not j["dup_of_existing"]:
                    new += 1
            if len(cards) < 10:
                break
            time.sleep(2)
        per_query[q] = {"cards": found, "new": new}
        print(f"  cards={found} new={new}")

    print(f"\nTotal unique cards: {len(all_jobs)}")
    
    # Normalize and gate each fresh job
    fresh_jobs = [j for j in all_jobs.values() if not j["dup_of_existing"]]
    new_rows = []
    
    for j in fresh_jobs:
        raw = {
            "title": j["title"],
            "company": j["company"],
            "url": j["url"],
            "location": j.get("location", ""),
            "source": "linkedin_guest_api",
            "source_id": f"li_{j['source_id']}",
            "date_posted": j.get("date_posted_raw", ""),
            "notes": f"posted_rel={j.get('posted_rel','')}; sweep=linkedin_guest_{date.today().isoformat()}",
        }
        try:
            row = d.normalize_job(raw)
        except ValueError as e:
            print(f"  !! normalize failed for {j['company']} | {j['title']}: {e}")
            continue
        
        verdict, flags = d.scrutinize(row)
        row["status"] = "rejected" if verdict == "reject" else "open"
        row["missing_info"] = ";".join(flags)
        
        if verdict == "reject":
            gated_out += 1
            print(f"  GATED OUT: {j['company']} | {j['title']} | flags={flags}")
        else:
            accepted += 1
            new_rows.append(row)
            print(f"  ACCEPTED: {j['company']} | {j['title']} | flags={flags}")
        
        # Add to seen to prevent dupes within this sweep
        seen.add(j["source_id"].lower())
        seen.add(j["company"].lower().replace(" ", "_") + "|" + j["title"].lower().replace(" ", "_"))

    # Append to CSV
    if new_rows:
        with open(JOBS_CSV, newline="") as f:
            existing = list(csv.DictReader(f))
        cols = list(existing[0].keys()) if existing else list(new_rows[0].keys())
        with open(JOBS_CSV, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            for row in new_rows:
                w.writerow(row)

    # Log to search_runs.csv
    total_scanned = sum(v["cards"] for v in per_query.values())
    total_new = sum(v["new"] for v in per_query.values())
    
    run_id = f"li_guest_{date.today().isoformat()}_{int(time.time())%10000:04d}"
    notes = (f"queries={QUERIES}; gated_out={gated_out}; "
             f"accepted={accepted}; total_new={total_new}")
    
    search_runs_csv = config_lib.data_root() / "tracking" / "search_runs" / "search_runs.csv"
    search_runs_csv.parent.mkdir(parents=True, exist_ok=True)
    
    file_exists = search_runs_csv.exists()
    with open(search_runs_csv, "a", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["run_id", "date", "sources", "queries", "total_scanned", 
                        "new_jobs_found", "duplicates_skipped", "strong_fits", "notes"])
        w.writerow([run_id, date.today().isoformat(), "linkedin_guest_api", len(QUERIES),
                    total_scanned, total_new, total_scanned - total_new, accepted, notes])

    # Write detailed output
    out_file = SRC_DIR / f"linkedin_sweep_{date.today().isoformat()}.json"
    fresh = [j for j in all_jobs.values() if not j["dup_of_existing"]]
    dups = [j for j in all_jobs.values() if j["dup_of_existing"]]
    out_file.write_text(json.dumps({
        "per_query": per_query,
        "fresh": fresh,
        "duplicates": dups,
        "accepted_count": accepted,
        "gated_out_count": gated_out,
    }, indent=2))
    
    print(f"\n=== SUMMARY ===")
    print(f"Total cards scanned: {total_scanned}")
    print(f"Fresh candidates: {len(fresh_jobs)}")
    print(f"Accepted (open): {accepted}")
    print(f"Gated out (rejected): {gated_out}")
    print(f"Duplicates skipped: {len(dups)}")
    print(f"Wrote {out_file}")
    print(f"Appended {len(new_rows)} rows to jobs.csv")
    print(f"Logged run {run_id} to search_runs.csv")


if __name__ == "__main__":
    main()