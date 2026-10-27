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

# Feed extractor for content searches
extractor_code = open("/home/vchopra/.hermes/profiles/job-hunt-fresh/skills/career-automation/linkedin-hiring-post-monitor/scripts/linkedin_feed_extractor.js").read()

# People extractor for people searches
people_extractor = """() => {
    const results = [];
    const links = document.querySelectorAll('a[href*="/in/"]');
    for (const link of links) {
        try {
            const linkedinUrl = link.href.split('?')[0];
            const linkText = link.innerText.trim();
            const parent = link.parentElement;
            const parentText = parent ? parent.innerText.trim() : '';
            const grandParent = parent ? parent.parentElement : null;
            const grandParentText = grandParent ? grandParent.innerText.trim() : '';
            const allText = (linkText + '\\n' + parentText + '\\n' + grandParentText).trim();
            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            let name = '';
            let headline = '';
            let company = '';
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (line.toLowerCase().includes('connect') || 
                    line.toLowerCase().includes('message') ||
                    line.toLowerCase().includes('follow') ||
                    line === '•' ||
                    line.includes('|') ||
                    line.length < 3 ||
                    line.length > 80) {
                    continue;
                }
                if (!name && line.length > 2 && line.length < 50) {
                    name = line;
                } else if (!headline && (line.toLowerCase().includes('engineer') || line.toLowerCase().includes('scientist') || line.toLowerCase().includes('research') || line.toLowerCase().includes('manager') || line.toLowerCase().includes('director') || line.toLowerCase().includes('lead') || line.toLowerCase().includes('head') || line.toLowerCase().includes('vp') || line.toLowerCase().includes('cto') || line.toLowerCase().includes('recruiter') || line.toLowerCase().includes('talent') || line.toLowerCase().includes('sourcer') || line.toLowerCase().includes('ml') || line.toLowerCase().includes('ai') || line.toLowerCase().includes('machine learning') || line.toLowerCase().includes('inference') || line.toLowerCase().includes('agentic') || line.toLowerCase().includes('applied') || line.toLowerCase().includes('platform') || line.toLowerCase().includes('infrastructure'))) {
                    headline = line;
                } else if (!company && line.length > 3 && line.length < 80) {
                    company = line;
                }
            }
            if (name && linkedinUrl.includes('/in/')) {
                results.push({name, linkedinUrl, headline, company, rawLines: lines.slice(0, 8)});
            }
        } catch (e) {}
    }
    const seen = new Set();
    const unique = [];
    for (const p of results) {
        if (!seen.has(p.linkedinUrl)) {
            seen.add(p.linkedinUrl);
            unique.push(p);
        }
    }
    return unique;
}"""

for family, keywords, url in queries:
    print(f'\n=== [{family}] {keywords} ===')
    session.page.goto(url)
    print(f'URL: {session.page.url}')
    
    # Wait for content
    session.page.wait_for_timeout(8000)
    
    # Scroll extensively
    for i in range(15):
        session.page.evaluate("window.scrollBy(0, 2000)")
        session.page.wait_for_timeout(1000)
    
    if family == "a_hiring_posts":
        # Use the feed extractor for content searches
        posts = session.page.evaluate(extractor_code)
        print(f'Extracted {len(posts)} posts')
        for p in posts:
            print(f'  - {p.get("poster")} | {p.get("headline", "")[:80]}')
            all_posts.append({**p, "family": family, "query_keywords": keywords})
    else:
        # People search
        people = session.page.evaluate(people_extractor)
        print(f'Found {len(people)} people')
        for p in people[:15]:
            print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
            all_people.append({**p, "family": family, "query_keywords": keywords})

print(f'\nTotal posts: {len(all_posts)}')
print(f'Total people: {len(all_people)}')

# Save results
with open('/mnt/DATA/job_hunt/jobhunt-engine/sweep_results.json', 'w') as f:
    json.dump({"posts": all_posts, "people": all_people}, f, indent=2)

session.close()