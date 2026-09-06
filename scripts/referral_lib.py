"""Company registry library (Task 8).

Builds and maintains tracking/companies/companies_registry.csv from
tracking/jobs/jobs.csv and tracking/contacts/contacts.csv.
"""

import csv
import datetime
import json
import os
from datetime import date
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parents[1]

REGISTRY_COLUMNS = [
    "company_slug", "company", "careers_url", "ats_platform",
    "email_pattern", "email_pattern_status", "email_pattern_source",
    "jobs_open_count", "top_job_ids", "contacts_count", "contacts_by_type",
    "referral_coverage", "status", "last_updated", "notes",
]
REGISTRY_HEADER = REGISTRY_COLUMNS

DEFAULT_REGISTRY_PATH = config_lib.path("companies_registry")
DEFAULT_JOBS_PATH = config_lib.path("jobs_csv")
DEFAULT_CONTACTS_PATH = config_lib.path("contacts_csv")

TOP_JOBS_CAP = 5


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _slug(value):
    value = (value or "").strip().lower()
    out = []
    for ch in value:
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_")


def _new_row(slug, company, today=None):
    today = today or datetime.date.today().isoformat()
    return {
        "company_slug": slug,
        "company": company,
        "careers_url": "",
        "ats_platform": "",
        "email_pattern": "",
        "email_pattern_status": "unknown",
        "email_pattern_source": "",
        "jobs_open_count": "0",
        "top_job_ids": "",
        "contacts_count": "0",
        "contacts_by_type": "{}",
        "referral_coverage": "none",
        "status": "active",
        "last_updated": today,
        "notes": "",
    }


def seed_registry(jobs_path=None, contacts_path=None, registry_path=None,
                  today=None):
    """Build one registry row per distinct OPEN company in jobs_path."""
    jobs = _read_csv(jobs_path or DEFAULT_JOBS_PATH)
    contacts = _read_csv(contacts_path or DEFAULT_CONTACTS_PATH)

    # contacts keyed by slug; fall back to slugified company name
    by_slug = {}
    for c in contacts:
        slug = (c.get("company_slug") or "").strip() or _slug(c.get("company"))
        rel = (c.get("relationship") or "").strip()
        entry = by_slug.setdefault(slug, {"count": 0, "types": {}})
        entry["count"] += 1
        if rel:
            entry["types"][rel] = entry["types"].get(rel, 0) + 1

    companies = {}  # slug -> row
    for j in jobs:
        status = (j.get("status") or "").strip().lower()
        if status != "open":
            continue
        slug = (j.get("company_slug") or "").strip()
        if not slug:
            continue
        try:
            priority = float(j.get("priority_v2") or 0.0)
        except ValueError:
            priority = 0.0
        try:
            fit = float(j.get("fit_score") or 0.0)
        except ValueError:
            fit = 0.0
        row = companies.get(slug)
        if row is None:
            row = _new_row(slug, j.get("company") or slug, today=today)
            companies[slug] = row
        row["jobs_open_count"] = str(int(row["jobs_open_count"]) + 1)
        row.setdefault("_ranked", []).append((priority, fit, j.get("job_id", "")))
        if not row["company"]:
            row["company"] = j.get("company") or slug

    rows = []
    for slug, row in companies.items():
        ranked = sorted(row.pop("_ranked"), key=lambda t: (-t[0], -t[1], t[2]))
        top = [jid for _, _, jid in ranked[:TOP_JOBS_CAP] if jid]
        row["top_job_ids"] = ";".join(top)
        info = by_slug.get(slug, {"count": 0, "types": {}})
        row["contacts_count"] = str(info["count"])
        row["contacts_by_type"] = json.dumps(info["types"], sort_keys=True)
        if info["count"] == 0:
            row["referral_coverage"] = "none"
        elif info["types"].get("1st"):
            row["referral_coverage"] = "strong"
        else:
            row["referral_coverage"] = "weak"
        rows.append(row)

    rows.sort(key=lambda r: r["company_slug"])
    if registry_path:
        write_registry(rows, registry_path)
    return rows


def write_registry(rows, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTRY_COLUMNS)
        writer.writeheader()
        known = set(REGISTRY_COLUMNS)
        for r in rows:
            writer.writerow({k: v for k, v in r.items() if k in known})


def read_registry(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def _ensure_registry(registry_path, jobs_path=None, contacts_path=None):
    """Load the registry file, seeding it from defaults when missing."""
    if not os.path.exists(registry_path):
        seed_registry(jobs_path=jobs_path, contacts_path=contacts_path,
                      registry_path=registry_path)
    rows, fields = read_registry(registry_path)
    return rows, fields


def registry_row_for(company_slug, registry_path=None, jobs_path=None,
                     contacts_path=None):
    """Return the registry row dict for a slug, or None."""
    path = str(registry_path or DEFAULT_REGISTRY_PATH)
    rows, _ = _ensure_registry(path, jobs_path=jobs_path,
                               contacts_path=contacts_path)
    for r in rows:
        if r.get("company_slug") == company_slug:
            return dict(r)
    return None


def update_company_row(company_slug, updates, registry_path=None,
                       touch_timestamp=True):
    """Merge `updates` into a row; unknown columns are preserved.

    Unknown field *names* in `updates` are rejected (returns False).
    A value of None means "do not change this column".
    """
    path = str(registry_path or DEFAULT_REGISTRY_PATH)
    if not os.path.exists(path):
        return False
    rows, fields = read_registry(path)

    target = next((r for r in rows if r.get("company_slug") == company_slug),
                  None)
    if target is None:
        return False

    valid = set(fields)
    for key, value in updates.items():
        if key not in valid:
            return False

    for key, value in updates.items():
        if value is None:
            continue  # preserve existing value
        target[key] = value
    if touch_timestamp and "last_updated" in valid:
        target["last_updated"] = datetime.date.today().isoformat()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return True


if __name__ == "__main__":
    seeded = seed_registry(registry_path=str(DEFAULT_REGISTRY_PATH))
    print(f"wrote {len(seeded)} rows to {DEFAULT_REGISTRY_PATH}")


# ---------------------------------------------------------------------------
# Task 9: contact discovery — ranked people per company.
# ---------------------------------------------------------------------------

DEFAULT_POSTS_PATH = config_lib.path("hiring_posts_csv")

# Scoring weights (trust-ordered evidence).
SCORE_HM_POSTER = 30
SCORE_RECRUITER = 25
SCORE_ENGINEER = 15
SCORE_FIRST_DEGREE = 40
SCORE_GT_ALUMNI = 10
SCORE_SHARED_CONTEXT = 10
SCORE_JOB_FRESH = 10
FRESH_DAYS = 7

# Contacts with these outreach statuses must never surface again.
BLOCKED_STATUSES = {"requested", "connected", "contacted", "responded"}

GT_TOKENS = ("georgia tech", "georgia institute of technology", "gatech")


def resolve_company_slug(query, registry_path=None):
    """Resolve a user-supplied slug or company name to a canonical slug."""
    rows, _ = _ensure_registry(str(registry_path or DEFAULT_REGISTRY_PATH))
    q = _slug(query)
    for r in rows:
        if r.get("company_slug", "").strip() == q:
            return r.get("company_slug").strip()
    for r in rows:
        if _slug(r.get("company")) == q:
            return r.get("company_slug").strip()
    # fuzzy: containment either direction (e.g. "ACME Corp" -> acme)
    for r in rows:
        rs = r.get("company_slug", "").strip()
        if rs and (rs.startswith(q) or q.startswith(rs)):
            return rs
    return None


def _norm_name(value):
    return " ".join((value or "").lower().replace(".", " ").split())


def linkedin_slug(url):
    """Extract the LinkedIn profile slug from a URL, or ''. """
    url = (url or "").strip().lower()
    if "linkedin.com/in/" not in url:
        return ""
    tail = url.split("linkedin.com/in/", 1)[1]
    for ch in "/?#":
        tail = tail.split(ch, 1)[0]
    return tail.strip("/-")


def _fuzzy_same(a_name, a_co, b_name, b_co):
    na, nb = _norm_name(a_name), _norm_name(b_name)
    if not na or na != nb:
        return False
    ca, cb = _slug(a_co), _slug(b_co)
    if not ca or not cb:
        return False
    return ca == cb or ca in cb or cb in ca


def score_candidate(cand, today=None):
    """Score one candidate dict from evidence fields only."""
    today = today or date.today()
    score = 0
    ptype = (cand.get("poster_type") or "").strip().lower()
    if ptype == "hiring_manager":
        score += SCORE_HM_POSTER
    elif ptype == "recruiter":
        score += SCORE_RECRUITER
    elif ptype == "engineer_researcher":
        score += SCORE_ENGINEER
    rel = (cand.get("relationship") or "").strip().lower()
    if rel == "1st":
        score += SCORE_FIRST_DEGREE
    if cand.get("gt_alumni"):
        score += SCORE_GT_ALUMNI
    if (cand.get("shared_context") or "").strip():
        score += SCORE_SHARED_CONTEXT
    posted = (cand.get("posted_date") or "").strip()
    if posted:
        try:
            age = (today - date.fromisoformat(posted[:10])).days
            if 0 <= age < FRESH_DAYS:
                score += SCORE_JOB_FRESH
        except ValueError:
            pass
    return score


def compose_reason(cand):
    """Auto-compose reason_to_contact strictly from recorded evidence."""
    parts = []
    source = (cand.get("source") or "").strip()
    ptype = (cand.get("poster_type") or "").strip().lower()
    role = (cand.get("role") or "").strip()
    headline = (cand.get("headline") or "").strip()
    if source == "hiring_posts":
        kind = {"hiring_manager": "posted a hiring post",
                "recruiter": "recruiter who posted a hiring post",
                "engineer_researcher":
                    "engineer/researcher who posted a hiring post"}.get(
                    ptype, "posted a hiring post")
        parts.append(f"{kind} for this company")
        if cand.get("post_url"):
            parts.append("hiring post on file")
    elif source == "contacts":
        parts.append(f"already tracked in contacts ({role or 'role on file'})"
                     if role else "already tracked in contacts")
    elif source == "linkedin":
        parts.append(f"LinkedIn people search match"
                     + (f" ({role})" if role else ""))
    elif source == "web_search":
        parts.append("public web search hit"
                     + (f" ({role})" if role else ""))
    rel = (cand.get("relationship") or "").strip().lower()
    if rel == "1st":
        parts.append("1st-degree connection")
    elif rel:
        parts.append(f"{rel}-degree connection")
    if headline and headline not in role and ptype != "hiring_manager":
        parts.append(f"headline: {headline}")
    ctx = (cand.get("shared_context") or "").strip()
    if ctx:
        parts.append(f"shared context: {ctx}")
    if cand.get("gt_alumni"):
        parts.append("Georgia Tech affiliation")
    if cand.get("posted_date"):
        parts.append(f"posted {cand['posted_date'][:10]}")
    return "; ".join(parts) or f"{cand.get('name', '')} at {cand.get('company', '')}"


def _merge_into(target, other):
    """Fold `other`'s evidence into `target` (keep richest values)."""
    for key in ("relationship", "linkedin_url", "shared_context", "role",
                "headline", "posted_date", "post_url"):
        if not (target.get(key) or "").strip() and (other.get(key) or "").strip():
            target[key] = other[key]
    if (other.get("relationship") or "").strip().lower() == "1st":
        target["relationship"] = "1st"
    for src in ("hiring_posts", "linkedin", "contacts", "web_search"):
        if other.get("source") == src:
            target["source"] = src  # trust order: later writes only if earlier
    # enforce trust order explicitly
    order = ["hiring_posts", "contacts", "linkedin", "web_search"]
    if other.get("source") in order and target.get("source") in order:
        if order.index(other["source"]) < order.index(target["source"]):
            target["source"] = other["source"]
            target["poster_type"] = other.get("poster_type", "")
    if other.get("gt_alumni"):
        target["gt_alumni"] = True
    target.setdefault("evidence", []).extend(other.get("evidence", []))
    return target


def dedup_candidates(cands):
    """Merge duplicates by LinkedIn slug, then fuzzy(name+company)."""
    out = []
    by_slug = {}
    for c in cands:
        slug = linkedin_slug(c.get("linkedin_url"))
        if slug and slug in by_slug:
            _merge_into(by_slug[slug], c)
            continue
        match = None
        for t in out:
            if _fuzzy_same(t.get("name"), t.get("company"),
                           c.get("name"), c.get("company")):
                match = t
                break
        if match is not None:
            _merge_into(match, c)
            if slug:
                by_slug[slug] = match
            continue
        c = dict(c)
        c.setdefault("evidence", [])
        out.append(c)
        if slug:
            by_slug[slug] = c
    return out


def _company_matches(row, slug, company_name):
    row_co = (row.get("company") or "").strip()
    return _slug(row_co) == _slug(slug) or _slug(row_co) == _slug(company_name)


def _posters_for(slug, company_name, posts_path, today):
    out = []
    for row in _read_csv(posts_path or DEFAULT_POSTS_PATH):
        if not _company_matches(row, slug, company_name):
            continue
        name = (row.get("poster_name") or "").strip()
        if not name:
            continue
        ctx = (row.get("shared_context") or "").strip()
        out.append({
            "name": name,
            "company": row.get("company") or company_name,
            "source": "hiring_posts",
            "poster_type": (row.get("poster_type") or "").strip().lower(),
            "headline": (row.get("poster_headline") or "").strip(),
            "linkedin_url": (row.get("post_url") or "").strip()
            if "linkedin.com/in/" in (row.get("post_url") or "") else "",
            "post_url": (row.get("post_url") or "").strip(),
            "posted_date": (row.get("posted_date") or "").strip(),
            "shared_context": ctx,
            "gt_alumni": any(t in ctx.lower() or
                             t in (row.get("poster_headline") or "").lower()
                             for t in GT_TOKENS),
            "evidence": [f"hiring post {row.get('post_id', '')}".strip()],
        })
    return out


def _contacts_for(slug, company_name, contacts_path):
    out = []
    for row in _read_csv(contacts_path or DEFAULT_CONTACTS_PATH):
        if not _company_matches(row, slug, company_name):
            continue
        status = (row.get("outreach_status") or "").strip().lower()
        if status in BLOCKED_STATUSES:
            continue  # dedup guard: never re-surface contacted people
        ctx = (row.get("shared_context") or "").strip()
        rel = (row.get("relationship") or "").strip()
        out.append({
            "name": (row.get("name") or "").strip(),
            "company": row.get("company") or company_name,
            "source": "contacts",
            "poster_type": "",
            "role": (row.get("role") or "").strip(),
            "relationship": rel,
            "linkedin_url": (row.get("linkedin_url") or "").strip(),
            "shared_context": ctx,
            "gt_alumni": any(t in ctx.lower() or
                             t in (row.get("role") or "").lower()
                             for t in GT_TOKENS),
            "outreach_status": status,
            "evidence": [f"contacts row {row.get('contact_id', '')}".strip()],
        })
    return out


def _linkedin_search_candidates(company_name, queries, browser_fn=None):
    """Source 3: Playwright MCP LinkedIn people search (optional, live)."""
    if browser_fn is None:
        return []
    out = []
    for kind, query in queries:
        try:
            people = browser_fn(query) or []
        except Exception:
            continue
        for p in people:
            out.append({
                "name": p.get("name", ""),
                "company": p.get("company") or company_name,
                "source": "linkedin",
                "poster_type": "recruiter" if kind == "recruiter" else "",
                "role": p.get("role", ""),
                "relationship": p.get("relationship", ""),
                "linkedin_url": p.get("linkedin_url", ""),
                "shared_context": p.get("shared_context", ""),
                "evidence": [f"LinkedIn search: {query}"],
            })
    return out


def _web_search_candidates(company_name, web_search_fn, role_keywords=""):
    """Source 4: fallback web search for recruiters/talent at company."""
    if web_search_fn is None:
        return []
    out = []
    queries = [f"talent acquisition {company_name} LinkedIn recruiter"]
    if role_keywords:
        queries.append(f"{role_keywords} {company_name} LinkedIn")
    for query in queries:
        try:
            hits = web_search_fn(query) or []
        except Exception:
            continue
        for h in hits:
            name = (h.get("name") or "").strip()
            if not name:
                continue
            out.append({
                "name": name,
                "company": h.get("company") or company_name,
                "source": "web_search",
                "poster_type": "recruiter"
                if "talent acquisition" in query.lower() else "",
                "role": h.get("role", ""),
                "linkedin_url": h.get("linkedin_url", ""),
                "shared_context": h.get("shared_context", ""),
                "evidence": list(h.get("evidence") or
                                 [f"web search: {query}"]),
            })
    return out


def discover_contacts(company_query, registry_path=None, posts_path=None,
                      contacts_path=None, live_linkedin=False,
                      browser_fn=None, web_search_fn=None,
                      role_keywords="", top=None, today=None):
    """Ranked contact candidates for one company.

    Sources merged in trust order: hiring-post posters, existing contacts,
    live LinkedIn (only when live_linkedin and browser_fn provided),
    fallback web search. Returns a list sorted by descending score.
    """
    today = today or date.today()
    slug = resolve_company_slug(company_query, registry_path=registry_path)
    if not slug:
        return []
    row = registry_row_for(slug, registry_path=registry_path)
    company_name = row.get("company") or slug

    merged = []
    merged += _posters_for(slug, company_name, posts_path, today)
    merged += _contacts_for(slug, company_name, contacts_path)
    if live_linkedin and browser_fn is not None:
        queries = [
            ("recruiter", f"talent acquisition {company_name}"),
            ("team", f"{role_keywords} {company_name}".strip()),
            ("gt", f"Georgia Tech {company_name}"),
        ]
        merged += _linkedin_search_candidates(company_name, queries,
                                              browser_fn=browser_fn)
    merged += _web_search_candidates(company_name, web_search_fn,
                                     role_keywords=role_keywords)

    # Dedup guard against re-surfacing already-contacted people: even when a
    # person enters via another source (e.g. a fresh hiring post), suppress
    # them if their contact row shows outreach already made.
    blocked_names = []
    blocked_slugs = set()
    for row in _read_csv(contacts_path or DEFAULT_CONTACTS_PATH):
        status = (row.get("outreach_status") or "").strip().lower()
        if status in BLOCKED_STATUSES:
            blocked_names.append(((row.get("name") or "").strip(),
                                  (row.get("company") or "").strip()))
            s = linkedin_slug(row.get("linkedin_url"))
            if s:
                blocked_slugs.add(s)

    def _is_blocked(c):
        s = linkedin_slug(c.get("linkedin_url"))
        if s and s in blocked_slugs:
            return True
        return any(_fuzzy_same(c.get("name"), c.get("company"), bn, bc)
                   for bn, bc in blocked_names)

    deduped = [c for c in dedup_candidates(merged) if not _is_blocked(c)]
    # Guard again post-merge: a merge could re-attach a blocked person's data
    # only if the blocked row itself was the survivor — blocked rows never
    # enter `merged`, so survivors are safe by construction.
    ranked = []
    for c in deduped:
        if not (c.get("name") or "").strip():
            continue
        c["score"] = score_candidate(c, today=today)
        if not (c.get("reason_to_contact") or "").strip():
            c["reason_to_contact"] = compose_reason(c)
        ranked.append(c)
    ranked.sort(key=lambda c: (-c["score"], c["name"]))
    if top:
        ranked = ranked[: int(top)]
    return ranked
