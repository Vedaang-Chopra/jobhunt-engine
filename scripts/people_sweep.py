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
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote
import config_lib

REPO = Path(__file__).resolve().parents[1]

COLUMNS = [
    # Original columns stay first for additive schema compatibility.
    "sweep_run_id", "date", "name", "title", "company", "person_type",
    "linkedin_url", "post_url", "why_relevant", "status", "notes",
    # Structured referral/activity evidence (schema v2).
    "location", "team_domain", "target_job_ids", "target_post_urls",
    "connection_degree", "named_mutuals", "gt_overlap", "fortinet_overlap",
    "technical_alignment", "role_hiring_influence",
    "recent_hiring_post_activity", "recent_referral_hiring_activity",
    "profile_inspected_at", "recommended_ask", "outreach_priority",
    "ranking_score", "ranking_breakdown", "re_evaluation_reason",
    "source_query_id",
]

FAMILIES = ["a_hiring_posts", "b_recruiters", "c_company_people", "d_gt_alumni"]

BLOCKED_STATUSES = (
    "requested", "connection_sent", "connected", "contacted", "message_sent",
    "responded", "referred", "declined", "no_response",
)

# Canonical school used ONLY when the school family is explicitly enabled via
# policy and prefs carry no "school" entry. Never a silent query source.
DEFAULT_SCHOOL = "Georgia Tech"
_SCHOOL_FILTER_IDS = {DEFAULT_SCHOOL.lower(): "16818"}


class PreferencesMissing(RuntimeError):
    """Raised when no config file supplies target companies for the sweep."""


class RoleKeywordConfigError(RuntimeError):
    """Raised when role-keywords.yaml exists but its family schema is unusable."""

PEOPLE_CSV = config_lib.path("people_sweep_csv")

RECOGNIZED_KEYWORD_FIELDS = ("primary_keywords", "primary", "keywords")
DEFAULT_ROLE_KEYWORDS = {
    "agentic-ai": ["agentic AI", "AI agents", "tool use", "multi-agent"],
    "evaluation-inference": ["LLM evaluation", "benchmarks", "inference", "vLLM"],
    "applied-ai": ["applied AI", "research engineer", "machine learning engineer"],
}
POST_FAMILY_ORDER = (
    "post-training", "evaluation-inference", "agentic-ai", "research-engineer",
    "ml-training-arch", "multimodal", "ai-security", "applied-ai",
    "ml-engineering",
)
MAX_SEARCHES = 8
STRONG_OPTIMISTIC_FLOOR = 60.0
FRESH_JOB_DAYS = 14
FRESH_POST_DAYS = 14

_SLUG_RE = re.compile(r"linkedin\.com/in/([a-z0-9-]{3,60})")


def linkedin_slug(url: str) -> str:
    """Extract the /in/<slug> handle from a LinkedIn profile URL ('' if none)."""
    m = _SLUG_RE.search(url or "")
    return m.group(1) if m else ""


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore[import-untyped]
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RoleKeywordConfigError(f"Could not parse {path}: {exc}") from exc


def load_role_keywords(kw_path: Path) -> tuple[dict[str, list[str]], dict]:
    """Load role families with an auditable schema-validation report.

    ``primary_keywords`` is canonical. ``primary`` and ``keywords`` remain
    compatible. A present config with families but no recognized keyword field
    is an error; generic defaults are used only when the file itself is absent.
    """
    if not kw_path.exists():
        report = {
            "config_path": str(kw_path),
            "role_families_discovered": list(DEFAULT_ROLE_KEYWORDS),
            "families": [
                {"family": fam, "keywords_loaded": len(kws),
                 "source_field": "built_in_missing_file_fallback"}
                for fam, kws in DEFAULT_ROLE_KEYWORDS.items()
            ],
            "fallback_used": True,
        }
        return dict(DEFAULT_ROLE_KEYWORDS), report

    data = _load_yaml(kw_path)
    fams = data.get("role_families", data) if isinstance(data, dict) else {}
    if not isinstance(fams, dict):
        raise RoleKeywordConfigError(
            f"Invalid role-keyword config at {kw_path}: expected a role_families mapping."
        )

    loaded: dict[str, list[str]] = {}
    family_reports: list[dict] = []
    recognized_family_count = 0
    for fam, spec in fams.items():
        source_field = ""
        raw: Any = []
        if isinstance(spec, dict):
            for field in RECOGNIZED_KEYWORD_FIELDS:
                if field in spec:
                    source_field = field
                    raw = spec.get(field)
                    break
        elif isinstance(spec, list):
            source_field = "legacy_list"
            raw = spec
        keywords = [str(k).strip() for k in raw if str(k).strip()] \
            if isinstance(raw, list) else []
        if source_field:
            recognized_family_count += 1
        if keywords:
            loaded[str(fam)] = keywords
        family_reports.append({
            "family": str(fam),
            "keywords_loaded": len(keywords),
            "source_field": source_field or "unrecognized",
        })

    report = {
        "config_path": str(kw_path),
        "role_families_discovered": [str(f) for f in fams],
        "families": family_reports,
        "fallback_used": False,
    }
    if fams and recognized_family_count == 0:
        fields = ", ".join(RECOGNIZED_KEYWORD_FIELDS)
        raise RoleKeywordConfigError(
            f"Role families were found in {kw_path}, but none uses a recognized "
            f"keyword field. Use primary_keywords (canonical), primary, or keywords; "
            f"recognized fields: {fields}. Validation report: {json.dumps(report, sort_keys=True)}"
        )
    if fams and not loaded:
        raise RoleKeywordConfigError(
            f"Role families in {kw_path} loaded zero keywords. Add non-empty lists "
            f"under primary_keywords. Validation report: {json.dumps(report, sort_keys=True)}"
        )
    return loaded, report


def role_validation_text(report: dict) -> str:
    lines = [
        "role-keyword validation:",
        f"  config={report.get('config_path', '')}",
        f"  fallback_used={str(bool(report.get('fallback_used'))).lower()}",
    ]
    for fam in report.get("families", []):
        lines.append(
            f"  - {fam['family']}: {fam['keywords_loaded']} keyword(s) "
            f"via {fam['source_field']}"
        )
    return "\n".join(lines)


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
    company_profiles: dict[str, dict] = {}
    policy: dict = {}

    kw_path = repo / "job_research" / "config" / "role-keywords.yaml"
    role_keywords, validation = load_role_keywords(kw_path)

    comp_path = repo / "job_research" / "config" / "target-companies.yaml"
    if comp_path.exists():
        try:
            data = _load_yaml(comp_path)
            items = data.get("companies", data if isinstance(data, list) else [])
            for item in items:
                if isinstance(item, dict):
                    name = item.get("company") or item.get("name") or ""
                    profile = dict(item)
                else:
                    name = str(item)
                    profile = {"name": name}
                if name:
                    companies.append(name)
                    company_profiles[_company_key(name)] = profile
            people_cfg = data.get("people_research", {}) if isinstance(data, dict) else {}
            annotations = people_cfg.get("company_profiles", []) \
                if isinstance(people_cfg, dict) else []
            for ann in annotations:
                if not isinstance(ann, dict) or not ann.get("name"):
                    continue
                key = _company_key(str(ann["name"]))
                company_profiles[key] = {**company_profiles.get(key, {}), **ann}
                if str(ann["name"]) not in companies:
                    companies.append(str(ann["name"]))
            policy = dict(people_cfg.get("policy", {})) \
                if isinstance(people_cfg, dict) else {}
        except RoleKeywordConfigError:
            raise
        except Exception as exc:
            raise PreferencesMissing(f"Could not parse target companies {comp_path}: {exc}") from exc

    if not companies:
        raise PreferencesMissing(
            f"No target companies found: {comp_path} is missing or empty. "
            "Define companies in job_research/config/target-companies.yaml "
            "(no hard-coded fallback)."
        )
    return {
        "role_keywords": role_keywords,
        "role_validation": validation,
        "companies": companies,
        "company_profiles": company_profiles,
        "policy": policy,
        "school": "Georgia Institute of Technology",
    }


def _read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _as_date(value: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _role_family(value: str) -> str:
    normalized = (value or "").strip().lower().replace("_", "-")
    return {
        "agentic": "agentic-ai", "agentic-ai": "agentic-ai",
        "eval-inference": "evaluation-inference",
        "evaluation-inference": "evaluation-inference",
        "applied-ml": "applied-ai", "applied-ai": "applied-ai",
        "applied-ai-ml": "applied-ai", "production-ml": "applied-ai",
        "inference": "evaluation-inference", "llm-evaluation": "evaluation-inference",
        "ml-training-arch": "ml-training-arch",
        "research-engineer": "research-engineer",
        "post-training": "post-training", "ai-security": "ai-security",
        "multimodal": "multimodal",
    }.get(normalized, normalized)


def _job_is_qualified(row: dict) -> bool:
    if (row.get("status") or "").strip().lower() not in {"open", "queued", ""}:
        return False
    if (row.get("fit_class") or "").strip().lower() == "disqualified":
        return False
    if _truthy(row.get("is_medical_false_positive")) or _truthy(row.get("stale_flag")):
        return False
    if (row.get("application_status") or "").strip().lower() in {
            "submitted", "acknowledged", "interview", "rejected", "withdrawn"}:
        return False
    if not (row.get("company") or "").strip():
        return False
    if not ((row.get("canonical_application_url") or "").strip() or
            (row.get("job_url") or "").strip()):
        return False
    action = (row.get("recommended_action") or "").strip().upper()
    if action in {"APPLY_NOW", "APPLY"}:
        return True
    return action == "OPTIMISTIC" and _as_float(row.get("priority_v2")) >= STRONG_OPTIMISTIC_FLOOR


def _post_is_actionable(row: dict, today: datetime.date) -> tuple[bool, bool]:
    if (row.get("status") or "").strip().lower() != "new":
        return False, False
    posted = _as_date(row.get("posted_date") or row.get("discovered_date") or "")
    fresh = bool(posted and 0 <= (today - posted).days <= FRESH_POST_DAYS)
    poster_type = (row.get("poster_type") or "").strip().lower()
    role_path = bool((row.get("application_url") or "").strip())
    human_path = poster_type in {
        "hiring_manager", "team_lead", "founder", "recruiter", "engineer_researcher"
    }
    concrete_role = bool((row.get("roles_mentioned") or "").strip())
    role_text = (row.get("roles_mentioned") or "").lower()
    ineligible = any(token in role_text for token in ("internship", "intern ", "campus role"))
    notes = (row.get("notes") or "").lower()
    commentary = "commentary" in notes or "market signal only" in notes
    hiring_text = f"{role_text} {notes}"
    hiring_intent = any(token in hiring_text for token in (
        "we're hiring", "we are hiring", "join my team", "looking for",
        "hiring", "role open", "roles open", "apply"))
    usable_url = bool((row.get("post_url") or "").strip())
    actionable = fresh and usable_url and bool((row.get("poster_name") or "").strip()) and \
        hiring_intent and not commentary and not ineligible and concrete_role and (
        role_path or human_path)
    return fresh, actionable


def _job_trigger_id(job: dict) -> str:
    if (job.get("job_id") or "").strip():
        return str(job["job_id"]).strip()
    url = ((job.get("canonical_application_url") or "").strip() or
           (job.get("job_url") or "").strip())
    return "url_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _post_urls(post: dict) -> tuple[str, str]:
    url = (post.get("post_url") or "").strip()
    if "/in/" in url:
        return url, ""
    if "/posts/" in url or "/feed/update/" in url:
        return "", url
    return "", ""


def load_planning_history(path: Path | None = None) -> dict[str, dict]:
    """Aggregate persisted company/query coverage and yield from JSONL runs."""
    path = Path(path or config_lib.path("people_research_runs"))
    stats: dict[str, dict] = {}
    if not path.exists():
        return stats
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                run = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            for item in run.get("company_yield", []):
                key = _company_key(str(item.get("company") or ""))
                if not key:
                    continue
                s = stats.setdefault(key, {"runs": 0, "new_contacts": 0,
                                           "duplicates": 0, "last_searched": ""})
                s["runs"] += 1
                s["new_contacts"] += int(item.get("new_contacts") or 0)
                s["duplicates"] += int(item.get("duplicates") or 0)
                s["last_searched"] = max(s["last_searched"],
                                          str(run.get("finished_at") or run.get("started_at") or ""))
    return stats


def _profile_for(company: str, prefs: dict) -> dict:
    return dict(prefs.get("company_profiles", {}).get(_company_key(company), {}))


def _matching_post_family(post: dict, role_keywords: dict[str, list[str]]) -> str:
    configured = {_role_family(f): f for f in role_keywords}
    family = _role_family(post.get("role_family") or "")
    if family in configured:
        return family
    text = " ".join(str(post.get(k) or "") for k in (
        "roles_mentioned", "poster_headline", "team_or_org", "notes")).lower()
    for configured_family, original in configured.items():
        if any(str(keyword).lower() in text for keyword in role_keywords[original]):
            return configured_family
    return ""


def _packet_score(packet: dict, profile: dict, history: dict,
                  today: datetime.date) -> tuple[float, list[str]]:
    score = 0.0
    reasons = list(packet.get("selection_reasons") or [])
    job = packet.get("job") or {}
    post = packet.get("post") or {}
    action = (job.get("recommended_action") or "").upper()
    if action == "APPLY_NOW":
        score += 52
    elif action == "APPLY":
        score += 46
    elif action == "OPTIMISTIC":
        score += 34
    score += min(_as_float(job.get("priority_v2")), 100.0) * 0.18
    discovered = _as_date(job.get("date_discovered") or job.get("last_scored") or "")
    if discovered and 0 <= (today - discovered).days <= FRESH_JOB_DAYS:
        score += 8
    if post:
        score += 42 if packet.get("actionable_post") else 14
    tags = {str(t) for t in profile.get("tags", [])}
    score += _as_float(profile.get("fit_score"), 0.0)
    if "high_priority" in tags:
        score += 10
    family = _role_family(packet.get("role_family") or "")
    if "Fortinet_adjacent" in tags and family in {"ai-security", "applied-ai", "agentic-ai"}:
        score += 12
        reasons.append("Fortinet adjacency is a credible differentiator")
    if profile.get("exploration") or "exploration" in tags:
        if not post and not job:
            score -= 100
        elif post or action in {"APPLY_NOW", "APPLY"}:
            score += 2
    contacts = int(packet.get("known_contacts") or 0)
    score -= min(contacts, 10) * 1.5
    h = history.get(_company_key(packet.get("company") or ""), {})
    runs = int(h.get("runs") or 0)
    if runs:
        score += min(int(h.get("new_contacts") or 0) / runs, 3) * 4
        score -= min(int(h.get("duplicates") or 0) / runs, 5) * 1.5
    last = _as_date(str(h.get("last_searched") or ""))
    if last:
        score += min(max((today - last).days, 0), 21) * 0.6
    else:
        score += 8
    return round(score, 2), list(dict.fromkeys(reasons))


def build_research_packets(prefs: dict, jobs: list[dict], posts: list[dict],
                           contacts: list[dict] | None = None,
                           history: dict[str, dict] | None = None,
                           today: datetime.date | None = None) -> list[dict]:
    """Create ranked job/hiring-post packets; never a fixed company queue."""
    today = today or datetime.date.today()
    history = history or {}
    contacts = contacts or []
    contact_counts: dict[str, int] = {}
    for contact in contacts:
        key = _company_key(contact.get("company") or "")
        contact_counts[key] = contact_counts.get(key, 0) + 1

    qualified_jobs = [row for row in jobs if _job_is_qualified(row)]
    jobs_by_company: dict[str, list[dict]] = {}
    for row in qualified_jobs:
        jobs_by_company.setdefault(_company_key(row.get("company") or ""), []).append(row)

    packets: list[dict] = []
    for job in qualified_jobs:
        company = (job.get("company") or "").strip()
        company_profile = _profile_for(company, prefs)
        trigger_id = _job_trigger_id(job)
        discovered = _as_date(job.get("date_discovered") or job.get("last_scored") or "")
        age = (today - discovered).days if discovered else 999
        packet = {
            "packet_id": f"job:{trigger_id}",
            "kind": "job",
            "company": company,
            "company_slug": job.get("company_slug") or _company_key(company),
            "linkedin_id": company_profile.get("linkedin_id") or "",
            "job": job,
            "post": None,
            "job_id": job.get("job_id") or "",
            "job_trigger_id": trigger_id,
            "job_url": job.get("canonical_application_url") or job.get("job_url") or "",
            "team_or_org": job.get("team_or_org") or job.get("relevant_team") or "",
            "role_family": _role_family(job.get("role_family") or "applied-ai"),
            "technical_domain": job.get("role_family") or job.get("key_requirements") or "",
            "hiring_post_author": "",
            "relationship_search_priorities": [
                "1st-degree", "2nd-degree named mutual", "Georgia Tech alumni",
                "Fortinet overlap", "team/hiring manager", "role-specific recruiter",
            ],
            "known_contacts": contact_counts.get(_company_key(company), 0),
            "selection_reasons": [
                f"{job.get('recommended_action')} job in canonical ledger",
                "newly qualified" if age <= FRESH_JOB_DAYS else "active qualified job",
            ],
            "actionable_post": False,
        }
        score, reasons = _packet_score(packet, company_profile, history, today)
        packet["selection_score"], packet["selection_reasons"] = score, reasons
        packets.append(packet)

    for post in posts:
        fresh, actionable = _post_is_actionable(post, today)
        if not fresh:
            continue
        matched_family = _matching_post_family(post, prefs.get("role_keywords", {}))
        if not matched_family:
            continue
        company = (post.get("company") or "").strip()
        company_profile = _profile_for(company, prefs)
        poster_profile_url, source_post_url = _post_urls(post)
        company_jobs = jobs_by_company.get(_company_key(company), [])
        application_url = (post.get("application_url") or "").strip()
        linked_job = next((j for j in company_jobs if application_url and
                           application_url in {
                               (j.get("job_url") or "").strip(),
                               (j.get("canonical_application_url") or "").strip(),
                           }), None)
        if linked_job is None and company_jobs:
            post_fam = _role_family(post.get("role_family") or "")
            linked_job = next((j for j in company_jobs
                               if _role_family(j.get("role_family") or "") == post_fam),
                              company_jobs[0])
        packet = {
            "packet_id": f"post:{post.get('post_id') or _company_key(company)}",
            "kind": "hiring_post" if actionable else "market_signal",
            "packet_kind": "company_expansion" if company else "direct_poster",
            "company": company,
            "company_slug": (linked_job or {}).get("company_slug") or _company_key(company),
            "linkedin_id": company_profile.get("linkedin_id") or "",
            "job": linked_job,
            "post": post,
            "job_id": (linked_job or {}).get("job_id") or "",
            "job_url": (linked_job or {}).get("canonical_application_url") or
                       (linked_job or {}).get("job_url") or post.get("application_url") or "",
            "team_or_org": post.get("team_or_org") or "",
            "role_family": matched_family,
            "technical_domain": post.get("roles_mentioned") or "",
            "hiring_post_author": post.get("poster_name") or "",
            "hiring_post_author_type": post.get("poster_type") or "",
            "poster_profile_url": poster_profile_url,
            "source_post_url": source_post_url,
            "relationship_search_priorities": [
                "hiring-post author", "1st-degree", "2nd-degree named mutual",
                "Georgia Tech alumni", "Fortinet overlap", "team/hiring manager",
            ],
            "known_contacts": contact_counts.get(_company_key(company), 0),
            "selection_reasons": [
                "fresh actionable hiring post" if actionable else "fresh market signal",
                "linked to canonical job" if linked_job else "job link not yet identified",
            ],
            "actionable_post": actionable,
        }
        score, reasons = _packet_score(packet, company_profile, history, today)
        packet["selection_score"], packet["selection_reasons"] = score, reasons
        packets.append(packet)
    return sorted(packets, key=lambda p: (-p["selection_score"], p["packet_id"]))


def _post_query(family: str, keywords: list[str]) -> dict:
    """Build a focused LinkedIn post query, not a broad Boolean keyword dump."""
    primary = next((term.strip() for term in keywords if term and term.strip()), "AI")
    query = f'hiring "{primary}"'
    return {
        "query_id": f"post:{family}",
        "family": "hiring_posts",
        "role_family": family,
        "surface": "linkedin_feed_then_posts",
        "keywords": query,
        "url": ("https://www.linkedin.com/search/results/content/?keywords="
                f"{quote(query, safe='')}&origin=FACETED_SEARCH"),
        "filters": {"content_type": "posts", "date_posted": "past_week",
                    "sort": "latest"},
        "verify": "chips+result_count",
        "secondary_web_query": f"site:linkedin.com/posts {query}",
        "web_confidence": "lower_freshness_sensitive",
    }


def _people_query(packet: dict, family: str, keywords: str = "") -> dict:
    company = packet["company"]
    slug = packet.get("linkedin_id") or packet.get("company_slug") or _company_key(company)
    filters: dict[str, Any] = {"current_company": company,
                               "location": ["United States", "Remote-US"]}
    params = [f"currentCompany={quote(str(slug), safe='')}",
              "geoU=%5B%22us%22%5D", "origin=FACETED_SEARCH"]
    if family == "existing_1st":
        filters["connection_degree"] = ["1st"]
        params.append("network=%5B%22S%22%5D")
    elif family == "existing_2nd_named_mutual":
        filters["connection_degree"] = ["2nd"]
        filters["require_named_mutual"] = True
        params.append("network=%5B%22O%22%5D")
    elif family == "gt_alumni":
        filters["school"] = ["Georgia Institute of Technology"]
        params.append("schoolFilter=%5B%2216818%22%5D")
    else:
        filters["keywords"] = keywords
        params.append(f"keywords={quote(keywords, safe='')}")
    return {
        "query_id": f"{packet['packet_id']}:{family}",
        "packet_id": packet["packet_id"],
        "family": family,
        "surface": "linkedin_people",
        "company": company,
        "job_id": packet.get("job_id") or "",
        "url": "https://www.linkedin.com/search/results/people/?" + "&".join(params),
        "filters": filters,
        "verify": "chips+result_count",
    }


def plan_searches(prefs: dict, packets: list[dict], limit: int = MAX_SEARCHES) -> dict:
    """Allocate four post-first slots and four relationship-filtered job slots."""
    limit = max(1, min(int(limit), MAX_SEARCHES))
    role_keywords = prefs.get("role_keywords", {})
    ordered_families = [f for f in POST_FAMILY_ORDER if role_keywords.get(f)]
    ordered_families += [f for f in role_keywords if f not in ordered_families]
    queries = [_post_query(fam, role_keywords[fam]) for fam in ordered_families[:4]]

    serious = [p for p in packets if p.get("job_id") or p.get("actionable_post")]
    primary = next((p for p in serious if p.get("job_id")), serious[0] if serious else None)
    selected_packets = [primary] if primary else []
    can_expand_company = bool(primary and primary.get("company"))
    if primary and can_expand_company and len(queries) < limit:
        queries.append(_people_query(primary, "existing_1st"))
    if primary and can_expand_company and len(queries) < limit:
        queries.append(_people_query(primary, "existing_2nd_named_mutual"))
    if primary and can_expand_company and len(queries) < limit and prefs.get("policy", {}).get(
            "enable_school_family", True):
        queries.append(_people_query(primary, "gt_alumni"))
    if primary and can_expand_company and len(queries) < limit:
        profile = _profile_for(primary["company"], prefs)
        tags = set(profile.get("tags", []))
        if "Fortinet_adjacent" in tags or _role_family(primary.get("role_family")) == "ai-security":
            family, keywords = "fortinet_overlap", "Fortinet"
        else:
            family = "hiring_manager_recruiter"
            keywords = ("Research Engineer OR Research Scientist OR Applied Scientist OR "
                        "ML Engineer OR Manager OR Lead OR Recruiter OR Talent")
        queries.append(_people_query(primary, family, keywords))
    return {
        "max_searches": MAX_SEARCHES,
        "search_count": min(len(queries), limit),
        "packets_selected": [p for p in selected_packets if p],
        "queries": queries[:limit],
        "direct_poster_reviews": [
            {"packet_id": p["packet_id"], "poster_name": p.get("hiring_post_author", ""),
             "poster_profile_url": p.get("poster_profile_url", ""),
             "source_post_url": p.get("source_post_url", "")}
            for p in selected_packets if p and p.get("packet_kind") == "direct_poster"
        ],
        "allocation": {
            "hiring_post_content": sum(q["family"] == "hiring_posts" for q in queries[:limit]),
            "packet_linked_people": sum(q["surface"] == "linkedin_people" for q in queries[:limit]),
            "job_linked_people": sum(q["surface"] == "linkedin_people" and bool(q.get("job_id"))
                                     for q in queries[:limit]),
            "post_linked_people": sum(q["surface"] == "linkedin_people" and not q.get("job_id")
                                      for q in queries[:limit]),
        },
    }


def build_plan(repo: Path | str | None = None, limit: int = MAX_SEARCHES,
               today: datetime.date | None = None) -> dict:
    root = Path(repo) if repo is not None else config_lib.data_root()
    prefs = load_preferences(root)
    history_path = root / "execution_results" / "linkedin_people" / "runs.jsonl"
    packets = build_research_packets(
        prefs,
        _read_csv(root / "tracking" / "jobs" / "jobs.csv"),
        _read_csv(root / "tracking" / "hiring_posts" / "hiring_posts.csv"),
        _read_csv(root / "tracking" / "contacts" / "contacts.csv"),
        load_planning_history(history_path),
        today=today,
    )
    plan = plan_searches(prefs, packets, limit=limit)
    plan["role_validation"] = prefs["role_validation"]
    plan["packets_considered"] = len(packets)
    plan["canonical_paths"] = {
        "data_root": str(root),
        "jobs": str(root / "tracking" / "jobs" / "jobs.csv"),
        "hiring_posts": str(root / "tracking" / "hiring_posts" / "hiring_posts.csv"),
        "contacts": str(root / "tracking" / "contacts" / "contacts.csv"),
        "people_sweeps": str(root / "tracking" / "people_sweeps" / "people_sweep.csv"),
        "run_history": str(history_path),
    }
    return plan


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
    ranked = rank_candidate(raw)
    row = {column: "" for column in COLUMNS}
    row.update({
        "sweep_run_id": run_id,
        "date": datetime.date.today().isoformat(),
        "name": name,
        "title": raw.get("title", ""),
        "company": raw.get("company", ""),
        "person_type": raw.get("person_type", ""),
        "linkedin_url": raw.get("linkedin_url", ""),
        "post_url": raw.get("post_url", ""),
        "why_relevant": raw.get("why_relevant") or ranked["why_now"],
        "status": "pending_review" if ranked["priority"] != "SKIP" else "skipped_low_signal",
        "notes": raw.get("notes", ""),
        "location": raw.get("location", ""),
        "team_domain": raw.get("team_domain") or raw.get("team") or "",
        "target_job_ids": _join_values(raw.get("target_job_ids") or raw.get("job_id")),
        "target_post_urls": _join_values(raw.get("target_post_urls") or
                                          raw.get("hiring_post_urls") or raw.get("post_url")),
        "connection_degree": _normalize_degree(raw),
        "named_mutuals": _join_values(_named_mutuals(raw.get("named_mutuals") or
                                                       raw.get("mutuals"))),
        "gt_overlap": str(_truthy(raw.get("gt_overlap") or raw.get("gt_alumni"))).lower(),
        "fortinet_overlap": str(_truthy(raw.get("fortinet_overlap"))).lower(),
        "technical_alignment": _join_values(ranked["technical_alignment"]),
        "role_hiring_influence": ranked["role_hiring_influence"],
        "recent_hiring_post_activity": str(ranked["recent_hiring_post_activity"]).lower(),
        "recent_referral_hiring_activity": str(ranked["recent_referral_hiring_activity"]).lower(),
        "profile_inspected_at": raw.get("profile_inspected_at") or "",
        "recommended_ask": ranked["recommended_ask"],
        "outreach_priority": ranked["priority"],
        "ranking_score": str(ranked["score"]),
        "ranking_breakdown": json.dumps(ranked["breakdown"], sort_keys=True),
        "re_evaluation_reason": _reevaluation_reason(raw),
        "source_query_id": raw.get("source_query_id") or "",
    })
    return row


TECHNICAL_SIGNALS = {
    "agentic_rag_retrieval": ("agentic rag", "retrieval", "rag", "search"),
    "post_training_alignment": ("post-training", "rlhf", "dpo", "grpo", "reward model", "preference"),
    "llm_evaluation_reliability": ("evaluation", "evals", "benchmark", "red team", "reliability"),
    "inference_distributed": ("vllm", "inference", "model serving", "fsdp", "distributed training", "gpu"),
    "ai_security": ("ai security", "adversarial ml", "red team", "threat", "security"),
    "multimodal_representation": ("multimodal", "vision-language", "vlm", "representation learning"),
    "production_ml_research_engineering": ("production ml", "research engineer", "ml platform", "mlops"),
}


def _truthy(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _join_values(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def _normalize_degree(raw: dict) -> str:
    value = str(raw.get("connection_degree") or raw.get("degree") or
                raw.get("relationship") or "").strip().lower()
    if value.startswith("1") or "first" in value:
        return "1st"
    if value.startswith("2") or "second" in value:
        return "2nd"
    if value.startswith("3") or "third" in value:
        return "3rd"
    return "unknown"


def _named_mutuals(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        values = [str(v).strip() for v in value]
    else:
        values = re.split(r"[;,]", str(value or ""))
    return [v for v in values if v and not v.isdigit() and
            not re.fullmatch(r"\d+\s+mutuals?", v.lower())]


def _technical_alignment(raw: dict) -> list[str]:
    explicit = raw.get("technical_alignment")
    if isinstance(explicit, list):
        return [str(v).strip() for v in explicit if str(v).strip()]
    text = " ".join(str(raw.get(k) or "") for k in (
        "title", "team_domain", "team", "domain", "snippet", "why_relevant",
        "notes", "role_family",
    )).lower()
    return [name for name, tokens in TECHNICAL_SIGNALS.items()
            if any(token in text for token in tokens)]


def _activity_is_recent(raw: dict, field: str, url_field: str) -> bool:
    value = raw.get(field)
    if _truthy(value):
        return True
    date_value = _as_date(str(value or raw.get(field + "_date") or ""))
    if date_value and 0 <= (datetime.date.today() - date_value).days <= 30:
        return True
    return bool(raw.get(url_field))


def _influence(raw: dict) -> str:
    explicit = str(raw.get("role_hiring_influence") or raw.get("poster_type") or "").lower()
    title = str(raw.get("title") or "").lower()
    if "founder" in explicit or "founder" in title:
        return "founder"
    if "hiring_manager" in explicit or any(t in title for t in ("manager", "head of", "director")):
        return "hiring_manager"
    if "team_lead" in explicit or " lead" in f" {title}":
        return "technical_lead"
    if "recruiter" in explicit or any(t in title for t in ("recruiter", "talent", "sourcer")):
        return "role_specific_recruiter"
    return "team_member" if raw.get("same_team") else "none"


def rank_candidate(raw: dict) -> dict:
    """Structured person ranking with activity as a first-class signal."""
    degree = _normalize_degree(raw)
    mutuals = _named_mutuals(raw.get("named_mutuals") or raw.get("mutuals"))
    gt = _truthy(raw.get("gt_overlap") or raw.get("gt_alumni"))
    fortinet = _truthy(raw.get("fortinet_overlap"))
    technical = _technical_alignment(raw)
    influence = _influence(raw)
    hiring_active = _activity_is_recent(raw, "recent_hiring_post_activity", "hiring_post_urls") \
        or bool(raw.get("post_url"))
    referral_active = _activity_is_recent(raw, "recent_referral_hiring_activity",
                                          "referral_post_urls")
    job_linked = bool(raw.get("target_job_ids") or raw.get("job_id"))
    post_linked = bool(raw.get("target_post_urls") or raw.get("hiring_post_urls") or
                       raw.get("post_url"))
    exceptional = _truthy(raw.get("exceptional_shared_context"))
    breakdown = {
        "live_job_link": 18 if job_linked else 0,
        "post_link": 8 if post_linked else 0,
        "connection_degree": {"1st": 12, "2nd": 7, "3rd": 1}.get(degree, 0),
        "named_mutuals": min(len(mutuals) * 6, 18),
        "gt_overlap": 10 if gt else 0,
        "fortinet_overlap": 10 if fortinet else 0,
        "technical_alignment": min(len(technical) * 5, 20),
        "hiring_influence": {
            "hiring_manager": 16, "technical_lead": 14, "founder": 15,
            "role_specific_recruiter": 10, "team_member": 6,
        }.get(influence, 0),
        "recent_hiring_post_activity": 24 if hiring_active else 0,
        "recent_referral_hiring_activity": 18 if referral_active else 0,
        "exceptional_context": 8 if exceptional else 0,
    }
    relevance = bool(technical or influence != "none" or hiring_active or referral_active)
    if degree == "1st" and job_linked:
        priority = "P0"
    elif ((degree == "2nd" and mutuals and relevance) or
          ((gt or fortinet) and relevance and (mutuals or job_linked or post_linked))):
        priority = "P1"
    elif job_linked and relevance:
        priority = "P2"
    elif degree == "3rd" and (hiring_active or influence in {
            "hiring_manager", "technical_lead", "founder"} or exceptional) and (job_linked or post_linked):
        priority = "P3"
    else:
        priority = "SKIP"
    if priority == "P0":
        ask = "Direct referral or hiring-team introduction, subject to human approval"
    elif hiring_active or referral_active:
        ask = "Reference the recent hiring/referral post and ask about the linked role"
    elif mutuals:
        ask = "Ask the named mutual for an introduction before outreach"
    elif gt or fortinet:
        ask = "Request a brief role-specific conversation using the shared context"
    elif influence == "role_specific_recruiter":
        ask = "Ask whether they recruit for the linked role/team"
    else:
        ask = "Ask a specific technical question about the linked team/role"
    why = []
    if job_linked:
        why.append("linked to a live relevant job")
    if hiring_active:
        why.append("recent active hiring poster")
    if referral_active:
        why.append("recent referral activity")
    if influence != "none":
        why.append(influence.replace("_", " "))
    if mutuals:
        why.append("named mutuals: " + ", ".join(mutuals[:3]))
    if gt:
        why.append("Georgia Tech overlap")
    if fortinet:
        why.append("Fortinet overlap")
    if technical:
        why.append("technical alignment: " + ", ".join(technical[:3]))
    return {
        "score": sum(breakdown.values()),
        "priority": priority,
        "breakdown": breakdown,
        "recommended_ask": ask,
        "why_now": "; ".join(why) or "no credible live-role, activity, relationship, or technical rationale",
        "technical_alignment": technical,
        "role_hiring_influence": influence,
        "recent_hiring_post_activity": hiring_active,
        "recent_referral_hiring_activity": referral_active,
    }


def _reevaluation_reason(raw: dict) -> str:
    reasons = []
    if _truthy(raw.get("fresh_hiring_post")) or _activity_is_recent(
            raw, "recent_hiring_post_activity", "hiring_post_urls"):
        reasons.append("fresh_relevant_hiring_post")
    if _truthy(raw.get("new_matching_job")):
        reasons.append("new_matching_job")
    if _truthy(raw.get("relationship_changed")) or _truthy(raw.get("activity_changed")):
        reasons.append("material_relationship_or_activity_change")
    return ";".join(reasons)


def append_rows(rows: list[dict], out_path: str | Path) -> int:
    """Append normalized rows to the sweep CSV (creating it with schema)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists() or out_path.stat().st_size == 0
    if not new_file:
        with out_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            old_fields = list(reader.fieldnames or [])
            old_rows = list(reader)
        if old_fields != COLUMNS:
            with out_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=COLUMNS)
                writer.writeheader()
                for old in old_rows:
                    writer.writerow({k: old.get(k, "") for k in COLUMNS})
    with out_path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})
    return len(rows)


METRIC_KEYS = (
    "packets_selected", "posts_examined", "fresh_relevant_posts", "actionable_posts",
    "people_search_queries_run", "profiles_examined", "new_contacts",
    "contacts_tied_to_live_jobs", "active_hiring_posters", "gt_overlap_candidates",
    "fortinet_overlap_candidates", "duplicates", "p0", "p1", "p2", "p3",
)


def classify_run_status(metrics: dict) -> str:
    if metrics.get("planning_config_error"):
        return "planning_config_validation_failure"
    if metrics.get("browser_unavailable"):
        return "browser_unavailable_or_auth_wall"
    if metrics.get("completed") and not metrics.get("new_contacts") and metrics.get("duplicates"):
        return "completed_no_new_people_dedupe_suppressed"
    if metrics.get("completed") and not metrics.get("profiles_examined") and not metrics.get("actionable_posts"):
        return "completed_zero_relevant_results"
    if metrics.get("completed"):
        return "completed_successfully"
    return "incomplete"


def record_run_metrics(metrics: dict, path: Path | None = None) -> dict:
    """Append one auditable JSONL record with query/company yield metadata."""
    path = Path(path or config_lib.path("people_research_runs"))
    record: dict[str, Any] = {key: int(metrics.get(key) or 0) for key in METRIC_KEYS}
    record.update({
        "run_id": metrics.get("run_id") or
                  f"people_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "started_at": metrics.get("started_at") or "",
        "finished_at": metrics.get("finished_at") or
                       datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "degree_distribution": dict(metrics.get("degree_distribution") or {}),
        "query_yield": list(metrics.get("query_yield") or []),
        "company_yield": list(metrics.get("company_yield") or []),
        "status": classify_run_status(metrics),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def main(argv: list[str] | None = None) -> int:
    """Plan-only by default; optionally persist a completed agent-run metrics file."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="print planned searches; no browser, no writes (default)")
    ap.add_argument("--limit", type=int, default=MAX_SEARCHES,
                    help="max planned searches (hard-capped at eight)")
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    ap.add_argument("--record-results", type=Path,
                    help="append metrics from an agent-produced JSON file; no browsing")
    args = ap.parse_args(argv)

    if args.record_results:
        metrics = json.loads(args.record_results.read_text(encoding="utf-8"))
        print(json.dumps(record_run_metrics(metrics), indent=2, sort_keys=True))
        return 0
    try:
        plan = build_plan(limit=args.limit)
    except (RoleKeywordConfigError, PreferencesMissing) as exc:
        error = {"status": "planning_config_validation_failure", "error": str(exc)}
        print(json.dumps(error, indent=2) if args.json else f"ERROR: {exc}")
        return 2
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    print(role_validation_text(plan["role_validation"]))
    print(f"people_sweep dry-run: packets_considered={plan['packets_considered']} "
          f"packets_selected={len(plan['packets_selected'])} "
          f"searches={plan['search_count']}/{plan['max_searches']}")
    for packet in plan["packets_selected"]:
        print(f"  packet {packet['packet_id']}: {packet['company']} "
              f"job={packet.get('job_id') or '-'} score={packet['selection_score']}")
    for query in plan["queries"]:
        print(f"  [{query['query_id']}] filters={json.dumps(query['filters'], sort_keys=True)}")
        print(f"    {query['url']}")
    print("dry-run: nothing executed. Browser extraction remains read-only and agent-driven.")
    return 0


class PeopleDedupIndex:
    """Never-twice interlock: slug + fuzzy(name, company) against contacts.csv
    and prior sweep rows. Blocked statuses are suppressed outright."""

    def __init__(self) -> None:
        self._slugs: set[str] = set()
        self._names: list[tuple[str, str, str]] = []  # (norm_name, company, status)
        self._contact_status: dict[tuple[str, str], str] = {}
        self._records: dict[tuple[str, str], dict] = {}

    # -- loading ------------------------------------------------------------
    def add_seen(self, slug: str = "", name: str = "", company: str = "",
                 status: str = "", record: dict | None = None) -> None:
        if slug:
            self._slugs.add(slug)
        if name:
            self._names.append((_norm_name(name), company or "", status))
            self._records[(_norm_name(name), _company_key(company))] = dict(record or {})

    def load_contacts(self, path: str | Path) -> None:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = row.get("name", "")
                slug = linkedin_slug(row.get("linkedin_url", "") or "")
                status = (row.get("outreach_status") or "").strip().lower()
                self.add_seen(slug=slug, name=name,
                              company=row.get("company", ""), status=status,
                              record=row)
                if name:
                    self._contact_status[
                        (_norm_name(name), _company_key(row.get("company", "")))] = status

    def load_prior_rows(self, path: str | Path) -> None:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.add_seen(
                    slug=linkedin_slug(row.get("linkedin_url", "") or ""),
                    name=row.get("name", ""),
                    company=row.get("company", ""),
                    status=(row.get("status") or "").strip().lower(),
                    record=row)

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

    def verdict(self, name: str, company: str, linkedin_url: str = "",
                evidence: dict | None = None) -> str:
        """'blocked' (touched before — suppress), 'duplicate' (seen, untouched),
        'reevaluate' (preserve identity but refresh material evidence), or 'new'."""
        reason = _reevaluation_reason(evidence or {})
        duplicate = self.fuzzy_seen(name, company) or bool(
            linkedin_url and self.seen_before(linkedin_url))
        key = (_norm_name(name), _company_key(company))
        status = self._contact_status.get(key, "")
        if not status:
            # A legacy contact without company data may still identify the same
            # person by profile URL, but never cross-block two named companies.
            status = self._contact_status.get((_norm_name(name), ""), "")
        if status in BLOCKED_STATUSES:
            return "reevaluate" if reason else "blocked"
        if duplicate:
            return "reevaluate" if reason else "duplicate"
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
                          linkedin_url=row["linkedin_url"], evidence=raw)
        if v == "new":
            if row["status"] == "skipped_low_signal":
                blocked.append(row)
                continue
            accepted.append(row)
            index.add_seen(slug=linkedin_slug(row["linkedin_url"]),
                           name=row["name"], company=row["company"], record=row)
        elif v == "reevaluate":
            # Re-evaluation is a research refresh, never a second contact or send.
            row["status"] = "reevaluation_pending"
            row["notes"] = "; ".join(filter(None, [
                row.get("notes", ""), "existing identity; do not duplicate outreach"
            ]))
            accepted.append(row)
        elif v == "blocked":
            blocked.append(row)
        else:
            dups.append(row)
    return accepted, dups, blocked


if __name__ == "__main__":
    raise SystemExit(main())
