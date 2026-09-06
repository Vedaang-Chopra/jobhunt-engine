#!/usr/bin/env python3
"""people_sweep — LinkedIn people-discovery sweep pure logic.

Builds search queries across four query families (hiring posts, recruiters,
company people, GT alumni), normalizes found people into a canonical CSV
schema, and enforces the never-twice dedup interlock against contacts.csv and
prior sweep rows. Browser extraction is agent-driven (Playwright MCP); this
module owns the decisions and the ledger.

CSV: tracking/people_sweeps/people_sweep.csv (append-only).
"""
from __future__ import annotations

import csv
import datetime
import difflib
import re
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parents[1]

COLUMNS = [
    "sweep_run_id", "date", "name", "title", "company", "person_type",
    "linkedin_url", "post_url", "why_relevant", "status", "notes",
]

FAMILIES = ["a_hiring_posts", "b_recruiters", "c_company_people", "d_gt_alumni"]

BLOCKED_STATUSES = ("requested", "connected", "contacted", "responded")

# Canonical school used ONLY when the school family is explicitly enabled via
# policy and prefs carry no "school" entry. Never a silent query source.
DEFAULT_SCHOOL = "Georgia Tech"
_SCHOOL_FILTER_IDS = {DEFAULT_SCHOOL.lower(): "16818"}


class PreferencesMissing(RuntimeError):
    """Raised when no config file supplies target companies for the sweep."""

PEOPLE_CSV = config_lib.path("people_sweep_csv")

_SLUG_RE = re.compile(r"linkedin\.com/in/([a-z0-9-]{3,60})")


def linkedin_slug(url: str) -> str:
    """Extract the /in/<slug> handle from a LinkedIn profile URL ('' if none)."""
    m = _SLUG_RE.search(url or "")
    return m.group(1) if m else ""


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def load_preferences(repo: Path | str | None = None) -> dict:
    """Parse role-keyword families + target companies from preference configs.

    ``repo=None`` resolves through ``config_lib.data_root()``; an explicit
    path (tests, ad-hoc roots) is used as-is.
    """
    if repo is None:
        repo = config_lib.data_root()
    repo = Path(repo)
    role_keywords: dict[str, list[str]] = {}
    companies: list[str] = []

    kw_path = repo / "job_research" / "config" / "role-keywords.yaml"
    if kw_path.exists():
        try:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(kw_path.read_text()) or {}
            fams = data.get("role_families", data)
            if isinstance(fams, dict):
                for fam, spec in fams.items():
                    if isinstance(spec, dict):
                        kws = spec.get("primary") or spec.get("keywords") or []
                    else:
                        kws = spec or []
                    if isinstance(kws, list) and kws:
                        role_keywords[str(fam)] = [str(k) for k in kws][:6]
        except Exception:
            pass

    comp_path = repo / "job_research" / "config" / "target-companies.yaml"
    if comp_path.exists():
        try:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(comp_path.read_text()) or {}
            items = data.get("companies", data if isinstance(data, list) else [])
            for item in items:
                if isinstance(item, dict):
                    name = item.get("company") or item.get("name") or ""
                else:
                    name = str(item)
                if name:
                    companies.append(name)
        except Exception:
            pass

    # Role-keyword fallback keeps the sweep usable even if role-keywords.yaml
    # moves; companies have NO fallback — an empty target list is a hard error.
    if not role_keywords:
        role_keywords = {
            "agentic_ai": ["agentic AI", "AI agents"],
            "eval_inference": ["inference", "LLM evaluation"],
            "applied_ml": ["machine learning engineer"],
        }
    if not companies:
        raise PreferencesMissing(
            f"No target companies found: {comp_path} is missing or empty. "
            "Define companies in job_research/config/target-companies.yaml "
            "(no hard-coded fallback)."
        )
    return {"role_keywords": role_keywords, "companies": companies}


def build_queries(prefs: dict, policy: dict | None = None) -> list[dict]:
    """Build one query per (family × company/keyword) with search URLs.

    Family a (hiring posts) rotates across role families; b targets recruiters;
    c targets company people. Family d (school alumni, e.g. GT alumni at each
    company) is OPT-IN via ``policy={"enable_school_family": True}`` — the
    candidate's school must never become a permanent search term by default.
    The school name comes from ``prefs["school"]`` when present, else
    DEFAULT_SCHOOL; it is never hard-coded into query construction here.
    """
    policy = dict(policy or {})
    queries: list[dict] = []
    fam_kws = list(prefs.get("role_keywords", {}).items())
    companies = prefs.get("companies", [])
    school_family_enabled = bool(policy.get("enable_school_family", False))
    school = str(prefs.get("school") or DEFAULT_SCHOOL)

    for fam, kws in fam_kws:
        kw = " OR ".join(kws)
        queries.append({
            "family": "a_hiring_posts",
            "keywords": kw,
            "url": ("https://www.linkedin.com/search/results/content/"
                    f"?keywords={_urlenc(f'({kw}) hiring')}&origin=FACETED_SEARCH"),
        })

    for company in companies:
        inner = f'"talent acquisition" "{company}"'
        queries.append({
            "family": "b_recruiters",
            "keywords": f"talent acquisition {company}",
            "url": ("https://www.linkedin.com/search/results/people/"
                    f"?keywords={_urlenc(inner)}"
                    "&origin=FACETED_SEARCH"),
        })
        inner2 = f'"{company}"'
        queries.append({
            "family": "c_company_people",
            "keywords": company,
            "url": ("https://www.linkedin.com/search/results/people/"
                    f"?keywords={_urlenc(inner2)}"
                    "&origin=FACETED_SEARCH"),
        })
        if school_family_enabled:
            inner3 = f'"{school}" "{company}"'
            # LinkedIn's numeric schoolFilter only exists for known schools;
            # omit it rather than apply the wrong school's filter id.
            filter_param = ""
            filter_id = _SCHOOL_FILTER_IDS.get(school.lower())
            if filter_id:
                filter_param = f"&schoolFilter={filter_id}"
            queries.append({
                "family": "d_gt_alumni",
                "keywords": f"{school} {company}",
                "url": ("https://www.linkedin.com/search/results/people/"
                        f"?keywords={_urlenc(inner3)}{filter_param}"
                        "&origin=FACETED_SEARCH"),
            })
    return queries


def _urlenc(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def _people_url(keywords: str) -> str:
    from urllib.parse import quote

    return ("https://www.linkedin.com/search/results/people/"
            "?keywords=" + quote(keywords, safe="") + "&origin=FACETED_SEARCH")


def cap_queries(queries: list[dict], limit: int) -> list[dict]:
    """Round-robin across families so each batch covers all four."""
    by_fam: dict[str, list[dict]] = {}
    for q in queries:
        by_fam.setdefault(q["family"], []).append(q)
    capped: list[dict] = []
    fams = [f for f in FAMILIES if f in by_fam] + [
        f for f in by_fam if f not in FAMILIES]
    while len(capped) < limit and any(by_fam[f] for f in fams):
        for f in fams:
            if by_fam[f] and len(capped) < limit:
                capped.append(by_fam[f].pop(0))
    return capped


def normalize_person(raw: dict, run_id: str) -> dict:
    """Map an extraction dict onto the canonical COLUMNS schema."""
    name = (raw.get("name") or "").strip()
    if not name:
        raise ValueError("normalize_person requires a non-empty name")
    return {
        "sweep_run_id": run_id,
        "date": datetime.date.today().isoformat(),
        "name": name,
        "title": raw.get("title", ""),
        "company": raw.get("company", ""),
        "person_type": raw.get("person_type", ""),
        "linkedin_url": raw.get("linkedin_url", ""),
        "post_url": raw.get("post_url", ""),
        "why_relevant": raw.get("why_relevant", ""),
        "status": "pending_review",
        "notes": raw.get("notes", ""),
    }


def append_rows(rows: list[dict], out_path: str | Path) -> int:
    """Append normalized rows to the sweep CSV (creating it with schema)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    """Read-only CLI: print the queries this sweep would run (no browsing,
    no writes). The browser extraction itself stays agent-driven."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="print planned searches; no browser, no writes "
                         "(default and only mode)")
    ap.add_argument("--limit", type=int, default=12,
                    help="max queries to print after family capping")
    args = ap.parse_args(argv)

    prefs = load_preferences()
    queries = cap_queries(build_queries(prefs, policy=prefs.get("policy")),
                          max(1, args.limit))
    print(f"people_sweep dry-run: {len(queries)} planned query(ies) "
          f"(companies={len(prefs.get('companies', []))})")
    for q in queries:
        print(f"  [{q.get('family', '?')}] {q.get('keywords', '')}")
        url = q.get("url") or ""
        if url:
            print(f"    {url}")
    print("dry-run: nothing executed. Browser extraction is agent-driven.")
    return 0


class PeopleDedupIndex:
    """Never-twice interlock: slug + fuzzy(name, company) against contacts.csv
    and prior sweep rows. Blocked statuses are suppressed outright."""

    def __init__(self) -> None:
        self._slugs: set[str] = set()
        self._names: list[tuple[str, str, str]] = []  # (norm_name, company, status)
        self._contact_status: dict[str, str] = {}  # norm_name -> outreach_status

    # -- loading ------------------------------------------------------------
    def add_seen(self, slug: str = "", name: str = "", company: str = "",
                 status: str = "") -> None:
        if slug:
            self._slugs.add(slug)
        if name:
            self._names.append((_norm_name(name), company or "", status))

    def load_contacts(self, path: str | Path) -> None:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = row.get("name", "")
                slug = linkedin_slug(row.get("linkedin_url", "") or "")
                status = (row.get("outreach_status") or "").strip().lower()
                self.add_seen(slug=slug, name=name,
                              company=row.get("company", ""), status=status)
                if name:
                    self._contact_status[_norm_name(name)] = status

    def load_prior_rows(self, path: str | Path) -> None:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.add_seen(
                    slug=linkedin_slug(row.get("linkedin_url", "") or ""),
                    name=row.get("name", ""),
                    company=row.get("company", ""),
                    status=(row.get("status") or "").strip().lower())

    # -- lookups ------------------------------------------------------------
    def seen_before(self, linkedin_url: str) -> bool:
        return linkedin_slug(linkedin_url) in self._slugs

    def fuzzy_seen(self, name: str, company: str) -> bool:
        n = _norm_name(name)
        for seen_name, seen_co, _s in self._names:
            if not seen_name:
                continue
            ratio = difflib.SequenceMatcher(None, n, seen_name).ratio()
            same_co = bool(company) and bool(seen_co) and \
                company.strip().lower() == seen_co.strip().lower()
            if ratio >= 0.85 and same_co:
                return True
        return False

    def verdict(self, name: str, company: str, linkedin_url: str = "") -> str:
        """'blocked' (touched before — suppress), 'duplicate' (seen, untouched),
        or 'new'."""
        status = self._contact_status.get(_norm_name(name), "")
        if status in BLOCKED_STATUSES:
            return "blocked"
        if self.fuzzy_seen(name, company):
            return "duplicate"
        if linkedin_url and self.seen_before(linkedin_url):
            return "duplicate"
        for seen_name, seen_co, _s in self._names:
            if _norm_name(name) and _norm_name(name) == seen_name and \
                    (not seen_co or not company or
                     seen_co.lower() == company.lower()):
                return "duplicate"
        return "new"


def merge_extraction(raw_people: list[dict], index: PeopleDedupIndex,
                     run_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify extraction rows -> (accepted, duplicates, blocked)."""
    accepted: list[dict] = []
    dups: list[dict] = []
    blocked: list[dict] = []
    for raw in raw_people:
        try:
            row = normalize_person(raw, run_id)
        except ValueError:
            continue
        v = index.verdict(name=row["name"], company=row["company"],
                          linkedin_url=row["linkedin_url"])
        if v == "new":
            accepted.append(row)
            index.add_seen(slug=linkedin_slug(row["linkedin_url"]),
                           name=row["name"], company=row["company"])
        elif v == "blocked":
            blocked.append(row)
        else:
            dups.append(row)
    return accepted, dups, blocked


if __name__ == "__main__":
    raise SystemExit(main())
