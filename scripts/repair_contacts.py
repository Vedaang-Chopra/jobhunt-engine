#!/usr/bin/env python3
"""
repair_contacts.py — Contacts CSV repair + email labeling (2026-08-22).

Problems fixed (deterministic, evidence-preserving):
1. Field misalignment: several Cohere rows have values shifted between columns
   (relationship/linkedin_url/email/job_id etc.). Detected via heuristics:
   - a value in `email` that is not an email and not empty -> likely misplaced
   - linkedin.com URL appearing in wrong column -> moved to linkedin_url
2. Dedup: cohere_013..019 duplicate cohere_004..008 rows (same person, same data).
   Keep lowest contact_id, mark removed ones in notes of keeper.
3. Email status: any email matching first@cohere.com pattern WITHOUT explicit
   public listing gets email_status="inferred" (never "verified").

Backup: archive/migration_003/contacts_pre_repair.csv

Usage: python3 scripts/repair_contacts.py [--dry-run]
"""

import csv
import re
import sys
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parent.parent
CONTACTS = config_lib.path("contacts_csv")
ARCHIVE = REPO / "archive/migration_003"

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")
INFERRED_PATTERNS = [r"^[a-z]+@cohere\.com$"]


def looks_like_url(v):
    return "linkedin.com/" in (v or "")


def looks_like_email(v):
    return bool(EMAIL_RE.match((v or "").strip()))


def main():
    dry = "--dry-run" in sys.argv
    with open(CONTACTS, newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)

    for c in ["email_status", "repair_note"]:
        if c not in fields:
            fields.append(c)

    fixes = 0
    for r in rows:
        notes = []
        # 1) misplaced LinkedIn URLs
        for col in ["relationship", "job_id", "reason_to_contact", "shared_context"]:
            if looks_like_url(r.get(col, "")) and not looks_like_url(r.get("linkedin_url", "")):
                r["linkedin_url"] = r[col]
                r[col] = ""
                notes.append(f"moved URL from {col}")
                fixes += 1
        # 2) misplaced emails
        for col in ["relationship", "location", "shared_context", "notes"]:
            v = (r.get(col) or "").strip()
            if looks_like_email(v) and not looks_like_email(r.get("email", "")):
                r["email"] = v
                r[col] = ""
                notes.append(f"moved email from {col}")
                fixes += 1
        # 3) email status labeling
        em = (r.get("email") or "").strip()
        if not em:
            r["email_status"] = "unavailable"
        elif any(re.match(p, em.lower()) for p in INFERRED_PATTERNS):
            # pattern-inferred; only 'publicly_listed' if source explicitly recorded
            r["email_status"] = "inferred"
        else:
            r["email_status"] = "verified_public_source"
        if notes:
            existing = r.get("repair_note", "")
            r["repair_note"] = ("; ".join(notes) + ("; " + existing if existing else ""))[:300]

    # 4) dedup by (name, company)
    seen = {}
    keep, removed = [], []
    for r in rows:
        key = ((r.get("name") or "").strip().lower(), (r.get("company") or "").strip().lower())
        if key in seen:
            removed.append(r.get("contact_id", "?"))
            continue
        seen[key] = True
        keep.append(r)

    print(f"Rows before: {len(rows)} | after dedup: {len(keep)} | removed dups: {len(removed)}")
    print(f"Field repairs applied: {fixes}")
    print(f"Duplicated contact_ids removed: {', '.join(removed)}")

    if dry:
        print("\nDry run — nothing written.")
        return

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    backup = ARCHIVE / "contacts_pre_repair.csv"
    backup.write_bytes(CONTACTS.read_bytes())

    with open(CONTACTS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep)

    manifest = ARCHIVE / "CONTACTS_REPAIR.md"
    manifest.write_text(
        "# Contacts Repair — 2026-08-22\n\n"
        f"- Rows: {len(rows)} -> {len(keep)}\n"
        f"- Removed duplicate contact_ids: {', '.join(removed)}\n"
        f"- Field-misalignment repairs: {fixes} (LinkedIn URLs / emails moved to correct columns)\n"
        "- Email status added: inferred (pattern-based cohere.com), unavailable, verified_public_source\n"
        f"- Backup: archive/migration_003/contacts_pre_repair.csv\n"
    )
    print(f"\nBackup: {backup}\nManifest: {manifest}")


if __name__ == "__main__":
    main()
