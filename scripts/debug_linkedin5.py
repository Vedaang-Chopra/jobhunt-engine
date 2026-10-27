#!/usr/bin/env python3
"""Debug LinkedIn page - extract jobs by looking at the actual HTML of occludable cards."""

from playwright.sync_api import sync_playwright
import time
import json

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

# Extract jobs by getting the HTML of each card and parsing
jobs = page.evaluate("""() => {
    const jobs = [];
    const cards = document.querySelectorAll('li[data-occludable-job-id]');
    console.log('Cards found:', cards.length);
    cards.forEach(card => {
        // Get the inner HTML for debugging
        const link = card.querySelector('a[href*="/jobs/view/"]');
        if (!link) return;
        
        // Try to find title and company within the card
        // LinkedIn uses artdeco-entity-lockup structure
        const titleEl = card.querySelector('.artdeco-entity-lockup__title, h3, [data-test-id="job-title"]');
        const companyEl = card.querySelector('.artdeco-entity-lockup__subtitle, h4, [data-test-id="company-name"]');
        const locationEl = card.querySelector('[class*="location"], [data-test-id="job-location"]');
        const timeEl = card.querySelector('time');
        
        const title = titleEl?.textContent?.trim() || link.textContent?.trim() || '';
        const company = companyEl?.textContent?.trim() || '';
        const location = locationEl?.textContent?.trim() || '';
        const time = timeEl?.textContent?.trim() || '';
        const url = link.href;
        const m = url.match(/\\/jobs\\/view\\/([^\\/?]+)/);
        const source_id = m ? m[1] : '';
        
        // Debug first card
        if (jobs.length === 0) {
            console.log('First card HTML snippet:', card.innerHTML.substring(0, 500));
            console.log('Title element:', titleEl?.outerHTML);
            console.log('Company element:', companyEl?.outerHTML);
        }
        
        if (title && company && url && title.length > 3) {
            jobs.push({ title, company, location, date_posted: time, url, source_id });
        }
    });
    return jobs;
}""")

print(f"\nFound {len(jobs)} jobs:")
for j in jobs:
    print(f"  {j['title']} at {j['company']} - {j['location']} - {j['source_id']}")

page.screenshot(path="/tmp/linkedin_debug5.png")
print("Screenshot saved")

page.close()
browser.close()
pw.stop()