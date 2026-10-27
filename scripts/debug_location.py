#!/usr/bin/env python3
"""Debug LinkedIn location extraction."""

from playwright.sync_api import sync_playwright
import time

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9333")
ctx = browser.contexts[0] if browser.contexts else browser.new_context()
page = ctx.pages[0] if ctx.pages else ctx.new_page()

url = "https://www.linkedin.com/jobs/search/?keywords=Research%20Engineer%20Machine%20Learning&location=United%20States&f_TPR=r604800"
print(f"Navigating to: {url}")
page.goto(url, wait_until="domcontentloaded", timeout=60000)
time.sleep(5)

# Scroll down to load more jobs
for _ in range(3):
    page.mouse.wheel(0, 1000)
    time.sleep(1)

# Debug location extraction
debug = page.evaluate("""() => {
    const cards = document.querySelectorAll('li[data-occludable-job-id]');
    const result = [];
    cards.forEach((card, index) => {
        if (index >= 3) return; // Just first 3
        const link = card.querySelector('a[href*="/jobs/view/"]');
        if (!link) return;
        
        // Try multiple selectors for location
        const locationSelectors = [
            '[class*="location"]',
            '[data-test-id="job-location"]',
            '.artdeco-entity-lockup__caption',
            '.job-search-card__location',
            '.job-search-card__location[class*="location"]',
            'span[class*="location"]',
            'div[class*="location"]'
        ];
        
        let location = '';
        let foundSelector = '';
        for (const selector of locationSelectors) {
            const el = card.querySelector(selector);
            if (el && el.textContent?.trim()) {
                location = el.textContent.trim();
                foundSelector = selector;
                break;
            }
        }
        
        // Also try to find by looking for text with commas and state codes
        if (!location) {
            const allText = card.innerText;
            const lines = allText.split('\\n');
            for (const line of lines) {
                if (line.match(/^[A-Za-z\\s]+,\\s*[A-Z]{2}$/) || 
                    line.match(/^[A-Za-z\\s]+,\\s*[A-Za-z\\s]+,\\s*[A-Z]{2}$/)) {
                    location = line.trim();
                    break;
                }
            }
        }
        
        result.push({
            index,
            title: card.querySelector('.artdeco-entity-lockup__title, h3, [data-test-id="job-title"]')?.textContent?.trim() || '',
            company: card.querySelector('.artdeco-entity-lockup__subtitle, h4, [data-test-id="company-name"]')?.textContent?.trim() || '',
            location: location,
            location_selector: foundSelector,
            snippet: card.innerText.substring(0, 200)
        });
    });
    return result;
}""")

print("Location debug info:")
for d in debug:
    print(f"  Card {d['index']}:")
    print(f"    Title: {d['title']}")
    print(f"    Company: {d['company']}")
    print(f"    Location: '{d['location']}' (via {d['location_selector']})")
    print(f"    Snippet: {d['snippet']}...")
    print()

page.close()
browser.close()
pw.stop()