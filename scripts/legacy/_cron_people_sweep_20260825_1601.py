"""People sweep 16:0x v2 — 8 LinkedIn people/content searches via CDP (read-only)."""
import json, os, time, urllib.request
import websocket

REPO = "/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting"
OUT = os.path.join(REPO, ".playwright-mcp", "people-sweep-1601.json")

QUERIES = [
    ("a_hiring_posts", "https://www.linkedin.com/search/results/content/?keywords=%28agentic%20AI%20OR%20AI%20agents%29%20hiring&origin=FACETED_SEARCH"),
    ("b_recruiters", "https://www.linkedin.com/search/results/people/?keywords=%22talent%20acquisition%22%20%22Cohere%22&origin=FACETED_SEARCH"),
    ("c_company_people", "https://www.linkedin.com/search/results/people/?keywords=%22Cohere%22&origin=FACETED_SEARCH"),
    ("d_gt_alumni", "https://www.linkedin.com/search/results/people/?keywords=%22Georgia%20Tech%22%20%22Cohere%22&schoolFilter=16818&origin=FACETED_SEARCH"),
    ("a_hiring_posts", "https://www.linkedin.com/search/results/content/?keywords=%28inference%20OR%20LLM%20evaluation%29%20hiring&origin=FACETED_SEARCH"),
    ("b_recruiters", "https://www.linkedin.com/search/results/people/?keywords=%22talent%20acquisition%22%20%22Together%20AI%22&origin=FACETED_SEARCH"),
    ("c_company_people", "https://www.linkedin.com/search/results/people/?keywords=%22Together%20AI%22&origin=FACETED_SEARCH"),
    ("d_gt_alumni", "https://www.linkedin.com/search/results/people/?keywords=%22Georgia%20Tech%22%20%22Together%20AI%22&schoolFilter=16818&origin=FACETED_SEARCH"),
]

EXTRACT_PEOPLE = """(() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="/in/"]').forEach(a => {
    const t = (a.innerText || '').trim();
    if (!t || t.indexOf('\\u2022') === -1 || !t.includes('\\n')) return;
    const url = a.href.split('?')[0];
    if (seen.has(url)) return;
    const lines = t.split('\\n').map(s => s.trim()).filter(Boolean);
    const name = lines[0] || '';
    if (!name || name.length > 60) return;
    const degLine = lines.find(l => l.startsWith('\\u2022'));
    const degree = degLine ? degLine.replace('\\u2022','').trim() : '';
    const rest = lines.filter(l => l !== lines[0] && l !== degLine);
    const title = rest[0] || '';
    const location = rest[1] || '';
    seen.add(url);
    out.push({name, degree, title, location, linkedin_url: url});
  });
  return out.slice(0, 12);
})()"""

EXTRACT_POSTS = """(() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="/feed/update/"], a[href*="/posts/"]').forEach(a => {
    const url = a.href.split('?')[0];
    if (seen.has(url)) return;
    seen.add(url);
    // climb to the card container
    let card = a.closest('div');
    for (let i = 0; i < 6 && card && card.parentElement && card.innerText.length < 300; i++) card = card.parentElement;
    const txt = card ? card.innerText.trim().slice(0, 400) : '';
    out.push({post_url: url, text: txt});
  });
  return out.slice(0, 10);
})()"""

ver = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/version", timeout=5))
ws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=120, suppress_origin=True)
_id = [0]

def cmd(method, params=None, session=None):
    _id[0] += 1
    msg = {"id": _id[0], "method": method, "params": params or {}}
    if session:
        msg["sessionId"] = session
    ws.send(json.dumps(msg))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == _id[0]:
            if "error" in m:
                raise RuntimeError(f"{method}: {m['error']}")
            return m.get("result", {})

def ev(expr, sess):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, session=sess)
    if r.get("exceptionDetails"):
        print("JS ERROR:", json.dumps(r["exceptionDetails"])[:400])
        return None
    return r.get("result", {}).get("value")

results = []
tid = cmd("Target.createTarget", {"url": "about:blank"})["targetId"]
sess = cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
cmd("Page.enable", session=sess)

for fam, url in QUERIES:
    cmd("Page.navigate", {"url": url}, session=sess)
    time.sleep(7)
    loc = ev("location.href + ' || ' + document.title", sess) or ""
    if "authwall" in loc or "login" in loc.lower():
        print(f"WALL on {fam}: {loc}")
        results.append({"family": fam, "url": url, "blocked": True})
        break
    items = ev(EXTRACT_POSTS if "/content/" in url else EXTRACT_PEOPLE, sess) or []
    results.append({"family": fam, "url": url, "count": len(items), "items": items})
    print(f"{fam}: {len(items)} extracted")
    time.sleep(3)

try:
    cmd("Target.closeTarget", {"targetId": tid})
except Exception:
    pass
json.dump(results, open(OUT, "w"), indent=1)
print(f"DONE saved={OUT}")
