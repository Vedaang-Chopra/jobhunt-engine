#!/usr/bin/env python3
"""
Migration script: Consolidate job_search/state/applications.csv into tracking/applications/applications.csv
Updated for new repository structure.
"""

import csv
from datetime import datetime
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib
DATA = config_lib.data_root()
REPO_ROOT = Path(__file__).parent.parent
SECONDARY_CSV = REPO_ROOT / "archive" / "migration_001" / "job_research_legacy" / "job_search" / "state" / "applications.csv"
OUTPUT_CSV = DATA / "tracking" / "applications" / "applications.csv"
COMPANIES_OUTPUT = DATA / "tracking" / "companies" / "companies.csv"
CONTACTS_OUTPUT = DATA / "tracking" / "contacts" / "contacts.csv"
OUTREACH_OUTPUT = DATA / "tracking" / "messages" / "outreach.csv"
SEARCH_RUNS_OUTPUT = DATA / "tracking" / "search_runs" / "search_runs.csv"
JOBS_CSV = DATA / "tracking" / "jobs" / "jobs.csv"
COHERE_CONTACTS = REPO_ROOT / "archive" / "migration_001" / "job_research_legacy" / "cohere_contacts" / "cohere_final_contacts.csv"

# Read the secondary applications CSV
applications = []
with open(SECONDARY_CSV, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        applications.append(row)

print(f"Loaded {len(applications)} application records")

# Write canonical applications CSV
fieldnames = [
    'application_id', 'job_id', 'company', 'role', 'job_url', 'status',
    'resume_variant', 'referral_contact', 'date_queued', 'date_resume_ready',
    'date_submitted', 'date_acknowledged', 'date_last_status_change',
    'current_stage', 'rejection_reason', 'follow_up_date', 'notes'
]

with open(OUTPUT_CSV, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    
    for app in applications:
        # Preserve queued status - do not mark as submitted
        row = {
            'application_id': app.get('application_id', ''),
            'job_id': app.get('job_id', ''),
            'company': app.get('company', ''),
            'role': app.get('role', ''),
            'job_url': app.get('job_url', ''),
            'status': app.get('status', 'queued'),  # Keep as queued
            'resume_variant': app.get('resume_variant', ''),
            'referral_contact': app.get('referral_contact', ''),
            'date_queued': app.get('date_queued', ''),
            'date_resume_ready': app.get('date_resume_ready', ''),
            'date_submitted': app.get('date_submitted', ''),
            'date_acknowledged': app.get('date_acknowledged', ''),
            'date_last_status_change': app.get('date_last_status_change', ''),
            'current_stage': app.get('current_stage', 'queued'),
            'rejection_reason': app.get('rejection_reason', ''),
            'follow_up_date': app.get('follow_up_date', ''),
            'notes': app.get('notes', ''),
        }
        writer.writerow(row)

print(f"Written to {OUTPUT_CSV}")

# Also create companies.csv
# Extract unique companies from jobs
companies = {}
with open(JOBS_CSV, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        company = row['company']
        if company not in companies:
            companies[company] = {
                'company_slug': company.lower().replace(' ', '_').replace('.', ''),
                'company_name': company,
                'careers_url': '',
                'ats_platform': 'greenhouse',
                'h1b_sponsor': 'unknown',
                'company_tier': 'unknown',
                'sector': 'AI/ML',
                'size': 'unknown',
                'last_checked': datetime.now().strftime('%Y-%m-%d'),
                'open_roles_count': 0,
                'contacts_count': 0,
                'notes': ''
            }
        companies[company]['open_roles_count'] += 1

# Set known H-1B sponsors and tiers
tier1_companies = ['togetherai', 'anthropic', 'databricks', 'scaleai', 'cohere', 'salesforce', 'servicenow', 'snowflake', 'palantir', 'fireworks ai', 'anyscale', 'wandb', 'reka', 'character.ai', 'runway']
tier2_companies = ['nvidia', 'google', 'meta', 'microsoft', 'amazon', 'xai', 'ai2', 'sierra ai', 'cognition', 'adept']

for company_key, company_data in companies.items():
    slug = company_data['company_slug']
    if slug in tier1_companies:
        company_data['company_tier'] = 'T1'
        company_data['h1b_sponsor'] = 'yes'
    elif slug in tier2_companies:
        company_data['company_tier'] = 'T2'
        company_data['h1b_sponsor'] = 'yes'
    
    # Set careers URL
    if slug == 'togetherai':
        company_data['careers_url'] = 'https://job-boards.greenhouse.io/togetherai'
    elif slug == 'anthropic':
        company_data['careers_url'] = 'https://job-boards.greenhouse.io/anthropic'
    elif slug == 'databricks':
        company_data['careers_url'] = 'https://databricks.com/company/careers'
    elif slug == 'scaleai':
        company_data['careers_url'] = 'https://job-boards.greenhouse.io/scaleai'
    elif slug == 'cohere':
        company_data['careers_url'] = 'https://cohere.com/careers'

company_fieldnames = [
    'company_slug', 'company_name', 'careers_url', 'ats_platform', 'h1b_sponsor',
    'company_tier', 'sector', 'size', 'last_checked', 'open_roles_count',
    'contacts_count', 'notes'
]

with open(COMPANIES_OUTPUT, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=company_fieldnames)
    writer.writeheader()
    for company_data in companies.values():
        writer.writerow(company_data)

print(f"Written {len(companies)} companies to {COMPANIES_OUTPUT}")

# Create empty contacts.csv with proper schema
contacts_fieldnames = [
    'contact_id', 'name', 'company', 'role', 'relationship', 'linkedin_url',
    'email', 'job_id', 'reason_to_contact', 'shared_context', 'outreach_status',
    'date_identified', 'date_contacted', 'followup_date', 'response', 'notes'
]
with open(CONTACTS_OUTPUT, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=contacts_fieldnames)
    writer.writeheader()

# Migrate cohere contacts
with open(COHERE_CONTACTS, 'r') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        contact_row = {
            'contact_id': f"cohere_{i+1:03d}",
            'name': row.get('Name', ''),
            'company': 'Cohere',
            'role': row.get('Current Role', ''),
            'relationship': row.get('Connection Degree', ''),
            'linkedin_url': row.get('LinkedIn Profile URL', ''),
            'email': row.get('Email Format 1 (first@cohere.com)', ''),
            'job_id': '',
            'reason_to_contact': row.get('Common Ground (Why This Person)', ''),
            'shared_context': '',
            'outreach_status': 'not_contacted',
            'date_identified': row.get('Last Updated', ''),
            'date_contacted': '',
            'followup_date': '',
            'response': '',
            'notes': row.get('Notes', ''),
        }
        with open(CONTACTS_OUTPUT, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=contacts_fieldnames)
            writer.writerow(contact_row)

print(f"Migrated Cohere contacts to {CONTACTS_OUTPUT}")

# Create empty outreach.csv
outreach_fieldnames = [
    'outreach_id', 'contact_id', 'job_id', 'company', 'contact_name', 'channel',
    'message_type', 'message_text', 'status', 'date_drafted', 'date_approved',
    'date_sent', 'followup_date', 'response_date', 'response_summary', 'notes'
]
with open(OUTREACH_OUTPUT, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=outreach_fieldnames)
    writer.writeheader()

print(f"Created empty outreach tracking at {OUTREACH_OUTPUT}")

# Create empty search_runs CSV
search_runs_fieldnames = [
    'run_id', 'date', 'sources', 'queries', 'total_scanned', 'new_jobs_found',
    'duplicates_skipped', 'strong_fits', 'notes'
]
with open(SEARCH_RUNS_OUTPUT, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=search_runs_fieldnames)
    writer.writeheader()

print(f"Created empty search runs tracking at {SEARCH_RUNS_OUTPUT}")