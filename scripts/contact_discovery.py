#!/usr/bin/env python3
"""Contact discovery CLI (Task 9).

Usage:
  python scripts/contact_discovery.py --company <slug-or-name> [--top N]
      [--live-linkedin] [--role-keywords "..."]

Ranks people to contact for one company (or across all registry companies
when --company is omitted, using --top N as a per-company cap).
Sources in trust order: hiring-post posters, existing contacts,
[optional live LinkedIn], fallback web search.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import referral_lib as rl


_TITLE_WORDS = {"talent", "acquisition", "recruiter", "recruiting", "partner",
                "manager", "sourcer", "hiring", "linkedin", "jobs", "careers"}


def _looks_like_person(name):
    words = name.replace("-", " ").split()
    if not 2 <= len(words) <= 4:
        return False
    return not any(w.lower() in _TITLE_WORDS for w in words)


def _default_web_search_fn(query):
    """Fallback web search via the Hermes web_search tool, if available."""
    try:
        from hermes_tools import web_search as _ws  # type: ignore
    except Exception:
        return []
    try:
        data = _ws(query, limit=5)
    except Exception:
        return []
    out = []
    for r in data.get("data", {}).get("web", []):
        title = (r.get("title") or "").strip()
        # crude name extraction: "Name - Role at Company | LinkedIn"
        name = title.split(" - ")[0].split(" | ")[0].split(" – ")[0].strip()
        if not name or len(name) > 60 or not _looks_like_person(name):
            continue
        out.append({"name": name, "evidence": [r.get("url") or query]})
    return out


def format_row(c):
    return (f"  {c['score']:>3}  {c['name']:<28} "
            f"[{c.get('source', '')}/"
            f"{c.get('poster_type') or c.get('relationship') or '-'}]  "
            f"{c.get('reason_to_contact', '')}")


def main():
    ap = argparse.ArgumentParser(description="Ranked contact discovery")
    ap.add_argument("--company", help="company slug or name (registry-resolved)")
    ap.add_argument("--top", type=int, default=10,
                    help="max contacts per company (default 10)")
    ap.add_argument("--role-keywords", default="",
                    help="team/role keywords for LinkedIn/web queries")
    ap.add_argument("--live-linkedin", action="store_true",
                    help="enable live LinkedIn people search via browser_fn")
    args = ap.parse_args()

    web_fn = _default_web_search_fn

    if args.company:
        companies = [args.company]
    else:
        rows, _ = rl.read_registry(str(rl.DEFAULT_REGISTRY_PATH))
        companies = [r["company_slug"] for r in rows if r.get("status") == "active"]

    any_result = False
    for slug in companies:
        ranked = rl.discover_contacts(
            slug, live_linkedin=args.live_linkedin,
            browser_fn=None,  # wire Playwright MCP browser_fn externally
            web_search_fn=web_fn, role_keywords=args.role_keywords,
            top=args.top)
        if not ranked:
            continue
        any_result = True
        print(f"\n=== {slug} ===")
        for c in ranked:
            print(format_row(c))

    if not any_result:
        print("no candidates found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
