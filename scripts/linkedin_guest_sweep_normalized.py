#!/usr/bin/env python3
"""LinkedIn guest-API sweep normalized through discovery_lib.

Fetches via the public jobs-guest API (no login), normalizes each hit with
discovery_lib.normalize_job + scrutinize, dedupes against tracking/jobs/jobs.csv
via DedupIndex, appends new rows, and logs the run to
tracking/search_runs/search_runs.csv.
"""
import csv
import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
try:
    from scripts import discovery_lib  # noqa: E402
    from scripts import config_lib  # noqa: E402
except ImportError:
    import discovery_lib  # noqa: E402
    import config_lib  # noqa: E402

JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
RUNS_CSV = config_lib.data_root() / "tracking" / "search_runs" / "search_runs.csv"
OUT_DIR = config_lib.path("execution_results_dir")
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
        jobs.append({
            "source_id": num_id,
            "title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else "",
            "company": html.unescape(re.sub(r"<[^>]+>", "", comp.group(1))).strip() if comp else "",
            "location": html.unescape(re.sub(r"<[^>]+>", "", loc.group(1))).strip() if loc else "",
            "date_posted": t.group(1)[:10] if t else "",
            "url": f"https://www.linkedin.com/jobs/view/{num_id}/",
        })
    return jobs


def main():
    index = discovery_lib.DedupIndex()
    with open(JOBS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            index.add(row)

    all_hits = {}
    per_query = {}
    blocked = False
    for q in QUERIES:
        kw = urllib.parse.quote(q)
        found = 0
        for start in (0, 25):
            url = BASE.format(kw=kw, start=start)
            req = urllib.request.Request(url, headers=HEADERS)
            try:
                resp = urllib.request.urlopen(req, timeout=30)
                body = resp.read().decode("utf-8", "ignore")
            except urllib.error.HTTPError as e:
                print(f"  !! HTTP {e.code} q={q!r} start={start}")
                if e.code in (429, 999):
                    blocked = True
                break
            except Exception as e:
                print(f"  !! fetch failed q={q!r} start={start}: {e}")
                break
            if "authwall" in body[:2000].lower() or "captcha" in body.lower():
                print("  !! CAPTCHA/authwall detected — stopping")
                blocked = True
                break
            cards = parse_cards(body)
            for j in cards:
                all_hits.setdefault(j["source_id"], {**j, "query": q})
            found += len(cards)
            if len(cards) < 10:
                break
            time.sleep(2)
        per_query[q] = found
        print(f"{q}: cards={found}")
        if blocked:
            break
        time.sleep(2)

    new_rows, dup_count, rej_count = [], 0, []
    for sid, j in all_hits.items():
        try:
            row = discovery_lib.normalize_job({
                "title": j["title"], "company": j["company"],
                "url": j["url"], "source_id": sid,
                "location": j.get("location", ""),
                "source": "linkedin", "date_posted": j.get("date_posted", ""),
                "notes": f"linkedin_guest_sweep query={j['query']!r}",
            })
        except ValueError:
            continue
        verdict, flags = discovery_lib.scrutinize(row)
        if verdict == "reject":
            rej_count.append((row["title"], row["company"], flags))
            continue
        is_dup, _match = index.seen_before(row)
        if is_dup:
            dup_count += 1
            continue
        index.add(row)
        new_rows.append(row)

    if new_rows and not blocked:
        fieldnames = list(new_rows[0].keys())
        with open(JOBS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        if header != fieldnames:  # align to canonical column order
            new_rows = [{k: row.get(k, "") for k in header} for row in new_rows]
            fieldnames = header
        with open(JOBS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            for row in new_rows:
                w.writerow(row)

    run_id = f"linkedin_guest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    notes = f"guest-api sweep; queries={len(per_query)}; scanned={sum(per_query.values())}"
    if blocked:
        notes += "; BLOCKED(captcha/ratelimit) partial"
    with open(RUNS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([run_id, date.today().isoformat(), "l1,l2(guest)",
                    "; ".join(f"{q}:{n}" for q, n in per_query.items()),
                    sum(per_query.values()), len(new_rows), dup_count,
                    "", notes])

    out = OUT_DIR / f"linkedin_sweep_{date.today().isoformat()}.json"
    out.write_text(json_dumps := __import__("json").dumps(
        {"per_query": per_query, "new": [r["job_url"] for r in new_rows],
         "duplicates_skipped": dup_count,
         "rejected": [{"title": t, "company": c, "flags": fl}
                      for t, c, fl in rej_count]}, indent=2))
    print(f"\nscanned={sum(per_query.values())} NEW={len(new_rows)} "
          f"dups={dup_count} rejected={len(rej_count)} blocked={blocked}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
