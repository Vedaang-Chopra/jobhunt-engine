"""
Helper functions for AI/ML job market research browser automation.
This file is auto-imported into every browser_exec call.
Updated for new repository structure.
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).parent.parent

try:
    from config_lib import data_root
except ImportError:  # direct-import fallback when scripts/ is not on sys.path
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from config_lib import data_root  # type: ignore  # noqa: F811

DATA_DIR = data_root() / "job_research" / "data"
JOBS_DIR = data_root() / "tracking" / "job_descriptions" / "active"

DATA_DIR.mkdir(exist_ok=True)
JOBS_DIR.mkdir(exist_ok=True)

RAW_RESULTS_FILE = DATA_DIR / "raw_search_results.jsonl"
VERIFIED_JOBS_FILE = DATA_DIR / "verified_jobs.jsonl"
REJECTED_JOBS_FILE = DATA_DIR / "rejected_jobs.jsonl"


def save_raw_result(result: Dict[str, Any]) -> None:
    """Append a raw search result to the log."""
    result["timestamp"] = datetime.now().isoformat()
    with open(RAW_RESULTS_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")


def save_verified_job(job: Dict[str, Any]) -> None:
    """Append a verified job to the log."""
    job["verified_at"] = datetime.now().isoformat()
    with open(VERIFIED_JOBS_FILE, "a") as f:
        f.write(json.dumps(job) + "\n")


def save_rejected_job(job: Dict[str, Any], reason: str) -> None:
    """Log a rejected job with reason."""
    job["rejected_at"] = datetime.now().isoformat()
    job["rejection_reason"] = reason
    with open(REJECTED_JOBS_FILE, "a") as f:
        f.write(json.dumps(job) + "\n")


def load_verified_jobs() -> List[Dict[str, Any]]:
    """Load all verified jobs from the log."""
    jobs = []
    if VERIFIED_JOBS_FILE.exists():
        with open(VERIFIED_JOBS_FILE) as f:
            for line in f:
                if line.strip():
                    jobs.append(json.loads(line))
    return jobs


def load_rejected_jobs() -> List[Dict[str, Any]]:
    """Load all rejected jobs from the log."""
    jobs = []
    if REJECTED_JOBS_FILE.exists():
        with open(REJECTED_JOBS_FILE) as f:
            for line in f:
                if line.strip():
                    jobs.append(json.loads(line))
    return jobs


def is_duplicate(job: Dict[str, Any], existing_jobs: List[Dict[str, Any]]) -> bool:
    """Check if a job is a duplicate of an existing one."""
    key = (job.get("company", "").lower().strip(), 
           job.get("title", "").lower().strip(),
           job.get("location", "").lower().strip())
    for existing in existing_jobs:
        existing_key = (existing.get("company", "").lower().strip(),
                        existing.get("title", "").lower().strip(),
                        existing.get("location", "").lower().strip())
        if key == existing_key:
            return True
    return False


def extract_job_id(url: str) -> str:
    """Extract a unique identifier from a job URL."""
    # Remove query params and fragments
    clean_url = url.split("?")[0].split("#")[0]
    # Get last path segment
    return clean_url.rstrip("/").split("/")[-1]


def sanitize_filename(text: str) -> str:
    """Sanitize text for use in filename."""
    # Replace spaces and special chars
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.strip('_')


def save_job_description(job: Dict[str, Any]) -> str:
    """Save full job description to a markdown file. Returns the file path."""
    company = sanitize_filename(job.get("company", "unknown_company"))
    title = sanitize_filename(job.get("title", "unknown_title"))
    job_id = extract_job_id(job.get("url", ""))
    
    filename = f"{company}__{title}__{job_id}.md"
    filepath = JOBS_DIR / filename
    
    md_content = f"""# {job.get('title', 'Unknown Title')}

**Company:** {job.get('company', 'Unknown')}
**Location:** {job.get('location', 'Unknown')}
**Remote/Hybrid/On-site:** {job.get('work_type', 'Unknown')}
**Job URL:** {job.get('url', 'Unknown')}
**Source:** {job.get('source', 'Unknown')}
**Date Discovered:** {job.get('date_discovered', 'Unknown')}
**Date Posted:** {job.get('date_posted', 'Unknown')}
**Salary Range:** {job.get('salary', 'Not listed')}
**Team:** {job.get('team', 'Not specified')}

---

## Role Description
{job.get('role_description', 'Not provided')}

---

## Responsibilities
{job.get('responsibilities', 'Not provided')}

---

## Minimum Qualifications
{job.get('min_qualifications', 'Not provided')}

---

## Preferred Qualifications
{job.get('preferred_qualifications', 'Not provided')}

---

## Required Technologies
{job.get('required_tech', 'Not provided')}

---

## Preferred Technologies
{job.get('preferred_tech', 'Not provided')}

---

## Experience Requirement
{job.get('experience_req', 'Not specified')}

---

## Education Requirement
{job.get('education_req', 'Not specified')}

---

## Full Job Description Text
{job.get('full_jd_text', 'Not captured')}

---

## My Fit Analysis
**Fit Score:** {job.get('fit_score', 'Not scored')}
**Interview Probability:** {job.get('interview_category', 'Not categorized')}

**Why It Fits:**
{job.get('why_fits', 'Not analyzed')}

**Biggest Gap:**
{job.get('biggest_gap', 'Not analyzed')}

**Technical Skill Overlap:** {job.get('tech_overlap', 'Not scored')}/25
**Research/Domain Overlap:** {job.get('research_overlap', 'Not scored')}/20
**Production Engineering Overlap:** {job.get('prod_overlap', 'Not scored')}/15
**Experience Level Compatibility:** {job.get('exp_compatibility', 'Not scored')}/15
**Education/Research Compatibility:** {job.get('edu_compatibility', 'Not scored')}/10
**Project Demonstration Potential:** {job.get('project_potential', 'Not scored')}/10
**Location/Start Date Practicality:** {job.get('location_practicality', 'Not scored')}/5

---

*Saved on: {datetime.now().isoformat()}*
"""
    
    with open(filepath, "w") as f:
        f.write(md_content)
    
    return str(filepath)


def extract_text_from_page() -> str:
    """Extract all visible text from the current page."""
    return js("() => document.body.innerText")


def wait_for_page_load(seconds: float = 3) -> None:
    """Wait for page to fully load."""
    time.sleep(seconds)
    wait_for_load()


def find_job_links_on_page(base_url: str = "") -> List[Dict[str, str]]:
    """Find all job links on the current page."""
    # This will be customized per site
    links = js("""
    () => {
        const links = [];
        const anchors = document.querySelectorAll('a[href]');
        for (const a of anchors) {
            const href = a.href;
            const text = a.innerText.trim();
            if (href && text.length > 5) {
                links.push({url: href, text: text});
            }
        }
        return links;
    }
    """)
    return links


def scroll_to_bottom() -> None:
    """Scroll to bottom of page to load lazy content."""
    js("() => window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)


def click_load_more() -> bool:
    """Try to click 'Load More' or similar buttons."""
    selectors = [
        "button:contains('Load More')",
        "button:contains('Show More')",
        "button:contains('See More')",
        "[data-testid='load-more']",
        ".load-more",
        "#load-more"
    ]
    
    for selector in selectors:
        try:
            result = js(f"""
            () => {{
                const btn = document.querySelector('{selector}');
                if (btn) {{
                    btn.click();
                    return true;
                }}
                return false;
            }}
            """)
            if result:
                time.sleep(2)
                return True
        except:
            continue
    return False


# Candidate profile for reference during scoring
CANDIDATE_PROFILE = {
    "education": "M.S. Computer Science, Machine Learning specialization, Georgia Tech (Dec 2026)",
    "experience_years": "4+ years professional software/ML engineering",
    "research_focus": [
        "LLM post-training",
        "reinforcement learning",
        "program synthesis / code generation",
        "agentic AI systems",
        "multimodal models",
        "model routing",
        "tool-using agents",
        "iterative execution, evaluation, and repair"
    ],
    "production_experience": [
        "ML systems",
        "backend/distributed systems",
        "production AI systems",
        "RAG / agentic workflows",
        "APIs and tool calling",
        "search/retrieval infrastructure",
        "Python",
        "Golang"
    ],
    "target_graduation": "December 2026",
    "target_start": "December 2026 / early 2027",
    "preferred_locations": ["US", "Remote-US", "SF Bay Area", "NYC", "Seattle", "Boston", "Atlanta"],
    "primary_roles": [
        "Research Engineer — LLMs / Agents / Reasoning",
        "Research Engineer — Post-training / RL / RLHF / Alignment",
        "Applied Scientist — LLM / Generative AI",
        "Applied AI Engineer / AI Engineer",
        "Agentic AI Engineer",
        "Machine Learning Engineer — LLM / Generative AI",
        "LLM Training / Post-Training Engineer",
        "Research Software Engineer — AI/ML",
        "ML Systems Engineer (training/inference focused)",
        "Multimodal Research Engineer",
        "Inference / Model Optimization Engineer (ML-heavy)"
    ],
    "avoid_roles": [
        "generic data scientist",
        "data analyst",
        "BI / analytics",
        "traditional backend",
        "frontend",
        "DevOps/SRE",
        "pure MLOps/platform",
        "classical ML only",
        "sales engineering",
        "solutions architect",
        "AI product management",
        "8-10+ years specialized exp required",
        "PhD required (no equiv)",
        "internships",
        "CV apps unrelated to multimodal FMs",
        "external LLM API only roles"
    ]
}