#!/usr/bin/env python3
import csv
from pathlib import Path
import sys
sys.path.insert(0, '/mnt/DATA/job_hunt/jobhunt-engine/scripts')
import config_lib

# Load target companies
def get_target_companies():
    repo = config_lib.data_root()
    from pathlib import Path
    repo = Path(repo)
    companies = []
    comp_path = repo / "job_research" / "config" / "target-companies.yaml"
    if comp_path.exists():
        try:
            import yaml
            data = yaml.safe_load(comp_path.read_text()) or {}
            items = data.get("companies", data if isinstance(data, list) else [])
            for item in items:
                if isinstance(item, dict):
                    name = item.get("company") or item.get("name") or ""
                else:
                    name = str(item)
                if name:
                    companies.append(name)
        except Exception:
            pass
    return companies

# Email pattern finder logic (simplified)
def get_email_pattern_status(company):
    """Return the email pattern status for a company from contacts.csv or registry."""
    CONTACTS_PATH = config_lib.path("contacts_csv")
    REGISTRY_PATH = config_lib.path("companies_registry")
    
    # First, check contacts.csv for observed emails
    if Path(CONTACTS_PATH).exists():
        with open(CONTACTS_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("company", "").strip() == company:
                    email = row.get("email", "").strip()
                    if email:
                        # We have at least one observed email, so we can derive a pattern
                        # For simplicity, we'll just return confirmed if we see any email
                        # In reality, the script derives the pattern and marks it confirmed
                        return "confirmed"
    
    # Then, check the registry
    if Path(REGISTRY_PATH).exists():
        with open(REGISTRY_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("company", "").strip() == company:
                    status = row.get("email_pattern_status", "").strip()
                    if status in ("confirmed", "unverified", "guessed", "unknown"):
                        return status
    
    return "unknown"

if __name__ == "__main__":
    companies = get_target_companies()
    confirmed_count = 0
    for company in companies:
        status = get_email_pattern_status(company)
        if status == "confirmed":
            confirmed_count += 1
            print(f"{company}: confirmed")
        #else:
        #    print(f"{company}: {status}")
    
    print(f"\nTotal companies with confirmed email patterns: {confirmed_count}")