#!/usr/bin/env python3
"""Board discovery probe: find live Greenhouse / Ashby / Lever boards at scale.

For each candidate company, probes the public board-token endpoints:
  - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{token}/jobs
  - Ashby:      https://api.ashbyhq.com/posting-api/job-board/{org}
  - Lever:      https://api.lever.co/v0/postings/{org}?mode=json

Candidates come from a JSON file (list of {name, greenhouse?, ashby?, lever?})
where the optional keys are guessed board tokens (default: slugified name).
Writes results to a TSV so verified live boards can be merged into
career-ops/portals.yml.

Usage:
  python3 scripts/probe_boards.py candidates.json results.tsv [--workers 8]
"""
import json
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{tok}/jobs"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{org}"
LEVER = "https://api.lever.co/v0/postings/{org}?mode=json"

HEADERS = {"User-Agent": "job-discovery-probe/1.0"}
TIMEOUT = 12


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)  # greenhouse/ashby tokens have no separators usually; try both variants
    return s


def variants(name: str):
    base = slugify(name)
    dashed = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    spaced = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    out = []
    for tok in [base, dashed, spaced.replace(" ", "")]:
        if tok and tok not in out:
            out.append(tok)
    return out


def fetch(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return None, str(e).encode()


def probe_greenhouse(tok: str):
    status, body = fetch(GREENHOUSE.format(tok=tok))
    if status == 200:
        try:
            n = len(json.loads(body).get("jobs", []))
            return ("greenhouse", tok, n)
        except Exception:
            return None
    return None


def probe_ashby(org: str):
    status, body = fetch(ASHBY.format(org=org))
    if status == 200:
        try:
            data = json.loads(body)
            jobs = data.get("jobs") or []
            return ("ashby", org, len(jobs))
        except Exception:
            return None
    return None


def probe_lever(org: str):
    status, body = fetch(LEVER.format(org=org))
    if status == 200:
        try:
            return ("lever", org, len(json.loads(body)))
        except Exception:
            return None
    return None


def probe_company(entry: dict):
    name = entry["name"]
    hits = []
    # Explicit tokens win; otherwise try slug variants.
    for platform in ("greenhouse", "ashby", "lever"):
        tokens = entry.get(platform) or variants(name)
        for tok in tokens[:3]:
            fn = {"greenhouse": probe_greenhouse, "ashby": probe_ashby, "lever": probe_lever}[platform]
            r = fn(tok)
            if r and r[2] > 0:
                hits.append(r)
                break
            if r:  # live but zero jobs — record once, stop probing this platform
                hits.append(r)
                break
    return {"name": name, "boards": hits}


def main():
    args = sys.argv[1:]
    cand_path = args[0]
    out_path = args[1]
    workers = 8
    if "--workers" in args:
        workers = int(args[args.index("--workers") + 1])

    with open(cand_path) as f:
        candidates = json.load(f)

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe_company, c): c["name"] for c in candidates}
        done = 0
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 25 == 0:
                print(f"  probed {done}/{len(candidates)}...", file=sys.stderr)

    results.sort(key=lambda r: r["name"].lower())
    live = sum(1 for r in results if any(h[2] > 0 for h in r["boards"]))
    total_boards = sum(len(r["boards"]) for r in results)

    with open(out_path, "w") as f:
        f.write("company\tplatform\tboard_token\topen_jobs\n")
        for r in results:
            if not r["boards"]:
                f.write(f"{r['name']}\tNONE\t-\t-\n")
                continue
            for plat, tok, n in r["boards"]:
                f.write(f"{r['name']}\t{plat}\t{tok}\t{n}\n")

    print(f"\nProbed {len(candidates)} companies: {live} with >=1 live non-empty board, "
          f"{total_boards} boards total.")
    print(f"Results -> {out_path}")


if __name__ == "__main__":
    main()
