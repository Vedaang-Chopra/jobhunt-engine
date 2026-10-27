#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import json

session = open_logged_in_session(source='people_sweep')
print('Auth state:', session.check_auth_state())

# Test one people search - use page.evaluate to wait for and extract
url = "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Wait for network idle
session.page.wait_for_load_state("networkidle", timeout=30000)

# Scroll extensively
for i in range(15):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(1500)

# Try to extract using page.evaluate with a more comprehensive approach
people = session.page.evaluate("""() => {
    const results = [];
    
    // Find all elements that look like person cards
    // Try multiple selector strategies
    const selectors = [
        'li[data-entity-urn*="person"]',
        'div[data-entity-urn*="person"]',
        '.reusable-search__result-container',
        '.entity-result',
        '[data-view-name="search-entity-result"]',
        'li:has(a[href*="/in/"])',
        'div:has(a[href*="/in/"])'
    ];
    
    let cards = [];
    for (const sel of selectors) {
        const found = document.querySelectorAll(sel);
        if (found.length > 0) {
            cards = Array.from(found);
            console.log('Found cards with selector:', sel, found.length);
            break;
        }
    }
    
    // Fallback: all links with /in/
    if (cards.length === 0) {
        const links = document.querySelectorAll('a[href*="/in/"]');
        cards = Array.from(links).map(l => l.closest('li, div')).filter(Boolean);
        console.log('Fallback to links, cards:', cards.length);
    }
    
    for (const card of cards) {
        try {
            // Get the profile link
            const linkEl = card.querySelector('a[href*="/in/"]');
            if (!linkEl) continue;
            const linkedinUrl = linkEl.href.split('?')[0];
            
            // Get name - try multiple strategies
            let name = '';
            const nameSelectors = [
                '.entity-result__title-text a',
                '.entity-result__title-text span[aria-hidden="true"]',
                'span[aria-hidden="true"]',
                '.entity-result__title-text',
                'h3',
                'h2',
                '[data-anonymize="person-name"]'
            ];
            for (const sel of nameSelectors) {
                const el = card.querySelector(sel);
                if (el) {
                    const text = el.innerText.trim();
                    if (text && text.length > 2 && text.length < 60) {
                        name = text;
                        break;
                    }
                }
            }
            
            // Get headline
            let headline = '';
            const headlineSelectors = [
                '.entity-result__primary-subtitle',
                '.entity-result__subtitle',
                '.entity-result__summary',
                '[data-anonymize="person-headline"]'
            ];
            for (const sel of headlineSelectors) {
                const el = card.querySelector(sel);
                if (el) {
                    headline = el.innerText.trim();
                    break;
                }
            }
            
            // Get company/location
            let company = '';
            const companySelectors = [
                '.entity-result__secondary-subtitle',
                '.entity-result__summary--2-lines',
                '[data-anonymize="person-company"]'
            ];
            for (const sel of companySelectors) {
                const el = card.querySelector(sel);
                if (el) {
                    company = el.innerText.trim();
                    break;
                }
            }
            
            if (name) {
                results.push({name, linkedinUrl, headline, company});
            }
        } catch (e) {
            console.error('Error processing card:', e);
        }
    }
    
    return results;
}""")

print(f'Found {len(people)} people')
for p in people[:20]:
    print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
    print(f'    URL: {p.get("linkedinUrl")}')

session.close()