#!/usr/bin/env python3
"""
extend_companies.py — Migrate tracking/companies/companies.csv to the full
company-intelligence schema (2026-08-22), preserving all existing data.

New columns per user directive §11: company_category, company_priority,
company_quality, research_strength, major_ai_initiatives, relevant_teams,
agentic_work, post_training_work, reasoning_work, ai_infrastructure_work,
security_domain_relevance, asymmetric_advantage, known_connections,
referral_opportunities, next_research_date.

Existing data preserved: company_slug, company_name, careers_url, ats_platform,
h1b_sponsor, company_tier, sector, size, last_checked, open_roles_count,
contacts_count, notes.

Usage: python3 scripts/extend_companies.py
"""

import csv
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
CSV = config_lib.path("companies_csv")

NEW = ["company_category", "company_priority", "company_quality",
       "research_strength", "major_ai_initiatives", "relevant_teams",
       "agentic_work", "post_training_work", "reasoning_work",
       "ai_infrastructure_work", "security_domain_relevance",
       "asymmetric_advantage", "known_connections", "referral_opportunities",
       "next_research_date"]

# Seed intelligence from existing notes + known facts (empty = needs research pass)
SEED = {
    "cohere": dict(company_category="ai_native_leader", company_priority="P0",
                   company_quality=80, research_strength=80,
                   major_ai_initiatives="Command models; Aya multilingual; Embeddings/Search",
                   relevant_teams="Applied Research; Agentic AI; Platform; Toronto Research",
                   agentic_work="yes", post_training_work="yes",
                   reasoning_work="yes", ai_infrastructure_work="partial",
                   security_domain_relevance="none",
                   asymmetric_advantage="8 existing 1st connections; 4 GT alumni",
                   known_connections="41 contacts in contacts.csv",
                   referral_opportunities="high (P0 connections)"),
    "salesforce": dict(company_category="enterprise_ai", company_priority="P1",
                       company_quality=75, research_strength=70,
                       major_ai_initiatives="Einstein GPT; Agentforce; Applied Research",
                       relevant_teams="Agentic AI; Applied Research; ML Platform",
                       agentic_work="yes", post_training_work="unknown",
                       reasoning_work="partial", ai_infrastructure_work="yes",
                       security_domain_relevance="none",
                       asymmetric_advantage="GT pipeline; enterprise ML scale story",
                       known_connections="", referral_opportunities="unknown"),
    "databricks": dict(company_category="ai_infrastructure", company_priority="P1",
                       company_quality=85, research_strength=75,
                       major_ai_initiatives="Mosaic AI; MLflow; Agent Bricks",
                       relevant_teams="Mosaic AI; ML Platform; Inference; Agentic AI",
                       agentic_work="yes", post_training_work="partial",
                       reasoning_work="partial", ai_infrastructure_work="yes",
                       security_domain_relevance="none",
                       asymmetric_advantage="Strong GT alumni",
                       known_connections="", referral_opportunities="medium"),
    "together_ai": dict(company_category="ai_infrastructure", company_priority="P1",
                        company_quality=80, research_strength=75,
                        major_ai_initiatives="vLLM core team; open-source inference; RedPajama",
                        relevant_teams="Inference; vLLM; Research; Model Serving",
                        agentic_work="partial", post_training_work="yes",
                        reasoning_work="partial", ai_infrastructure_work="yes",
                        security_domain_relevance="none",
                        asymmetric_advantage="ARTEMIS/vLLM direct alignment",
                        known_connections="", referral_opportunities="unknown"),
    "anthropic": dict(company_category="frontier_lab", company_priority="P2",
                      company_quality=90, research_strength=95,
                      major_ai_initiatives="Claude; Constitutional AI; Alignment research",
                      relevant_teams="Applied AI; Post-Training; Evals; Safeguards",
                      agentic_work="yes", post_training_work="yes",
                      reasoning_work="yes", ai_infrastructure_work="partial",
                      security_domain_relevance="partial (cyber safeguards)",
                      asymmetric_advantage="Security background fits Safeguards teams",
                      known_connections="", referral_opportunities="low-moderate"),
    "scale_ai": dict(company_category="ai_infrastructure", company_priority="P1",
                     company_quality=78, research_strength=70,
                     major_ai_initiatives="Data Engine; SEIL; Frontier data for post-training",
                     relevant_teams="Frontier Agents; Evaluation; Data Engine",
                     agentic_work="yes", post_training_work="yes",
                     reasoning_work="yes", ai_infrastructure_work="yes",
                     security_domain_relevance="none",
                     asymmetric_advantage="Eval harness story (CAD 202 tests)",
                     known_connections="", referral_opportunities="unknown"),
    "cisco": dict(company_category="security_ai", company_priority="P0",
                  company_quality=70, research_strength=55,
                  major_ai_initiatives="AI Defense; Talos threat intelligence ML",
                  relevant_teams="Threat Intelligence; Detection Engineering; ML Platform; Security AI",
                  agentic_work="partial", post_training_work="unknown",
                  reasoning_work="partial", ai_infrastructure_work="partial",
                  security_domain_relevance="direct (Fortinet competitor)",
                  asymmetric_advantage="Fortinet alumni network; domain credibility; patent adjacency",
                  known_connections="", referral_opportunities="unknown"),
    "xai": dict(company_category="ai_native_leader", company_priority="P2",
                company_quality=82, research_strength=80,
                major_ai_initiatives="Grok; massive compute training",
                relevant_teams="Training; Inference; Agents",
                agentic_work="yes", post_training_work="yes",
                reasoning_work="yes", ai_infrastructure_work="yes",
                security_domain_relevance="none",
                asymmetric_advantage="none known",
                known_connections="", referral_opportunities="low"),
}


def main():
    with open(CSV, newline="") as f:
        reader = csv.DictReader(f)
        old_fields = list(reader.fieldnames)
        rows = list(reader)

    fields = old_fields[:]
    for c in NEW:
        if c not in fields:
            fields.append(c)

    for r in rows:
        slug = r.get("company_slug", "")
        seed = SEED.get(slug, {})
        for c in NEW:
            if not (r.get(c) or "").strip():
                r[c] = str(seed.get(c, "")) if c in seed else ""
        # default priority from tier if not set
        if not (r.get("company_priority") or "").strip():
            r["company_priority"] = {"T1": "P0", "T2": "P1", "T3": "P2", "T4": "P3"} \
                .get(r.get("company_tier", ""), "")
        if not (r.get("company_quality") or "").strip():
            r["company_quality"] = {"T1": "70", "T2": "65", "T3": "55", "T4": "55"} \
                .get(r.get("company_tier", ""), "")

    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    seeded = sum(1 for r in rows if r.get("company_slug") in SEED)
    print(f"Migrated {len(rows)} companies to full schema ({len(fields)} columns).")
    print(f"Seed intelligence applied to {seeded} companies; rest need research pass.")
    print(f"Preserved all existing columns: {old_fields}")


if __name__ == "__main__":
    main()
