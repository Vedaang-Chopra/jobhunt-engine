#!/usr/bin/env python3
"""Debug LinkedIn page - extract jobs with Playwright - using occludable job IDs."""

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

# Extract jobs using the li[data-occludable-job-id] as container
jobs = page.evaluate("""() => {
    const jobs = [];
    // Use the occludable job ID cards as containers
    const cards = document.querySelectorAll('li[data-occludable-job-id]');
    console.log('Cards found:', cards.length);
    cards.forEach(card => {
        const link = card.querySelector('a[href*="/jobs/view/"]');
        if (!link) return;
        const title = card.querySelector('h3')?.textContent?.trim() || 
                      card.querySelector('[data-test-id="job-title"]')?.textContent?.trim() ||
                      link.textContent?.trim() || '';
        const company = card.querySelector('h4')?.textContent?.trim() || 
                        card.querySelector('[data-test-id="company-name"]')?.textContent?.trim() || '';
        const location = card.querySelector('[class*="location"]')?.textContent?.trim() || '';
        const time = card.querySelector('time')?.textContent?.trim() || '';
        const url = link.href;
        const m = url.match(/\\/jobs\\/view\\/([^\\/?]+)/);
        const source_id = m ? m[1] : '';
        if (title && company && url && title.length > 3) {
            jobs.push({ title, company, location, date_posted: time, url, source_id });
        }
    });
    return jobs;
}""")

print(f"\nFound {len(jobs)} jobs:")
for j in jobs:
    print(f"  {j['title']} at {j['company']} - {j['location']} - {j['source_id']}")

page.screenshot(path="/tmp/linkedin_debug4.png")
print("Screenshot saved")

page.close()
browser.close()
pw.stop()