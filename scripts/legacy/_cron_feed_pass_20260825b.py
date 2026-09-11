"""Raw-CDP feed pass cron 2026-08-25 evening. One pass, 10 scrolls, read-only."""
import json, os, sys, time, urllib.request
import websocket

REPO = "/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting"
OUT = os.path.join(REPO, ".playwright-mcp", "feed-posts-cron-b.json")
EXTRACTOR = open(os.path.join(REPO, "scripts", "linkedin_feed_extractor.js")).read()

ver = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/version", timeout=5))
ws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=90, suppress_origin=True)
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

tid = cmd("Target.createTarget", {"url": "about:blank"})["targetId"]
sess = cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
cmd("Page.enable", session=sess)
cmd("Page.navigate", {"url": "https://www.linkedin.com/feed/"}, session=sess)
time.sleep(8)

def ev(expr):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, session=sess)
    if r.get("exceptionDetails"):
        return None
    return r.get("result", {}).get("value")

loc = ev("location.href + ' || ' + document.title")
print("PAGE:", loc)
if not loc or "/feed" not in loc.split(" || ")[0] or "authwall" in loc or "login" in loc.lower():
    json.dump([], open(OUT, "w"))
    print(f"NOT_LOGGED_IN h2_count=0 extracted=0 saved={OUT}")
    try: cmd("Target.closeTarget", {"targetId": tid})
    except Exception: pass
    sys.exit(0)

scroll_js = "(() => { const f = document.querySelector('main'); if (f) f.scrollBy(0,2000); return true; })()"
for i in range(10):
    ev(scroll_js)
    time.sleep(1.5)
n = ev("document.querySelectorAll('main h2').length") or 0
posts = ev("(" + EXTRACTOR + ")()") or []
json.dump(posts, open(OUT, "w"), indent=1)
try:
    cmd("Target.closeTarget", {"targetId": tid})
except Exception:
    pass
print(f"OK h2_count={n} extracted={len(posts)} saved={OUT}")
