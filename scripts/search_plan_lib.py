"""Filter-first LinkedIn search plan builder (right-people feature, Task 3).

Rule 08 (BROWSER_AND_TOOLS) / rule 05 (LINKEDIN_REFERRALS): never bare keyword
search. Every pass pins a native people-search filter — connection degree,
current company, location, school filter — and the keywords facet is only ever
used ON TOP of a pinned company filter. URL params mirror UI filters only.

Pure logic; no browser, no I/O. See tests/test_search_plan_lib.py.
"""

from __future__ import annotations

from urllib.parse import urlencode

GT_SCHOOL_FILTER_ID = "16818"

PEOPLE_SEARCH_URL = "https://www.linkedin.com/search/results/people/"
CONTENT_SEARCH_URL = "https://www.linkedin.com/search/results/content/"

# degree -> LinkedIn network mirror value (S=1st, O=2nd, A=3rd)
DEGREE_MIRRORS = {"1st": "S", "2nd": "O", "3rd": "A"}

LOCATION_FILTER = ["United States", "Remote-US"]  # geography rule: US + Remote-US

DEFAULT_TEAM_KEYWORDS = ["ML Engineer", "Applied Scientist", "Research Engineer"]
DEFAULT_MANAGER_ROLES = ["Manager", "Lead", "Director"]
DEFAULT_DOMAIN_TERMS = ["AI"]
DEFAULT_RECRUITER_ROLES = ["Recruiter", "Talent", "Recruiting"]
RECRUITER_DOMAIN_TERMS = ["AI", "ML", "Engineering"]
DEFAULT_UNIVERSITY_KEYWORDS = ["University", "Campus", "Early Career"]

HIRING_POST_PHRASES = ['"we\'re hiring"', '"refer my"']
HIRING_POST_DATE = "past_month"  # date-posted <= 30d


def _keyword_or(terms):
    """Join facet terms with OR the way LinkedIn's keyword facet mirrors them."""
    return " OR ".join(terms)


def _kw(hints_key, defaults, hints):
    if hints and hints.get(hints_key):
        return list(hints[hints_key])
    return list(defaults)


def _mirror(value):
    """Wrap a single select-filter value the way LinkedIn URL mirrors do."""
    return '["%s"]' % value


def _people_url(params):
    return PEOPLE_SEARCH_URL + "?" + urlencode(params)


def _content_url(params):
    return CONTENT_SEARCH_URL + "?" + urlencode(params)


def build_search_plan(target: dict, hints: dict | None = None, limit_hint: int = 15) -> list[dict]:
    """Build the ordered filter-first search plan for a company/job target.

    target = {"company": str, "company_slug": str, "kind": "company"|"job",
              "job": {...}|None}
    hints  = {"keywords": [...], "domain_terms": [...]} from jd_hints_lib
             (job mode only; injected into team/hiring-manager/recruiter passes).
    """
    company = target["company"]
    slug = target["company_slug"]
    plan = []

    def add(pass_id, family, tier, url, filters):
        plan.append(
            {
                "pass_id": pass_id,
                "family": family,
                "tier": tier,
                "url": url,
                "filters": filters,
                "verify": "chips+result_count",
                "limit": limit_hint,
            }
        )

    # --- Passes 1-3: existing connections by degree (company + degree + location) ---
    for idx, degree in enumerate(("1st", "2nd", "3rd"), start=1):
        filters = {
            "current_company": company,
            "network": [degree],
            "location": list(LOCATION_FILTER),
        }
        url = _people_url(
            {
                "network": _mirror(DEGREE_MIRRORS[degree]),
                "currentCompany": _mirror(slug),
                "geoU": _mirror("us"),
            }
        )
        add("%02d_existing_%s" % (idx, degree), "existing_%s" % degree, degree, url, filters)

    # --- Pass 4: hiring posts (company content search, date + content type) ---
    hp_filters = {
        "company": slug,
        "keywords": _keyword_or(HIRING_POST_PHRASES),
        "date_posted": HIRING_POST_DATE,
        "content_type": "posts",
    }
    hp_url = _content_url(
        {
            "keywords": hp_filters["keywords"],
            "company": slug,
            "datePosted": _mirror("P1M"),
            "contentType": _mirror("posts"),
        }
    )
    add("04_hiring_posts", "hiring_posts", "content", hp_url, hp_filters)

    # --- Pass 5: GT alumni (company + schoolFilter=16818) ---
    gt_filters = {
        "current_company": company,
        "school": ["Georgia Institute of Technology"],
        "location": list(LOCATION_FILTER),
    }
    gt_url = _people_url(
        {
            "currentCompany": _mirror(slug),
            "schoolFilter": _mirror(GT_SCHOOL_FILTER_ID),
            "geoU": _mirror("us"),
        }
    )
    add("05_gt_alumni", "gt_alumni", "alumni", gt_url, gt_filters)

    # --- Pass 6: former coworkers (company pinned + Fortinet keyword facet) ---
    fw_filters = {
        "current_company": company,
        "keywords": "Fortinet",
        "location": list(LOCATION_FILTER),
    }
    fw_url = _people_url(
        {
            "currentCompany": _mirror(slug),
            "keywords": "Fortinet",
            "geoU": _mirror("us"),
        }
    )
    add("06_former_coworkers", "former_coworkers", "affinity", fw_url, fw_filters)

    # --- Passes 7-10: targeted keyword facets, always on top of company pin ---
    team_terms = _kw("keywords", DEFAULT_TEAM_KEYWORDS, hints)
    manager_terms = DEFAULT_MANAGER_ROLES + _kw("domain_terms", DEFAULT_DOMAIN_TERMS, hints)
    recruiter_terms = DEFAULT_RECRUITER_ROLES + _kw("domain_terms", RECRUITER_DOMAIN_TERMS, hints)
    university_terms = list(DEFAULT_UNIVERSITY_KEYWORDS)

    targeted = [
        ("07_team_members", "team_members", "targeted", team_terms),
        ("08_hiring_managers", "hiring_managers", "targeted", manager_terms),
        ("09_recruiters", "recruiters", "targeted", recruiter_terms),
        ("10_university_recruiters", "university_recruiters", "targeted", university_terms),
    ]
    for pass_id, family, tier, terms in targeted:
        keywords = _keyword_or(terms)
        filters = {
            "current_company": company,
            "keywords": keywords,
            "location": list(LOCATION_FILTER),
        }
        url = _people_url(
            {
                "currentCompany": _mirror(slug),
                "keywords": keywords,
                "geoU": _mirror("us"),
            }
        )
        add(pass_id, family, tier, url, filters)

    return plan
