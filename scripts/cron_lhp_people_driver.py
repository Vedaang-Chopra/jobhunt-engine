#!/usr/bin/env python3
"""LinkedIn feed pass + people searches via the canonical BrowserSessionManager.

Migrated 2026-08-26 from raw websocket CDP onto browser_session_lib — this
driver no longer opens its own DevTools socket; every browser access goes
through the shared automation Chrome on :9333 like all other sweeps.
"""
import json, sys, time

from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent))
from browser_session_lib import (
    open_logged_in_session,
    AUTHENTICATED,
    AUTH_REQUIRED,
)

REPO = str(_Path(__file__).resolve().parents[1])
EXTRACTOR = open(f"{REPO}/scripts/linkedin_feed_extractor.js").read()


def feed_pass(page):
    page.goto("https://www.linkedin.com/feed/", timeout=45000)
    time.sleep(3)
    if "/login" in page.url or "authwall" in page.url:
        print("AUTH_REQUIRED")
        return None
    for i in range(10):
        page.evaluate("() => { const m = document.querySelector('main'); if (m) m.scrollBy(0, 2000); }")
        time.sleep(1.5)
    posts = page.evaluate(EXTRACTOR)
    return posts


def people_search(page, url):
    page.goto(url, timeout=45000)
    time.sleep(3)
    if "/login" in page.url or "authwall" in page.url:
        return {"url": url, "login_wall": True, "people": []}
    people = page.evaluate("""
() => {
  const out = [];
  document.querySelectorAll('div.entity-result, li.reusable-search__result-container, div.reusable-search__result-container').forEach(r => {
    const a = r.querySelector('a[href*="/in/"]');
    if (!a) return;
    const name = (r.querySelector('.entity-result__title-text a span[aria-hidden=\\"true\\"], .entity-result__title-line a span[aria-hidden=\\"true\\"]') || {}).textContent || a.textContent;
    name = (name || '').trim().split('\\n')[0];
    const titleEl = r.querySelector('.entity-result__primary-subtitle');
    const metaEl = r.querySelector('.entity-result__secondary-subtitle');
    if (!name) return;
    out.push({name, title: titleEl ? titleEl.textContent.trim() : '', location: metaEl ? metaEl.textContent.trim() : '', url: a.href.split('?')[0]});
  });
  return out.slice(0, 12);
}
""")
    return {"url": url, "login_wall": False, "people": people}


def main():
    with open_logged_in_session(source="cron_lhp_people_driver") as session:
        state = session.check_auth_state()
        print("[browser] auth:", state)
        if state == AUTH_REQUIRED:
            # Never retry or bypass; stop and surface.
            sys.exit(3)

        posts = feed_pass(session.page)
        queries = [
            'https://www.linkedin.com/search/results/people/?keywords=%22Together%20AI%22&origin=GLOBAL_SEARCH_HEADER',
            'https://www.linkedin.com/search/results/people/?keywords=%22Perplexity%20AI%22&origin=GLOBAL_SEARCH_HEADER',
        ]
        results = [people_search(session.page, u) for u in queries]
        print(json.dumps({"feed_posts": len(posts or []), "people": results}, indent=2)[:4000])


if __name__ == "__main__":
    main()
