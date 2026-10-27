#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date, datetime
from pathlib import Path

# Add the repo to the path
REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
    from scripts.discovery_lib import normalize_job, scrutinize, DedupIndex
except ImportError:
    import config_lib
    from discovery_lib import normalize_job, scrutinize, DedupIndex

# LinkedIn constants
LINKEDIN_BASE = "https://www.linkedin.com"
JOB_SEARCH_BASE = LINKEDIN_BASE + "/jobs/search-results/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# Queries from linkedin_guest_sweep.py
QUERIES = [
    "Research Engineer Machine Learning",
    "AI Research Scientist",
    "Post-Training LLM",
    "LLM Fine-Tuning Engineer",
    "AI Agent Engineer",
    "Applied Scientist AI",
    "Machine Learning Engineer LLM",
    "LLM Evaluation Research",
]

def build_search_url(query):
    params = {
        "keywords": query,
        "location": "United States",
        "f_TPR": "r604800",
        "geoId": "103644278"
    }
    return JOB_SEARCH_BASE + "?" + urllib.parse.urlencode(params)

def extract_jobs_from_html(html):
    """Extract jobs from LinkedIn server-rendered HTML using the method from the skill."""
    jobs = []
    # Find all componentkey matches for job-card-component-ref-(\d+)
    pattern = r'componentkey=\.job-card-component-ref-(\d+)\.'
    matches = list(re.finditer(pattern, html))
    for match in matches:
        job_id = match.group(1)
        # Slice ~6000 chars after the match
        start = match.end()
        snippet = html[start:start+6000]
        # Strip tags to pipes
        snippet = re.sub(r'<[^>]+>', '|', snippet)
        # Collapse pipes and whitespace
        snippet = re.sub(r'\|+', '|', snippet)
        snippet = re.sub(r'\s*\|\s*', '|', snippet)
        # Parse pipe fields: title | company | location
        # The pattern: ^[0-9]+\"|(.+?)\|(.+?)\|([A-Za-z .]+, [A-Z]{2})
        # But we don't have the leading number and quote? Let's look for the first pipe after the number.
        # We'll split by pipe and take the first three non-empty fields.
        parts = [p.strip() for p in snippet.split('|') if p.strip()]
        if len(parts) >= 3:
            title = parts[0]
            company = parts[1]
            location = parts[2]
            # Sometimes the location might have extra text, we'll take the first part that looks like a location
            # But we'll just use the third part as is.
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                "source_id": job_id,
                # We don't have date_posted from this method, but we can try to extract from the snippet?
                # We'll leave it empty for now.
            })
    return jobs

def main():
    # Ensure we are in the repo directory
    os.chdir(REPO)
    
    # Paths
    jobs_csv = config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
    search_runs_csv = config_lib.data_root() / "tracking" / "search_runs" / "search_runs.csv"
    execution_results_dir = config_lib.path("execution_results_dir")
    execution_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Load existing jobs for dedupe
    dedup_index = DedupIndex()
    if jobs_csv.exists():
        with open(jobs_csv, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                dedup_index.add(row)
    else:
        # If the file doesn't exist, we'll create it later
        pass
    
    # We'll use the Playwright MCP tools to get the HTML for each query
    # We need to navigate to LinkedIn first (to establish context)
    # Then for each query, run a fetch and get the HTML.
    
    # We'll collect all jobs from all queries
    all_jobs = []
    per_query_stats = {}
    
    # We'll use the mcp__playwright__browser_run_code_unsafe tool to run the fetch in the browser context.
    # But note: we are in a Python script, we cannot directly call the MCP tool.
    # We have to use the Hermes agent's tool system. However, we are writing a script to be run by the agent.
    # We are in a bind: we cannot call the MCP tool from within the script because the script is run by the agent's Python interpreter.
    # We have to change our approach: we will use the Hermes agent to run the MCP tools and then pass the HTML to the script.
    # But the user asked us to run the sweep ourselves using the Playwright MCP browser.
    # We are the agent, so we can call the MCP tools directly in our response.
    # Therefore, we will not run this script as a standalone Python script. Instead, we will use the MCP tools in our response and then do the parsing in Python.
    # Let's change our plan: we will do the navigation and fetching in the agent's response using the MCP tools, and then we will run the parsing in a Python code block.
    
    # We'll break out of this script and do the rest in the agent's response.
    print("This script is intended to be run by the Hermes agent using MCP tools. Exiting.")
    return

if __name__ == "__main__":
    main()