"""Core normalization helpers for the job-discovery pipeline (Task 1).

CSV-only persistence; ISO 8601 dates. Column names mirror
tracking/jobs/jobs.csv.
"""

from __future__ import annotations

import re
import datetime
from urllib.parse import urlparse

ATS_PATTERNS = {
    "greenhouse": re.compile(r"boards\.greenhouse\.io/[^/]+/jobs/(\d+)"),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/[^/]+/([^/?#]+)"),
    "lever": re.compile(r"jobs\.lever\.co/[^/]+/([^/?#]+)"),
}

_CSV_COLUMNS = [
    "job_id", "company", "title", "location", "job_url",
    "canonical_application_url", "source", "date_discovered", "date_posted",
    "date_updated", "status", "fit_score", "fit_tier", "role_family",
    "seniority", "key_requirements", "matching_strengths", "main_gaps",
    "resume_variant", "networking_priority", "application_priority",
    "last_checked", "notes", "full_description_hash", "description_file",
    "is_medical_false_positive", "company_slug", "source_id", "stale_flag",
    "last_verified", "merged_from", "opportunity_level", "recommended_action",
    "priority_v2", "score_explanation", "score_confidence", "missing_info",
    "override_reason", "last_scored",
    "ats_score", "keyword_match_score", "keyword_matched", "keyword_missing",
    "ats_issues", "last_ats_check",
    # UI-maintained columns (add-only evolution):
    # review_flag — /jobs dialog triage flag (ui/data.set_job_review_flag);
    # application_status — mirror of the linked application's engine status
    # (ui/data.sync_job_application_status).
    "review_flag", "application_status",
]


def slugify(name: str) -> str:
    """Lowercase, strip, and join words with underscores."""
    return "_".join(
        w for w in re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).split("_") if w
    )


def extract_ats_id(url: str) -> str | None:
    """Extract the ATS posting ID from a greenhouse/ashby/lever URL."""
    for pattern in ATS_PATTERNS.values():
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None


def detect_source(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for source in ATS_PATTERNS:
        if source in host:
            return source
    return None


# Host-based rules for the full controlled `source` vocabulary
# (tracking/jobs/SCHEMA.md). Matching is on the URL host, suffix-style:
# host equals the domain or ends with "." + domain.
SOURCE_HOST_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("greenhouse", ("greenhouse.io",)),
    ("ashby", ("ashbyhq.com",)),
    ("lever", ("lever.co",)),
    ("workday", ("myworkdayjobs.com", "myworkdaysite.com")),
    ("oracle_hcm", ("oraclecloud.com",)),
    ("wellfound", ("wellfound.com", "angel.co")),
    ("linkedin", ("linkedin.com",)),
]


def _host_matches(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def normalize_source(url: str, fallback: str = "") -> str:
    """Map a job/careers URL onto the controlled ``source`` vocabulary.

    Returns one of: greenhouse, lever, ashby, workday, oracle_hcm,
    wellfound, linkedin — derived from the URL host. When nothing matches
    (or ``url`` is empty), returns ``fallback``; callers pass "company_page"
    for direct company career-site URLs and "other" as the last resort.
    Every jobs.csv writer must set ``source`` through this helper whenever
    the value would otherwise be blank/unknown.
    """
    url = (url or "").strip()
    if not url:
        return fallback
    candidate = url if "://" in url else f"https://{url}"
    host = urlparse(candidate).netloc.lower().strip()
    if not host:
        return fallback
    for source, domains in SOURCE_HOST_RULES:
        if _host_matches(host, domains):
            return source
    return fallback


def normalize_job(raw: dict) -> dict:
    """Normalize a raw job dict into a row matching tracking/jobs/jobs.csv columns.

    Required keys: title, company, url. Fills defaults: status=open,
    date_discovered=today (ISO 8601).
    """
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title:
        raise ValueError("title is required")
    if not company:
        raise ValueError("company is required")
    if not url:
        raise ValueError("url is required")

    today = datetime.date.today().isoformat()

    def _date(key: str) -> str:
        val = (raw.get(key) or "").strip()
        if not val:
            return ""
        return datetime.date.fromisoformat(val[:10]).isoformat()

    defaults = {
        "job_id": "",
        "company": company,
        "title": title,
        "location": "",
        "job_url": url,
        "canonical_application_url": url,
        "source": "",
        "source_id": "",
        "date_discovered": today,
        "date_posted": "",
        "date_updated": "",
        "status": "open",
        "fit_score": "",
        "fit_tier": "",
        "role_family": "",
        "seniority": "",
        "key_requirements": "",
        "matching_strengths": "",
        "main_gaps": "",
        "resume_variant": "",
        "networking_priority": "",
        "application_priority": "",
        "last_checked": "",
        "notes": "",
        "full_description_hash": "",
        "description_file": "",
        "is_medical_false_positive": "",
        "company_slug": slugify(company),
        "stale_flag": "",
        "last_verified": "",
        "merged_from": "",
        "opportunity_level": "",
        "recommended_action": "",
        "priority_v2": "",
        "score_explanation": "",
        "score_confidence": "",
        "missing_info": "",
        "override_reason": "",
        "last_scored": "",
    }
    derived = {
        "source": detect_source(url),
        "source_id": extract_ats_id(url),
        "canonical_application_url": raw.get("canonical_application_url"),
    }
    row = {k: "" for k in _CSV_COLUMNS}
    row.update(defaults)
    for key, value in derived.items():
        if value:
            row[key] = value
    # Caller-supplied values win over defaults (but not over validation).
    for key, value in raw.items():
        if key in row and key not in ("title", "company", "url"):
            if isinstance(value, str):
                value = value.strip() or row[key]
            if value not in (None, ""):
                row[key] = value
    return row


# ---------------- Task 2: prefix-proof cross-source dedup ----------------

SOURCE_ID_PREFIXES = ("gh_", "ashby_", "lever_")


def strip_source_prefix(source_id: str) -> str:
    """Reduce gh_/ashby_/ash_<board>_ prefixed source ids to the raw ATS id."""
    sid = (source_id or "").strip()
    for prefix in SOURCE_ID_PREFIXES:
        if sid.startswith(prefix):
            return sid[len(prefix):]
    if sid.startswith("ash_"):
        # ash_<board>_<id> — drop board segment (greenhouse ids are numeric,
        # ashby ids use hyphens, so a single underscore split is safe)
        parts = sid.split("_", 2)
        if len(parts) == 3:
            return parts[2]
    return sid


def normalize_url(url: str) -> str:
    """Canonical URL form: lowercase host, no query/fragment, no trailing slash."""
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}{path}"


def _title_similarity(a: str, b: str) -> float:
    """Jaccard similarity over normalized title word sets."""
    ta = set(re.findall(r"[a-z0-9]+", (a or "").lower()))
    tb = set(re.findall(r"[a-z0-9]+", (b or "").lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _parse_date(value):
    try:
        return datetime.date.fromisoformat((value or "")[:10])
    except (ValueError, TypeError):
        return None


class DedupIndex:
    """Prefix-proof dedup index over job rows.

    Match order:
      1. normalized URL
      2. (company_slug, ats_id) pair with prefix variants stripped
      3. fuzzy title+company within 45 days of an existing row
         (normalized title similarity >= 0.85)
    """

    FUZZY_THRESHOLD = 0.85
    WINDOW_DAYS = 45

    def __init__(self) -> None:
        self.rows = []
        self._by_url = {}
        self._by_pair = {}

    def add(self, row: dict) -> None:
        row = dict(row)
        row["company_slug"] = row.get("company_slug") or slugify(row.get("company", ""))
        ats_id = extract_ats_id(row.get("job_url") or row.get("url") or "")
        row["_ats_id"] = strip_source_prefix(row.get("source_id")) or ats_id
        self.rows.append(row)
        nu = normalize_url(row.get("job_url") or row.get("url") or "")
        if nu:
            self._by_url.setdefault(nu, row)
        pair = (row["company_slug"], row["_ats_id"])
        if pair[1]:
            self._by_pair.setdefault(pair, row)

    def seen_before(self, row: dict):
        """Return (is_duplicate, matched_row_or_None)."""
        company_slug = row.get("company_slug") or slugify(row.get("company", ""))
        url = row.get("job_url") or row.get("url") or ""
        nu = normalize_url(url)

        # 1. normalized URL
        if nu and nu in self._by_url:
            return True, self._by_url[nu]

        # 2. (company_slug, ats_id) pair
        ats_id = extract_ats_id(url)
        cand_id = strip_source_prefix(row.get("source_id")) or ats_id
        if cand_id and company_slug:
            for cid in {cand_id, ats_id}:
                if not cid:
                    continue
                hit = self._by_pair.get((company_slug, cid))
                if hit is not None:
                    return True, hit

        # 3. fuzzy title+company within 45 days
        date_new = _parse_date(row.get("date_discovered"))
        title = row.get("title", "")
        if title and company_slug and date_new is not None:
            for existing in self.rows:
                if existing["company_slug"] != company_slug:
                    continue
                date_old = _parse_date(existing.get("date_discovered"))
                if date_old is None:
                    continue
                if abs((date_new - date_old).days) > self.WINDOW_DAYS:
                    continue
                sim = _title_similarity(title, existing.get("title", ""))
                if sim >= self.FUZZY_THRESHOLD:
                    return True, existing
        return False, None


# ---------------- Task 3: scrutiny gate ----------------

_SUPPORTED_CITIES = (
    "san francisco",
    "sf",
    "new york",
    "nyc",
    "seattle",
    "boston",
    "atlanta",
)

_SENIOR_BAR_RE = re.compile(
    r"\b(staff|principal|director|vp|manager)\b", re.IGNORECASE
)

# US state names + two-letter codes, so e.g. "Austin, TX" or "Denver,
# Colorado" pass the location gate without being on the metro list.
_US_STATE_RE = re.compile(
    r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|"
    r"delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|"
    r"kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    r"mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|"
    r"new mexico|new york state|north carolina|north dakota|ohio|oklahoma|"
    r"oregon|pennsylvania|rhode island|south carolina|south dakota|"
    r"tennessee|texas|utah|vermont|virginia|washington state|west virginia|"
    r"wisconsin|wyoming|"
    r"al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|"
    r"ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|"
    r"wa|wv|wi|wy)\b(?![-\w])",
    re.IGNORECASE,
)

# India exception: only "very good" jobs pass. Very good = APPLY tier
# (priority_v2 >= 68) or an explicit exceptional=True mark from review.
_INDIA_MIN_PRIORITY = 68
_YEARS_RE = re.compile(r"(\d+)\+?\s*(?:-|to\s+)?\s*years?\b", re.IGNORECASE)
_INTERNSHIP_RE = re.compile(r"\bintern(ship)?\b", re.IGNORECASE)
_CONVERSION_RE = re.compile(
    r"full[- ]time conversion|return offer|conversion to full[- ]time|"
    r"convert(s|ion)? (?:to )?(?:a )?full[- ]time|full-time offer",
    re.IGNORECASE,
)


def _location_supported(location: str) -> bool:
    loc = (location or "").lower()
    if any(city in loc for city in _SUPPORTED_CITIES):
        return True
    # Anywhere in the United States: state codes, "US/USA/United States",
    # "Remote - US". US-wide, not just the approved metro list.
    if re.search(r"\b(us|usa|u\.s\.|united states)\b", loc):
        return True
    if _US_STATE_RE.search(loc):
        return True
    # Remote - US / United States remote
    return bool(re.search(r"\bremote\b", loc)) and (
        re.search(r"\b(us|usa|u\.s\.|united states)\b", loc) is not None
    )


def _is_india(location: str) -> bool:
    return "india" in (location or "").lower()


def scrutinize(row: dict) -> tuple[str, list[str]]:
    """Scrutiny gate: return ('accept'|'reject', [machine-readable flags])."""
    title = row.get("title") or ""
    desc = row.get("description") or ""
    location = row.get("location") or ""
    verdict = "accept"
    flags: list[str] = []

    # Location gate: US-wide allowed; India only for very good jobs;
    # every other country (UK, Canada, EU, ...) hard-rejected.
    if not _location_supported(location):
        if _is_india(location):
            try:
                priority = float(row.get("priority_v2") or 0)
            except (TypeError, ValueError):
                priority = 0.0
            very_good = row.get("exceptional") or priority >= _INDIA_MIN_PRIORITY
            if very_good:
                flags.append("india_exceptional")
            else:
                verdict = "reject"
                flags.append("india_below_exceptional")
        else:
            verdict = "reject"
            flags.append("location_not_supported")

    # Seniority gate
    years_match = _YEARS_RE.search(desc)
    years = int(years_match.group(1)) if years_match else None
    if years is not None and 5 <= years <= 8:
        flags.append("senior_soft")
    elif years is not None and years >= 9:
        verdict = "reject"
        flags.append("seniority_bar")
    if _SENIOR_BAR_RE.search(title):
        verdict = "reject"
        flags.append("seniority_bar")
    elif re.search(r"\bsenior\b", title, re.IGNORECASE):
        flags.append("senior_soft")

    # Internship gate
    if _INTERNSHIP_RE.search(title) or _INTERNSHIP_RE.search(desc):
        if not _CONVERSION_RE.search(desc):
            verdict = "reject"
            flags.append("internship_no_conversion")

    # Advisory flags
    if len(desc) < 500:
        flags.append("thin_jd")

    posted = _parse_date(row.get("date_posted"))
    if posted and (datetime.date.today() - posted).days > 90:
        flags.append("stale_risk")

    return verdict, flags
