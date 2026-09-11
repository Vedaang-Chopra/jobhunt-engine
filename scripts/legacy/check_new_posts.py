import csv
import re
from datetime import datetime

# Existing CSV path
csv_path = "/Users/vedaangchopra/all_data/Applications Custom/hermes/application_hunting/tracking/hiring_posts/hiring_posts.csv"

# Read existing post_urls
existing_urls = set()
try:
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_urls.add(row['post_url'])
except FileNotFoundError:
    pass

# Web search results from earlier (hardcoded)
results = [
    {
        "url": "https://www.linkedin.com/posts/lumay_hiring-aimlengineer-aijobs-activity-7495465423950393345-ECUv",
        "title": "We're hiring an AI/ML Engineer to join the growing team at LuMay AI. | LuMay AI",
        "description": "# We're hiring an AI/ML Engineer to join the growing team at LuMay AI. | LuMay AI Â· LinkedIn Â· 2026-08-18 ... We're looking for an experienced AI/ML professional who can build, evaluate, and deploy production-grade AI solutions across Machine Learning, Deep Learning, Generative AI, LLM applications, and AI agents. ... â¢ Machine Learning, Deep Learning & Generative AI ... is ideal for someone who ... Key responsibilities ... â¢ Build and deploy production-ready AI/ML solutions. ... â¢ Develop LLM applications, RAG pipelines, AI agents, and model workflows. ... â¢ Build retrieval and evaluation pipelines. ... â¢ Evaluate models for accuracy, relevance, grounding, hallucination, latency, and cost. ... â¢ Integrate AI services into production applications. ... rails and responsible-AI practices. ... ð Location: Chennai (Onsite) ... ð Experience: 3â5 years ... â¡ Joining: Immediate joiners or up to 10 days' notice ... How to apply ... ð§ jobs@lumay.ai ... ð www.lumay.ai"
    },
    {
        "url": "https://www.linkedin.com/posts/runplutus_hiring-activity-7493274103290736640-vz2p",
        "title": "We're a new Founding Machine Learning Engineer in Kirkland, Washington. Apply today or share this post with your network. | Plutus",
        "description": "We're#hiring a new Founding Machine Learning Engineer in Kirkland, Washington. Apply today or share this post with your network. ... ## Founding Machine Learning Engineer ... ### Plutus, Kirkland, WA"
    },
    {
        "url": "https://www.linkedin.com/posts/kayla-jade-butkow_were-hiring-a-machine-learning-engineer-activity-7490788141134479360-Fy5Q",
        "title": "Kayla-Jade Butkow's Post",
        "description": "# ð§ Weâre hiring a Machine Learning Engineer at auryx! | Kayla-Jade Butkow Â· LinkedIn Â· 2026-08-05 ... ð§ Weâre hiring a Machine Learning Engineer at [auryx](https://linkedin.com/company/auryxai)! ... If you enjoy developing and deploying machine learning models, conducting research from the ground up and turning it into a real-world product, this role could be a great fit. ... Youâll help us transform everyday earbuds into health and fitness sensors by developing models that extract meaningful insights from audio and biosignals. ... As part of a small, early-stage team, youâll work closely with me and our ML engineers, with plenty of ownership and the opportunity to shape our technical direction as we grow. ... See the full role description and application details here: https://shorturl.at/8ysdi"
    },
    {
        "url": "https://www.linkedin.com/posts/feiwang8177_were-hiring-ml-engineers-my-team-is-activity-7496431968964722690-BHsJ",
        "title": "We're hiring ML engineers! ð | Fei Wang",
        "description": "# We're hiring ML engineers! ð | Fei Wang Â· LinkedIn Â· 2026-08-21 ... We're hiring ML engineers! ð ... My team is hiring multiple ML engineers (IC5âIC7) to work on ranking for a brand-new standalone app we're building from the ground up at Meta. ... This is true 0â1 work: greenfield systems, fast iteration, and the chance to shape core ranking from day one â with high impact and visibility to match. ... Open to both internal transfers and external candidates. ... If fast-paced, ground-floor ML work sounds like you (or someone you know), reach out â I'd love to chat. ... > Hi Fei, Iâm interested in the ML Engineer opportunities at Meta. I have hands-on experience in Machine Learning, Deep Learning, Python, Generative AI, LLMs, and AI. Iâd be grateful if you could consider my profile for a suitable opportunity. Thank you!"
    },
    {
        "url": "https://www.linkedin.com/posts/kumaran-ponnambalam-961a344_machine-learning-engineer-in-san-jose-california-activity-7490511047846436865-GaYQ",
        "title": "Kumaran Ponnambalam's Post",
        "description": "# Weâre hiring a Machine Learning Engineer at Cisco. | Kumaran Ponnambalam Â· LinkedIn Â· 2026-08-04 ... Weâre hiring a Machine Learning Engineer at Cisco. ... Join the AI Incubation team in Cisco Customer Experience (CX) and help turn emerging AI ideas into scalable, production-ready capabilities. We are looking for someone with strong ML fundamentals, solid engineering skills, and the drive to build AI systems that create measurable real-world impact. ... You will work across machine learning, generative AI, and software engineering to: ... â¢ Build intelligent services that solve real customer problems â¢ Take AI from experimentation to enterprise deployment ... â¢ Collaborate with product and engineering teams â¢ Shape new AI capabilities for Cisco CX ... Interested, or know someone who would be a strong fit? ... Please apply here (& do not send resumes in DMs): ... https://lnkd.in/eUQ7eapf"
    }
]

# Role keywords from preferences (simplified)
role_keywords = [
    'ML', 'machine learning', 'AI', 'LLM', 'research engineer', 'applied scientist',
    'data scientist', 'inference', 'agentic', 'deep learning', 'software engineer',
    'SWE', 'backend', 'platform', 'vision', 'robotics'
]

def role_match(text):
    pattern = re.compile('|'.join(role_keywords), re.I)
    return bool(pattern.search(text))

def extract_poster_and_company(title, description):
    # Try to get company from title after ' at ' or before ' | '
    company = None
    # Pattern: "... at Company ..."
    match = re.search(r'at\s+([^|]+?)(?:\s+\||$)', title, re.I)
    if match:
        company = match.group(1).strip()
    else:
        # Pattern: "| Company" at end
        match = re.search(r'\|\s*([^|]+)$', title)
        if match:
            company = match.group(1).strip()
    if not company:
        # Fallback: look for known companies in description
        known = ['LuMay AI', 'Plutus', 'auryx', 'Meta', 'Cisco']
        for k in known:
            if k.lower() in description.lower():
                company = k
                break
    if not company:
        company = 'Unknown'
    return company, company  # poster_name same as company for simplicity

new_posts = []
for res in results:
    if res['url'] in existing_urls:
        continue
    if not role_match(res['description']):
        continue
    poster_name, company = extract_poster_and_company(res['title'], res['description'])
    # Extract date from description if possible
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', res['description'])
    posted_date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
    # Determine priority (simplified: high if hiring manager or recruiter detected)
    priority = 'medium'
    # Role family (simplified)
    role_family = 'applied_ml'  # default
    if re.search(r'agentica?i?c', res['description'], re.I):
        role_family = 'agentic_ai'
    elif re.search(r'inference|llm evaluation', res['description'], re.I):
        role_family = 'eval_inference'
    # Shared context: check for GT or Fortinet
    shared_context = []
    if re.search(r'GT|Georgia Tech', res['description'], re.I):
        shared_context.append('GT alumni')
    if re.search(r'Fortinet', res['description'], re.I):
        shared_context.append('Fortinet')
    shared_context_str = '; '.join(shared_context) if shared_context else ''
    new_posts.append({
        'poster_name': poster_name,
        'company': company,
        'roles_mentioned': res['description'][:100],  # placeholder
        'post_url': res['url'],
        'posted_date': posted_date,
        'priority': priority,
        'role_family': role_family,
        'shared_context': shared_context_str
    })

# Output new posts as JSON for easy consumption
import json
print(json.dumps(new_posts, indent=2))