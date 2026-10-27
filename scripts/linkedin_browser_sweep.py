#!/usr/bin/env python3
"""LinkedIn browser sweep using Playwright MCP - runs ONE tab, ≤8 searches, applies hard eligibility gates G1-G6."""

import sys
import csv
import json
import time
import re
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from scripts import config_lib
from scripts import discovery_lib

JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = config_lib.path("search_runs_csv")
OUT_DIR = config_lib.path("execution_results_dir")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Same queries as linkedin_guest_sweep_normalized.py
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

def build_search_url(query: str, start: int = 0) -> str:
    """Build LinkedIn jobs search URL with past-week filter."""
    from urllib.parse import quote
    kw = quote(query)
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location=United%20States&f_TPR=r604800&start={start}"

def extract_jobs_from_page(page) -> list[dict]:
    """Extract job cards from current page using JavaScript."""
    return page.evaluate("""() => {
        const jobs = [];
        // Use the occludable job ID cards as containers
        const cards = document.querySelectorAll('li[data-occludable-job-id]');
        cards.forEach(card => {
            const link = card.querySelector('a[href*="/jobs/view/"]');
            if (!link) return;
            const titleEl = card.querySelector('.artdeco-entity-lockup__title, h3, [data-test-id="job-title"]');
            const companyEl = card.querySelector('.artdeco-entity-lockup__subtitle, h4, [data-test-id="company-name"]');
            const locationEl = card.querySelector('.artdeco-entity-lockup__caption, [class*="location"], [data-test-id="job-location"]');
            const timeEl = card.querySelector('time');
            
            const title = titleEl?.textContent?.trim() || link.textContent?.trim() || '';
            const company = companyEl?.textContent?.trim() || '';
            const location = locationEl?.textContent?.trim() || '';
            const time = timeEl?.textContent?.trim() || '';
            const url = link.href;
            const m = url.match(/\\/jobs\\/view\\/([^\\/?]+)/);
            const source_id = m ? m[1] : '';
            if (title && company && url && title.length > 3) {
                jobs.push({ title, company, location, date_posted: time, url, source_id });
            }
        });
        return jobs;
    }""")

def apply_eligibility_gates(row: dict) -> tuple[str, list[str]]:
    """
    Apply hard eligibility gates G1-G6 from ROLE_FIT_RULES.md §9.
    Returns (verdict, flags) where verdict is 'useful', 'borderline', or 'non_useful'.
    """
    title = (row.get("title") or "").strip()
    desc = (row.get("description") or "").strip()
    location = (row.get("location") or "").strip()
    job_url = (row.get("job_url") or "").strip()
    
    verdict = "useful"
    flags = []
    
    # G1: Experience ceiling - ~4.5 yrs production ML hard minimum
    years_match = discovery_lib._YEARS_RE.search(desc)
    years = int(years_match.group(1)) if years_match else None
    if years is not None and years >= 5:
        # Check for flexible "or equivalent" phrasing
        flexible = bool(re.search(r"or equivalent|equivalent experience|or related", desc, re.IGNORECASE))
        if not flexible:
            verdict = "non_useful"
            flags.append(f"G1_experience_ceiling_{years}yrs")
    
    # G2: Seniority ceiling - Director/VP/Head/Chief/Principal/people-manager titles
    if discovery_lib._SENIOR_BAR_RE.search(title):
        verdict = "non_useful"
        flags.append("G2_seniority_title")
    
    # G3: Early-career exclusion - Internships, co-ops, new-grad, early-career programs
    if discovery_lib._INTERNSHIP_RE.search(title) or discovery_lib._INTERNSHIP_RE.search(desc):
        if not discovery_lib._CONVERSION_RE.search(desc):
            verdict = "non_useful"
            flags.append("G3_internship_no_conversion")
    
    # G4: Pay floor - Posted pay below $150k (only when posted)
    pay_match = re.search(r"\$(\d{3,})[kK]", desc)
    if pay_match:
        pay = int(pay_match.group(1)) * 1000
        if pay < 150000:
            verdict = "non_useful"
            flags.append(f"G4_pay_floor_{pay}")
    
    # G5: Profile fit - Role unrelated to target families
    # Target: Research/Applied Scientist, MLE, AI Engineer with agentic/reasoning/post-training/inference/eval focus
    # Exclude: frontend-only, PM, data-analyst, hardware, bioinformatics, sales, etc.
    excluded_patterns = [
        r"\bfrontend\b", r"\bfront-end\b", r"\bproduct manager\b", r"\bdata analyst\b",
        r"\bhardware\b", r"\bbioinformatics\b", r"\bsales\b", r"\bmarketing\b",
        r"\bdevops\b", r"\bsre\b", r"\binfrastructure engineer\b(?![^.]*ml)",
        r"\bplatform engineer\b(?![^.]*ml)", r"\bsecurity engineer\b(?![^.]*ml|.*ai)",
        r"\bqa\b", r"\btest engineer\b", r"\bsupport\b", r"\boperations\b",
    ]
    for pattern in excluded_patterns:
        if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, desc, re.IGNORECASE):
            verdict = "non_useful"
            flags.append(f"G5_profile_fit_{pattern}")
            break
    
    # G6: Link/JD presence - No working link AND no retrievable JD
    if not job_url:
        verdict = "non_useful"
        flags.append("G6_no_link")
    
    return verdict, flags

def run_browser_sweep():
    """Run LinkedIn jobs sweep using Playwright MCP browser."""
    from playwright.sync_api import sync_playwright
    
    # Connect to existing Chrome on CDP port 9333
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9333")
    
    # Get or create context/page
    if browser.contexts:
        ctx = browser.contexts[0]
    else:
        ctx = browser.new_context()
    
    if ctx.pages:
        page = ctx.pages[0]
    else:
        page = ctx.new_page()
    
    # Load existing jobs for dedup
    index = discovery_lib.DedupIndex()
    if JOBS_CSV.exists():
        with open(JOBS_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                index.add(row)
    
    all_hits = {}
    per_query = {}
    blocked = False
    
    try:
        for q in QUERIES:
            if blocked:
                break
            print(f"\n=== Query: {q} ===")
            found = 0
            
            for start in (0, 25):  # Two pages max
                url = build_search_url(q, start)
                print(f"  Navigating to: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)  # Let results load
                
                # Check for auth wall / CAPTCHA
                page_text = page.inner_text("body").lower()
                if "authwall" in page_text[:2000] or "captcha" in page_text or "sign in to view" in page_text:
                    print("  !! CAPTCHA/authwall detected — stopping")
                    blocked = True
                    break
                
                # Wait for job cards to appear
                try:
                    page.wait_for_selector('a[href*="/jobs/view/"]', timeout=15000)
                except Exception:
                    print("  No job links found on page, checking for auth wall...")
                    page_text = page.inner_text("body").lower()
                    if "authwall" in page_text[:2000] or "captcha" in page_text or "sign in to view" in page_text:
                        print("  !! CAPTCHA/authwall detected — stopping")
                        blocked = True
                    break
                
                # Extract jobs
                cards = extract_jobs_from_page(page)
                print(f"  Found {len(cards)} cards on page start={start}")
                
                for j in cards:
                    all_hits.setdefault(j["source_id"], {**j, "query": q})
                
                found += len(cards)
                
                if len(cards) < 10:
                    break
                time.sleep(2)
            
            per_query[q] = found
            print(f"  {q}: cards={found}")
            time.sleep(2)
    
    finally:
        # Close the page but don't kill the shared browser
        page.close()
        browser.close()
        pw.stop()
    
    # Process hits through normalization + gates + dedup
    new_rows = []
    dup_count = 0
    rej_count = []
    gated_out = 0
    
    for sid, j in all_hits.items():
        try:
            raw = {
                "title": j["title"],
                "company": j["company"],
                "url": j["url"],
                "source_id": sid,
                "location": j.get("location", ""),
                "source": "linkedin",
                "date_posted": j.get("date_posted", ""),
                "notes": f"linkedin_browser_sweep query={j['query']!r}",
                "description": "",  # No JD from guest view
            }
            row = discovery_lib.normalize_job(raw)
        except ValueError:
            continue
        
        # Apply scrutiny gate (location, etc.)
        verdict, flags = discovery_lib.scrutinize(row)
        if verdict == "reject":
            rej_count.append((row["title"], row["company"], flags))
            continue
        
        # Apply hard eligibility gates G1-G6
        verdict, gate_flags = apply_eligibility_gates(row)
        if verdict == "non_useful":
            gated_out += 1
            rej_count.append((row["title"], row["company"], gate_flags))
            continue
        elif verdict == "borderline":
            flags.extend(gate_flags)
        
        # Dedup
        is_dup, _match = index.seen_before(row)
        if is_dup:
            dup_count += 1
            continue
        
        index.add(row)
        
        # Set status and recommended_action
        if verdict == "non_useful":
            row["status"] = "open"
            row["recommended_action"] = "SKIP"
            row["notes"] = f"GATED OUT at ingest: {', '.join(gate_flags)}"
        else:
            row["status"] = "open"
            row["recommended_action"] = ""
            row["notes"] = f"Discovered via LinkedIn browser sweep query={j['query']!r}"
        
        new_rows.append(row)
    
    # Append new rows to jobs.csv
    if new_rows and not blocked:
        fieldnames = list(new_rows[0].keys())
        with open(JOBS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        if header != fieldnames:
            new_rows = [{k: row.get(k, "") for k in header} for row in new_rows]
            fieldnames = header
        with open(JOBS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            for row in new_rows:
                w.writerow(row)
    
    # Log search run
    run_id = f"linkedin_browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    notes = f"browser sweep; queries={len(per_query)}; scanned={sum(per_query.values())}"
    if blocked:
        notes += "; BLOCKED(captcha/authwall) partial"
    with open(RUNS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([run_id, date.today().isoformat(), "linkedin_browser",
                    "; ".join(f"{q}:{n}" for q, n in per_query.items()),
                    sum(per_query.values()), len(new_rows), dup_count,
                    "", notes])
    
    # Output summary
    out = OUT_DIR / f"linkedin_browser_sweep_{date.today().isoformat()}.json"
    out.write_text(json.dumps({
        "per_query": per_query,
        "new": [r["job_url"] for r in new_rows],
        "duplicates_skipped": dup_count,
        "rejected": [{"title": t, "company": c, "flags": fl} for t, c, fl in rej_count],
        "gated_out": gated_out,
    }, indent=2))
    
    print(f"\n{'='*50}")
    print(f"SCANNED={sum(per_query.values())} NEW={len(new_rows)} DUPS={dup_count} REJECTED={len(rej_count)} GATED_OUT={gated_out} BLOCKED={blocked}")
    print(f"Wrote {out}")
    
    return {
        "scanned": sum(per_query.values()),
        "new": len(new_rows),
        "duplicates": dup_count,
        "rejected": len(rej_count),
        "gated_out": gated_out,
        "blocked": blocked,
    }

if __name__ == "__main__":
    result = run_browser_sweep()
    sys.exit(0 if not result["blocked"] else 1)