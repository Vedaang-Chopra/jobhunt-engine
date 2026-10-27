#!/usr/bin/env python3
"""Debug LinkedIn page loading."""

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

print("URL:", page.url)
print("Title:", page.title())

# Check for job links
links = page.query_selector_all('a[href*="/jobs/view/"]')
print(f"Found {len(links)} job links")

# Get page text snippet
text = page.inner_text("body")[:3000]
print("Page text snippet:", text[:1000])

page.screenshot(path="/tmp/linkedin_debug.png")
print("Screenshot saved to /tmp/linkedin_debug.png")

page.close()
browser.close()
pw.stop()