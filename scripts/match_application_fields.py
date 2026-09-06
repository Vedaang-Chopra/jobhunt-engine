#!/usr/bin/env python3
"""Field-matching engine for application auto-fill.

Classifies a form field label into an answer-bank key from
profile_info/preferences/application_answers.yaml.

Matching strategy (tiered):
  1. EXACT / normalized exact match against known question labels the user
     has already answered (execution_results/simplify_questions_extract.json)
  2. Regex/keyword rules derived from Simplify's fieldNameAliases +
     observed Greenhouse/Workday/Lever label conventions
  3. ASK_USER for anything unclassified or policy-sensitive

Usage:
  python3 scripts/match_application_fields.py --label "First Name"
  python3 scripts/match_application_fields.py --labels-file fields.txt
  echo '[{"label":"First name","type":"text"},...]' | python3 scripts/match_application_fields.py --stdin-json
"""
import argparse
import json
import os
import re
import sys

import yaml

try:
    from scripts import config_lib
except ImportError:
    import config_lib
ROOT = str(config_lib.data_root())
ANSWERS_PATH = os.path.join(str(ROOT), "profile_info/preferences/application_answers.yaml")
OBSERVED_QUESTIONS = os.path.join(
    ROOT, "execution_results/simplify_questions_extract.json"
)


def load_answers():
    with open(ANSWERS_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Tier 2 rules: (compiled regex on normalized label) -> answer key
# Order matters: first match wins. Derived from Simplify's alias groups and
# the 181 observed real-world labels.
# ---------------------------------------------------------------------------
RULES = [
    # identity
    (r"^(first|given)\s*name", "identity.first_name"),
    (r"^(last|family|surname)", "identity.last_name"),
    (r"^full\s*name|^your\s*name|^(name)$", "identity.full_name"),
    (r"preferred\s*(first\s*)?name", "identity.first_name"),
    (r"\bemail\b", "identity.email"),
    (r"\bphone\b|mobile|contact\s*number", "identity.phone"),
    (r"linkedin", "identity.linkedin"),
    (r"github|git\s*hub\s*url", "identity.github"),
    (r"portfolio|website|personal\s*(site|url)", "never.portfolio"),
    # location
    (r"^(city|town)$|\bcity\s*$", "identity.location_city"),
    (r"^(state|province|region)$", "identity.location_state"),
    (r"^(country)$", "identity.location_country"),
    (r"postal|zip\s*code|\bzip\b", "identity.postal_code"),
    (r"current\s*location|where\s*(are\s*you\s*)?(located|based)", "identity.location"),
    (r"^address", "identity.address"),
    # work auth & sponsorship (policy sensitive -> gate)
    (r"legally\s*authorized|authorized\s*to\s*work|work\s*authorization|eligible\s*to\s*work",
     "work_authorization.authorized_to_work_us"),
    (r"sponsorship|sponsor\b|visa\s*sponsor|h-?1b", "work_authorization.require_sponsorship"),
    (r"u\.?s\.?\s*person|us\s*(citizen|person)|permanent\s*resident",
     "work_authorization.us_person_status"),
    # demographics -> always ask
    (r"gender|ethnic|race\b|veteran|disability|lgbt|sexual\s*orientation",
     "demographics.GATE_EEO"),
    # age
    (r"over\s*18|age\s*18|18\s*or\s*older", "identity.over_18"),
    (r"over\s*21|21\s*or\s*older", "identity.over_21"),
    # common attestation/company-specific
    (r"previously\s*(been\s*)?(employed|worked)\s*(by|at|for)|current\s*or\s*former\s*employee|have\s*you\s*worked\s*(at|for)",
     "company_specific.previous_employee"),
    (r"how\s*did\s*you\s*hear", "reusable_answers.how_did_you_hear"),
    (r"willing\s*to\s*relocate|open\s*to\s*relocation", "reusable_answers.willing_to_relocate"),
    (r"earliest\s*start|start\s*date|when\s*can\s*you\s*start|available\s*from",
     "reusable_answers.earliest_start_date"),
    (r"salary|compensation\s*expectations|pay\s*expectations",
     "never.salary"),
    (r"cover\s*letter", "application.cover_letter"),
    (r"^resume|upload.*resume|attach.*resume", "application.resume_upload"),
]

ASK_ALWAYS = {
    "demographics.GATE_EEO",
    "never.salary",
    "work_authorization.authorized_to_work_us",
    "work_authorization.require_sponsorship",
    "work_authorization.us_person_status",
}


def normalize(label: str) -> str:
    return re.sub(r"\s+", " ", label.lower().replace("_", " ")).strip()


def classify(label: str, answers: dict) -> dict:
    n = normalize(label)

    # Gate first: policy-sensitive fields NEVER auto-fill, even if the user
    # has answered this exact label before.
    for pat, key in RULES:
        if key in ASK_ALWAYS and re.search(pat, n):
            return {"label": label, "key": key,
                    "source": f"rule:{pat[:30]}", "action": "ASK_USER"}

    # Tier 1: previously-answered bank (fuzzy containment)
    try:
        obs = json.load(open(OBSERVED_QUESTIONS))
    except Exception:
        obs = []
    for q in obs:
        ql = normalize(q.get("label", ""))
        if ql and (ql == n or (len(n) > 12 and n in ql)):
            return {"label": label, "key": None,
                    "source": "observed_answer_bank", "action": "USE_SAVED_ANSWER"}

    # Tier 2: rules
    for pat, key in RULES:
        if re.search(pat, n):
            return {"label": label, "key": key, "source": f"rule:{pat[:30]}", "action": "AUTO_FILL"}

    return {"label": label, "key": None, "source": "unmatched", "action": "ASK_USER"}


def resolve(key: str, answers: dict):
    """Walk dotted path into answers; return value or None."""
    node = answers
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label")
    ap.add_argument("--labels-file")
    ap.add_argument("--stdin-json", action="store_true",
                    help="JSON array of {label, type?} objects on stdin")
    args = ap.parse_args()

    answers = load_answers()
    labels = []
    if args.label:
        labels.append(args.label)
    if args.labels_file:
        labels += [l.strip() for l in open(args.labels_file) if l.strip()]
    if args.stdin_json:
        labels += [f.get("label", "") for f in json.load(sys.stdin)]

    results = [classify(l, answers) for l in labels]
    for r in results:
        val = resolve(r["key"], answers) if r["key"] else None
        if isinstance(val, str) and val == "ASK_USER":
            r["action"] = "ASK_USER"
            r["value"] = None
        elif isinstance(val, dict) and isinstance(val.get("default"), str):
            r["value"] = val["default"]
        else:
            r["value"] = val if isinstance(val, str) else None
    print(json.dumps(results, indent=1))

    filled = sum(1 for r in results if r["action"] == "AUTO_FILL")
    print(f"\nsummary: {filled}/{len(results)} auto-fillable, "
          f"{sum(1 for r in results if r['action']=='ASK_USER')} need you",
          file=sys.stderr)


if __name__ == "__main__":
    main()
