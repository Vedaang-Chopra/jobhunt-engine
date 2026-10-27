#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session

session = open_logged_in_session(source='people_sweep_debug')
print('Auth state:', session.check_auth_state())

# Test one URL
url = "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait longer for dynamic content
session.page.wait_for_timeout(10000)

# Scroll to trigger lazy loading
for i in range(5):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(2000)

# Extract raw HTML and look for data structures
html = session.page.content()

# Search for entity URN patterns
import re
urns = re.findall(r'data-entity-urn="([^"]*)"', html)
print(f'Found {len(urns)} entity URNs')
for u in urns[:10]:
    print(f'  {u}')

# Search for person names in the HTML
person_names = re.findall(r'<span[^>]*aria-hidden="true"[^>]*>([^<]+)</span>', html)
print(f'\nFound {len(person_names)} potential names')
for n in person_names[:20]:
    print(f'  {n}')

# Search for /in/ links with context
in_links = re.findall(r'href="([^"]*/in/[^"]*)"[^>]*>([^<]*)<', html)
print(f'\nFound {len(in_links)} /in/ links with text')
for link, text in in_links[:20]:
    print(f'  {text[:60]} | {link}')

session.close()