#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import re

session = open_logged_in_session(source='people_sweep_debug')
print('Auth state:', session.check_auth_state())

# Test content search
url = "https://www.linkedin.com/search/results/content/?keywords=%28agentic%20AI%20OR%20AI%20agents%29%20hiring&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait for content
session.page.wait_for_timeout(5000)

# Scroll to load results
for i in range(5):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(2000)

# Get HTML and save
html = session.page.content()
with open('/tmp/linkedin_content_debug.html', 'w') as f:
    f.write(html)
print(f'Saved HTML ({len(html)} chars)')

# Look for patterns
urns = re.findall(r'data-entity-urn="([^"]*)"', html)
print(f'Entity URNs: {len(urns)}')
for u in urns[:10]:
    print(f'  {u}')

# Look for post content
posts = re.findall(r'feed-shared-update-v2', html)
print(f'feed-shared-update-v2: {len(posts)}')

# Look for author names
names = re.findall(r'update-components-actor__name[^>]*>([^<]+)<', html)
print(f'Actor names: {len(names)}')
for n in names[:10]:
    print(f'  {n}')

# Look for /in/ links in posts
in_links = re.findall(r'href="([^"]*/in/[^"]*)"[^>]*>([^<]*)<', html)
print(f'/in/ links: {len(in_links)}')
for link, text in in_links[:20]:
    print(f'  {text[:60]} | {link}')

session.close()