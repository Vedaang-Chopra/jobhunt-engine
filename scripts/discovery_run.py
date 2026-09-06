#!/usr/bin/env python3
"""Unified discovery orchestrator (master-plan Task 13).

Sources:
  l1          scripts/linkedin_portal_sweep.py        (needs live browser)
  l2          scripts/linkedin_recommended_sweep.py   (needs live browser)
  career_ops  ../career-ops node scan.mjs --quiet
              -> scripts/import_career_ops_scan.py -> scripts/score_jobs_v2.py
  freshness   scripts/freshness_check.py

NOTE ON L1/L2 LINKEDIN SWEEPS: these require a logged-in interactive browser
session and are intentionally NOT cron-scheduled yet. They piggyback on
interactive sessions; when run unattended/headless they are detected and
SKIPPED with a clear 'needs interactive session' log line instead of crashing.

Behavior:
- Each source is wrapped in try/except; per-source status recorded.
- A summary line is appended to tracking/search_runs/search_runs.csv with
  run_id = discovery_<ts> and notes = per-source outcomes.
- Health: failure streaks per source tracked in execution_results/ops/health.json.
  streak >= 2 -> source self-paused (skipped on subsequent runs) and an alert
  line appended to execution_results/ops/alerts.log.
- Lock: .hermes/ops.lock prevents concurrent runs from double-executing.
- --dry-run prints what would run without executing anything.

CLI:
  python scripts/discovery_run.py [--sources l1,l2,career_ops,freshness|all-due] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import re
import subprocess
import sys
import typing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import config_lib

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:
    import config_lib

OPS_DIR = config_lib.path("ops_dir")
HEALTH_JSON = OPS_DIR / "health.json"
ALERTS_LOG = OPS_DIR / "alerts.log"
SEARCH_RUNS_CSV = config_lib.path("search_runs_csv")
LOCK_FILE = REPO / ".hermes" / "ops.lock"

CAREER_OPS_DIR = REPO.parent / "career-ops"

PAUSE_STREAK = 2
ALL_SOURCES = ["l1", "l2", "career_ops", "freshness"]

# On-demand source aliases (daily-rhythm plan Task 1).
SOURCE_ALIASES = {
    "linkedin": ["l1", "l2"],
    "career_ops": ["career_ops"],
    "hiring_posts": ["hiring_posts"],
    "wellfound": ["wellfound"],
    "all": list(ALL_SOURCES),
}

F_TPR_OVERRIDE_ENV = "LINKEDIN_F_TPR_OVERRIDE"

JOBS_CSV = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
CONTACTS_CSV = config_lib.path("contacts_csv")
JD_ACTIVE_DIR = config_lib.path("jd_active_dir")


class LoginWallError(RuntimeError):
    """Raised when a job page requires a logged-in (persistent-profile) browser."""


# ---------------------------------------------------------------------------
# On-demand recency mapping (Task 1)
# ---------------------------------------------------------------------------

def recency_to_seconds(spec: str) -> int:
    """Parse '1h'/'5h'/'24h'/'7d'/arbitrary Nh/Nd into seconds."""
    import re as _re
    m = _re.fullmatch(r"\s*(\d+)\s*([hd])\s*", str(spec))
    if not m:
        raise ValueError(f"invalid recency {spec!r}: expected e.g. 1h/5h/24h/7d")
    n, unit = int(m.group(1)), m.group(2)
    if n <= 0:
        raise ValueError(f"invalid recency {spec!r}: must be positive")
    return n * 3600 if unit == "h" else n * 86400


def f_tpr_for(spec: str) -> str:
    """Map a recency spec to the LinkedIn f_TPR URL param value."""
    return f"r{recency_to_seconds(spec)}"


def resolve_sources(alias: str) -> list[str]:
    alias = (alias or "").strip().lower()
    if alias not in SOURCE_ALIASES:
        raise ValueError(
            f"unknown --source {alias!r}; valid: {sorted(SOURCE_ALIASES)}")
    return list(SOURCE_ALIASES[alias])


# ---------------------------------------------------------------------------
# Single-job ingestion (Task 2)
# ---------------------------------------------------------------------------

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_LOGIN_MARKERS = (
    "authwall", "sign in to continue", "loginwall", "please sign in",
    "log in to continue", "session has expired",
)


def greenhouse_api_url(url: str) -> str | None:
    m = re.search(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if not m:
        return None
    board, jid = m.group(1), m.group(2)
    return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}"


def lever_api_url(url: str) -> str | None:
    m = re.search(r"jobs\.lever\.co/([^/]+)/([^/?#]+)", url)
    if not m:
        return None
    co, jid = m.group(1), m.group(2)
    return f"https://api.lever.co/v0/postings/{co}/{jid}?mode=json"


def _strip_html(html: str) -> str:
    import html as _html
    text = re.sub(r"<[^>]+>", "\n", html)
    text = _html.unescape(text)
    return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def detect_login_wall(status: int, text: str) -> bool:
    if status in (401, 403):
        return True
    head = (text or "")[:4000].lower()
    return any(marker in head for marker in _LOGIN_MARKERS)


def fetch_job_page(url: str) -> dict:
    """Fetch a job posting. Greenhouse/Lever via public JSON APIs; otherwise
    plain requests with login-wall detection (never attempts Playwright login)."""
    import html as _html
    import requests
    api = greenhouse_api_url(url)
    if api:
        r = requests.get(api, timeout=30, headers={"User-Agent": _UA})
        if r.status_code == 404:
            raise RuntimeError(f"greenhouse posting not found: {api}")
        r.raise_for_status()
        j = r.json()
        board = re.search(r"boards\.greenhouse\.io/([^/]+)/", url).group(1)
        return {
            "title": j.get("title") or "",
            "company": board.replace("-", " ").replace("_", " ").title(),
            "url": j.get("absolute_url") or url,
            "location": (j.get("location") or {}).get("name", ""),
            "description": _strip_html(j.get("content") or ""),
            "date_posted": (j.get("updated_at") or "")[:10],
            "company_slug_hint": board,
        }
    api = lever_api_url(url)
    if api:
        r = requests.get(api, timeout=30, headers={"User-Agent": _UA})
        if r.status_code == 404:
            raise RuntimeError(f"lever posting not found: {api}")
        r.raise_for_status()
        j = r.json()
        co = re.search(r"jobs\.lever\.co/([^/]+)/", url).group(1)
        cats = j.get("categories") or {}
        return {
            "title": j.get("text") or "",
            "company": co.replace("-", " ").title(),
            "url": j.get("hostedUrl") or url,
            "location": cats.get("location") or "",
            "description": _strip_html(j.get("description") or ""),
            "date_posted": (j.get("createdAt") and datetime.fromtimestamp(
                j["createdAt"] / 1000, tz=timezone.utc).date().isoformat()) or "",
            "company_slug_hint": co,
        }
    # Generic page fetch with login-wall detection.
    r = requests.get(url, timeout=30, headers={"User-Agent": _UA})
    if detect_login_wall(r.status_code, r.text):
        raise LoginWallError(
            f"{url} is login-walled; needs persistent-profile browser "
            "(not attempting Playwright login)")
    if r.status_code >= 400:
        raise RuntimeError(f"fetch failed HTTP {r.status_code}: {url}")
    # Minimal og-meta extraction.
    def _og(prop: str) -> str:
        m = re.search(
            rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']+)',
            r.text, re.IGNORECASE)
        return _html.unescape(m.group(1)) if m else ""
    host = re.sub(r"^www\.", "", urlparse(url).netloc).split(".")[0]
    return {
        "title": _og("og:title"),
        "company": host.title(),
        "url": url,
        "location": _og("og:job:location") or "",
        "description": _og("og:description") or _strip_html(r.text)[:20000],
        "date_posted": "",
    }


def find_contacts(company_slug: str) -> list[dict]:
    if not CONTACTS_CSV.exists():
        return []
    from discovery_lib import slugify
    hits = []
    with CONTACTS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row.get("name") or ""
            if slugify(row.get("company") or "") == company_slug and name:
                hits.append({
                    "name": name,
                    "role": row.get("role") or "",
                    "linkedin_url": row.get("linkedin_url") or "",
                })
    return hits


def write_jd_file(row: dict, description: str) -> tuple[str, str]:
    """Write JD markdown to active dir. Returns (relative_path, sha256_hex)."""
    import hashlib
    jd_dir = Path(JD_ACTIVE_DIR)
    jd_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(description.encode("utf-8")).hexdigest()
    path = jd_dir / f"{row['job_id']}.md"
    content = (
        f"# {row['title']}\n"
        f"Company: {row['company']}\n"
        f"Source: {row['source']}\n"
        f"URL: {row['job_url']}\n"
        f"Hash: {digest}\n"
        f"Discovered: {row['date_discovered']}\n\n"
        f"## Full Job Description Text\n{description}\n\n---\n")
    path.write_text(content)
    try:
        rel = str(path.relative_to(REPO))
    except ValueError:
        import os as _os
        rel = _os.path.relpath(path, REPO)
    return rel, digest


def ingest(url: str) -> int:
    """Single-job ingestion pipeline. Returns process exit code."""
    print(f"ingest: {url}")
    try:
        raw = fetch_job_page(url)
    except LoginWallError as exc:
        print(f"VERDICT: INGEST BLOCKED — {exc}")
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"VERDICT: FETCH FAILED — {type(exc).__name__}: {exc}")
        return 2

    from discovery_lib import (
        DedupIndex,
        normalize_job,
        normalize_source,
        scrutinize,
    )
    raw.setdefault("url", url)
    try:
        row = normalize_job(raw)
    except ValueError as exc:
        print(f"VERDICT: NORMALIZE FAILED — {exc}")
        return 2
    # Source provenance: derive from the URL when normalize_job could not
    # (non-ATS hosts). The generic fetch path pulled the page directly, so an
    # unmatched host is a company career page; "other" is the last resort.
    row["source"] = row.get("source") or normalize_source(
        url, fallback="company_page") or "other"

    # Scrutiny gate on description-bearing view of the row.
    verdict, flags = scrutinize({**row, "description": raw.get("description", "")})

    # Dedup check before any write.
    idx = DedupIndex()
    if JOBS_CSV.exists():
        with JOBS_CSV.open(newline="", encoding="utf-8") as fh:
            for existing in csv.DictReader(fh):
                idx.add(existing)
    dup, matched = idx.seen_before(row)
    if dup:
        mid = (matched or {}).get("job_id", "?")
        print(f"VERDICT: DUPLICATE — already tracked as job_id={mid} "
              f"(no new row written)")
        print(f"  flags: {flags or ['dup_existing_row']}")
        return 0

    if verdict != "accept":
        print(f"VERDICT: REJECTED by scrutiny gate — flags={flags}")
        return 2

    # Build stable job_id, write JD file, then the row.
    sys.path.insert(0, str(REPO / "scripts"))
    from linkedin_portal_sweep import append_jobs  # reuse canonical writer
    from discovery_lib import extract_ats_id as _ats_id, slugify as _slug
    desc = raw.get("description", "")
    sid = row.get("source_id") or _ats_id(row["job_url"]) or \
        __import__("hashlib").sha256(desc.encode()).hexdigest()[:12]
    row["job_id"] = f"{_slug(row['company'])}_{_slug(row['title'])}_{sid}"
    rel_path, digest = write_jd_file(row, desc)
    row["full_description_hash"] = digest
    row["description_file"] = rel_path
    append_jobs([row], str(JOBS_CSV))

    # Score via score_jobs_v2 config.
    code, out = run_cmd([sys.executable, "scripts/score_jobs_v2.py"], REPO)
    if code != 0:
        print(f"WARN: score_jobs_v2 exit={code}: {out[-200:]}")

    # Re-read scored row + contacts verdict.
    scored = {}
    if JOBS_CSV.exists():
        with JOBS_CSV.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("job_id") == row["job_id"]:
                    scored = r
                    break
    tier = scored.get("opportunity_level") or scored.get("fit_tier") or "unscored"
    priority = scored.get("priority_v2") or "?"
    action = scored.get("recommended_action") or ""
    print(f"VERDICT: ACCEPT — job_id={row['job_id']}")
    print(f"  title:    {row['title']}")
    print(f"  company:  {row['company']}  location: {row['location']}")
    print(f"  posted:   {row['date_posted'] or '?'}  discovered: {row['date_discovered']}")
    print(f"  tier:     {tier}  priority_v2={priority}  action={action}")
    print(f"  flags:    {flags or 'none'}")
    print(f"  jd_file:  {rel_path}")
    contacts = find_contacts(row["company_slug"])
    if contacts:
        print(f"  contacts at {row['company']} ({len(contacts)}):")
        for c in contacts[:5]:
            print(f"    - {c['name']} ({c['role']}) {c['linkedin_url']}")
    else:
        print(f"  contacts: none tracked at {row['company']}")
    return 0




def _headless() -> bool:
    """Heuristic: are we running unattended (no interactive user browser)?"""
    return (
        not sys.stdout.isatty()
        or bool(os.environ.get("HERMES_UNATTENDED"))
        or bool(os.environ.get("CI"))
    )


def load_health() -> dict:
    if HEALTH_JSON.exists():
        try:
            return json.loads(HEALTH_JSON.read_text())
        except Exception:
            pass
    return {}


def save_health(health: dict) -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    HEALTH_JSON.write_text(json.dumps(health, indent=2, sort_keys=True))


def update_health(source: str, failed: bool) -> dict:
    """Update failure streak for one source; self-pause at >= PAUSE_STREAK."""
    health = load_health()
    entry = health.get(source) or {"failure_streak": 0, "status": "active"}
    streak = int(entry.get("failure_streak") or 0)
    if failed:
        streak += 1
    else:
        streak = 0
    status = "self-paused" if streak >= PAUSE_STREAK else "active"
    entry.update({
        "failure_streak": streak,
        "status": status,
        "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_result": "fail" if failed else "ok",
    })
    health[source] = entry
    save_health(health)
    if status == "self-paused":
        alert(f"'{source}' failed {streak}x consecutively — self-paused "
              f"(reset by editing {HEALTH_JSON}).")
    return entry


def alert(message: str) -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ALERTS_LOG.open("a") as f:
        f.write(f"{ts} ALERT {message}\n")
    print(f"[ALERT] {message}")


def run_cmd(cmd: list[str], cwd: Path, extra_env: dict | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([str(c) for c in cmd], cwd=str(cwd),
                       capture_output=True, text=True, env=env)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def run_source(name: str, dry: bool, recency: str | None = None) -> tuple[str, str]:
    """Run one source. Returns (status, note). status: ok|fail|skip."""
    extra_env = {}
    if recency:
        extra_env[F_TPR_OVERRIDE_ENV] = f_tpr_for(recency)
    try:
        if name == "l1":
            if _headless():
                return "skip", ("l1 linkedin_portal_sweep needs interactive "
                                "session (logged-in browser); skipped")
            cmd = [sys.executable, "scripts/linkedin_portal_sweep.py", "--live"]
        elif name == "l2":
            if _headless():
                return "skip", ("l2 linkedin_recommended_sweep needs "
                                "interactive session (logged-in browser); skipped")
            cmd = [sys.executable, "scripts/linkedin_recommended_sweep.py",
                   "--live"]
        elif name == "career_ops":
            if dry:
                pass
            else:
                if not CAREER_OPS_DIR.exists():
                    raise FileNotFoundError(
                        f"sibling scanner dir not found: {CAREER_OPS_DIR}")
                code, out = run_cmd(["node", "scan.mjs", "--quiet"],
                                    CAREER_OPS_DIR)
                if code != 0:
                    raise RuntimeError(f"node scan.mjs exit={code}: {out[-400:]}")
                code, out = run_cmd([sys.executable,
                                     "scripts/import_career_ops_scan.py"], REPO)
                if code != 0:
                    raise RuntimeError(f"import_career_ops_scan exit={code}: {out[-400:]}")
                code, out = run_cmd([sys.executable, "scripts/score_jobs_v2.py"],
                                    REPO)
                if code != 0:
                    raise RuntimeError(f"score_jobs_v2 exit={code}: {out[-400:]}")
            cmd = ["node ../career-ops/scan.mjs --quiet -> import_career_ops_scan.py -> score_jobs_v2.py"]
        elif name == "hiring_posts":
            # Existing hiring-post pipeline: poster fast-path queue builder.
            # Default (dry) mode rebuilds connection_requests.csv; sends happen
            # only via the separate --live path with its daily cap.
            if not dry:
                code, out = run_cmd(
                    [sys.executable, "scripts/poster_connect_sweep.py"], REPO)
                if code != 0:
                    raise RuntimeError(f"poster_connect_sweep exit={code}: {out[-400:]}")
            cmd = ["poster_connect_sweep.py (queue build; sends stay capped/live-only)"]
        elif name == "wellfound":
            # Existing daily crawler script.
            if not dry:
                wf = config_lib.path("wellfound_crawler")
                if not wf.exists():
                    raise FileNotFoundError(f"wellfound crawler not found: {wf}")
                code, out = run_cmd([sys.executable, str(wf)], REPO)
                if code != 0:
                    raise RuntimeError(f"wellfound_crawler exit={code}: {out[-400:]}")
            cmd = ["job_research/scripts/wellfound_crawler.py"]
        elif name == "freshness":
            if dry:
                pass
            else:
                # Registry counts drift as freshness expires rows — reseed
                # BEFORE verifying so spot-checks always match reality.
                code, out = run_cmd([sys.executable, "scripts/referral_lib.py"],
                                    REPO)
                if code != 0:
                    raise RuntimeError(
                        f"registry reseed exit={code}: {out[-400:]}")
                code, out = run_cmd([sys.executable, "scripts/freshness_check.py",
                                     "--live"], REPO)
                if code != 0:
                    raise RuntimeError(f"freshness_check exit={code}: {out[-400:]}")
            cmd = ["referral_lib.py reseed -> freshness_check.py --live"]
        else:
            return "fail", f"unknown source '{name}'"
        return "ok", " ".join(cmd)
    except Exception as exc:  # noqa: BLE001 - per-source isolation required
        return "fail", f"{type(exc).__name__}: {exc}"


def append_search_run(run_id: str, sources: list[str], outcomes: dict) -> None:
    SEARCH_RUNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    new_file = not SEARCH_RUNS_CSV.exists()
    notes = "; ".join(f"{s}={outcomes[s][0]}:{outcomes[s][1][:120]}"
                      for s in sources)
    import csv as _csv
    with SEARCH_RUNS_CSV.open("a", newline="") as f:
        w = _csv.writer(f)
        if new_file:
            w.writerow(["run_id,date,sources,queries,total_scanned,"
                        "new_jobs_found,duplicates_skipped,strong_fits,notes"])
        w.writerow([run_id, datetime.now().date().isoformat(),
                    ",".join(sources), "", "", "", "", "", notes])


class OpsLock:
    """Advisory lock via .hermes/ops.lock so concurrent runs don't overlap."""

    def __init__(self):
        self.fh: typing.TextIO = None  # type: ignore[assignment]

    def __enter__(self):
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.fh = LOCK_FILE.open("w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pid = ""
            try:
                pid = LOCK_FILE.read_text()[:40]
            except OSError:
                pass
            raise SystemExit(
                f"another discovery run holds {LOCK_FILE} ({pid}); aborting.")
        self.fh.write(f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}\n")
        self.fh.flush()
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        finally:
            self.fh.close()
        return False


def _tier_summary(min_tier: str) -> None:
    """Read-only printout: open jobs with fit_tier at or above ``min_tier``."""
    rank = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
    cutoff = rank.get((min_tier or "").upper())
    if cutoff is None:
        return
    import csv as _csv
    path = JOBS_CSV
    if not path.is_file():
        print(f"tier summary: {path} not found")
        return
    hits = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            tier = (row.get("fit_tier") or "").strip().upper()
            status = (row.get("status") or "").strip().lower()
            if tier in rank and rank[tier] <= cutoff and \
                    status not in {"rejected", "withdrawn", "closed"}:
                hits.append(row)
    print(f"\ntier summary (fit_tier >= {min_tier.upper()}): "
          f"{len(hits)} open job(s)")
    for row in hits[:10]:
        print(f"  [{row.get('fit_tier')}] {row.get('fit_score')} "
              f"{row.get('company')} — {row.get('title', '')[:70]} "
              f"({row.get('job_id', '')})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default="all-due",
                    help=f"comma list or all-due ({','.join(ALL_SOURCES)})")
    ap.add_argument("--recency", default=None,
                    help="on-demand freshness window: 1h/5h/24h/7d or Nh/Nd; "
                         "overrides saved-search f_TPR filters and runs now")
    ap.add_argument("--source", default=None,
                    help="on-demand single source: linkedin|career_ops|"
                         "hiring_posts|wellfound|all")
    ap.add_argument("--ingest", default=None, metavar="URL_OR_JOB_ID",
                    help="single-job ingestion: fetch -> normalize -> dedup -> "
                         "scrutiny -> score -> write row + JD file -> verdict")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-tier", default=None,
                    help="after planning/running, print a read-only summary "
                         "of open jobs with fit_tier at or above this tier "
                         "(A best … E worst); no behavior change")
    args = ap.parse_args(argv)

    if args.ingest:
        return ingest(args.ingest)

    recency = None
    if args.recency:
        try:
            recency_to_seconds(args.recency)  # validate early
        except ValueError as exc:
            ap.error(str(exc))
        recency = args.recency
        # Export so the agent-driven L1/L2 sweeps inherit the override.
        os.environ[F_TPR_OVERRIDE_ENV] = f_tpr_for(recency)

    if args.source is not None:
        try:
            sources = resolve_sources(args.source)
        except ValueError as exc:
            ap.error(str(exc))
    elif args.sources.strip() == "all-due":
        sources = list(ALL_SOURCES)
    else:
        requested = [s.strip() for s in args.sources.split(",") if s.strip()]
        bad = [s for s in requested if s not in ALL_SOURCES]
        if bad:
            ap.error(f"unknown source(s) {bad}; valid: {ALL_SOURCES}")
        sources = [s for s in ALL_SOURCES if s in requested]

    print(f"discovery_run plan ({'DRY-RUN' if args.dry_run else 'LIVE'}):")
    if recency:
        print(f"  - recency override: --recency {recency} -> "
              f"f_TPR={f_tpr_for(recency)} on all LinkedIn searches")
    health = load_health()

    # Skip planning for self-paused sources unless explicitly requested.
    effective = []
    for s in sources:
        h = health.get(s) or {}
        if h.get("status") == "self-paused":
            print(f"  - {s}: SKIPPED self-paused (failure_streak="
                  f"{h.get('failure_streak')})")
        else:
            effective.append(s)

    if args.dry_run:
        for s in effective:
            status, note = run_source(s, dry=True, recency=recency)
            print(f"  - {s}: would run -> {note}")
        print("dry-run: nothing executed.")
        if args.min_tier:
            _tier_summary(args.min_tier)
        return 0

    outcomes: dict[str, tuple[str, str]] = {}
    new_passing_gate = 0
    # Callers that already hold .hermes/ops.lock (e.g. scripts/daily_ops.py)
    # set HERMES_OPS_LOCK_HELD=1 to avoid self-deadlock on re-acquisition.
    import contextlib
    lock_ctx = (contextlib.nullcontext()
                if os.environ.get("HERMES_OPS_LOCK_HELD") else OpsLock())
    with lock_ctx:
        for s in effective:
            print(f"\n=== [{s}] ===")
            status, note = run_source(s, dry=False, recency=recency)
            tail = note[-300:] if status == "fail" else note[:300]
            print(f"[{s}] {status} :: {tail}")
            outcomes[s] = (status, note)
            update_health(s, failed=(status == "fail"))
            for m in re.finditer(r"\bnew=(\d+)", note):
                new_passing_gate += int(m.group(1))

    run_id = f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    append_search_run(run_id, effective, outcomes)
    ok = sum(1 for v in outcomes.values() if v[0] == "ok")
    print(f"\n{run_id}: {ok}/{len(effective)} ok, "
          f"{sum(1 for v in outcomes.values() if v[0] == 'skip')} skipped")
    if recency:
        print(f"new-passing-gate (rows accepted this run): {new_passing_gate}")
    return 0 if all(v[0] == "ok" for v in outcomes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
