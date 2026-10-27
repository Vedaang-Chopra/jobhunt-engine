#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import re
import json

session = open_logged_in_session(source='people_sweep')
print('Auth state:', session.check_auth_state())

# Test one people search with more debugging
url = "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait for content
session.page.wait_for_timeout(8000)

# Scroll to load results
for i in range(10):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(1500)

# Get HTML and save
html = session.page.content()
with open('/tmp/linkedin_people_debug.html', 'w') as f:
    f.write(html)
print(f'Saved HTML ({len(html)} chars)')

# Look for people search specific patterns
# Modern LinkedIn uses different structures
patterns = [
    r'data-entity-urn="urn:li:person:(\d+)"',
    r'data-entity-urn="([^"]*)"',
    r'class="[^"]*entity-result[^"]*"',
    r'class="[^"]*reusable-search__result-container[^"]*"',
    r'data-test-entity-type="person"',
    r'data-view-name="search-entity-result"',
]

for p in patterns:
    matches = re.findall(p, html)
    print(f'Pattern {p[:40]}: {len(matches)} matches')
    for m in matches[:5]:
        print(f'  {m[:100]}')

# Look for structured data
structured = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>([^<]+)</script>', html)
print(f'\nLD+JSON scripts: {len(structured)}')
for s in structured[:3]:
    print(f'  {s[:200]}')

session.close()