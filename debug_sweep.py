#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session

session = open_logged_in_session(source='people_sweep_debug')
print('Auth state:', session.check_auth_state())

# Test one URL and take a snapshot
url = "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait for content
session.page.wait_for_timeout(3000)

# Get page content
html = session.page.content()
# Save for inspection
with open('/tmp/linkedin_debug.html', 'w') as f:
    f.write(html)
print(f'Saved HTML to /tmp/linkedin_debug.html ({len(html)} chars)')

# Try to find people elements
elements = session.page.query_selector_all('*')
print(f'Total elements: {len(elements)}')

# Look for specific selectors
for sel in ['.entity-result', '.reusable-search__result-container', '[data-entity-urn*="people"]', '.search-result', 'li']:
    els = session.page.query_selector_all(sel)
    print(f'  {sel}: {len(els)}')

session.close()