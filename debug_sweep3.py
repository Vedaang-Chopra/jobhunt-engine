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

# Extract people from profile links
people_data = session.page.evaluate("""() => {
    const results = [];
    const links = document.querySelectorAll('a[href*="/in/"]');
    for (const link of links) {
        try {
            const href = link.href.split('?')[0];
            // Get the parent card-like container
            let container = link.closest('[data-entity-urn]') || link.closest('li') || link.closest('.entity-result') || link.parentElement;
            let name = '';
            let headline = '';
            let company = '';
            
            // Try to find name
            const nameEl = container?.querySelector('[aria-hidden="true"]') || container?.querySelector('.entity-result__title-text') || link.querySelector('span[aria-hidden="true"]');
            if (nameEl) name = nameEl.innerText.trim();
            
            // Try headline
            const headlineEl = container?.querySelector('.entity-result__primary-subtitle, .entity-result__subtitle');
            if (headlineEl) headline = headlineEl.innerText.trim();
            
            // Try company
            const companyEl = container?.querySelector('.entity-result__secondary-subtitle');
            if (companyEl) company = companyEl.innerText.trim();
            
            if (name && href.includes('/in/')) {
                results.push({name, linkedinUrl: href, headline, company, rawText: container?.innerText?.trim().slice(0, 300)});
            }
        } catch (e) {}
    }
    return results;
}""")

print(f'Found {len(people_data)} people')
for p in people_data:
    print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
    print(f'    URL: {p.get("linkedinUrl")}')

session.close()