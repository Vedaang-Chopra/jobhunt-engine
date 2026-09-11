"""Cron LinkedIn sweep 2026-08-24 evening: parse logged-in fetch results + guest API merge."""
import csv, json, re, sys, datetime, urllib.request, time

sys.path.insert(0, "scripts")
import discovery_lib as dl

SPLIT = "/Users/vedaangchopra/.hermes/profiles/job-hunt/cache/spillover/5e5d2266-9660-4607-82e6-57af13c6bca3.txt"
JOBS = "tracking/jobs/jobs.csv"
RUNS = "tracking/search_runs/search_runs.csv"

outer = json.load(open(SPLIT))["result"]          # "### Result\n\"[...]\"\n..."
inner = outer.split("### Result\n", 1)[1].strip()
dec = json.JSONDecoder()
s = inner
if s.startswith('"'):
    s, _ = dec.raw_decode(s)
data = dec.raw_decode(s.strip())[0]
print(f"records from logged-in fetch: {len(data)}")

# ---- parse card text: componentkey=..."> TITLE COMPANY LOC ... ----
def parse_card(text):
    t = re.sub(r"^componentkey=.*?>", "", text)
    # salary
    sal = re.search(r"\$[\d.,]+K?/yr\s*-\s*\$[\d.,]+K?/yr", t)
    conn = re.search(r"(\d+) (?:company alumni|connections?) work(?:s)? here", t)
    posted = re.search(r"Posted (\d+|\d+\+?) (hour|day|week)s? ago", t)
    return {"salary": sal.group(0) if sal else "", "conn": conn.group(0) if conn else "",
            "posted": posted.group(0) if posted else ""}

cards = {}
for r in data:
    if "error" in r or not r.get("id"):
        continue
    meta = parse_card(r["text"])
    c = cards.setdefault(r["id"], {**meta, "queries": []})
    c["queries"].append(r["q"])
    for k in ("salary", "conn", "posted"):
        if not c[k] and meta[k]:
            c[k] = meta[k]
    if len(c["text"] if "text" in c else "") < len(r["text"]) and "text" not in c:
        pass

# need title/company/location per id: pull first raw text of each id again
first_text = {}
for r in data:
    if r.get("id") and r["id"] not in first_text:
        first_text[r["id"]] = r["text"]

def parse_fields(text):
    t = re.sub(r"^componentkey=[^>]*>", "", text)
    t = t.split(" Viewed")[0]
    # location patterns: ends with state/remote before Posted/salary/connections
    m_loc = re.search(r",\s*([A-Z]{2}|United States|Remote)[^A-Za-z]*(?:\(On-site\)|\(Hybrid\)|\(Remote\))?", t)
    return t[:300]

jobs = []
for jid, meta in cards.items():
    txt = re.sub(r"^componentkey=[^>]*>", "", first_text[jid])
    txt = re.split(r" Viewed| Posted", txt)[0]
    txt = re.sub(r"\s+", " ", txt).strip()
    # Heuristic split: last "City, ST ..." chunk = location
    mloc = re.search(r"([A-Za-z .]+,\s*[A-Z]{2}(?:\s*\([^)]*\))?|[A-Za-z ]+, United States(?:\s*\([^)]*\))?|United States(?:\s*\([^)]*\))?)", txt)
    loc = mloc.group(1) if mloc else "United States"
    head = txt[:mloc.start()] if mloc else txt
    head = head.strip()
    # company/title: hard to split generically; use known pattern "Title CompanyName Location"
    jobs.append({"id": jid, "raw": txt, "head": head, "loc": loc.strip(), **meta})
print(f"unique job ids: {len(jobs)}")

# ---- guest API merge ----
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
def guest(q, start=0):
    url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords="
           + urllib.parse.quote(q) + "&location=United%20States&f_TPR=r604800&geoId=103644278&start=" + str(start))
    req = urllib.request.Request(url, headers=UA)
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    out = []
    for card in re.findall(r'<div class="base-card".*?</div>\s*</div>', html, re.S):
        mid = re.search(r"/jobs/view/[^\"']*?(\d{6,})", card)
        mt = re.search(r"<h3[^>]*>\s*(.*?)\s*</h3>", card, re.S)
        mc = re.search(r"<h4[^>]*>\s*(.*?)\s*</h4>", card, re.S)
        ml = re.search(r'job-search-card__location">\s*(.*?)\s*<', card, re.S)
        md = re.search(r'datetime="([^"]+)"', card)
        if mid and mt:
            out.append({"id": mid.group(1), "title": re.sub(r"<[^>]+>", "", mt.group(1)).strip(),
                        "company": re.sub(r"<[^>]+>", "", mc.group(1)).strip() if mc else "",
                        "loc": re.sub(r"<[^>]+>", "", ml.group(1)).strip() if ml else "",
                        "date_posted": md.group(1)[:10] if md else ""})
    return out

import urllib.parse
guest_jobs = []
for q in ["AI engineer", "machine learning engineer", "LLM engineer"]:
    try:
        g = guest(q)
        print(f"guest '{q}': {len(g)}")
        guest_jobs.extend(g)
        time.sleep(1.2)
    except Exception as e:
        print(f"guest '{q}' failed: {e}")

# ---- build normalized candidate rows ----
# For logged-in cards we lack clean title/company; try matching guest ids first.
by_id_guest = {g["id"]: g for g in guest_jobs}
candidates = []
for j in jobs:
    g = by_id_guest.get(j["id"])
    if g:
        candidates.append({"title": g["title"], "company": g["company"], "url": f"https://www.linkedin.com/jobs/view/{j['id']}/",
                           "location": g["loc"] or j["loc"], "source": "linkedin", "source_id": j["id"],
                           "notes_extra": j["conn"], "salary": j["salary"], "date_posted": g.get("date_posted", "")})
    else:
        candidates.append({"title_raw": j["head"], "url": f"https://www.linkedin.com/jobs/view/{j['id']}/",
                           "location": j["loc"], "source": "linkedin", "source_id": j["id"],
                           "notes_extra": j["conn"], "salary": j["salary"]})

json.dump(candidates, open("tracking/search_runs/_cron_candidates_20260824_evening.json", "w"), indent=1)

# dedupe index from canonical csv
rows = list(csv.DictReader(open(JOBS)))
idx = dl.DedupIndex()
for r in rows:
    idx.add(r)

new_rows, dup_ids, unparsed = [], [], []
for cand in candidates:
    if cand.get("title"):
        title, company = cand["title"], cand["company"]
    else:
        unparsed.append(cand)
        continue
    if not title or not company:
        unparsed.append(cand); continue
    row = dl.normalize_job({
        "title": title, "company": company, "url": cand["url"],
        "location": cand["location"], "source": "linkedin", "source_id": cand["source_id"],
        "date_posted": cand.get("date_posted", ""),
        "notes": f"linkedin cron sweep 2026-08-24 evening past-week US"
                 + (f"; {cand['notes_extra']}" if cand.get("notes_extra") else "")
                 + (f"; salary {cand['salary']}" if cand.get("salary") else ""),
    })
    slug = row["job_id"].rsplit("_", 1)[0]  # not used; build explicit
    row["job_id"] = f"{dl.slugify(company)}_{dl.slugify(title)}_{cand['source_id']}"
    is_dup, match = idx.seen_before(row)
    if is_dup:
        dup_ids.append(cand["source_id"])
    else:
        idx.add(row)
        new_rows.append(row)

print(f"\nnew: {len(new_rows)}  dups: {len(dup_ids)}  unparsed(logged-in-only, needs title/company): {len(unparsed)}")
json.dump(unparsed, open("tracking/search_runs/_cron_unparsed_20260824_evening.json", "w"), indent=1)

if new_rows:
    import shutil
    shutil.copy(JOBS, JOBS + ".bak_cron_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    cols = list(csv.reader(open(JOBS)))[0]
    with open(JOBS, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        for r in new_rows:
            w.writerow({k: r.get(k, "") for k in cols})
    with open(RUNS, "a", newline="") as f:
        csv.writer(f).writerow([datetime.datetime.now().isoformat(timespec="seconds"),
                                "linkedin_jobs", "logged-in fetch + guest API, past-week US, 9 queries",
                                len(candidates), len(new_rows), 0, "ok"])

for r in new_rows:
    print("NEW:", r["company"], "|", r["title"], "|", r["location"])
