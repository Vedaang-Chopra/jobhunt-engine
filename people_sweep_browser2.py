#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import re
import json

session = open_logged_in_session(source='people_sweep')
print('Auth state:', session.check_auth_state())

# Run the 8 queries
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

all_people = []

for family, keywords, url in queries:
    print(f'\n=== [{family}] {keywords} ===')
    session.page.goto(url)
    print(f'URL: {session.page.url}')
    
    # Wait for content
    session.page.wait_for_timeout(5000)
    
    # Scroll to load results
    for i in range(5):
        session.page.evaluate("window.scrollBy(0, 2000)")
        session.page.wait_for_timeout(2000)
    
    # Get HTML and extract people
    html = session.page.content()
    
    if 'people' in url:
        # People search - extract from /in/ links with surrounding context
        # Pattern: href="/in/..." followed by name in nearby span
        people = []
        # Find all /in/ links with their surrounding 500 chars
        for match in re.finditer(r'href="([^"]*/in/[^"]*)"', html):
            href = match.group(1)
            start = max(0, match.start() - 500)
            end = min(len(html), match.end() + 500)
            context = html[start:end]
            
            # Extract name from context - look for aria-hidden spans
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
            # Look for patterns like "Title at Company" or "Title • Company"
            title_matches = re.findall(r'>([^<]{5,100}?(?:Engineer|Scientist|Researcher|Manager|Director|Lead|Head|VP|CTO|CFO|Recruiter|Talent|Sourcer|ML|AI|Machine Learning|Inference|Agentic|Applied|Platform|Infrastructure)[^<]{0,80})<', context)
            for t in title_matches:
                t = t.strip()
                if len(t) > 10 and len(t) < 120:
                    if not headline and ('at ' in t or ' @ ' in t or ' • ' in t or ' | ' in t):
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
    else:
        # Content search - posts
        pass

print(f'\nTotal extracted: {len(all_people)}')
print(json.dumps(all_people, indent=2))

session.close()