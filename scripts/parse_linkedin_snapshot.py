#!/usr/bin/env python3
"""Parse Playwright MCP accessibility-snapshot YAML of LinkedIn job search results.
Pairs each card's Dismiss-label (title/company/location/footer) with its /url currentJobId.
Outputs JSON list of jobs."""
import json
import re
import sys

def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    jobs = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.search(r'Dismiss (.+?) job\b', line)
        if m:
            label = re.sub(r'^\s*-\s+(?:link|button)\s+"', '', line)
            label = label.rsplit('" [ref=', 1)[0]
            # find next /url line within 6 lines
            url = ""
            for j in range(i + 1, min(i + 7, len(lines))):
                um = re.search(r'/url:\s*(\S+)', lines[j])
                if um:
                    url = um.group(1)
                    break
            jm = re.search(r'(?:currentJobId=|jobs/view/)(\d+)', url)
            if jm:
                # clean label: strip leading "Company City ... Dismiss" prefix noise by
                # splitting on ' Dismiss '
                core = label.split(" Dismiss ")[0]
                jobs.append({"job_id": jm.group(1), "raw": core[:300]})
        i += 1
    return jobs

if __name__ == "__main__":
    all_jobs = {}
    for p in sys.argv[1:]:
        for j in parse(p):
            all_jobs.setdefault(j["job_id"], j)
    print(json.dumps(list(all_jobs.values()), indent=0))
