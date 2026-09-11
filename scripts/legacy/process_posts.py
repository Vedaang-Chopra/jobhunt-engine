import csv
from datetime import datetime, timedelta
from pathlib import Path
import re

REPO = Path('/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting')
DATA_ROOT = REPO
POSTS_CSV = DATA_ROOT / 'tracking' / 'hiring_posts' / 'hiring_posts.csv'

POSTS_HEADER = [
    'post_id', 'poster_name', 'poster_headline', 'poster_type', 'company',
    'team_or_org', 'post_url', 'posted_date', 'discovered_date',
    'roles_mentioned', 'application_url', 'connection_degree',
    'shared_context', 'priority', 'role_family', 'status', 'notes',
]

def classify_poster(headline):
    h = (headline or '').lower()
    if any(w in h for w in ('recruiter', 'talent acquisition', 'talent partner', 'sourcing', 'recruiting')):
        return 'recruiter'
    if any(w in h for w in ('manager', 'director', 'vp ', 'founder', 'ceo', 'cto', 'head of')):
        return 'hiring_manager'
    return 'engineer_researcher'

def classify_priority(poster_type):
    return 'high' if poster_type in ('recruiter', 'hiring_manager') else 'normal'

ROLE_FAMILY_HINTS = [
    ('agentic', 'agentic_ai'), ('agent', 'agentic_ai'), ('multi-agent', 'agentic_ai'),
    ('rag', 'agentic_ai'), ('langgraph', 'agentic_ai'), ('distributed training', 'ml_training_arch'),
    ('pre-training', 'ml_training_arch'), ('training engineer', 'ml_training_arch'),
    ('training infra', 'ml_training_arch'), ('gpu', 'ml_training_arch'), ('fsdp', 'ml_training_arch'),
    ('evaluation', 'eval_inference'), ('evals', 'eval_inference'), ('benchmark', 'eval_inference'),
    ('vllm', 'eval_inference'), ('inference', 'eval_inference'), ('red team', 'ai_security'),
    ('adversarial', 'ai_security'), ('applied scientist', 'applied_ml'),
    ('machine learning engineer', 'applied_ml'), ('research engineer', 'research_engineer'),
]

def classify_role_family(text):
    t = (text or '').lower()
    for hint, family in ROLE_FAMILY_HINTS:
        if hint in t:
            return family
    return 'other'

def parse_relative_time(time_str):
    # time_str is like "2w", "4d", "3h", etc.
    # We'll only handle weeks and days for simplicity.
    if time_str.endswith('w'):
        weeks = int(time_str[:-1])
        return datetime.now() - timedelta(weeks=weeks)
    elif time_str.endswith('d'):
        days = int(time_str[:-1])
        return datetime.now() - timedelta(days=days)
    elif time_str.endswith('h'):
        hours = int(time_str[:-1])
        return datetime.now() - timedelta(hours=hours)
    else:
        # If we can't parse, return today
        return datetime.now()

def _post_id(post, discovered_date):
    slug_src = (post.get('company') or post.get('poster') or 'post').strip()
    slug = ''.join(c if c.isalnum() else '_' for c in slug_src.lower())[:40].strip('_')
    tail = (post.get('urn') or post.get('posterUrl') or post.get('post_url') or 'x')
    tail = ''.join(c for c in tail if c.isalnum())[-8:] or 'x'
    return f'{slug}_{discovered_date}_{tail}'

def to_post_row(post, discovered_date, source_note):
    headline = post.get('headline', '')[:300]
    roles = (post.get('roles_mentioned') or '').strip()
    body = (post.get('body') or '')[:400]
    poster_type = classify_poster(headline)
    text_for_family = ' '.join((headline, roles, body))
    return {
        'post_id': _post_id(post, discovered_date),
        'poster_name': post.get('poster', ''),
        'poster_headline': headline,
        'poster_type': poster_type,
        'company': (post.get('company') or '').strip(),
        'team_or_org': '',
        'post_url': post.get('posterUrl') or post.get('post_url', ''),
        'posted_date': post.get('posted_date', ''),
        'discovered_date': discovered_date,
        'roles_mentioned': roles,
        'application_url': post.get('link_url', '') or post.get('application_url', ''),
        'connection_degree': post.get('degree', ''),
        'shared_context': '',
        'priority': classify_priority(poster_type),
        'role_family': classify_role_family(text_for_family),
        'status': 'new',
        'notes': f'{source_note}; urn:{post.get("urn", "")}; {body[:160]}'.strip('; '),
    }

def load_seen_posts(posts_csv):
    seen = set()
    if not posts_csv.exists():
        return seen
    with open(posts_csv, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            url = (row.get('post_url') or '').strip().rstrip('/')
            if url:
                seen.add(url.lower())
            notes_urn = ''
            notes = row.get('notes') or ''
            if 'urn:' in notes:
                notes_urn = notes.split('urn:')[-1].split()[0].strip('.,;')
            if notes_urn:
                seen.add(f'urn:{notes_urn}'.lower())
            key = '|'.join(str(x or '').strip().lower() for x in (row.get('poster_name'), row.get('roles_mentioned'), row.get('posted_date')))
            if key.strip('|'):
                seen.add(key)
    return seen

def post_key(post):
    keys = []
    url = (post.get('post_url') or '').strip().rstrip('/')
    if url:
        keys.append(url.lower())
    if post.get('urn'):
        keys.append(f"urn:{post['urn']}".lower())
    fuzzy = '|'.join(str(x or '').strip().lower() for x in (post.get('poster'), post.get('roles_mentioned'), post.get('posted_date')))
    if fuzzy.strip('|'):
        keys.append(fuzzy)
    return keys

def main():
    # The two posts we extracted from the feed
    posts = [
        {
            'poster': 'Dino Alabre',
            'posterUrl': 'https://www.linkedin.com/in/dino-alabre-144417239/',
            'degree': '2nd',
            'headline': 'Founder | Talent Recruiter for Contrario (YC W25), Rounds & Paraform | Hiring Engineers, Operators, Product & GTM Talent',
            'time': '2w',
            'urn': '',
            'role_match': True,
            'body': "I'm partnering with several YC and VC backed AI startups in San Francisco that are building some of the most ambitious products I've seen, and we're looking for exceptional engineers who want to build from zero to one.\nWe're currently hiring for:\nApplied AI Engineers\nMembers of Technical Staff\nForward Deployed Engineers\nFounding Engineers\nWe're looking for engineers with 2–6 years of experience who thrive in fast paced startup environments and want to work directly alongside founders.\nSome backgrounds that stand out:\nFormer founders\nFounding engineers\nEarly startup engineers\nPalantir Forward Deployed Engineers\nEngineers from companies like Ramp, Mercury, Brex, Decagon, Sierra, Glean, Retell, Vapi, Deepgram, Harvey, and other AI native startups\nExperience building AI agents, MCP infrastructure, LLMs, backend systems, developer tools, or production AI products\nStrong CS backgrounds from schools like Stanford, MIT, CMU, Berkeley, Harvard, Princeton, Yale, Cornell, Georgia Tech, UIUC, Waterloo, and similar programs\nThese roles are all based in San Francisco, so candidates should either already be in SF or be excited to relocate and build in person with an incredible team.\nIf you're exp",
            'link_url': '',
            'post_url': ''
        },
        {
            'poster': 'Dino Alabre',
            'posterUrl': 'https://www.linkedin.com/in/dino-alabre-144417239/',
            'degree': '2nd',
            'headline': 'Founder | Talent Recruiter for Contrario (YC W25), Rounds & Paraform | Hiring Engineers, Operators, Product & GTM Talent',
            'time': '4d',
            'urn': '',
            'role_match': True,
            'body': "I’m hiring for 2 YC-backed, VC-backed AI startups in San Francisco. 🚀\nBoth are early-stage teams looking for high-agency engineers who want 0→1 ownership, direct access to founders/customers, and the ability to ship quickly.\nBackend Software Engineer — YC S24\n💰 $165K–$300K + equity\n• 2–6 years of backend engineering experience\n• Backend / production systems\n• Node.js, TypeScript, PostgreSQL, Python, AWS\n• Strong CS background\n• High-growth VC-backed startup experience\n• SF, in person\nAI Forward Deployed Engineer — YC W24\n💰 $150K–$300K + 0.25%–0.75% equity\n• 3+ YOE\n• Strong Python or TypeScript\n• Customer-facing + project ownership\n• AI agents / workflow automation\n• Own deployments from customer problem → production\n• SF, in person\nEspecially interested in former founders, founding engineers, early startup engineers, and technical FDEs who thrive in ambiguity and move fast.\nIf this sounds like you or someone exceptional comes to mind DM me or send me your resume.\n​",
            'link_url': '',
            'post_url': ''
        }
    ]

    # Process each post: add company and posted_date
    for post in posts:
        # Determine company from headline
        if 'Contrario' in post['headline']:
            post['company'] = 'Contrario'
        elif 'YC-backed' in post['headline'] and 'VC-backed' in post['headline']:
            post['company'] = 'YC-backed AI startups'
        else:
            post['company'] = ''
        # Compute posted_date from time string
        post['posted_date'] = parse_relative_time(post['time']).strftime('%Y-%m-%d')

    seen = load_seen_posts(POSTS_CSV)
    new_rows = []
    for post in posts:
        keys = [k for k in post_key(post) if k.strip('|')]
        if any(k in seen for k in keys):
            print(f"Skipping duplicate post by {post['poster']}")
            continue
        # Not seen, add to new_rows and update seen
        discovered_date = datetime.now().strftime('%Y-%m-%d')
        row = to_post_row(post, discovered_date, f'feed_sweep_{datetime.now().strftime("%Y%m%d_%H%M")}')
        new_rows.append(row)
        seen.update(keys)

    if new_rows:
        file_exists = POSTS_CSV.exists() and POSTS_CSV.stat().st_size > 0
        with open(POSTS_CSV, 'a', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=POSTS_HEADER)
            if not file_exists:
                writer.writeheader()
            for row in new_rows:
                writer.writerow({k: row.get(k, '') for k in POSTS_HEADER})
        print(f'Appended {len(new_rows)} new hiring posts to {POSTS_CSV}')
        # Also mirror to job_research/companies/<slug>/hiring_posts.csv if dir exists
        for row in new_rows:
            company_slug = re.sub(r'[^a-z0-9]+', '-', row['company'].lower()).strip('-')
            if company_slug:
                company_dir = DATA_ROOT / 'job_research' / 'companies' / company_slug
                if company_dir.exists():
                    company_posts_csv = company_dir / 'hiring_posts.csv'
                    company_file_exists = company_posts_csv.exists() and company_posts_csv.stat().st_size > 0
                    with open(company_posts_csv, 'a', newline='', encoding='utf-8') as fh:
                        writer = csv.DictWriter(fh, fieldnames=POSTS_HEADER)
                        if not company_file_exists:
                            writer.writeheader()
                        writer.writerow({k: row.get(k, '') for k in POSTS_HEADER})
                    print(f'Mirrored to {company_posts_csv}')
    else:
        print('No new posts to append')

if __name__ == '__main__':
    main()