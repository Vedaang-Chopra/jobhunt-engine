#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import re
import json

session = open_logged_in_session(source='people_sweep')
print('Auth state:', session.check_auth_state())

# Run all 8 queries
queries = [
    ("a_hiring_posts", "agentic AI OR AI agents", "https://www.linkedin.com/search/results/content/?keywords=%28agentic%20AI%20OR%20AI%20agents%29%20hiring&origin=FACETED_SEARCH"),
    ("b_recruiters", "talent acquisition Mistral AI", "https://www.linkedin.com/search/results/people/?keywords=%22talent%20acquisition%22%20%22Mistral%20AI%22&origin=FACETED_SEARCH"),
    ("c_company_people", "Mistral AI", "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"),
    ("a_hiring_posts", "inference OR LLM evaluation", "https://www.linkedin.com/search/results/content/?keywords=%28inference%20OR%20LLM%20evaluation%29%20hiring&origin=FACETED_SEARCH"),
    ("b_recruiters", "talent acquisition Reka", "https://www.linkedin.com/search/results/people/?keywords=%22talent%20acquisition%22%20%22Reka%22&origin=FACETED_SEARCH"),
    ("c_company_people", "Reka", "https://www.linkedin.com/search/results/people/?keywords=%22Reka%22&origin=FACETED_SEARCH"),
    ("a_hiring_posts", "machine learning engineer", "https://www.linkedin.com/search/results/content/?keywords=%28machine%20learning%20engineer%29%20hiring&origin=FACETED_SEARCH"),
    ("b_recruiters", "talent acquisition Liquid AI", "https://www.linkedin.com/search/results/people/?keywords=%22talent%20acquisition%22%20%22Liquid%20AI%22&origin=FACETED_SEARCH"),
]

all_posts = []
all_people = []

# First, do content searches (a_hiring_posts)
extractor_code = open("/home/vchopra/.hermes/profiles/job-hunt-fresh/skills/career-automation/linkedin-hiring-post-monitor/scripts/linkedin_feed_extractor.js").read()

for family, keywords, url in queries:
    print(f'\n=== [{family}] {keywords} ===')
    session.page.goto(url)
    print(f'URL: {session.page.url}')
    
    # Wait for content
    session.page.wait_for_timeout(5000)
    
    # Scroll to load results
    for i in range(8):
        session.page.evaluate("window.scrollBy(0, 2000)")
        session.page.wait_for_timeout(1500)
    
    if family == "a_hiring_posts":
        # Use the feed extractor for content searches
        posts = session.page.evaluate(extractor_code)
        print(f'Extracted {len(posts)} posts')
        for p in posts:
            print(f'  - {p.get("poster")} | {p.get("headline", "")[:80]}')
            all_posts.append({**p, "family": family, "query_keywords": keywords})
    else:
        # People search - extract from HTML
        html = session.page.content()
        
        # Find all /in/ links with context
        people = []
        for match in re.finditer(r'href="([^"]*/in/[^"]*)"', html):
            href = match.group(1)
            start = max(0, match.start() - 500)
            end = min(len(html), match.end() + 500)
            context = html[start:end]
            
            # Extract name from context
            name_matches = re.findall(r'aria-hidden="true"[^>]*>([^<]+)<', context)
            name = ''
            for n in name_matches:
                n = n.strip()
                if 2 < len(n) < 50 and not any(bad in n.lower() for bad in ['connect', 'message', 'follow', 'linkedin', 'jobs', 'company', 'school', 'groups', 'events', 'posts', 'articles', 'notification', 'settings', 'help', 'sign out', 'me', 'home', 'my network', 'messaging', 'work', 'learning', '•', '|', '@']):
                    name = n
                    break
            
            # Extract headline/company from context
            headline = ''
            company = ''
            # Look for patterns indicating role/company
            title_matches = re.findall(r'>([^<]{5,120}?(?:Engineer|Scientist|Researcher|Manager|Director|Lead|Head|VP|CTO|CFO|Recruiter|Talent|Sourcer|ML|AI|Machine Learning|Inference|Agentic|Applied|Platform|Infrastructure|Data|Science|MLOps|Backend|Full Stack)[^<]{0,80})<', context)
            for t in title_matches:
                t = t.strip()
                if len(t) > 10 and len(t) < 150:
                    if not headline and ('at ' in t or ' @ ' in t or ' • ' in t or ' | ' in t or 'Engineer' in t or 'Scientist' in t or 'Researcher' in t or 'Manager' in t or 'Director' in t or 'Lead' in t or 'Head' in t or 'VP' in t or 'CTO' in t or 'Recruiter' in t or 'Talent' in t or 'Sourcer' in t):
                        headline = t
                    elif not company and not headline:
                        company = t
            
            if name:
                people.append({
                    "name": name,
                    "linkedinUrl": f"https://www.linkedin.com{href}" if href.startswith('/') else href,
                    "headline": headline,
                    "company": company
                })
        
        print(f'Found {len(people)} people')
        for p in people[:10]:
            print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
            all_people.append({**p, "family": family, "query_keywords": keywords})

print(f'\nTotal posts: {len(all_posts)}')
print(f'Total people: {len(all_people)}')

session.close()