"""Debug: dump search-result DOM structure."""
import json, time, urllib.request
import websocket

REPO = "/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting"
URL = "https://www.linkedin.com/search/results/people/?keywords=%22talent%20acquisition%22%20%22Cohere%22&origin=FACETED_SEARCH"

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

tid = cmd("Target.createTarget", {"url": "about:blank"})["targetId"]
sess = cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
cmd("Page.enable", session=sess)
cmd("Page.navigate", {"url": URL}, session=sess)
time.sleep(8)

def ev(expr):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, session=sess)
    if r.get("exceptionDetails"):
        print("JS ERROR:", json.dumps(r["exceptionDetails"])[:400])
        return None
    return r.get("result", {}).get("value")

print("LOC:", ev("location.href + ' || ' + document.title"))
print(ev("document.body.innerText.slice(0, 1500)"))
html = ev("""(() => {
  const inl = [...document.querySelectorAll('a[href*=\"/in/\"]')].slice(0, 10).map(a => ({
    href: a.href.split('?')[0], cls: a.className.slice(0,80), text: a.innerText.trim().slice(0,120),
    parentCls: (a.parentElement && a.parentElement.className || '').slice(0,100),
    gpCls: (a.closest('div') && a.closest('div').parentElement ? a.closest('div').parentElement.className : '').slice(0,120),
  }));
  return JSON.stringify(inl, null, 1);
})()""")
print(html)
cmd("Target.closeTarget", {"targetId": tid})
