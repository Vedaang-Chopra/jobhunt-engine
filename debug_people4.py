#!/usr/bin/env python3
from scripts.browser_session_lib import open_logged_in_session
import json

session = open_logged_in_session(source='people_sweep')
print('Auth state:', session.check_auth_state())

# Test one people search - simpler approach
url = "https://www.linkedin.com/search/results/people/?keywords=%22Mistral%20AI%22&origin=FACETED_SEARCH"
session.page.goto(url)
print(f'URL: {session.page.url}')

# Just wait
session.page.wait_for_timeout(8000)

# Scroll extensively
for i in range(15):
    session.page.evaluate("window.scrollBy(0, 2000)")
    session.page.wait_for_timeout(1000)

# Try to extract using page.evaluate
people = session.page.evaluate("""() => {
    const results = [];
    
    // Get all profile links
    const links = document.querySelectorAll('a[href*="/in/"]');
    
    for (const link of links) {
        try {
            const linkedinUrl = link.href.split('?')[0];
            
            // Get the text of the link and its parents
            const linkText = link.innerText.trim();
            const parent = link.parentElement;
            const parentText = parent ? parent.innerText.trim() : '';
            const grandParent = parent ? parent.parentElement : null;
            const grandParentText = grandParent ? grandParent.innerText.trim() : '';
            
            const allText = (linkText + '\\n' + parentText + '\\n' + grandParentText).trim();
            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            
            // Name is usually the first short line
            let name = '';
            let headline = '';
            let company = '';
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                
                // Skip UI elements
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
    
    // Deduplicate by URL
    const seen = new Set();
    const unique = [];
    for (const p of results) {
        if (!seen.has(p.linkedinUrl)) {
            seen.add(p.linkedinUrl);
            unique.push(p);
        }
    }
    
    return unique;
}""")

print(f'Found {len(people)} people')
for p in people[:20]:
    print(f'  - {p.get("name")} | {p.get("headline", "")[:80]} | {p.get("company", "")[:50]}')
    print(f'    URL: {p.get("linkedinUrl")}')

session.close()