#!/usr/bin/env python3
import csv
from pathlib import Path
import sys
sys.path.insert(0, '/mnt/DATA/job_hunt/jobhunt-engine/scripts')
import config_lib

# Load contacts to see which companies have confirmed email patterns
CONTACTS_PATH = config_lib.path("contacts_csv")

def get_companies_with_confirmed_patterns():
    """Get list of companies that have confirmed email patterns from contacts.csv"""
    companies_with_patterns = set()
    if Path(CONTACTS_PATH).exists():
        with open(CONTACTS_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                company = row.get("company", "").strip()
                email = row.get("email", "").strip()
                if company and email:
                    companies_with_patterns.add(company)
    return companies_with_patterns

def get_target_companies():
    """Get list of target companies from config"""
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

if __name__ == "__main__":
    companies_with_patterns = get_companies_with_confirmed_patterns()
    target_companies = get_target_companies()
    
    print(f"Companies with confirmed patterns from contacts: {len(companies_with_patterns)}")
    for company in sorted(list(companies_with_patterns)[:10]):
        print(f"  {company}")
    if len(companies_with_patterns) > 10:
        print(f"  ... and {len(companies_with_patterns) - 10} more")
    
    print()
    print(f"Target companies: {len(target_companies)}")
    companies_needing_patterns = [c for c in target_companies if c not in companies_with_patterns]
    print(f"Target companies needing patterns: {len(companies_needing_patterns)}")
    for company in sorted(companies_needing_patterns)[:10]:
        print(f"  {company}")
    if len(companies_needing_patterns) > 10:
        print(f"  ... and {len(companies_needing_patterns) - 10} more")