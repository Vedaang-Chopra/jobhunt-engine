"""Target resolver for the "right people" feature (Task 1).

Resolves a CLI target (--company NAME | --job-url URL) into a canonical
dict: either a company slug from the companies registry, or a full job row
from the canonical jobs CSV (exact job_url -> canonical_application_url ->
fuzzy company-slug + title-token fallback).

Pure logic only — no browser, no network. `repo` lets tests seed a temp
repo layout (``<repo>/jobhunt-data/...``) without touching real data.
"""

from __future__ import annotations

import csv
from pathlib import Path

import config_lib
import referral_lib

VALID_FLAGS = ("--company", "--job-url")

JOBS_CSV_NAME = Path("jobhunt-data") / "tracking" / "jobs" / "jobs.csv"
REGISTRY_REL = (Path("jobhunt-data") / "tracking" / "companies"
                / "companies_registry.csv")
DATA_ROOT_DIR = "jobhunt-data"


class TargetNotFound(Exception):
    """Raised when the requested company or job cannot be resolved."""


def _clean_row(row):
    return {k: (v if v is not None else "") for k, v in row.items()}


def _registry_path_for(repo):
    """Registry path override for a seeded repo, or None for the default."""
    if repo is None:
        return None
    candidate = Path(repo) / REGISTRY_REL
    return str(candidate) if candidate.exists() else None


def _jobs_csv_path_for(repo):
    """Jobs CSV for the repo override, or None when absent/default."""
    if repo is None:
        return config_lib.path("jobs_csv")
    candidate = Path(repo) / JOBS_CSV_NAME
    return candidate if candidate.exists() else None


def _read_jobs(jobs_csv):
    with open(jobs_csv, newline="", encoding="utf-8") as f:
        return [_clean_row(r) for r in csv.DictReader(f)]


def _url_path_tokens(url):
    """Slugified tokens of the URL path (ignoring scheme/host/query)."""
    text = (url or "").strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[1] if "/" in text else ""
    text = text.split("?", 1)[0].split("#", 1)[0]
    return [t for t in referral_lib._slug(text).split("_") if t]


def _title_tokens(title):
    return [t for t in referral_lib._slug(title).split("_") if t]


def _company_token_matches(company_slug, url_tokens):
    """True if the row's company slug relates to any URL path token."""
    for tok in url_tokens:
        if not tok:
            continue
        if (company_slug == tok or company_slug.startswith(tok)
                or tok.startswith(company_slug)):
            return True
    return False


def _fuzzy_match(rows, value):
    """Match on normalized company slug + title tokens from the URL."""
    url_tokens = _url_path_tokens(value)
    if not url_tokens:
        return None
    for row in rows:
        company_slug = (row.get("company_slug") or "").strip()
        title_tokens = set(_title_tokens(row.get("title") or ""))
        if not company_slug or not title_tokens:
            continue
        if _company_token_matches(company_slug, url_tokens) \
                and title_tokens.issubset(set(url_tokens)):
            return row
    return None


def _resolve_jd_path(description_file, repo):
    """Resolve description_file relative to the data root; None if absent."""
    desc = (description_file or "").strip()
    if not desc:
        return None
    candidate = Path(desc)
    if not candidate.is_absolute():
        bases = []
        if repo is not None:
            bases.append(Path(repo) / DATA_ROOT_DIR)
            bases.append(Path(repo))
        else:
            bases.append(config_lib.data_root())
        candidate = next(
            (base / candidate for base in bases if (base / candidate).exists()),
            bases[0] / candidate)
    return str(candidate) if candidate.exists() else None


def _resolve_company(value, repo):
    registry_path = _registry_path_for(repo)
    if repo is not None and registry_path is None:
        raise TargetNotFound(
            f"no companies registry found under {Path(repo) / REGISTRY_REL}")
    slug = referral_lib.resolve_company_slug(value, registry_path=registry_path)
    if not slug:
        raise TargetNotFound(f"could not resolve company: {value!r}")
    name = value
    try:
        reg_row = referral_lib.registry_row_for(slug, registry_path=registry_path)
        if reg_row and (reg_row.get("company") or "").strip():
            name = reg_row["company"].strip()
    except (OSError, csv.Error):
        pass
    return {"kind": "company", "company": name, "company_slug": slug,
            "job": None, "jd_path": None, "hints": None}


def _resolve_job(value, repo):
    jobs_csv = _jobs_csv_path_for(repo)
    if jobs_csv is None:
        raise TargetNotFound(f"jobs.csv not found for repo {repo!r}")
    rows = _read_jobs(jobs_csv)
    match = next(
        (r for r in rows if (r.get("job_url") or "").strip() == value), None)
    if match is None:
        match = next(
            (r for r in rows
             if (r.get("canonical_application_url") or "").strip() == value),
            None)
    if match is None:
        match = _fuzzy_match(rows, value)
    if match is None:
        raise TargetNotFound(f"no job row matches URL: {value!r}")
    return {
        "kind": "job",
        "company": (match.get("company") or "").strip(),
        "company_slug": (match.get("company_slug") or "").strip(),
        "job": match,
        "jd_path": _resolve_jd_path(match.get("description_file"), repo),
        "hints": None,
    }


def resolve_target(flag: str, value: str, repo: Path | None = None) -> dict:
    """Resolve --company/--job-url into a canonical target dict."""
    if flag not in VALID_FLAGS:
        raise ValueError(
            f"argument {flag}: expected one of {', '.join(VALID_FLAGS)}")
    if not (value or "").strip():
        raise ValueError(f"argument {flag}: value must not be empty")
    value = value.strip()
    if flag == "--company":
        return _resolve_company(value, repo)
    return _resolve_job(value, repo)
