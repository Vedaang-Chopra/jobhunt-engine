#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session

session = open_logged_in_session(source='people_sweep_debug')
print('Auth state:', session.check_auth_state())

# Test one URL and take a snapshot
url = "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait longer for dynamic content
session.page.wait_for_timeout(10000)

# Scroll to trigger lazy loading
for i in range(5):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(2000)

# Get page content after scrolling
html = session.page.content()
# Save for inspection
with open('/tmp/linkedin_debug2.html', 'w') as f:
    f.write(html)
print(f'Saved HTML to /tmp/linkedin_debug2.html ({len(html)} chars)')

# Look for specific selectors
for sel in ['[data-entity-urn*="people"]', '.entity-result', 'li.reusable-search__result-container', 'div[data-test-entity-type="person"]', 'a[href*="/in/"]']:
    els = session.page.query_selector_all(sel)
    print(f'  {sel}: {len(els)}')
    if len(els) > 0:
        for j, el in enumerate(els[:3]):
            try:
                text = el.inner_text()[:200]
                print(f'    [{j}] {text}')
            except:
                pass

session.close()