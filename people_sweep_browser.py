#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import json

session = open_logged_in_session(source='people_sweep')
print('Mode:', session.mode)
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
    
    # Scroll to load results
    for i in range(3):
        session.page.evaluate("""async () => {
            const f = document.querySelector('main') || document.querySelector('.search-results-container') || document.body;
            if (f) {
                f.scrollBy(0, 2000);
                await new Promise(r => setTimeout(r, 1500));
            }
        }""")
    
    # Extract people from the page
    if 'people' in url:
        people = session.page.evaluate("""() => {
            const results = [];
            for (const card of document.querySelectorAll('.reusable-search__result-container, .entity-result')) {
                try {
                    const nameEl = card.querySelector('.entity-result__title-text a, .entity-result__title-text span[aria-hidden="true"]');
                    const name = nameEl ? nameEl.innerText.trim() : '';
                    
                    const linkEl = card.querySelector('a[href*="/in/"]');
                    const linkedinUrl = linkEl ? linkEl.href.split('?')[0] : '';
                    
                    const headlineEl = card.querySelector('.entity-result__primary-subtitle, .entity-result__subtitle');
                    const headline = headlineEl ? headlineEl.innerText.trim() : '';
                    
                    const companyEl = card.querySelector('.entity-result__secondary-subtitle');
                    const company = companyEl ? companyEl.innerText.trim() : '';
                    
                    if (name && linkedinUrl) {
                        results.push({name, linkedinUrl, headline, company});
                    }
                } catch (e) {}
            }
            return results;
        }""")
    else:
        # Content search - extract posts
        people = session.page.evaluate("""() => {
            const results = [];
            for (const card of document.querySelectorAll('.feed-shared-update-v2, .fie-impression-container')) {
                try {
                    const nameEl = card.querySelector('.update-components-actor__name, .feed-shared-actor__name a, .feed-shared-actor__name span');
                    const name = nameEl ? nameEl.innerText.trim() : '';
                    
                    const linkEl = card.querySelector('a[href*="/in/"]');
                    const linkedinUrl = linkEl ? linkEl.href.split('?')[0] : '';
                    
                    const headlineEl = card.querySelector('.update-components-actor__description, .feed-shared-actor__description');
                    const headline = headlineEl ? headlineEl.innerText.trim() : '';
                    
                    const bodyEl = card.querySelector('.feed-shared-update-v2__description, .update-components-text');
                    const body = bodyEl ? bodyEl.innerText.trim() : '';
                    
                    if (name && linkedinUrl) {
                        results.push({name, linkedinUrl, headline, body});
                    }
                } catch (e) {}
            }
            return results;
        }""")
    
    print(f'Found {len(people)} people')
    for p in people[:5]:
        print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
        all_people.append({**p, "family": family, "query_keywords": keywords})

print(f'\nTotal extracted: {len(all_people)}')
print(json.dumps(all_people, indent=2))

session.close()