#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import re
import json

session = open_logged_in_session(source='people_sweep')
print('Auth state:', session.check_auth_state())

# Test content search with more waiting
url = "https://www.linkedin.com/search/results/content/?keywords=%28agentic%20AI%20OR%20AI%20agents%29%20hiring&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait for content with explicit wait for results
try:
    session.page.wait_for_selector('.feed-shared-update-v2, .fie-impression-container, [data-entity-urn*="activity"]', timeout=30000)
    print('Found results container')
except Exception as e:
    print(f'Wait failed: {e}')

# Additional scrolling
for i in range(8):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(2000)

# Get HTML and extract posts using the extractor from the skill
extractor_code = open("/home/vchopra/.hermes/profiles/job-hunt-fresh/skills/career-automation/linkedin-hiring-post-monitor/scripts/linkedin_feed_extractor.js").read()
posts = session.page.evaluate(extractor_code)
print(f'Extracted {len(posts)} posts')

for p in posts:
    print(json.dumps(p, indent=2))

session.close()