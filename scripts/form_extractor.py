#!/usr/bin/env python3
"""Form-field extraction for application URLs (apply-plan Task 3).

extract_fields(url, out_path) captures every visible field of an application
form into a JSON snapshot consumed by apply_pipeline.py stage_fillplan().

Extraction strategy per ATS family:
  - Greenhouse / Lever / Ashby: form is embedded in the job page -> generic
    DOM walk over input/textarea/select/radiogroup elements.
  - Workday CXS (wd*.myworkdayjobs.com): click Apply -> Apply Manually, then
    either (a) run the embedded JS_SNIPPET via the Playwright MCP
    browser_evaluate tool and pass the result back with --browser-json, or
    (b) POST the CXS getJobPost endpoint for the applicantQuestions schema.
    Multi-page forms: page 1 is extracted; total pages recorded when the
    "current step N of M" indicator is present.
  - Login wall / unexpected auth redirect -> writes
    {"needs_manual": true, "reason": "..."} and exits non-zero. NEVER type
    credentials; never click Submit.

This script itself never drives the browser directly; it consumes what the
Playwright MCP session captured (one tab, closed afterwards by the caller).
It also exposes the exact JS snippet and step-by-step recipe so any agent can
perform the capture consistently.

Usage:
  # agent-driven capture (preferred):
  python3 scripts/form_extractor.py <url> \
      --out execution_results/apply_runs/<job_id>_fields.json \
      --browser-json /tmp/captured_fields.json

  # CXS API fallback for Workday:
  python3 scripts/form_extractor.py <workday_url> --out <path> --cxs-api

Output format:
  {
    "url": ..., "captured_at": ISO, "ats": "workday|greenhouse|lever|ashby|generic",
    "current_step": 1, "total_steps": 8|null,
    "fields": [{"label","type","required","options"?}, ...]
  }
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# JS evaluated inside the application tab via mcp__playwright__browser_evaluate.
# Returns {count, currentStepText, fields:[{label,type,required,options?}]}.
JS_SNIPPET = r"""
() => {
  function lbl(el){
    let t='';
    if(el.getAttribute('aria-labelledby')){
      const sel = el.getAttribute('aria-labelledby').split(/\s+/)
        .map(id=>'#'+CSS.escape(id)).join(',');
      t=[...document.querySelectorAll(sel)].map(n=>n.innerText||'').join(' ');
    }
    if(!t && el.id){ const l=document.querySelector(`[for="${el.id}"]`); if(l) t=l.innerText; }
    if(!t){
      let w=el.closest('[data-automation-id]');
      for(let i=0;i<4&&w;i++){ w=w.parentElement;
        if(!w) break;
        const l=w.querySelector('[data-automation-id="formLabel"],label');
        if(l){ t=l.innerText; break; } }
    }
    if(!t && el.closest('label')) t=el.closest('label').innerText;
    return (t||'').replace(/\s+/g,' ').trim();
  }
  function req(el){
    if(el.getAttribute('aria-required')==='true'||el.required) return true;
    let p=el.parentElement;
    for(let i=0;i<5&&p;i++,p=p.parentElement){
      if(p.getAttribute&&p.getAttribute('aria-required')==='true') return true; }
    return false;
  }
  const out=[];
  document.querySelectorAll(
    'input:not([type=hidden]),textarea,select,[role=radiogroup],[role=listbox],[role=checkbox]'
  ).forEach(el=>{
    let type = el.tagName==='INPUT'? el.type.toLowerCase()
             : el.tagName==='TEXTAREA'?'textarea'
             : el.tagName==='SELECT'?'select'
             : (el.getAttribute('role')||'unknown');
    const o={label:lbl(el), type:type, required:req(el)};
    const grp = el.getAttribute('role')==='radiogroup' ? el : null;
    if(grp){
      o.options=[...grp.querySelectorAll('[role=radio],input[type=radio]')]
        .map(r=>((r.innerText||r.value||(r.closest('label')&&r.closest('label').innerText)||''))
          .replace(/\s+/g,' ').trim()).filter(Boolean);
    }
    if(el.tagName==='SELECT'){
      o.options=[...el.options].map(op=>op.textContent.trim());
    }
    if(o.label || o.type!=='unknown') out.push(o);
  });
  const stepM=(document.body.innerText.match(/(?:current\s*)?step\s*(\d+)\s*of\s*(\d+)/i));
  return {count: out.length,
          currentStepText: stepM? `${stepM[1]} of ${stepM[2]}` : null,
          fields: out};
}
"""


def detect_ats(url: str) -> str:
    u = url.lower()
    if "myworkdayjobs.com" in u or "myworkdaysite.com" in u:
        return "workday"
    if "boards.greenhouse.io" in u or "job-boards.greenhouse.io" in u:
        return "greenhouse"
    if "jobs.lever.co" in u or "jobapp.lever.co" in u:
        return "lever"
    if "jobs.ashbyhq.com" in u:
        return "ashby"
    return "generic"


def cxs_api_fields(job_url: str) -> dict | None:
    """Workday CXS fallback: POST getJobPost, pull applicantQuestions."""
    if "myworkdayjobs.com" not in job_url:
        return None
    m = re.search(r"/(?:en-US/)?[^/]+/job/(.+)$", job_url)
    if not m:
        return None
    site = re.search(r"https://([^/]+)/", job_url).group(1).split(".")[0]
    tenant_m = re.search(r"https://([^.]+)\.", job_url)
    tenant, site_name = tenant_m.group(1), site.split(".")[0]
    api = (f"https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/"
           f"{site_name}/job/{m.group(1)}")
    body = json.dumps({})
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-X", "POST", api,
             "-H", "Content-Type: application/json",
             "-H", "Accept: application/json",
             "-H", "User-Agent: Mozilla/5.0", "-d", body],
            capture_output=True, text=True, timeout=40)
        d = json.loads(r.stdout or "{}")
    except Exception:
        return None
    info = d.get("jobPostingInfo") or {}
    aq = info.get("applicantQuestions")
    if not aq:
        return None
    fields = []
    for sec in aq.get("sections", []):
        for q in sec.get("questions", []):
            item = q.get("question", q)
            label = item.get("text", "") or item.get("label", "")
            ftype = item.get("type", "").lower() or "unknown"
            opts = [o.get("value", "") or o.get("text", "")
                    for o in item.get("options", [])]
            f = {"label": re.sub(r"\s+", " ", label).strip(),
                 "type": {"text": "text", "textarea": "textarea",
                          "single_select": "select", "multi_select": "multiselect",
                          "date": "date", "number": "number"}.get(ftype, ftype),
                 "required": bool(item.get("required"))}
            if opts:
                f["options"] = opts
            fields.append(f)
    return {"fields": fields,
            "total_steps": aq.get("numberOfStages")
            or len(aq.get("sections", [])) or None}


AUTH_PATTERNS = ("sign in to continue", "log in to your account",
                 "create account to continue")


def looks_like_login_wall(page_text: str) -> bool | str:
    low = page_text.lower()
    for p in AUTH_PATTERNS:
        if p in low:
            return f"login/auth wall detected ('{p}')"
    return False


def extract_fields(url: str, out_path: str, browser_json: str | None = None,
                   use_cxs: bool = False, page_text: str = "") -> dict:
    """Build and save the field snapshot. See module docstring for contract."""
    ats = detect_ats(url)
    result: dict[str, Any] = {"url": url,
              "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
              "ats": ats}

    wall = looks_like_login_wall(page_text or "")
    if wall:
        result.update({"needs_manual": True, "reason": wall})
        _save(result, out_path)
        print(f"NEEDS_MANUAL: {wall}", file=sys.stderr)
        return result

    payload = None
    if browser_json:
        raw = json.load(open(browser_json))
        if isinstance(raw, str):
            raw = json.loads(raw)
        payload = raw.get("fields", raw if isinstance(raw, list) else [])
        result["current_step"], result["total_steps"] = 1, None
        m = re.match(r"(\d+) of (\d+)", raw.get("currentStepText") or "")
        if m:
            result["current_step"], result["total_steps"] = int(m.group(1)), int(m.group(2))
        elif raw.get("currentStepText"):
            result["current_step"] = int(re.match(r"\d+", raw["currentStepText"]).group(0))
    elif use_cxs:
        payload_block = cxs_api_fields(url)
        if payload_block is None:
            result.update({"needs_manual": True,
                           "reason": "CXS API returned no applicantQuestions"})
            _save(result, out_path)
            print("NEEDS_MANUAL: CXS API unavailable", file=sys.stderr)
            return result
        payload = payload_block["fields"]
        result["total_steps"] = payload_block.get("total_steps")
        result["via"] = "workday-cxs-api"

    if payload is None:
        result.update({
            "needs_manual": True,
            "reason": ("no capture provided; run JS_SNIPPET via the Playwright "
                       "MCP browser_evaluate tool in one tab, then rerun with "
                       "--browser-json (recipe in this script's docstring)")})
        _save(result, out_path)
        print("NEEDS_MANUAL: browser capture required (--browser-json)",
              file=sys.stderr)
        return result

    # Normalize + dedupe radio groups sharing a label; skip honeypot/password.
    seen, fields, password_count = set(), [], 0
    for f in payload:
        label = (f.get("label") or "").strip()
        ftype = f.get("type", "unknown").lower()
        if ftype == "password":
            password_count += 1
            continue  # never record credential fields
        if "for robots only" in label.lower():
            continue  # honeypot
        key = (label.lower(), "radio" if ftype == "radio" else ftype)
        if ftype == "radio" and key in seen:
            continue
        seen.add(key)
        rec = {"label": label, "type": ftype,
               "required": bool(f.get("required"))}
        if f.get("options"):
            rec["options"] = f["options"]
        fields.append(rec)

    # Workday account-creation wall: page 1 demanding password(s) means the
    # portal requires a new applicant account — automation must NOT proceed
    # (no-credentials rule). Flag it loudly so the queue routes elsewhere.
    if password_count >= 1 and any(
            f["type"] == "text" and "email" in f["label"].lower()
            for f in fields):
        result["fields"] = fields
        result["field_count"] = len(fields)
        result["needs_manual"] = True
        result["reason"] = ("account_creation_required: page 1 demands "
                            "password fields alongside email — Workday "
                            "applicant account wall; create the account once "
                            "manually in the persistent browser profile, then "
                            "re-extract. Queue should prefer Greenhouse/Ashby "
                            "jobs meanwhile.")
        _save(result, out_path)
        print("NEEDS_MANUAL: account_creation_required (Workday wall)",
              file=sys.stderr)
        return result

    result["fields"] = fields
    result["field_count"] = len(fields)
    _save(result, out_path)
    print(f"saved {len(fields)} fields -> {out_path}", file=sys.stderr)
    return result


def _save(obj: dict, out_path: str):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump(obj, open(out_path, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--out", required=True, help="snapshot output path")
    ap.add_argument("--browser-json",
                    help="JSON result of JS_SNIPPET run via browser_evaluate")
    ap.add_argument("--cxs-api", action="store_true",
                    help="try the Workday CXS getJobPost API instead of a browser")
    ap.add_argument("--page-text-file", help="optional visible page text (auth check)")
    args = ap.parse_args()

    page_text = open(args.page_text_file).read() if args.page_text_file else ""
    res = extract_fields(args.url, args.out, args.browser_json, args.cxs_api,
                         page_text)
    print(json.dumps(res, indent=1))
    sys.exit(1 if res.get("needs_manual") else 0)


if __name__ == "__main__":
    main()
