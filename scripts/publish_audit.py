#!/usr/bin/env python3
"""Publish audit: scan working tree AND full git history for private material.

Checks:
  1. /Users/<name> absolute personal paths
  2. Resume PDF/docx files
  3. API-key patterns (sk-, OR-, ghp_, AWS AKIA)
  4. .env file content
  5. Contact CSVs with real email addresses outside archive/

This tool is REPORT-ONLY. It never rewrites history or modifies files.
Exit code 0 = PASS, 1 = FAIL (findings present).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Patterns that should never appear in a publishable repo.
PATH_RE = re.compile(r"/Users/[A-Za-z0-9._-]+")
KEY_PATTERNS = {
    "openai-style sk-": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "openrouter OR-": re.compile(r"\bOR-[A-Za-z0-9_-]{20,}"),
    "github ghp_": re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    "aws AKIA": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RESUME_SUFFIXES = {".pdf", ".docx"}
EXAMPLE_OR_PLACEHOLDER_RE = re.compile(
    r"config\.example\.|example\.yaml|placeholder|<your|your[-_]?key", re.IGNORECASE)

SKIP_DIRS = {".git", ".venv", "__pycache__", ".hermes"}


def iter_files() -> list[Path]:
    files = []
    for p in REPO.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            files.append(p)
    return files


def git_revs() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "rev-list", "--all"],
                         capture_output=True, text=True)
    return out.stdout.split()


def git_grep(pattern: str, revs: list[str]) -> list[str]:
    """Return 'rev:path' hits for a regex across the given revisions."""
    hits: list[str] = []
    batch = 200
    for i in range(0, len(revs), batch):
        chunk = revs[i:i + batch]
        out = subprocess.run(
            ["git", "-C", str(REPO), "grep", "-I", "-E", pattern, *chunk],
            capture_output=True, text=True)
        for line in out.stdout.splitlines():
            rev, _, path = line.partition(":")
            hits.append(f"{rev[:10]}:{path}")
    return hits


def git_files_in_history(suffixes: tuple[str, ...]) -> set[str]:
    out = subprocess.run(["git", "-C", str(REPO), "log", "--all",
                          "--pretty=format:", "--name-only", "--diff-filter=A"],
                         capture_output=True, text=True)
    return {line.strip() for line in out.stdout.splitlines()
            if line.strip().endswith(tuple(RESUME_SUFFIXES))}


def main() -> int:
    findings: list[tuple[str, str]] = []

    # --- Working tree scans -------------------------------------------------
    contact_csvs: list[Path] = []
    env_files: list[Path] = []
    resume_files: list[Path] = []
    path_hits: list[Path] = []
    key_hits: list[Path] = []
    email_hits: list[tuple[Path, str]] = []

    for f in iter_files():
        rel = f.relative_to(REPO).as_posix()
        low = rel.lower()
        if low.endswith(tuple(RESUME_SUFFIXES)) and ("resume" in low or "cv" in low):
            resume_files.append(f)
        if f.name == ".env" or low.startswith(".env"):
            env_files.append(f)
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if PATH_RE.search(text):
            path_hits.append(f)
        matched_keys = [name for name, rx in KEY_PATTERNS.items() if rx.search(text)]
        if matched_keys and not EXAMPLE_OR_PLACEHOLDER_RE.search(text):
            key_hits.append(f)
        if f.suffix == ".csv" and "contact" in low and not rel.startswith("archive/"):
            contact_csvs.append(f)
            emails = [m for m in EMAIL_RE.findall(text)
                      if not EXAMPLE_OR_PLACEHOLDER_RE.search(m)]
            for e in sorted(set(emails)):
                email_hits.append((f, e))

    for f in path_hits:
        findings.append(("worktree-personal-path", f.relative_to(REPO).as_posix()))
    for f in resume_files:
        findings.append(("worktree-resume-file", f.relative_to(REPO).as_posix()))
    for f in env_files:
        findings.append(("worktree-env-file", f.relative_to(REPO).as_posix()))
    for f in key_hits:
        findings.append(("worktree-api-key-pattern", f.relative_to(REPO).as_posix()))
    for f, e in email_hits:
        findings.append(("contact-csv-email", f"{f.relative_to(REPO)}: {e}"))

    # --- Git history scans --------------------------------------------------
    revs = git_revs()
    hist_paths = git_grep(PATH_RE.pattern, revs)
    findings.extend(("history-personal-path", h) for h in hist_paths)
    for name, rx in KEY_PATTERNS.items():
        for h in git_grep(rx.pattern, revs):
            findings.append((f"history-api-key ({name})", h))
    for p in sorted(git_files_in_history(tuple(RESUME_SUFFIXES))):
        if "resume" in p.lower():
            findings.append(("history-resume-file", p))

    # --- Report -------------------------------------------------------------
    print("=" * 70)
    print("PUBLISH AUDIT REPORT")
    print(f"repo: {REPO}")
    print(f"revisions scanned: {len(revs)}")
    print("=" * 70)

    if not findings:
        print("PASS — no private-material findings.")
        return 0

    by_cat: dict[str, list[str]] = {}
    for cat, item in findings:
        by_cat.setdefault(cat, []).append(item)
    for cat in sorted(by_cat):
        items = by_cat[cat]
        print(f"\n[{cat}] — {len(items)} finding(s)")
        for item in items[:50]:
            print(f"  - {item}")
        if len(items) > 50:
            print(f"  ... and {len(items) - 50} more")
    print("\nFAIL — findings above require human review before publishing.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
