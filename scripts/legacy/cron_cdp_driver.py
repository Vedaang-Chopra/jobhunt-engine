#!/usr/bin/env python3
"""Raw-CDP LinkedIn driver: feed pass + people searches over :9333."""
import json, sys, time, urllib.request

BASE = "http://127.0.0.1:9333"
import websocket

REPO = "/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting"

class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=30, suppress_origin=True)
        self.id = 0
    def cmd(self, method, **params):
        self.id += 1
        self.ws.send(json.dumps({"id": self.id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})
    def goto(self, url, wait=4.0):
        self.cmd("Page.navigate", url=url)
        time.sleep(wait)
    def js(self, expr, await_promise=False):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True,
                     awaitPromise=await_promise)
        v = r.get("result", {})
        if v.get("subtype") == "error":
            raise RuntimeError(v.get("description", "js error"))
        return v.get("value")

def open_tab(url="about:blank"):
    req = urllib.request.Request(BASE + "/json/new?" + urllib.parse.quote(url, safe=""), method="PUT")
    t = json.loads(urllib.request.urlopen(req, timeout=10).read())
    c = CDP(t["webSocketDebuggerUrl"])
    c.cmd("Page.enable"); c.cmd("Runtime.enable")
    return t, c

def main_feed():
    import urllib.parse
    t, c = open_tab("https://www.linkedin.com/feed/")
    time.sleep(5)
    cur = c.js("location.href")
    if "/login" in cur or "authwall" in cur:
        print("LOGIN_WALL"); return
    for i in range(10):
        c.js("(() => { const m = document.querySelector('main'); if (m) m.scrollBy(0, 2000); })()")
        time.sleep(1.6)
    ext = open(REPO + "/scripts/linkedin_feed_extractor.js").read()
    posts = c.js("(" + ext + ")()")
    json.dump(posts, open("/tmp/feed_posts.json", "w"))
    print(f"FEED_OK url={cur} posts={len(posts)}")

def main_people(limit=8):
    sys.path.insert(0, REPO + "/scripts")
    from people_sweep import load_preferences, build_queries, cap_queries
    prefs = load_preferences()
    queries = cap_queries(build_queries(prefs), limit)
    PEOPLE_JS = """
(() => {
  const out = [];
  document.querySelectorAll('div.entity-result, li.reusable-search__result-container, div.reusable-search__result-container').forEach(r => {
    const a = r.querySelector('a[href*="/in/"]');
    if (!a) return;
    let name = '';
    const ne = r.querySelector('.entity-result__title-text a span[aria-hidden=\"true\"], .entity-result__title-line a span[aria-hidden=\"true\"]');
    name = ne ? ne.textContent.trim().split('\\n')[0] : a.textContent.trim().split('\\n')[0];
    const titleEl = r.querySelector('.entity-result__primary-subtitle');
    const metaEl = r.querySelector('.entity-result__secondary-subtitle');
    if (!name) return;
    out.push({name, title: titleEl ? titleEl.textContent.trim() : '', location: metaEl ? metaEl.textContent.trim() : '', url: a.href.split('?')[0]});
  });
  return out.slice(0, 12);
})()
"""
    t, c = open_tab()
    results = []
    for q in queries:
        try:
            c.goto(q["url"], wait=4.0)
            cur = c.js("location.href")
            wall = ("/login" in cur) or ("authwall" in cur)
            people = [] if wall else c.js(PEOPLE_JS)
        except Exception as e:
            wall, people, cur = False, [], f"ERR {e}"
        results.append({"family": q["family"], "keywords": q["keywords"],
                        "login_wall": wall, "url_final": cur, "people": people})
        time.sleep(2)
    json.dump(results, open("/tmp/people_results.json", "w"), indent=1)
    print("PEOPLE_OK", [(r["family"], len(r["people"]), r["login_wall"]) for r in results])

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "feed":
        main_feed()
    else:
        main_people(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
