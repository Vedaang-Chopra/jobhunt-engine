#!/usr/bin/env python3
import csv
from datetime import datetime
import sys
sys.path.insert(0, '/mnt/DATA/job_hunt/jobhunt-engine/scripts')
import config_lib

# Load preferences to build queries
def load_preferences(repo=None):
    if repo is None:
        repo = config_lib.data_root()
    from pathlib import Path
    repo = Path(repo)
    role_keywords = {}
    companies = []

    kw_path = repo / "job_research" / "config" / "role-keywords.yaml"
    if kw_path.exists():
        try:
            import yaml
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
            import yaml
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

    if not role_keywords:
        role_keywords = {
            "agentic_ai": ["agentic AI", "AI agents"],
            "eval_inference": ["inference", "LLM evaluation"],
            "applied_ml": ["machine learning engineer"],
        }
    if not companies:
        raise RuntimeError(f"No target companies found: {comp_path} is missing or empty.")

    return {"role_keywords": role_keywords, "companies": companies}

def _urlenc(s):
    from urllib.parse import quote
    return quote(s, safe="")

def build_queries(prefs, policy=None):
    policy = dict(policy or {})
    queries = []
    fam_kws = list(prefs.get("role_keywords", {}).items())
    companies = prefs.get("companies", [])
    school_family_enabled = bool(policy.get("enable_school_family", False))
    school = str(prefs.get("school") or "Georgia Tech")

    for fam, kws in fam_kws:
        kw = " OR ".join(kws)
        queries.append({
            "family": "a_hiring_posts",
            "keywords": kw,
            "url": f"https://www.linkedin.com/search/results/content/?keywords={_urlenc(f'({kw}) hiring')}&origin=FACETED_SEARCH"
        })

    for company in companies:
        inner = f'"talent acquisition" "{company}"'
        queries.append({
            "family": "b_recruiters",
            "keywords": f"talent acquisition {company}",
            "url": f"https://www.linkedin.com/search/results/people/?keywords={_urlenc(inner)}&origin=FACETED_SEARCH"
        })
        inner2 = f'"{company}"'
        queries.append({
            "family": "c_company_people",
            "keywords": company,
            "url": f"https://www.linkedin.com/search/results/people/?keywords={_urlenc(inner2)}&origin=FACETED_SEARCH"
        })
        if school_family_enabled:
            inner3 = f'"{school}" "{company}"'
            filter_param = ""
            filter_id = {"georgia tech": "16818"}.get(school.lower())
            if filter_id:
                filter_param = f"&schoolFilter={filter_id}"
            queries.append({
                "family": "d_gt_alumni",
                "keywords": f"{school} {company}",
                "url": f"https://www.linkedin.com/search/results/people/?keywords={_urlenc(inner3)}{filter_param}&origin=FACETED_SEARCH"
            })
    return queries

def cap_queries(queries, limit):
    FAMILIES = ["a_hiring_posts", "b_recruiters", "c_company_people", "d_gt_alumni"]
    by_fam = {}
    for q in queries:
        by_fam.setdefault(q["family"], []).append(q)
    capped = []
    fams = [f for f in FAMILIES if f in by_fam] + [f for f in by_fam if f not in FAMILIES]
    while len(capped) < limit and any(by_fam[f] for f in fams):
        for f in fams:
            if by_fam[f] and len(capped) < limit:
                capped.append(by_fam[f].pop(0))
    return capped

# Main execution
if __name__ == "__main__":
    prefs = load_preferences()
    queries = build_queries(prefs)
    capped = cap_queries(queries, 8)
    print(f"people_sweep dry-run: {len(capped)} planned query(ies) (companies={len(prefs.get('companies', []))})")
    for q in capped:
        print(f"  [{q.get('family', '?')}] {q.get('keywords', '')}")
        url = q.get("url", "")
        if url:
            print(f"    {url}")
    print("dry-run: nothing executed. Browser extraction is agent-driven.")