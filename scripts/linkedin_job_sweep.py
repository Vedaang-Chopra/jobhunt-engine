#!/usr/bin/env python3
"""Canonical deterministic LinkedIn Jobs discovery runner.

Exactly eight code-planned searches are executed through BOTH LinkedIn paths:
(1) guest jobs API and (2) authenticated server-rendered /jobs/search-results/
fetches. The runner never chooses query text and never uses an LLM. Plan-only
mode is network- and write-free. Live mode is discovery-only: no applications,
messages, connections, or Easy Apply actions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts import config_lib
    from scripts.discovery_lib import DedupIndex, _CSV_COLUMNS, normalize_job, slugify
    from scripts.linkedin_portal_sweep import parse_search_results_html
    from scripts.linkedin_query_planner import append_run, load_catalog, plan_queries, read_history
    from scripts.linkedin_qualification import cheap_qualify, qualify_job
except ImportError:  # pragma: no cover - direct script execution
    import config_lib
    from discovery_lib import DedupIndex, _CSV_COLUMNS, normalize_job, slugify
    from linkedin_portal_sweep import parse_search_results_html
    from linkedin_query_planner import append_run, load_catalog, plan_queries, read_history
    from linkedin_qualification import cheap_qualify, qualify_job

JOBS_CSV = config_lib.path("jobs_csv")
JD_DIR = config_lib.path("jd_active_dir")
REPORT_DIR = config_lib.path("execution_results_dir")
QUALIFICATION_FIELDS = [
    "technical_families", "seniority_risk", "experience_requirement",
    "experience_flexibility", "salary_evidence", "eligibility_verdict",
    "eligibility_reason", "stretch_rationale", "qualification_json",
]
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "Chrome/126.0 Safari/537.36")
GUEST_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def query_params(query) -> dict[str, str]:
    return {
        "keywords": query.query,
        "location": "United States",
        "geoId": query.geo_id,
        "f_TPR": f"r{query.recency_seconds}",
        "f_E": query.experience_levels,
    }


def logged_in_search_path(query) -> str:
    return "/jobs/search-results/?" + urllib.parse.urlencode(query_params(query))


def guest_search_url(query, start: int = 0) -> str:
    params = query_params(query)
    params["start"] = str(start)
    return GUEST_ENDPOINT + "?" + urllib.parse.urlencode(params)


def parse_guest_cards(page_html: str) -> list[dict]:
    cards = []
    blocks = re.findall(r'<div class="base-card.*?(?=<div class="base-card|</ol>)', page_html, re.S)
    for block in blocks:
        link = re.search(r'href="[^"]*/jobs/view/([^/?"]+)', block)
        if not link:
            continue
        slug = link.group(1)
        source_id = slug.rsplit("-", 1)[-1] if slug.rsplit("-", 1)[-1].isdigit() else slug
        def field(pattern: str) -> str:
            match = re.search(pattern, block, re.S)
            return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""
        cards.append({
            "source_id": source_id,
            "title": field(r"<h3[^>]*>\s*(.*?)\s*</h3>"),
            "company": field(r"<h4[^>]*>\s*(.*?)\s*</h4>"),
            "location": field(r"job-search-card__location[^>]*>\s*(.*?)\s*<"),
            "date_posted": field(r'<time[^>]*datetime="([^"]+)"'),
            "url": f"https://www.linkedin.com/jobs/view/{source_id}/",
            "retrieval_path": "guest",
        })
    return cards


def fetch_guest(query) -> list[dict]:
    found: dict[str, dict] = {}
    for start in (0, 25):
        request = urllib.request.Request(guest_search_url(query, start), headers={"User-Agent": USER_AGENT})
        body = urllib.request.urlopen(request, timeout=30).read().decode("utf-8", "ignore")
        cards = parse_guest_cards(body)
        for card in cards:
            found.setdefault(card["source_id"], card)
        if len(cards) < 10:
            break
        time.sleep(1)
    return list(found.values())


def fetch_logged_in(page, query) -> list[dict]:
    """Fetch server-rendered search HTML inside the authenticated browser."""
    path = logged_in_search_path(query)
    script = """async ({path}) => {
      const response = await fetch(path, {credentials: 'include', headers: {'accept': 'text/html'}});
      return {status: response.status, html: await response.text(), url: response.url};
    }"""
    response = page.evaluate(script, {"path": path})
    if not response or response.get("status") != 200:
        raise RuntimeError(f"logged-in fetch failed status={(response or {}).get('status')}")
    body = response.get("html") or ""
    lower = body[:8000].lower()
    if "authwall" in lower or "sign in to linkedin" in lower:
        raise RuntimeError("logged-in fetch returned authwall")
    rows = parse_search_results_html(body)
    for row in rows:
        row["retrieval_path"] = "logged_in"
    return rows


def _date_posted(raw: dict) -> str:
    value = str(raw.get("date_posted") or raw.get("posted_age") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    match = re.search(r"(\d+)\s+(hour|day|week)s?\s+ago", value, re.I)
    if not match:
        return ""
    amount, unit = int(match.group(1)), match.group(2).lower()
    days = 0 if unit == "hour" else amount if unit == "day" else amount * 7
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


def _candidate_key(row: dict) -> str:
    source_id = str(row.get("source_id") or "").strip()
    if source_id:
        return "id:" + source_id
    return "ct:" + slugify(row.get("company", "")) + "|" + slugify(row.get("title", ""))


def load_dedup_index(path: Path = JOBS_CSV) -> DedupIndex:
    index = DedupIndex()
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                index.add(row)
    return index


def fetch_jd(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    body = urllib.request.urlopen(request, timeout=30).read().decode("utf-8", "ignore")
    match = re.search(r'<div class="show-more-less-html__markup[^>]*>(.*?)</div>', body, re.S)
    if not match:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", "\n", match.group(1)))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _job_id(row: dict) -> str:
    return f"{slugify(row['company'])}_{slugify(row['title'])}_{row['source_id']}"


def _persist_jd(row: dict, description: str) -> tuple[str, str]:
    digest = hashlib.sha256(description.encode("utf-8")).hexdigest()
    JD_DIR.mkdir(parents=True, exist_ok=True)
    path = JD_DIR / f"{row['job_id']}.md"
    content = (
        f"# {row['title']}\n"
        f"Company: {row['company']}\n"
        f"Source: linkedin\n"
        f"URL: {row['job_url']}\n"
        f"Hash: {digest}\n"
        f"Discovered: {row['date_discovered']}\n\n"
        f"## Full Job Description Text\n{description}\n\n---\n"
    )
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(config_lib.data_root())), digest


def append_jobs(rows: list[dict], path: Path = JOBS_CSV) -> int:
    """Append rows after add-only header migration; never drops old columns."""
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    old_fields: list[str] = []
    if path.is_file() and path.stat().st_size:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            old_fields = list(reader.fieldnames or [])
            existing = list(reader)
    fields = old_fields + [field for field in list(_CSV_COLUMNS) + QUALIFICATION_FIELDS
                           if field not in old_fields]
    if not fields:
        fields = list(_CSV_COLUMNS)
    if existing and fields != old_fields:
        with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8",
                                         dir=path.parent, delete=False) as fh:
            tmp = Path(fh.name)
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing)
        tmp.replace(path)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _new_metric(query, run_id: str) -> dict:
    return {
        "run_id": run_id, "query_id": query.query_id, "query": query.query,
        "slot": query.slot, "role_family": query.role_family,
        "technical_family": query.technical_family,
        "last_run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_results": 0, "unique_results": 0, "duplicates": 0,
        "hard_rejections": 0, "eligible_jobs": 0, "apply_outcomes": 0,
        "optimistic_outcomes": 0, "failure_count": 0, "error": "",
    }


def _merge_sources(guest: list[dict], logged: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in guest + logged:
        key = _candidate_key(row)
        if key not in merged:
            merged[key] = dict(row)
            merged[key]["retrieval_paths"] = [row.get("retrieval_path", "")]
        else:
            current = merged[key]
            for field in ("salary", "alumni", "posted_age", "date_posted", "location"):
                if row.get(field) and not current.get(field):
                    current[field] = row[field]
            path = row.get("retrieval_path", "")
            if path and path not in current["retrieval_paths"]:
                current["retrieval_paths"].append(path)
    return list(merged.values())


def run_live() -> tuple[int, dict]:
    catalog = load_catalog()
    plan = plan_queries(catalog, read_history())
    run_id = "linkedin_jobs_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    metrics = {query.query_id: _new_metric(query, run_id) for query in plan}
    index = load_dedup_index()
    accepted: list[dict] = []
    candidate_queries: dict[str, set[str]] = defaultdict(set)
    candidates: dict[str, dict] = {}
    browser_ok = False
    browser_error = ""

    # Open one shared authenticated session. Guest retrieval remains independent.
    try:
        from browser_session_lib import open_logged_in_session
        session = open_logged_in_session(source="linkedin_job_sweep")
        page = session.page
        # Relative /jobs/search-results/ fetches require a LinkedIn origin.
        if not str(page.url).startswith("https://www.linkedin.com/"):
            page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
        if "/login" in page.url or "/authwall" in page.url or "/checkpoint" in page.url:
            raise RuntimeError(f"LinkedIn authentication/challenge page: {page.url}")
        browser_ok = True
    except Exception as exc:  # noqa: BLE001
        session = None
        page = None
        browser_error = f"{type(exc).__name__}: {exc}"

    try:
        for query in plan:
            guest, logged = [], []
            errors = []
            try:
                guest = fetch_guest(query)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"guest:{type(exc).__name__}:{exc}")
            if page is not None:
                try:
                    logged = fetch_logged_in(page, query)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"logged_in:{type(exc).__name__}:{exc}")
                    browser_ok = False
            else:
                errors.append("logged_in:browser_unavailable")
            metric = metrics[query.query_id]
            metric["raw_results"] = len(guest) + len(logged)
            merged = _merge_sources(guest, logged)
            metric["unique_results"] = len(merged)
            metric["failure_count"] = len(errors)
            metric["error"] = "; ".join(errors)
            for raw in merged:
                key = _candidate_key(raw)
                candidate_queries[key].add(query.query_id)
                candidates.setdefault(key, {**raw, "planned_query": query})
    finally:
        if session is not None:
            session.close()

    # Deterministic cheap gates happen before JD fetch.
    survivors = []
    for key, raw in candidates.items():
        query = raw["planned_query"]
        cheap = cheap_qualify(raw, query.role_family, query.technical_family)
        for qid in candidate_queries[key]:
            if cheap.eligibility == "rejected":
                metrics[qid]["hard_rejections"] += 1
        if cheap.eligibility == "rejected":
            continue
        try:
            norm = normalize_job({
                "title": raw.get("title"), "company": raw.get("company"),
                "url": raw.get("url"), "location": raw.get("location") or "",
                "source": "linkedin", "source_id": raw.get("source_id") or "",
                "date_posted": _date_posted(raw),
            })
        except ValueError:
            for qid in candidate_queries[key]:
                metrics[qid]["hard_rejections"] += 1
            continue
        duplicate, _ = index.seen_before(norm)
        if duplicate:
            for qid in candidate_queries[key]:
                metrics[qid]["duplicates"] += 1
            continue
        survivors.append((key, raw, norm))

    for key, raw, row in survivors:
        query = raw["planned_query"]
        try:
            description = fetch_jd(row["job_url"])
        except Exception:
            description = ""
        qualification = qualify_job(raw, description, query.role_family, query.technical_family)
        if qualification.eligibility == "rejected" or (
                qualification.eligibility == "stretch_review" and qualification.reject_reason):
            for qid in candidate_queries[key]:
                metrics[qid]["hard_rejections"] += 1
            continue
        row.update(qualification.ledger_fields())
        row["job_id"] = _job_id(row)
        row["source"] = "linkedin"
        row["notes"] = (
            f"linkedin_query_ids={','.join(sorted(candidate_queries[key]))}; "
            f"retrieval_paths={','.join(raw.get('retrieval_paths') or [])}; "
            f"qualification={qualification.eligibility}"
        )
        path, digest = _persist_jd(row, description)
        row["description_file"], row["full_description_hash"] = path, digest
        index.add(row)
        accepted.append(row)
        for qid in candidate_queries[key]:
            metrics[qid]["eligible_jobs"] += 1

    appended = append_jobs(accepted)
    score_exit = None
    if appended:
        score_result = subprocess.run([sys.executable, "scripts/score_jobs_v2.py"],
                                      cwd=str(Path(__file__).resolve().parents[1]),
                                      check=False)
        score_exit = score_result.returncode
        # Count final scored outcomes where available.
        accepted_ids = {row["job_id"]: key for key, _raw, row in survivors if row.get("job_id")}
        if JOBS_CSV.is_file():
            with JOBS_CSV.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    key = accepted_ids.get(row.get("job_id", ""))
                    if not key:
                        continue
                    action = (row.get("recommended_action") or "").upper()
                    for qid in candidate_queries[key]:
                        if action in {"APPLY_NOW", "APPLY"}:
                            metrics[qid]["apply_outcomes"] += 1
                        elif action in {"OPTIMISTIC", "STRETCH"}:
                            metrics[qid]["optimistic_outcomes"] += 1

    append_run(list(metrics.values()))
    report = {
        "run_id": run_id,
        "planned_queries": [query.to_dict() for query in plan],
        "guest_retrieval_attempted": True,
        "browser_retrieval_succeeded": browser_ok,
        "browser_error": browser_error,
        "score_exit_code": score_exit,
        "funnel": {
            "raw_results": sum(m["raw_results"] for m in metrics.values()),
            "unique_candidates": len(candidates),
            "duplicates": sum(m["duplicates"] for m in metrics.values()),
            "hard_rejections": sum(m["hard_rejections"] for m in metrics.values()),
            "eligible_jobs": len(accepted),
            "jobs_appended": appended,
            "query_failures": sum(m["failure_count"] for m in metrics.values()),
        },
        "per_query": list(metrics.values()),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    complete = (browser_ok and not any(m["failure_count"] for m in metrics.values())
                and score_exit in (None, 0))
    return (0 if complete else 3), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true",
                      help="print the deterministic plan; no network or writes")
    mode.add_argument("--live", action="store_true", help="perform discovery and write eligible jobs")
    args = parser.parse_args(argv)
    if args.plan_only:
        plan = plan_queries()
        print(json.dumps({"queries": [query.to_dict() for query in plan]}, indent=2))
        print("PLAN ONLY: no LinkedIn requests and no files written", file=sys.stderr)
        return 0
    code, _ = run_live()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
