#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session

session = open_logged_in_session(source='hiring_post_monitor')
print('Mode:', session.mode)
print('URL:', session.page.url)
print('Auth state:', session.check_auth_state())

# Navigate to feed
session.page.goto("https://www.linkedin.com/feed/")
print('After goto feed URL:', session.page.url)
print('Auth state:', session.check_auth_state())

# Scroll the feed to load posts
for i in range(10):
    session.page.evaluate("""async () => {
        const f = document.querySelector('main');
        if (f) {
            f.scrollBy(0, 2000);
            await new Promise(r => setTimeout(r, 1500));
        }
    }""")

# Run the extractor
extractor_code = open("/home/vchopra/.hermes/profiles/job-hunt-fresh/skills/career-automation/linkedin-hiring-post-monitor/scripts/linkedin_feed_extractor.js").read()
posts = session.page.evaluate(extractor_code)
print(f'Extracted {len(posts)} posts')

import json
for p in posts:
    print(json.dumps(p, indent=2))

session.close()