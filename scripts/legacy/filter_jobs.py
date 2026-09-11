#!/usr/bin/env python3
import sys
import json

data = json.load(sys.stdin)
jobs = data.get('jobs', [])

keywords = [
    'research', 'engineer', 'ml', 'ai', 'llm', 'machine learning',
    'training', 'post-training', 'rl', 'agent', 'reasoning',
    'multimodal', 'applied scientist', 'inference', 'optimization',
    'post training', 'rlhf', 'dpo', 'grpo', 'sft', 'reinforcement',
    'foundation', 'generative', 'agentic', 'coding', 'synthesis',
    'evaluation', 'synthetic', 'routing', 'tool', 'memory',
    'orchestration', 'planning', 'distributed', 'serving'
]

relevant = []
for j in jobs:
    title_lower = j['title'].lower()
    if any(kw in title_lower for kw in keywords):
        relevant.append(j)

print(f'Total jobs: {len(jobs)}')
print(f'Relevant jobs: {len(relevant)}')
for j in relevant:
    loc = j['location']['name'] if j.get('location') else 'Unknown'
    print(f"  - {j['title']} | {loc} | {j['absolute_url']}")