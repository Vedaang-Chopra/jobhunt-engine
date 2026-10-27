#!/usr/bin/env python3
"""
LinkedIn job sweep using guest API + logged-in fetch methods.
Normalizes through discovery_lib, dedupes against jobs.csv, applies gates, appends new rows.
"""

import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from scripts import config_lib
from scripts.discovery_lib import normalize_job, DedupIndex, scrutinize

JOBS_CSV = config_lib.path("jobs_csv")
SEARCH_RUNS_CSV = config_lib.path("search_runs_csv")
JD_ACTIVE_DIR = config_lib.path("jd_active_dir")
EXECUTION_RESULTS_DIR = config_lib.path("execution_results_dir")
EXECUTION_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
JD_ACTIVE_DIR.mkdir(parents=True, exist_ok=True)

# Profile-guided queries (from linkedin_guest_sweep.py)
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

BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}

CARD_RE = re.compile(r'<div class="base-card.*?(?=<div class="base-card|</ol>)', re.S)


def parse_cards(page_html):
    """Parse guest API HTML cards into job dicts."""
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
    """Load existing source_ids and company|title keys from jobs.csv for dedup."""
    keys = set()
    if not JOBS_CSV.exists():
        return keys
    with open(JOBS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            keys.add(row.get("source_id", "").lower())
            keys.add(row.get("job_id", "").lower())
            if row.get("company") and row.get("title"):
                keys.add(
                    row["company"].lower().replace(" ", "_") + "|"
                    + row["title"].lower().replace(" ", "_")
                )
    return keys


def load_existing_rows():
    """Load all existing rows for DedupIndex."""
    rows = []
    if not JOBS_CSV.exists():
        return rows
    with open(JOBS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def backup_jobs_csv():
    """Create a backup of jobs.csv before modifying."""
    if JOBS_CSV.exists():
        backup = JOBS_CSV.with_suffix(f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        JOBS_CSV.rename(backup)
        print(f"  Backed up jobs.csv to {backup}")


def fetch_jd(job_url, source_id):
    """Fetch full job description from LinkedIn job view page."""
    try:
        req = urllib.request.Request(job_url, headers=HEADERS)
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        # Parse description from div.show-more-less-html__markup
        desc_match = re.search(
            r'<div class="show-more-less-html__markup[^>]*>(.*?)</div>',
            body,
            re.S,
        )
        if desc_match:
            desc = html.unescape(re.sub(r"<[^>]+>", "\n", desc_match.group(1))).strip()
            return desc
    except Exception as e:
        print(f"    !! JD fetch failed for {source_id}: {e}")
    return ""


def make_job_id(source, company, title, source_id):
    """Create canonical job_id: source_company_title_sourceid"""
    company_slug = re.sub(r"[^a-z0-9]+", "_", company.strip().lower()).strip("_")
    title_slug = re.sub(r"[^a-z0-9]+", "_", title.strip().lower()).strip("_")
    return f"{source}_{company_slug}_{title_slug}_{source_id}"


def make_description_hash(desc):
    """SHA-256 hash of description, first 16 hex chars."""
    import hashlib
    return hashlib.sha256(desc.encode()).hexdigest()[:16]


def save_jd_file(job_id, desc):
    """Save JD to tracking/job_descriptions/active/"""
    if not desc:
        return ""
    filepath = JD_ACTIVE_DIR / f"{job_id}.md"
    filepath.write_text(desc)
    return str(filepath.relative_to(config_lib.data_root()))


def apply_gates(row, description):
    """Apply hard eligibility gates G1-G6 from ROLE_FIT_RULES.md §9.
    Returns (should_skip, gate_id) if gated out, else (False, None)."""
    title = row.get("title", "")
    desc = description or ""
    location = row.get("location", "")

    # G2: Director/VP/Head/Chief/Principal/people-manager titles
    senior_title_re = re.compile(
        r"\b(director|vp|vice president|head of|chief|principal|manager|lead|staff)\b",
        re.IGNORECASE,
    )
    if senior_title_re.search(title):
        return True, "G2"

    # G3: Internships/new-grad/early-career
    intern_re = re.compile(r"\bintern(ship)?\b", re.IGNORECASE)
    new_grad_re = re.compile(r"\b(new.?grad|entry.?level|early.?career|junior|new.?graduate)\b", re.IGNORECASE)
    if intern_re.search(title) or intern_re.search(desc) or new_grad_re.search(title) or new_grad_re.search(desc):
        # Check for conversion to full-time
        conversion_re = re.compile(
            r"full[- ]time conversion|return offer|conversion to full[- ]time|"
            r"convert(s|ion)? (?:to )?(?:a )?full[- ]time|full-time offer",
            re.IGNORECASE,
        )
        if not conversion_re.search(desc):
            return True, "G3"

    # G4: Posted pay <$150k - we can't easily detect this from LinkedIn guest API
    # Skip this gate for now since we don't have salary data from guest API

    # G5: Clearly unrelated roles (very broad - we'll rely on title matching in queries)
    # Our queries are already targeted, so skip explicit check

    # G1: Experience ceiling ~4.5 yrs hard minimum from JD text
    years_re = re.compile(r"(\d+)\+?\s*(?:-|to\s+)?\s*years?\b", re.IGNORECASE)
    years_match = years_re.search(desc)
    if years_match:
        years = int(years_match.group(1))
        if years >= 5:
            # Check for "or equivalent" phrasing
            equiv_re = re.compile(r"or equivalent|equivalent experience", re.IGNORECASE)
            if not equiv_re.search(desc):
                return True, "G1"

    # G6: Location gate - handled by scrutinize (US-wide, India only exceptional)
    # We'll let scrutinize handle this

    return False, None


def append_search_run(source, notes, new_count):
    """Append a row to search_runs.csv."""
    run_id = f"linkedin_{date.today().isoformat()}_{datetime.now().strftime('%H%M%S')}"
    file_exists = SEARCH_RUNS_CSV.exists()
    with open(SEARCH_RUNS_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["run_id", "sources", "notes", "new_count"])
        writer.writerow([run_id, source, notes, new_count])


def main():
    print("=== LinkedIn Job Sweep (Guest API) ===")
    print(f"Jobs CSV: {JOBS_CSV}")
    print(f"Queries: {len(QUERIES)}")

    # Load existing data for dedup
    seen_keys = existing_keys()
    existing_rows = load_existing_rows()
    dedup_index = DedupIndex()
    for row in existing_rows:
        dedup_index.add(row)

    print(f"Existing keys loaded: {len(seen_keys)}")
    print(f"Existing rows for dedup: {len(existing_rows)}")

    all_jobs = {}
    per_query_stats = {}
    total_fetched = 0
    total_new = 0
    total_gated = 0
    gate_counts = {"G1": 0, "G2": 0, "G3": 0, "G4": 0, "G5": 0, "G6": 0}

    for query in QUERIES:
        if total_fetched >= 8 * 25:  # Max 8 searches * 25 per page
            break

        params = {
            "keywords": query,
            "location": "United States",
            "f_TPR": "r604800",  # Past week
        }
        qs = urllib.parse.urlencode(params)

        found = 0
        new = 0
        gated = 0

        for start in (0, 25):
            if total_fetched >= 8 * 25:
                break

            url = f"{BASE_URL}?{qs}&start={start}"
            print(f"  Fetching: {query} (start={start})")
            req = urllib.request.Request(url, headers=HEADERS)
            try:
                body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
            except Exception as e:
                print(f"    !! fetch failed: {e}")
                break

            cards = parse_cards(body)
            if not cards:
                break

            for card in cards:
                source_id = card["source_id"]
                key = (
                    card["company"].lower().replace(" ", "_")
                    + "|"
                    + card["title"].lower().replace(" ", "_")
                )

                is_dup = (source_id.lower() in seen_keys) or (key in seen_keys)
                if source_id not in all_jobs:
                    all_jobs[source_id] = card

                if not is_dup:
                    # Fetch full JD
                    print(f"    New: {card['title']} @ {card['company']} (id={source_id})")
                    jd = fetch_jd(card["url"], source_id)
                    time.sleep(0.8)  # Rate limit

                    # Apply gates BEFORE adding to pipeline
                    should_skip, gate_id = apply_gates(card, jd)
                    if should_skip:
                        gated += 1
                        if gate_id:
                            gate_counts[gate_id] = gate_counts.get(gate_id, 0) + 1
                        print(f"      -> GATED OUT by {gate_id}")
                        continue

                    # Normalize through discovery_lib
                    raw = {
                        "title": card["title"],
                        "company": card["company"],
                        "url": card["url"],
                        "location": card["location"],
                        "source": "linkedin",
                        "source_id": source_id,
                        "date_posted": card["date_posted_raw"],
                        "description": jd,
                    }
                    try:
                        norm_row = normalize_job(raw)
                    except ValueError as e:
                        print(f"      !! normalize failed: {e}")
                        continue

                    # Additional dedup via DedupIndex
                    is_dup2, matched = dedup_index.seen_before(norm_row)
                    if is_dup2:
                        print(f"      -> DEDUP via index (matched: {matched.get('job_id')})")
                        continue

                    # Generate job_id
                    norm_row["job_id"] = make_job_id("linkedin", card["company"], card["title"], source_id)
                    norm_row["source_id"] = source_id
                    norm_row["source"] = "linkedin"

                    # Save JD and hash
                    if jd:
                        norm_row["full_description_hash"] = make_description_hash(jd)
                        norm_row["description_file"] = save_jd_file(norm_row["job_id"], jd)

                    # Scrutinize (location gate, etc.)
                    verdict, flags = scrutinize(norm_row)
                    if verdict == "reject":
                        gated += 1
                        gate_counts["G6"] = gate_counts.get("G6", 0) + 1
                        print(f"      -> SCRUTINY REJECT: {flags}")
                        continue

                    # Add to dedup index
                    dedup_index.add(norm_row)
                    seen_keys.add(source_id.lower())
                    seen_keys.add(key)

                    # Store for batch append
                    all_jobs[source_id] = {**card, **norm_row, "full_jd": jd}
                    new += 1
                    total_new += 1
                    print(f"      -> ACCEPTED (new count: {total_new})")
                else:
                    print(f"    Dup: {card['title']} @ {card['company']}")

            found += len(cards)
            total_fetched += len(cards)

            if len(cards) < 10:
                break
            time.sleep(2)

        per_query_stats[query] = {"cards": found, "new": new, "gated": gated}
        total_gated += gated
        print(f"  {query}: cards={found} new={new} gated={gated}")
        time.sleep(2)

    # Now append all new jobs to jobs.csv
    if total_new > 0:
        backup_jobs_csv()

        # Read existing CSV to get fieldnames
        fieldnames = []
        if JOBS_CSV.exists():
            with open(JOBS_CSV, newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames) if reader.fieldnames else []

        # Ensure all required columns
        from scripts.discovery_lib import _CSV_COLUMNS
        for col in _CSV_COLUMNS:
            if col not in fieldnames:
                fieldnames.append(col)

        # Write all rows (existing + new)
        all_rows = existing_rows[:]
        for job_data in all_jobs.values():
            if "full_jd" in job_data:  # This is a new job we accepted
                row = {k: v for k, v in job_data.items() if k != "full_jd"}
                # Filter to only canonical columns
                row = {k: v for k, v in row.items() if k in fieldnames}
                all_rows.append(row)

        with open(JOBS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)

        print(f"\nAppended {total_new} new jobs to {JOBS_CSV}")

    # Log search run
    notes = f"queries={len(QUERIES)} fetched={total_fetched} new={total_new} gated={total_gated} (G1={gate_counts.get('G1',0)} G2={gate_counts.get('G2',0)} G3={gate_counts.get('G3',0)} G6={gate_counts.get('G6',0)})"
    append_search_run("linkedin_guest", notes, total_new)

    print(f"\n=== SUMMARY ===")
    print(f"Total queries: {len(QUERIES)}")
    print(f"Total cards fetched: {total_fetched}")
    print(f"New jobs added: {total_new}")
    print(f"Gated out: {total_gated}")
    for gate, count in gate_counts.items():
        if count > 0:
            print(f"  {gate}: {count}")
    print(f"Search run logged to {SEARCH_RUNS_CSV}")

    # Save detailed results
    out_file = EXECUTION_RESULTS_DIR / f"linkedin_sweep_{date.today().isoformat()}.json"
    out_file.write_text(json.dumps({
        "per_query": per_query_stats,
        "summary": {
            "total_fetched": total_fetched,
            "total_new": total_new,
            "total_gated": total_gated,
            "gate_counts": gate_counts,
        }
    }, indent=2))
    print(f"Detailed results saved to {out_file}")


if __name__ == "__main__":
    main()