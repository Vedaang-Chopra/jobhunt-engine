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

# Extract people from profile links - more robust approach
people_data = session.page.evaluate("""() => {
    const results = [];
    const links = document.querySelectorAll('a[href*="/in/"]');
    for (const link of links) {
        try {
            const href = link.href.split('?')[0];
            // Get text content of the link and its parent
            const linkText = link.innerText.trim();
            const parentText = link.parentElement?.innerText?.trim() || '';
            const grandParentText = link.parentElement?.parentElement?.innerText?.trim() || '';
            
            // Heuristic: name is usually the first line, headline second, etc.
            const allText = (linkText + ' ' + parentText + ' ' + grandParentText).trim();
            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l);
            
            // Filter out obvious non-people links
            const badWords = ['connect', 'message', 'follow', 'linkedin', 'jobs', 'company', 'school', 'groups', 'events', 'posts', 'articles', 'notification', 'settings', 'help', 'sign out', 'me', 'home', 'my network', 'messaging', 'jobs', 'work', 'learning'];
            const isBad = badWords.some(b => linkText.toLowerCase().includes(b) || href.toLowerCase().includes(b));
            
            // Name should be short-ish and not contain pipes or @
            const nameCandidate = lines[0] || '';
            const isNameLike = nameCandidate.length > 2 && nameCandidate.length < 50 && !nameCandidate.includes('|') && !nameCandidate.includes('@') && !nameCandidate.includes('•') && !isBad;
            
            if (isNameLike && href.includes('/in/')) {
                // Try to extract headline and company from subsequent lines
                let headline = '';
                let company = '';
                for (let i = 1; i < Math.min(lines.length, 5); i++) {
                    const line = lines[i];
                    if (line.includes(' at ') || line.includes(' @ ') || line.includes(' | ') || line.toLowerCase().includes('engineer') || line.toLowerCase().includes('scientist') || line.toLowerCase().includes('research') || line.toLowerCase().includes('manager') || line.toLowerCase().includes('director') || line.toLowerCase().includes('lead')) {
                        if (!headline) headline = line;
                        else if (!company) company = line;
                    } else if (!company && line.length > 3 && line.length < 60) {
                        company = line;
                    }
                }
                
                results.push({name: nameCandidate, linkedinUrl: href, headline, company, rawLines: lines.slice(0, 5)});
            }
        } catch (e) {}
    }
    return results;
}""")

print(f'Found {len(people_data)} people')
for p in people_data:
    print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
    print(f'    URL: {p.get("linkedinUrl")}')
    print(f'    Raw: {p.get("rawLines")}')

session.close()