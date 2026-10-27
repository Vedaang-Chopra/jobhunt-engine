#!/usr/bin/env python3
"""Fetch LinkedIn guest API results for all 8 queries."""
import urllib.request
import urllib.parse

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'}

queries = [
    'Research Engineer Machine Learning',
    'AI Research Scientist',
    'Post-Training LLM',
    'LLM Fine-Tuning Engineer',
    'AI Agent Engineer',
    'Applied Scientist AI',
    'Machine Learning Engineer LLM',
    'LLM Evaluation Research',
]

for q in queries:
    params = {'keywords': q, 'location': 'United States', 'f_TPR': 'r604800', 'start': '0'}
    url = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        print(f'=== {q} ===')
        print(f'Length: {len(body)}')
        print(body[:3000])
        print('...')
        print()
    except Exception as e:
        print(f'Error for {q}: {e}')
        print()