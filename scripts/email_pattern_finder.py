#!/usr/bin/env python
"""Email pattern finder + application-triggered email drafts (Task 12).

Three-tier method per company, trust-ordered:
  1. observed  -> derive from real contact emails in contacts.csv
                  => email_pattern_status=confirmed
  2. cited     -> cited web research ('<company> email format')
                  => status=unverified, source URL recorded
  3. guessed   -> common-pattern candidates (first.last@, flast@, first@...)
                  => status=guessed

Safety invariants:
  * A pattern is NEVER marked confirmed unless derived from an actual
    observed address in contacts.csv.
  * Draft emails are only ever generated for CONFIRMED addresses.
    Unverified/guessed addresses are blocked by design.

CLI:
  python scripts/email_pattern_finder.py --company cohere [--apply]
  python scripts/email_pattern_finder.py --all-tier1 [--apply]

--dry-run is the default; --apply writes into companies_registry via
referral_lib.update_company_row().
"""
from __future__ import annotations

import argparse
import csv
import datetime
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import referral_lib  # noqa: E402
import config_lib

CONTACTS_PATH = config_lib.path("contacts_csv")
POSTS_PATH = config_lib.path("hiring_posts_csv")
DRAFTS_PATH = config_lib.path("connection_requests")

CANDIDATE_EMAIL = config_lib.identity_line("email")
BANNED_CLAIMS = ("rlhf", "dpo", "sft")

TIER1_SLUGS = [
    "fortinet", "sentinelone", "nvidia", "google", "google_deepmind",
    "microsoft", "microsoft_ai", "amazon", "amazon_web_services_aws",
    "cisco",
]

# Tier-2 cited research (status stays 'unverified' — never confirmed).
# Each entry: pattern key + domain + source URL from public '<company>
# email format' pages (addtocrm.com, leadiq.com, clay.com, rocketreach.co).
CITED_PATTERNS = {
    "google": {
        "pattern_key": "flast", "domain": "google.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/google",
        "note": "[first_initial][last] most common (77.5%)",
    },
    "google_deepmind": {
        "pattern_key": "flast", "domain": "google.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/google",
        "note": "Alphabet subsidiary; parent google.com format assumed",
    },
    "microsoft": {
        "pattern_key": "firstlasti", "domain": "microsoft.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/microsoft",
        "note": "[first][last_initial] most common (47.2%); "
                "rocketreach cites [first].[last] 35%",
    },
    "microsoft_ai": {
        "pattern_key": "firstlasti", "domain": "microsoft.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/microsoft",
        "note": "Microsoft subsidiary; parent microsoft.com format assumed",
    },
    "amazon": {
        "pattern_key": "firstlasti", "domain": "amazon.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/amazon",
        "note": "[first][last_initial] most common (68%)",
    },
    "amazon_web_services_aws": {
        "pattern_key": "firstlasti", "domain": "amazon.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/amazon",
        "note": "AWS uses parent amazon.com format",
    },
    "nvidia": {
        "pattern_key": "flast", "domain": "nvidia.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/nvidia",
        "note": "[first_initial][last] most common (93.8%)",
    },
    "cisco": {
        "pattern_key": "flast", "domain": "cisco.com",
        "status": "unverified",
        "source": "https://addtocrm.com/email-format/cisco",
        "note": "[first_initial][last] most common (92.4%)",
    },
    "fortinet": {
        "pattern_key": "flast", "domain": "fortinet.com",
        "status": "unverified",
        "source": "https://leadiq.com/c/fortinet/5a1d95d42300005300847fd9/"
                  "email-format",
        "note": "FLast@fortinet.com (90%)",
    },
    "sentinelone": {
        "pattern_key": "first.last", "domain": "sentinelone.com",
        "status": "unverified",
        "source": "https://www.clay.com/dossier/sentinelone-email-format",
        "note": "verified first.last@sentinelone.com",
    },
}

VALID_DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
EMAIL_RE = re.compile(r"^([^@\s]+)@([^@\s]+)$")


def status_for_method(method: str) -> str:
    return {"observed": "confirmed", "cited": "unverified",
            "guess": "guessed"}[method]


# ---------------------------------------------------------------------------
# Pattern derivation from observed contact emails
# ---------------------------------------------------------------------------

def _split_name(full_name: str):
    parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if len(parts) < 2 or any(not p.isalpha() for p in parts):
        return None, None
    return parts[0].lower(), parts[-1].lower()


def classify_localpart(local: str, first: str | None, last: str | None):
    """Classify an email local part against a person's name."""
    if not first or not last:
        return None
    first, last = first.lower(), last.lower()
    f, l = first[0], last[0]
    table = {
        "firstlast": f"{first}{last}",
        "flast": f"{f}{last}",
        "first.last": f"{first}.{last}",
        "first_last": f"{first}_{last}",
        "firstlasti": f"{first}{l}",
        "first.lasti": f"{first}.{l}",
        "lastfi": f"{last}{f}",
        "last.first": f"{last}.{first}",
        "lastfirst": f"{last}{first}",
        "first": first,
        "last": last,
    }
    for key, candidate in table.items():
        if local == candidate:
            return key if key != "last" else "last"
    return None


def derive_pattern_from_contacts(company_name: str,
                                 contacts_path=CONTACTS_PATH):
    """Derive the dominant email pattern from OBSERVED addresses.

    Returns (pattern_key, domain, evidence_emails) or None when no
    classifiable observed address exists for this company. Only real
    observed addresses can produce a 'confirmed' result.
    """
    if not Path(contacts_path).exists():
        return None
    counts: dict[str, int] = {}
    domains: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    with open(contacts_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("company", "").strip() != company_name.strip():
                continue
            m = EMAIL_RE.match((row.get("email") or "").strip().lower())
            if not m or not VALID_DOMAIN_RE.match(m.group(2)):
                continue
            local, domain = m.groups()
            first, last = _split_name(row.get("name") or "")
            key = classify_localpart(local, first, last)
            if key is None:
                continue
            counts[key] = counts.get(key, 0) + 1
            domains[domain] = domains.get(domain, 0) + 1
            evidence.setdefault(key, []).append(row["email"].strip())
    if not counts:
        return None
    best = max(counts, key=lambda k: counts[k])
    domain = max(domains, key=lambda k: domains[k])
    return best, domain, sorted(set(evidence[best]))


def guess_pattern_candidates(first: str, last: str, domain: str):
    """Common-pattern guesses. Status is ALWAYS 'guessed'; never send."""
    f, l = first[0].lower(), last[0].lower()
    first, last = first.lower(), last.lower()
    return [
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{f}{last}@{domain}",
        f"{first}{l}@{domain}",
        f"{first}@{domain}",
    ]


PATTERN_RENDER = {
    "flast": lambda f, l: f"{f[0]}{l}",
    "firstlasti": lambda f, l: f"{f}{l[0]}",
    "firstlast": lambda f, l: f"{f}{l}",
    "first.last": lambda f, l: f"{f}.{l}",
    "first_last": lambda f, l: f"{f}_{l}",
    "lastfi": lambda f, l: f"{l}{f[0]}",
    "last.first": lambda f, l: f"{l}.{f}",
    "lastfirst": lambda f, l: f"{l}{f}",
    "first": lambda f, l: f,
}


def render_example(pattern_key: str, first: str, last: str, domain: str):
    fn = PATTERN_RENDER.get(pattern_key)
    if not fn:
        return None
    return f"{fn(first.lower(), last.lower())}@{domain}"


# ---------------------------------------------------------------------------
# Registry lookup / apply
# ---------------------------------------------------------------------------

def _registry_row(slug, registry_path=None):
    path = registry_path or referral_lib.DEFAULT_REGISTRY_PATH
    try:
        return referral_lib.registry_row_for(slug, registry_path=path)
    except Exception:
        return None


def find_pattern(slug: str, contacts_path=CONTACTS_PATH, registry_path=None):
    """Return dict {slug, company, pattern, example_email, status, source}
    using observed > cited > none (guesses listed but never persisted)."""
    row = _registry_row(slug, registry_path)
    if row is None:
        return None
    company = row.get("company", slug)
    derived = derive_pattern_from_contacts(company, contacts_path)
    if derived:
        key, domain, evidence = derived
        return {"slug": slug, "company": company,
                "pattern": f"{key}@{domain}", "example_email": evidence[0],
                "status": status_for_method("observed"),
                "source": "contacts.csv:" + ",".join(evidence[:3]),
                "method": "observed"}
    cited = CITED_PATTERNS.get(slug)
    if cited:
        return {"slug": slug, "company": company,
                "pattern": f"{cited['pattern_key']}@{cited['domain']}",
                "example_email": render_example(cited["pattern_key"], "jane",
                                                "doe", cited["domain"]),
                "status": status_for_method("cited"),
                "source": cited["source"], "method": "cited",
                "note": cited.get("note", "")}
    # No observed data and no citation: report common guesses as
    # unactionable candidates only (dry-run info; --apply skips these).
    return {"slug": slug, "company": company, "pattern": "",
            "example_email": "", "status": "unknown", "source": "",
            "method": "none"}


def apply_pattern(slug, pattern, status, source, registry_path=None):
    """Persist one pattern row via referral_lib.update_company_row()."""
    assert status in ("confirmed", "unverified", "guessed", "unknown")
    if status == "confirmed":
        # hard guard: confirmed requires observed evidence recorded
        assert source.startswith("contacts.csv:"), (
            "confirmed requires observed-address provenance")
    path = registry_path or referral_lib.DEFAULT_REGISTRY_PATH
    return referral_lib.update_company_row(
        slug,
        {"email_pattern": pattern, "email_pattern_status": status,
         "email_pattern_source": source},
        registry_path=path)


# ---------------------------------------------------------------------------
# Draft lane: application-triggered emails (CONFIRMED addresses only)
# ---------------------------------------------------------------------------

def draft_application_emails(slug, registry_path=None,
                             contacts_path=CONTACTS_PATH,
                             posts_path=POSTS_PATH):
    """Draft short 'just applied' emails for posters/recruiters/HMs at
    `slug` who have CONFIRMED observed addresses only.

    Raises PermissionError when the company's pattern is not confirmed —
    drafts to unverified/guessed addresses are blocked by design.
    Returns a list of draft dicts matching connection_requests.csv schema.
    """
    path = registry_path or referral_lib.DEFAULT_REGISTRY_PATH
    row = _registry_row(slug, registry_path=path)
    if row is None:
        raise ValueError(f"unknown company slug: {slug}")
    if (row.get("email_pattern_status") or "").strip() != "confirmed":
        raise PermissionError(
            f"{slug}: email pattern is "
            f"'{row.get('email_pattern_status') or 'unknown'}'; drafting "
            "emails is blocked unless the pattern is CONFIRMED from an "
            "observed address.")

    company = row.get("company", slug)
    # Confirmed addresses come ONLY from contacts.csv observations.
    confirmed: dict[str, dict] = {}
    if Path(contacts_path).exists():
        with open(contacts_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("company", "").strip() != company.strip():
                    continue
                email = (r.get("email") or "").strip()
                m = EMAIL_RE.match(email)
                if not m or not VALID_DOMAIN_RE.match(m.group(2)):
                    continue
                confirmed[email.lower()] = r

    posts = []
    if Path(posts_path).exists():
        with open(posts_path, newline="", encoding="utf-8") as f:
            for p in csv.DictReader(f):
                if p.get("company", "").strip() == company.strip():
                    posts.append(p)

    drafts = []
    today = datetime.date.today().isoformat()
    seen = set()
    for post in posts:
        name = post.get("poster_name", "").strip()
        match = next((c for e, c in confirmed.items()
                      if _matches_person(name, c)), None)
        if match is None:
            continue  # no confirmed address for this poster
        email = match["email"].strip().lower()
        if email in seen:
            continue
        seen.add(email)
        role = (post.get("roles_mentioned") or "").strip() or \
            "the roles on your team"
        anchor = (match.get("reason_to_contact") or
                  match.get("shared_context") or "").strip()
        anchor_clause = ""
        if anchor:
            anchor_clause = f" ({anchor.split(';')[0][:80]})"
        body = (
            f"Hi {name.split()[0]},\n\nI just applied for {role} at "
            f"{company} and saw your post about hiring — I'm excited about "
            f"the work{anchor_clause}. {config_lib.identity_line('headline_background') or 'I am a machine learning engineer'}; I'd "
            f"love to be considered. My resume is attached.\n\nThank you,\n"
            f"{config_lib.identity_line('signature_name') or config_lib.identity_line('full_name')}\n{CANDIDATE_EMAIL}")
        low = body.lower()
        assert not any(b in low for b in BANNED_CLAIMS), "banned claim"
        drafts.append({
            "person_name": name,
            "company": company,
            "person_type": post.get("poster_type", ""),
            "linkedin_url": match.get("linkedin_url", ""),
            "email": email,
            "source_post_url": post.get("post_url", ""),
            "related_job_ids": "",
            "score": "",
            "note_draft": body,
            "note_basis": "hiring_post",
            "send_status": "pending",
            "date_queued": today,
            "notes": "channel=email; draft-only lane; "
                     f"post={post.get('post_id', '')}",
        })
    return drafts


def _matches_person(poster_name: str, contact_row: dict) -> bool:
    pn = re.sub(r"[^a-z ]", "", poster_name.lower()).split()
    cn = re.sub(r"[^a-z ]", "", (contact_row.get("name") or "").lower()).split()
    if not pn or not cn:
        return False
    return pn[0] == cn[0] and pn[-1] == cn[-1]


def write_drafts(drafts, drafts_path=DRAFTS_PATH):
    """Append draft rows to connection_requests.csv.

    Gracefully skips (returns 0) when the file does not yet exist — it is
    created concurrently by another task.
    """
    drafts_path = Path(drafts_path)
    if not drafts_path.exists():
        print(f"SKIP: {drafts_path} does not exist yet; nothing written.")
        return 0
    if not drafts:
        return 0
    with open(drafts_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = [h.split("(")[0].strip() for h in next(reader)]
    with open(drafts_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for d in drafts:
            writer.writerow([d.get(h, "") for h in header])
    return len(drafts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--company", help="company slug")
    g.add_argument("--all-tier1", action="store_true",
                   help="run over the tier-1 (C2) slug list")
    ap.add_argument("--draft", metavar="SLUG",
                    help="queue application-triggered email drafts "
                         "(confirmed addresses only)")
    ap.add_argument("--apply", action="store_true",
                    help="write patterns to companies_registry "
                         "(default: dry-run)")
    args = ap.parse_args(argv)

    slugs = TIER1_SLUGS if args.all_tier1 else [args.company]
    results = []
    for slug in slugs:
        res = find_pattern(slug)
        if res is None:
            print(f"{slug}: NOT IN REGISTRY — skipped")
            continue
        results.append(res)
        print(f"{res['slug']:<28} [{res['status']:^10}] "
              f"{res['pattern'] or '(no pattern)'}  {res['source']}")
        if res["status"] == "unknown":
            row = _registry_row(res["slug"])
            if row:
                print(f"    common guesses (DO NOT SEND): "
                      f"{guess_pattern_candidates('jane', 'doe', 'example')}"
                      f" style variants for {row.get('company')}")

    covered = sum(1 for r in results
                  if r["status"] in ("confirmed", "unverified"))
    if args.all_tier1:
        pct = 100.0 * covered / max(len(results), 1)
        print(f"\ntier-1 coverage (confirmed-or-cited): "
              f"{covered}/{len(results)} = {pct:.0f}%")

    if args.apply:
        for r in results:
            if not r["pattern"]:
                continue
            ok = apply_pattern(r["slug"], r["pattern"], r["status"],
                               r["source"])
            print(f"applied {r['slug']}: {ok}")

    if args.draft:
        drafts = draft_application_emails(args.draft)
        n = write_drafts(drafts)
        print(f"queued {n} email draft(s) for {args.draft}")


if __name__ == "__main__":
    main()
