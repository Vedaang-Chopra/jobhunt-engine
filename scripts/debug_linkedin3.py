#!/usr/bin/env python3
"""Debug LinkedIn page - extract jobs with Playwright - more debugging."""

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

# Debug: check what elements exist
debug = page.evaluate("""() => {
    const result = {};
    result.all_li = document.querySelectorAll('li').length;
    result.job_view_links = document.querySelectorAll('a[href*="/jobs/view/"]').length;
    result.occludable = document.querySelectorAll('li[data-occludable-job-id]').length;
    result.job_search_card = document.querySelectorAll('li[class*="job-search-card"]').length;
    result.jobs_search_results = document.querySelectorAll('li[class*="jobs-search-results"]').length;
    result.ul_role_list = document.querySelectorAll('ul[role="list"] > li').length;
    
    // Get first few job view links
    const links = document.querySelectorAll('a[href*="/jobs/view/"]');
    result.sample_links = [];
    for (let i = 0; i < Math.min(links.length, 5); i++) {
        result.sample_links.push({
            href: links[i].href,
            text: links[i].textContent?.trim().substring(0, 100),
            parent_tag: links[i].parentElement?.tagName,
            parent_class: links[i].parentElement?.className?.substring(0, 100)
        });
    }
    
    return result;
}""")

print("Debug info:", json.dumps(debug, indent=2))

# Try to extract with a broader approach
jobs = page.evaluate("""() => {
    const jobs = [];
    // Get all job view links
    const links = document.querySelectorAll('a[href*="/jobs/view/"]');
    links.forEach(link => {
        // Walk up to find a container that looks like a job card
        let card = link.closest('li');
        if (!card) card = link.closest('div[class*="job"]');
        if (!card) card = link.closest('article');
        if (!card) card = link.parentElement;
        
        const title = card?.querySelector('h3')?.textContent?.trim() || 
                      card?.querySelector('[data-test-id="job-title"]')?.textContent?.trim() ||
                      link.textContent?.trim() || '';
        const company = card?.querySelector('h4')?.textContent?.trim() || 
                        card?.querySelector('[data-test-id="company-name"]')?.textContent?.trim() || '';
        const location = card?.querySelector('[class*="location"]')?.textContent?.trim() || '';
        const time = card?.querySelector('time')?.textContent?.trim() || '';
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

page.screenshot(path="/tmp/linkedin_debug3.png")
print("Screenshot saved")

page.close()
browser.close()
pw.stop()