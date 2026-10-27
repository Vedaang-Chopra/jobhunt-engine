#!/usr/bin/env python3
import sys
sys.path.insert(0, 'scripts')
from people_sweep import load_preferences, build_queries, cap_queries

prefs = load_preferences()
print(f'Role families: {list(prefs["role_keywords"].keys())}')
print(f'Companies ({len(prefs["companies"])}): {prefs["companies"][:10]}...')

queries = build_queries(prefs, policy={'enable_school_family': False})
print(f'Total queries before cap: {len(queries)}')

capped = cap_queries(queries, 8)
print(f'After cap to 8: {len(capped)}')
for q in capped:
    print(f'  [{q["family"]}] {q["keywords"]}')
    print(f'    {q["url"]}')