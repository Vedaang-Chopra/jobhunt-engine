#!/usr/bin/env python3
"""
ats_check.py — ATS-score + keyword-match + ATS-compliance checker (2026-08-23).

For every non-archived job in tracking/jobs/jobs.csv:
  1. KEYWORD MATCH   — weighted coverage of the candidate's skill keywords
                       (built from <data_root>/profile_info/resume_fact_bank.yaml
                       technology/coursework facts + a hardcoded boost list
                       mirroring TECH_SKILLS in score_jobs_v2).
  2. ATS COMPLIANCE  — pass/fail checks on the posting itself (requirements
                       section present, description depth, location stated,
                       valid apply URL, posting date known, no anti-keywords,
                       title parses to a real role).
  3. ats_score       — 60% keyword_match + 40% compliance_pass_ratio (0-100).

Writes new columns back into jobs.csv (add-columns-only schema evolution):
  ats_score, keyword_match_score, keyword_matched, keyword_missing,
  ats_issues, last_ats_check
and a full detail report to <data_root>/job_research/data/ats_report.json.

Usage:
  python3 scripts/ats_check.py            # score and apply to jobs.csv
  python3 scripts/ats_check.py --dry-run  # print top-15, write nothing
"""

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

try:
    from scripts import config_lib
except ImportError:
    import config_lib

DATA_ROOT = config_lib.data_root()
JOBS_CSV = DATA_ROOT / "tracking/jobs/jobs.csv"
FACT_BANK = DATA_ROOT / "profile_info/resume_fact_bank.yaml"
REPORT_PATH = DATA_ROOT / "job_research/data/ats_report.json"

TODAY = date.today()

# New columns appended to jobs.csv (schema evolution: add columns only).
ATS_COLUMNS = [
    "ats_score",
    "keyword_match_score",
    "keyword_matched",
    "keyword_missing",
    "ats_issues",
    "last_ats_check",
]

# ------------------------------------------------------------------ keywords --
# Hardcoded boost list mirroring TECH_SKILLS in score_jobs_v2.py.
BOOST_SKILLS = {
    "pytorch": 3, "python": 2, "golang": 3, "go": 1, "transformers": 3,
    "hugging face": 2, "vllm": 3, "onnx": 3, "docker": 1, "ray": 2,
    "distributed systems": 2, "model serving": 2, "inference": 2,
    "optimization": 1, "profiling": 1, "data pipelines": 1, "fastapi": 1,
    "opensearch": 2, "elasticsearch": 2,
}
PER_KW_CAP = 3          # per-keyword cap (same rule as capped_keyword_score)
FULL_MARKS_RATIO = 0.55  # hitting ~55% of the weighted table = full marks,
                         # calibrated like score_jobs_v2 dimension tables.


def _collect_skill_strings(node, out):
    """Recursively gather skill-ish strings from fact-bank structures."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("technologies", "coursework", "models_served") and isinstance(value, list):
                out.extend(str(v) for v in value)
            elif key == "specialization" and isinstance(value, str):
                out.append(value)
            else:
                _collect_skill_strings(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_skill_strings(item, out)


def build_keyword_table(fact_bank_path):
    """Keyword -> weight table from resume_fact_bank.yaml + BOOST_SKILLS."""
    data = yaml.safe_load(Path(fact_bank_path).read_text())
    strings = []
    _collect_skill_strings(data, strings)

    table = {}
    for s in strings:
        kw = s.strip().lower()
        if not kw or len(kw) < 2:
            continue
        table[kw] = max(table.get(kw, 0), 1)
    for kw, w in BOOST_SKILLS.items():
        table[kw] = max(table.get(kw, 0), w)
    return table


def _keyword_in_text(kw, text):
    """Substring match; very short keywords must match on word boundaries."""
    if len(kw) <= 3:
        return f" {kw} " in f" {text} "
    return kw in text


def keyword_match(text, table):
    """Weighted coverage score 0-100 + matched/missing keyword lists."""
    total_possible = sum(min(w, PER_KW_CAP) for w in table.values())
    raw = 0
    matched = []
    missing = []
    for kw, w in table.items():
        if _keyword_in_text(kw, text):
            raw += min(w, PER_KW_CAP)
            matched.append(kw)
        else:
            missing.append((kw, w))
    ratio = min(1.0, raw / (total_possible * FULL_MARKS_RATIO)) if total_possible else 0.0
    score = round(ratio * 100.0, 1)
    matched_sorted = sorted(set(matched))
    missing_sorted = [kw for kw, _ in sorted(missing, key=lambda kv: -kv[1])]
    return score, matched_sorted, missing_sorted


# --------------------------------------------------------------- compliance --
GOOD_TITLE_PATTERN = re.compile(
    r"(engineer|eng\b|scientist|research|developer|develops|machine learning"
    r"|\bml\b|\bai\b|artificial intelligence|data sci|software|architect"
    r"|sre\b|devops|inference|training|post-training|agent)"
)
BAD_TITLE_PATTERN = re.compile(
    r"(recruiter|recruiting|talent acquisition|sales|marketing"
    r"|account executive|business development)"
)
ANTI_KEYWORDS = [
    "unpaid", "commission only", "pure commission", "equity only",
    "no salary", "uncompensated",
]
REQUIREMENTS_MARKERS = [
    "requirements", "qualifications", "what you'll need", "what you will need",
    "about you", "you have", "must have", "we're looking for",
    "we are looking for", "minimum qualifications", "preferred qualifications",
    "basic qualifications", "skills required", "experience required",
]
LOCATION_HINTS = re.compile(r"\b(remote|remote-friendly|hybrid|on-site|onsite)\b", re.I)


def compliance_checks(row, text):
    """Run posting-level checks. Returns (passed_count, total, issues)."""
    issues = []
    passed = 0

    # 1. Requirements/qualifications section marker present.
    if any(marker in text for marker in REQUIREMENTS_MARKERS):
        passed += 1
    else:
        issues.append("no requirements/qualifications section found in description")

    # 2. Description depth (thin-JD flag).
    if len(text.strip()) >= 500:
        passed += 1
    else:
        issues.append(f"thin job description ({len(text.strip())} chars, <500)")

    # 3. Explicit location stated.
    loc = (row.get("location") or "").strip()
    if loc or LOCATION_HINTS.search(text) or "location:" in text:
        passed += 1
    else:
        issues.append("no explicit location stated")

    # 4. Apply URL present and http(s).
    url = (row.get("canonical_application_url") or row.get("job_url") or "").strip()
    if url.startswith(("http://", "https://")):
        passed += 1
    else:
        issues.append("apply URL missing or not http(s)")

    # 5. Posting date known.
    posted = (row.get("date_posted") or "").strip()
    try:
        y, m, d = map(int, posted.split("-"))
        date(y, m, d)
        passed += 1
    except Exception:
        issues.append("posting date unknown/unparseable")

    # 6. No anti-keywords (e.g. unpaid / commission-only postings).
    blob = ((row.get("title") or "") + " " + text).lower()
    hits = [kw for kw in ANTI_KEYWORDS if kw in blob]
    if not hits:
        passed += 1
    else:
        issues.append("anti-keyword hit: " + ", ".join(hits))

    # 7. Title parses to a real engineering/research role.
    title = (row.get("title") or "").lower()
    if GOOD_TITLE_PATTERN.search(title) and not BAD_TITLE_PATTERN.search(title):
        passed += 1
    else:
        issues.append(f"title does not parse to a real technical role: {row.get('title', '')!r}")

    return passed, 7, issues


# ------------------------------------------------------------------- scoring --
def gather_jd_text(row, data_root):
    """JD text the same way score_jobs_v2 does: description_file body under
    '## Full Job Description Text', falling back to metadata columns."""
    jd_text = ""
    df = (row.get("description_file") or "").strip()
    if df:
        jd_path = Path(data_root) / df
        try:
            raw = jd_path.read_text()
            if "## Full Job Description Text" in raw:
                body = raw.split("## Full Job Description Text", 1)[1]
                body = body.rsplit("---", 1)[0]
                jd_text = body.lower()
        except OSError:
            pass
    meta_text = " ".join(filter(None, [
        row.get("title", ""), row.get("key_requirements", ""),
        row.get("matching_strengths", ""), row.get("main_gaps", ""),
        row.get("notes", "")])).lower()
    return (jd_text + " " + meta_text).strip() if jd_text else meta_text


def evaluate_job(row, table, data_root):
    """Compute the full ATS evaluation for one job row."""
    text = gather_jd_text(row, data_root)
    km_score, matched, missing = keyword_match(text, table)
    p_passed, p_total, issues = compliance_checks(row, text)
    compliance_ratio = p_passed / p_total if p_total else 0.0
    ats_score = round(0.6 * km_score + 0.4 * compliance_ratio * 100.0, 1)
    return {
        "ats_score": ats_score,
        "keyword_match_score": km_score,
        "keyword_matched": matched[:10],
        "keyword_missing": missing[:10],
        "compliance_passed": p_passed,
        "compliance_total": p_total,
        "ats_issues": issues,
        "text_length": len(text.strip()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="ATS-score + compliance checker")
    parser.add_argument("--dry-run", action="store_true",
                        help="print top-15 by ats_score without writing anything")
    parser.add_argument("--jobs-csv", default=None,
                        help="override path to jobs.csv")
    args = parser.parse_args(argv)

    jobs_csv = Path(args.jobs_csv) if args.jobs_csv else JOBS_CSV
    if not jobs_csv.is_file():
        sys.exit(f"ERROR: jobs.csv not found at {jobs_csv}")
    if not FACT_BANK.is_file():
        sys.exit(f"ERROR: resume_fact_bank.yaml not found at {FACT_BANK}")

    table = build_keyword_table(FACT_BANK)

    with open(jobs_csv, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    results = []
    evaluated = 0
    for row in rows:
        if (row.get("status") or "") == "archived":
            continue
        result = evaluate_job(row, table, DATA_ROOT)
        result["job_id"] = row.get("job_id")
        result["company"] = row.get("company")
        result["title"] = row.get("title")
        results.append(result)
        evaluated += 1

        if not args.dry_run:
            row["ats_score"] = str(result["ats_score"])
            row["keyword_match_score"] = str(result["keyword_match_score"])
            row["keyword_matched"] = "; ".join(result["keyword_matched"])
            row["keyword_missing"] = "; ".join(result["keyword_missing"])
            row["ats_issues"] = "; ".join(result["ats_issues"])
            row["last_ats_check"] = TODAY.isoformat()

    results.sort(key=lambda r: r["ats_score"], reverse=True)

    avg_ats = round(sum(r["ats_score"] for r in results) / evaluated, 1) if evaluated else 0.0
    flagged = sum(1 for r in results if r["ats_issues"])
    print(f"Evaluated {evaluated} jobs (dry_run={args.dry_run}) "
          f"against {len(table)} profile keywords")
    print(f"Avg ATS score: {avg_ats} | jobs with >=1 compliance issue: {flagged}")
    print("\nTOP 15 BY ATS SCORE:")
    for r in results[:15]:
        issues_n = len(r["ats_issues"])
        print(f"  [{r['ats_score']:5.1f}] kw={r['keyword_match_score']:5.1f} "
              f"issues={issues_n} {str(r['title'])[:52]} @ {r['company']}")

    if args.dry_run:
        print("\nDry run — no files written.")
        return

    for col in ATS_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    with open(jobs_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "generated": TODAY.isoformat(),
        "jobs_csv": str(jobs_csv),
        "fact_bank": str(FACT_BANK),
        "keyword_table_size": len(table),
        "summary": {
            "evaluated": evaluated,
            "average_ats_score": avg_ats,
            "with_compliance_issues": flagged,
        },
        "jobs": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {jobs_csv} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
