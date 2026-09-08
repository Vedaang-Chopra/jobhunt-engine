#!/usr/bin/env python3
"""LinkedIn posts sweep — feed + keyword search, CDP-attached to Chrome.

Drives the user's logged-in Chrome via the DevTools protocol (CDP) using a
local playwright install pointed at --remote-debugging-port. Read-only:
never likes, comments, reposts, or connects.

Modes
-----
feed      Scroll the home feed until ``--stop-dupes`` consecutive already-seen
          hiring posts are extracted (default 5), or ``--max-scrolls`` is hit.
keywords  Run LinkedIn post-search queries (search bar + Posts filter +
          Past-Week recency), scrolling each result set a bounded number of
          times. Query selection adapts: queries that historically yielded
          new posts are tried first (yield stats live in the run-history CSV).

Both modes: extract -> fit-gate -> dedupe against tracking/hiring_posts/
hiring_posts.csv -> append new rows -> log one coverage line to
tracking/search_runs/search_runs.csv.

CLI (main(argv=None) -> int so ui/triggers.py can subprocess it):
    linkedin_posts_sweep.py feed  [--max-scrolls 30] [--stop-dupes 5]
    linkedin_posts_sweep.py keywords [--queries 6]
    linkedin_posts_sweep.py dry-run   # no browser; prints plan + yield stats

Safety mirrors docs rules (06_LINKEDIN_HIRING_POSTS.md): read-only, bounded
scrolls, stop on authwall/CAPTCHA, rate-limit pauses between actions.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
import config_lib

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:
    import config_lib  # noqa: E402

DATA_ROOT = config_lib.data_root()
POSTS_CSV = DATA_ROOT / "tracking" / "hiring_posts" / "hiring_posts.csv"
RUNS_CSV = config_lib.path("search_runs_csv")
KEYWORDS_CSV = DATA_ROOT / "job_research" / "config" / "linkedin_keyword_yields.csv"
EXTRACTOR_JS = REPO / "scripts" / "linkedin_feed_extractor.js"
OUT_DIR = config_lib.path("linkedin_posts_dir")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CDP_URL = "http://localhost:9333"  # automation Chrome; legacy 9222 still probed
FEED_URL = "https://www.linkedin.com/feed/"
POST_SEARCH_URL = ("https://www.linkedin.com/search/results/posts/"
                   "?keywords={kw}&origin=SWITCH_SEARCH_VERTICAL"
                   "&sid=%3BpT")
PAUSE_S = (2.5, 4.5)

DEFAULT_KEYWORDS = {
    # phrase -> weight (higher = tried first when no history exists)
    "we're hiring": 5,
    "join my team": 4,
    "my team is looking": 4,
    "hiring research engineers": 4,
    "looking for ML engineers": 3,
    "building the team": 3,
    "new roles on my team": 3,
    "hiring AI engineers": 3,
    "agentic AI engineer": 2,
    "LLM evaluation hiring": 2,
    "machine learning engineer hiring": 2,
}

POSTS_HEADER = [
    "post_id", "poster_name", "poster_headline", "poster_type", "company",
    "team_or_org", "post_url", "posted_date", "discovered_date",
    "roles_mentioned", "application_url", "connection_degree",
    "shared_context", "priority", "role_family", "status", "notes",
]

# --------------------------------------------------------------------- pure


def load_seen_posts(posts_csv: Path = POSTS_CSV) -> set[str]:
    """Keys for every post already tracked: post_url, urn, poster+roles+date."""
    seen: set[str] = set()
    if not posts_csv.exists():
        return seen
    with open(posts_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            url = (row.get("post_url") or "").strip().rstrip("/")
            if url:
                seen.add(url.lower())
            notes_urn = ""
            notes = row.get("notes") or ""
            if "urn:" in notes:
                notes_urn = notes.split("urn:")[-1].split()[0].strip(".,;")
            if notes_urn:
                seen.add(f"urn:{notes_urn}".lower())
            key = _fuzzy_key(row.get("poster_name"), row.get("roles_mentioned"),
                             row.get("posted_date"))
            if key:
                seen.add(key)
    return seen


def _fuzzy_key(poster, roles, date) -> str:
    return "|".join(str(x or "").strip().lower() for x in (poster, roles, date))


def post_key(post: dict) -> list[str]:
    """All dedupe keys a freshly-extracted post produces."""
    keys = []
    url = (post.get("post_url") or "").strip().rstrip("/")
    if url:
        keys.append(url.lower())
    if post.get("urn"):
        keys.append(f"urn:{post['urn']}".lower())
    fuzzy = _fuzzy_key(post.get("poster"), post.get("roles_mentioned"),
                       post.get("posted_date"))
    if fuzzy.strip("|"):
        keys.append(fuzzy)
    return keys


def split_new_and_dup_posts(extracted: list[dict],
                            seen: set[str]) -> tuple[list[dict], list[dict]]:
    """Partition extracted posts into genuinely-new vs already-seen.

    A post counts as new only if NONE of its keys were seen before. The
    first new post's keys are folded into ``seen`` so repeated cards inside
    one extraction batch don't count as multiple new posts.
    """
    new, dups = [], []
    for p in extracted:
        keys = [k for k in post_key(p) if k.strip("|")]
        if any(k in seen for k in keys):
            dups.append(p)
            continue
        new.append(p)
        seen.update(keys)
    return new, dups


def classify_poster(headline: str) -> str:
    h = (headline or "").lower()
    if any(w in h for w in ("recruiter", "talent acquisition", "talent partner",
                            "sourcing", "recruiting")):
        return "recruiter"
    if any(w in h for w in ("manager", "director", "vp ", "founder", "ceo",
                            "cto", "head of")):
        return "hiring_manager"
    return "engineer_researcher"


def classify_priority(poster_type: str) -> str:
    return "high" if poster_type in ("recruiter", "hiring_manager") else "normal"


ROLE_FAMILY_HINTS = [
    ("agentic", "agentic_ai"),
    ("agent", "agentic_ai"),
    ("multi-agent", "agentic_ai"),
    ("rag", "agentic_ai"),
    ("langgraph", "agentic_ai"),
    ("distributed training", "ml_training_arch"),
    ("pre-training", "ml_training_arch"),
    ("training engineer", "ml_training_arch"),
    ("training infra", "ml_training_arch"),
    ("gpu", "ml_training_arch"),
    ("fsdp", "ml_training_arch"),
    ("evaluation", "eval_inference"),
    ("evals", "eval_inference"),
    ("benchmark", "eval_inference"),
    ("vllm", "eval_inference"),
    ("inference", "eval_inference"),
    ("red team", "ai_security"),
    ("adversarial", "ai_security"),
    ("applied scientist", "applied_ml"),
    ("machine learning engineer", "applied_ml"),
    ("research engineer", "research_engineer"),
]


def classify_role_family(text: str) -> str:
    t = (text or "").lower()
    for hint, family in ROLE_FAMILY_HINTS:
        if hint in t:
            return family
    return "other"


def to_post_row(post: dict, discovered_date: str, source_note: str) -> dict:
    """Extraction dict -> canonical hiring_posts.csv row."""
    headline = post.get("headline", "")[:300]
    roles = (post.get("roles_mentioned") or "").strip()
    body = (post.get("body") or "")[:400]
    poster_type = classify_poster(headline)
    text_for_family = " ".join((headline, roles, body))
    return {
        "post_id": _post_id(post, discovered_date),
        "poster_name": post.get("poster", ""),
        "poster_headline": headline,
        "poster_type": poster_type,
        "company": (post.get("company") or "").strip(),
        "team_or_org": "",
        "post_url": post.get("posterUrl") or post.get("post_url", ""),
        "posted_date": post.get("posted_date", ""),
        "discovered_date": discovered_date,
        "roles_mentioned": roles,
        "application_url": post.get("link_url", "") or post.get("application_url", ""),
        "connection_degree": post.get("degree", ""),
        "shared_context": "",
        "priority": classify_priority(poster_type),
        "role_family": classify_role_family(text_for_family),
        "status": "new",
        "notes": f"{source_note}; urn:{post.get('urn', '')}; {body[:160]}".strip("; "),
    }


def _post_id(post: dict, discovered_date: str) -> str:
    slug_src = (post.get("company") or post.get("poster") or "post").strip()
    slug = "".join(c if c.isalnum() else "_" for c in slug_src.lower())[:40].strip("_")
    tail = (post.get("urn") or post.get("posterUrl") or post.get("post_url") or "x")
    tail = "".join(c for c in tail if c.isalnum())[-8:] or "x"
    return f"{slug}_{discovered_date}_{tail}"


def append_rows(rows: list[dict], posts_csv: Path = POSTS_CSV) -> int:
    """Append rows to the canonical CSV (header created if missing)."""
    if not rows:
        return 0
    header_exists = posts_csv.exists() and posts_csv.stat().st_size > 0
    with open(posts_csv, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=POSTS_HEADER)
        if not header_exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in POSTS_HEADER})
    return len(rows)


def log_run(run_id: str, sources: str, detail: str, scanned: int,
            new: int, dups: int, status: str,
            runs_csv: Path = RUNS_CSV) -> None:
    """Append one run row in the CANONICAL 9-col search_runs schema.

    The canonical schema (search_runs.csv, shared with discovery_lib and
    wellfound_crawler) is:
        run_id,date,sources,queries,total_scanned,new_jobs_found,
        duplicates_skipped,strong_fits,notes
    Earlier this wrote a private 7/8-col schema into the same file, which
    made pandas fail to parse the whole CSV in ui.data.
    """
    runs_csv.parent.mkdir(parents=True, exist_ok=True)
    header_missing = not runs_csv.exists() or runs_csv.stat().st_size == 0
    with open(runs_csv, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if header_missing:
            w.writerow(["run_id", "date", "sources", "queries",
                        "total_scanned", "new_jobs_found",
                        "duplicates_skipped", "strong_fits", "notes"])
        w.writerow([run_id, datetime.now().strftime("%Y-%m-%d"), sources,
                    "", scanned, new, dups, 0,
                    f"{detail}; status={status}"])


# ------------------------------------------------------- keyword adaptation

QUERIES_CFG = DATA_ROOT / "job_research" / "config" / "search_queries.yaml"


def load_search_queries() -> dict:
    """Load surface-separated query config (search_queries.yaml).

    Returns {} when the file is absent so callers fall back to defaults.
    """
    try:
        import yaml
        with open(QUERIES_CFG, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:  # noqa: BLE001 - config optional, defaults still work
        return {}


def build_composite_post_queries(cfg: dict | None = None,
                                 limit: int = 12,
                                 yields: dict[str, dict] | None = None,
                                 ) -> list[str]:
    """Cross-product of hiring-intent phrases x domain keywords.

    Posts search ranks differently from Jobs: people write "we're hiring LLM
    engineers", never "research engineer post-training". Generates composite
    queries, then applies the same yield-based rotation used for base
    keywords (prefer untried and historically high-yield composites).
    """
    cfg = cfg if cfg is not None else load_search_queries()
    intents = cfg.get("POST_INTENT_PHRASES") or []
    domains = cfg.get("POST_DOMAIN_KEYWORDS") or []
    cap = int(cfg.get("POST_COMPOSITE_LIMIT") or limit)
    if not intents or not domains:
        return []

    composites = [f"{i} {d}" for i in intents for d in domains]
    yields = yields or {}
    scored: list[tuple[float, str]] = []
    for q in composites:
        s = yields.get(q.lower())
        if s and s["runs"] >= 2:
            score = s["new"] / max(s["runs"], 1)
        elif s:
            score = 1.0
        else:
            score = 1.25  # explore bonus for untried composites
        scored.append((-score, q))
    scored.sort()
    return [q for _, q in scored[:cap]]


def load_keyword_yields(yields_csv: Path = KEYWORDS_CSV) -> dict[str, dict]:
    """query -> {'runs': int, 'new': int} aggregated across past runs."""
    stats: dict[str, dict] = {}
    if not yields_csv.exists():
        return stats
    with open(yields_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            q = (row.get("query") or "").strip().lower()
            if not q:
                continue
            s = stats.setdefault(q, {"runs": 0, "new": 0})
            s["runs"] += int(row.get("runs") or 1)
            s["new"] += int(row.get("new") or 0)
    return stats


def select_queries(limit: int, yields: dict[str, dict],
                   base_keywords: dict[str, int] | None = None) -> list[str]:
    """Pick the next ``limit`` queries.

    Score = historical yield-per-run when the query has been tried at least
    twice; otherwise its static default weight. Explores untried queries
    before re-running low-yield ones (epsilon-style rotation).
    """
    base = base_keywords or DEFAULT_KEYWORDS
    scored: list[tuple[float, str]] = []
    for q, default_w in base.items():
        s = yields.get(q.lower())
        if s and s["runs"] >= 2:
            score = s["new"] / max(s["runs"], 1)
        elif s:
            score = float(default_w)  # give new queries a second chance
        else:
            score = float(default_w) + 0.25  # slight explore bonus
        scored.append((-score, q))
    scored.sort()
    return [q for _, q in scored[:limit]]


def record_keyword_yields(per_query_new: dict[str, int],
                          yields_csv: Path = KEYWORDS_CSV) -> None:
    """Append one line per query run: query, runs, new."""
    if not per_query_new:
        return
    yields_csv.parent.mkdir(parents=True, exist_ok=True)
    header_missing = not yields_csv.exists() or yields_csv.stat().st_size == 0
    with open(yields_csv, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if header_missing:
            w.writerow(["date", "query", "runs", "new"])
        today = datetime.now().strftime("%Y-%m-%d")
        for q, n in per_query_new.items():
            w.writerow([today, q, 1, int(n)])


# ---------------------------------------------------------------- browser

def _pause() -> None:
    time.sleep(random.uniform(*PAUSE_S))


class BrowserSession:
    """Playwright chromium attached to the shared logged-in Chrome.

    Resolution order (see browser_session_lib): CDP on :9333 (automation
    Chrome), then legacy CDP ports (9222, only when /json/version works),
    then a persistent context on the job-hunt profile.
    """

    def __init__(self, cdp_url: str = "") -> None:
        from browser_session_lib import open_logged_in_session

        session = open_logged_in_session()
        # Adopt the resolved session; reuse its close() semantics.
        self._pw = session._pw
        self.browser = session.browser  # None in persistent mode
        self.mode = session.mode
        self.page = session.page

    def close(self) -> None:
        try:
            if self.mode == "persistent":
                self.page.context.close()
            else:
                self.browser.close()  # drops our CDP connection only
        except Exception:  # noqa: BLE001
            pass
        try:
            self._pw.stop()
        except Exception:  # noqa: BLE001
            pass

    # -- shared helpers ----------------------------------------------------
    def _extract(self) -> list[dict]:
        js = EXTRACTOR_JS.read_text(encoding="utf-8")
        raw = self.page.evaluate(js)
        return [p for p in (raw or []) if isinstance(p, dict)]

    def check_wall(self) -> str | None:
        content = (self.page.content() or "").lower()
        if "authwall" in content[:4000] or "captcha" in content:
            return "authwall/captcha detected — stopping (read-only safety rule)"
        return None

    def scroll_main(self, rounds: int, round_pause: float = 1.6) -> None:
        for _ in range(rounds):
            self.page.evaluate(
                "() => { const m = document.querySelector('main') || "
                "document.scrollingElement; m.scrollBy(0, 2200); }")
            time.sleep(round_pause)


# ------------------------------------------------------------ feed mode

def run_feed(session: BrowserSession, max_scrolls: int, stop_dupes: int,
             seen: set[str]) -> tuple[list[dict], list[dict]]:
    """Scroll the feed; extraction happens every few scrolls.

    Stops early once ``stop_dupes`` consecutive already-seen posts appear
    (the feed has caught up with previously-swept territory).
    """
    session.page.goto(FEED_URL, wait_until="domcontentloaded")
    _pause()
    new_all: list[dict] = []
    dup_all: list[dict] = []
    consecutive_dups = 0
    scrolls_done = 0
    while scrolls_done < max_scrolls:
        session.scroll_main(3)
        scrolls_done += 3
        wall = session.check_wall()
        if wall:
            print(f"  !! {wall}")
            break
        extracted = session._extract()
        fresh, dups = split_new_and_dup_posts(extracted, seen)
        new_all.extend(fresh)
        dup_all.extend(dups)
        print(f"  scrolls={scrolls_done}/{max_scrolls} extracted={len(extracted)} "
              f"new={len(fresh)} dup={len(dups)}")
        if not fresh:
            consecutive_dups += len(dups)
        else:
            consecutive_dups = 0
        if consecutive_dups >= stop_dupes:
            print(f"  stop: {consecutive_dups} consecutive duplicates")
            break
        _pause()
    return new_all, dup_all


# --------------------------------------------------------- keywords mode

def run_keywords(session: BrowserSession, queries: list[str], seen: set[str],
                 max_scroll_rounds_per_query: int = 6) -> tuple[list[dict],
                                                               dict[str, int],
                                                               list[dict]]:
    """Run each query through LinkedIn post search; returns (new, per-query
    new-counts, all dups)."""
    new_all: list[dict] = []
    dup_all: list[dict] = []
    per_query_new: dict[str, int] = {}
    for qi, q in enumerate(queries, 1):
        kw = quote_plus(q)
        url = POST_SEARCH_URL.format(kw=kw)
        session.page.goto(url, wait_until="domcontentloaded")
        _pause()
        wall = session.check_wall()
        if wall:
            print(f"  !! {wall}")
            break
        extracted = session._extract()
        fresh, dups = split_new_and_dup_posts(extracted, seen)
        new_all.extend(fresh)
        dup_all.extend(dups)
        per_query_new[q] = len(fresh)
        print(f"  [{qi}/{len(queries)}] {q!r}: scanned={len(extracted)} "
              f"new={len(fresh)}")
        for r in range(max_scroll_rounds_per_query - 1):
            session.scroll_main(1)
            wall = session.check_wall()
            if wall:
                break
            extracted = session._extract()
            f2, d2 = split_new_and_dup_posts(extracted, seen)
            new_all.extend(f2)
            dup_all.extend(d2)
            per_query_new[q] += len(f2)
            if not f2:
                break  # results exhausted for this query
        _pause()
    return new_all, per_query_new, dup_all


# ------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LinkedIn posts sweep (feed/keywords)")
    sub = ap.add_subparsers(dest="mode", required=True)
    p_feed = sub.add_parser("feed", help="sweep the home feed for hiring posts")
    p_feed.add_argument("--max-scrolls", type=int, default=30)
    p_feed.add_argument("--stop-dupes", type=int, default=5)
    p_kw = sub.add_parser("keywords", help="run adaptive keyword searches")
    p_kw.add_argument("--queries", type=int, default=6)
    sub.add_parser("dry-run", help="print plan + keyword-yield stats, no browser")

    args = ap.parse_args(argv)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    yields = load_keyword_yields()
    cfg = load_search_queries()
    if args.mode == "dry-run":
        plan = build_composite_post_queries(cfg, limit=6, yields=yields)
        if not plan:   # fall back to base keywords if config missing/empty
            plan = select_queries(6, yields)
        print(json.dumps({
            "mode": "dry-run",
            "posts_csv": str(POSTS_CSV),
            "tracked_posts": len(load_seen_posts()),
            "planned_keyword_queries": plan,
            "keyword_yield_stats": {
                q: s for q, s in sorted(yields.items(), key=lambda kv: -kv[1]["new"])[:15]
            },
        }, indent=2))
        return 0

    seen = load_seen_posts()
    session = BrowserSession()
    started = datetime.now().strftime("%Y%m%d_%H%M")
    try:
        if args.mode == "feed":
            new, dups = run_feed(session, args.max_scrolls, args.stop_dupes, seen)
            rows = [to_post_row(p, discovered_date=datetime.now().strftime("%Y-%m-%d"),
                                source_note=f"feed_sweep_{started}") for p in new]
            append_rows(rows, POSTS_CSV)
            log_run(f"lpf_{ts}", "linkedin_feed_cdp", "feed sweep",
                    len(new) + len(dups), len(new), len(dups), "ok")
            out = OUT_DIR / f"feed_{ts}.json"
            out.write_text(json.dumps({"new": new, "dupes": len(dups)},
                                      indent=2, default=str))
            print(f"DONE feed: new={len(new)} dup={len(dups)} -> {out}")
        else:
            # Posts keyword sweep: use composite queries from config
            queries = build_composite_post_queries(cfg, limit=args.queries, yields=yields)
            if not queries:   # fall back to base keywords if config missing/empty
                queries = select_queries(args.queries, yields)
            print(f"selected queries: {queries}")
            new, per_query_new, dups = run_keywords(session, queries, seen)
            rows = [to_post_row(p, discovered_date=datetime.now().strftime("%Y-%m-%d"),
                                source_note=f"keyword_sweep_{started}") for p in new]
            append_rows(rows, POSTS_CSV)
            record_keyword_yields(per_query_new, KEYWORDS_CSV)
            log_run(f"lpk_{ts}", "linkedin_post_search_cdp",
                    "; ".join(f"{q}:{n}" for q, n in per_query_new.items()),
                    sum(per_query_new.values()) + len(dups), len(new), len(dups),
                    "ok")
            out = OUT_DIR / f"keywords_{ts}.json"
            out.write_text(json.dumps({"queries": per_query_new, "new": new,
                                       "dupes": len(dups)}, indent=2, default=str))
            print(f"DONE keywords: new={len(new)} -> {out}")
    finally:
        session.close()
    return 0


def per_query_new(d: dict) -> dict:
    return d


if __name__ == "__main__":
    sys.exit(main())

