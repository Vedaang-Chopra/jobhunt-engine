#!/usr/bin/env python3
import csv

# Read existing hiring posts
existing_urls = set()
with open('/mnt/DATA/job_hunt/jobhunt-engine/jobhunt-data/tracking/hiring_posts/hiring_posts.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        existing_urls.add(row.get('post_url', ''))

# LinkedIn post URLs from web search
web_search_urls = [
    "https://www.linkedin.com/posts/ivan-alagenchev-6003754a_ai-engineer-ii-generative-ai-agents-activity-7445959207670956032-Bf72",
    "https://www.linkedin.com/posts/thatstatsgirl_2026-fall-applied-science-internship-gen-activity-7453423363005317120-7WTA",
    "https://www.linkedin.com/posts/nikhilboreddy_microsoft-careers-activity-7476029815649660929-08rf",
    "https://www.linkedin.com/posts/perouz_agenticai-llm-airesearch-activity-7485441671455723520-Yr2S",
    "https://www.linkedin.com/posts/parmidab_hiring-activity-7425594408978493442-zqZT",
    "https://www.linkedin.com/posts/happygirlzt_aiforsoftwaresecurity-llmforcode-softwareengineering-activity-7427168368543145985-cvB8",
    "https://www.linkedin.com/posts/marcelo-d-amorim-a1a31121_im-looking-for-two-highly-motivated-students-activity-7485119054458941440-1wHO",
    "https://www.linkedin.com/posts/john-jumper-2ab9429b_research-scientist-llm-science-activity-7326143408152993792-55P2",
    "https://www.linkedin.com/posts/chuanche_im-hiring-an-edge-ai-ml-engineer-to-join-activity-7502933636908957696-YRQ2",
    "https://www.linkedin.com/posts/millman_join-my-team-we-are-hiring-two-junior-data-activity-7458295879079206912-Mpv7",
    "https://www.linkedin.com/posts/chen-yo-sun_join-mistral-ai-were-hiring-mistral-activity-7455787216251002881-CPGD",
    "https://www.linkedin.com/posts/seraphinatarrant_the-safety-team-at-cohere-is-hiring-2-full-activity-7475133202337234944-tmCT",
    "https://www.linkedin.com/posts/mads-jenkins_come-work-with-us-activity-7475135772023660544-rMzh",
    "https://www.linkedin.com/posts/nataliedwilson_careers-cohere-activity-7498878811678076928-C_4x",
    "https://www.linkedin.com/posts/essiane-abel_hiring-hiring-aiengineering-activity-7472343549078966273-UWyx",
    "https://www.linkedin.com/posts/mateizaharia_this-team-is-awesome-great-role-for-any-activity-7460546982529511424-6n6V",
    "https://www.linkedin.com/posts/mattkix_were-hiring-for-a-lot-of-ai-roles-on-my-activity-7485457406551056385-si7U",
    "https://www.linkedin.com/posts/julianeagu_im-building-a-new-team-at-databricks-ai-activity-7461134763681185792-qoWZ",
    "https://www.linkedin.com/posts/coherehealth_were-hiring-a-director-of-data-ai-to-lead-activity-7463302585790222336-SL-i",
    "https://www.linkedin.com/posts/andrewmcleodiii_you-asked-here-it-is-whats-the-hiring-activity-7470954517677719553-oJHD",
    "https://www.linkedin.com/posts/scottlgarner_ai-inference-is-the-new-bottleneck-why-hiring-activity-7417966917002641408-jETT",
    "https://www.linkedin.com/posts/jaiprasadr_ai-reinforcementlearning-aiagents-activity-7453557683598807040-6Vum",
    "https://www.linkedin.com/posts/yashchandak_were-expanding-our-post-training-efforts-activity-7396965448552017921-G7X_",
    "https://www.linkedin.com/posts/zhen-han-08a769128_2026-applied-science-internship-gen-ai-activity-7401125318314434560-SFo0",
    "https://www.linkedin.com/posts/hhillondeep_were-hiring-university-of-waterloo-winter-activity-7372017056856199168-4Bvc",
    "https://www.linkedin.com/posts/jennifer-zhu_2026-applied-science-internship-reinforcement-activity-7387151799788544000-84LK",
    "https://www.linkedin.com/posts/huibing-dong-728a3914b_closed-research-internship-opportunity-activity-7380100412793655296-Sull"
]

new_urls = [url for url in web_search_urls if url not in existing_urls]
print(f"Total web search URLs: {len(web_search_urls)}")
print(f"Existing URLs: {len(existing_urls)}")
print(f"New URLs: {len(new_urls)}")
print()
print("New URLs:")
for url in new_urls:
    print(f"  {url}")