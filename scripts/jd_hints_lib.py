"""JD intelligence hint extraction for the "right people" feature (Task 2).

Pure regex/string extraction over a job-description text:

- ``extract_jd_hints(jd_text)`` — deterministic hints: team name, hiring-manager
  hints, recruiter hints, title keywords, technical domain terms.
- ``llm_jd_hints(jd_text, llm_call)`` — thin contract wrapper that merges an
  injected (sync-or-async) LLM call's JSON output over the regex hints; the LLM
  wins on non-empty fields. No network here — the caller injects the client.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re

# --- Fixed canonical lists (output ordering follows these) -------------------

TITLE_KEYWORDS = [
    "ML Engineer",
    "Software Engineer",
    "Applied Scientist",
    "Research Scientist",
    "Research Engineer",
    "Data Scientist",
    "Engineering Manager",
    "Solutions Architect",
    "AI Engineer",
]

DOMAIN_TERMS = [
    "agentic AI",
    "AI agents",
    "LLM",
    "evaluation",
    "evals",
    "VLM",
    "vision language",
    "routing",
    "fine-tuning",
    "RLHF",
    "RAG",
    "retrieval-augmented",
    "inference",
    "multimodal",
    "foundation models",
    "embeddings",
    "MLOps",
]

SENIORITY_TERMS = [
    "Engineering Manager",
    "Director",
    "Head of",
]

EMPTY_HINTS = {
    "team": None,
    "manager_hints": [],
    "recruiter_hints": [],
    "keywords": [],
    "domain_terms": [],
}

# --- Compiled patterns -------------------------------------------------------

# "join our <X> team" / "the <X> team" — Capitalized name, team word follows.
_TEAM_JOIN_RE = re.compile(
    r"join (?:our|the)\s+((?:[A-Z][\w&-]*(?:\s+[A-Z][\w&-]*)*))\s+team", re.IGNORECASE
)
_TEAM_THE_RE = re.compile(
    r"\bthe\s+((?:[A-Z][\w&-]*)(?:\s+(?:[A-Z][\w&-]*))*)\s+team\b"
)
_TEAM_COLON_RE = re.compile(r"(?i:\bteam)\s*:\s*([A-Z][\w&-]*(?:\s+[A-Z][\w&-]*)*)")

_GENERIC_TEAM_NAMES = {"the", "team", "our", "hiring", "product", "engineering", "platform"}

# "reports to X" / "reporting to X" / "hiring manager: X" → capitalized name(s).
# The phrase part matches case-insensitively (scoped (?i:)); the captured name
# must still start each token with a capital letter.
_MANAGER_NAME_RE = re.compile(
    r"(?i:reports\s+to|reporting\s+to|hiring\s+manager)\s*:?\s*(?:[Tt]he\s+)?"
    r"([A-Z][\w'.-]*(?:[ \t]+[A-Z][\w'.-]*)*)"
)

# Seniority fallback: role strings appearing in the text.
_SENIORITY_RES = [(term, re.compile(re.escape(term), re.IGNORECASE)) for term in SENIORITY_TERMS]

# Recruiter contexts, in scan order below.
_RECRUITER_NAMED_RE = re.compile(r"recruiter\s*[:\-]\s*([^\n]+)", re.IGNORECASE)
_RECRUITER_BARE_RES = [
    ("talent acquisition", re.compile(r"talent\s+acquisition", re.IGNORECASE)),
    ("recruiting", re.compile(r"\brecruiting\b", re.IGNORECASE)),
]


def _term_pattern(term: str) -> re.Pattern:
    """Case-insensitive word-boundary pattern for a canonical term."""
    parts = [re.escape(p) for p in term.split()]
    body = r"\s+".join(parts)
    # Allow plural 's' on short acronyms (LLMs, RAGs).
    if term.isupper() and len(term) <= 5:
        body += "s?"
    return re.compile(r"\b" + body + r"\b", re.IGNORECASE)


_KEYWORD_RES = [(t, _term_pattern(t)) for t in TITLE_KEYWORDS]
_DOMAIN_RES = [(t, _term_pattern(t)) for t in DOMAIN_TERMS]


def _clean_team_name(name: str) -> str | None:
    name = (name or "").strip().rstrip(".,:")
    if not name or name.lower() in _GENERIC_TEAM_NAMES:
        return None
    return name


def _extract_team(text: str) -> str | None:
    for regex in (_TEAM_JOIN_RE, _TEAM_COLON_RE, _TEAM_THE_RE):
        match = regex.search(text)
        if match:
            name = _clean_team_name(match.group(1))
            if name:
                return name
    return None


def _extract_manager_hints(text: str) -> list[str]:
    """Named hints from 'reports to / hiring manager' phrases, plus seniority
    role strings, merged in order of appearance and deduplicated."""
    found: list[tuple[int, str]] = []
    for match in _MANAGER_NAME_RE.finditer(text):
        name = match.group(1).strip().rstrip(".,:")
        if name:
            found.append((match.start(1), name))
    for term, regex in _SENIORITY_RES:
        match = regex.search(text)
        if match:
            found.append((match.start(), term))
    found.sort(key=lambda item: item[0])
    hints: list[str] = []
    seen: set[str] = set()
    for _, name in found:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            hints.append(name)
    return hints


def _extract_recruiter_hints(text: str) -> list[str]:
    hints: list[str] = []
    for match in _RECRUITER_NAMED_RE.finditer(text):
        name = match.group(1).split("(")[0].strip().rstrip(".,:")
        if name and name.lower() not in {h.lower() for h in hints}:
            hints.append(name)
    for label, regex in _RECRUITER_BARE_RES:
        if regex.search(text):
            hints.append(label)
    return hints


def _extract_from_list(text: str, pairs) -> list[str]:
    return [term for term, regex in pairs if regex.search(text)]


def extract_jd_hints(jd_text: str) -> dict:
    """Extract deterministic "right people" hints from a job description.

    Returns ``{"team": str|None, "manager_hints": [..], "recruiter_hints": [..],
    "keywords": [..], "domain_terms": [..]}`` — all-empty for empty/None input,
    with deterministic ordering (fixed-list order; manager hints by appearance).
    """
    if not jd_text or not jd_text.strip():
        return dict(EMPTY_HINTS)
    return {
        "team": _extract_team(jd_text),
        "manager_hints": _extract_manager_hints(jd_text),
        "recruiter_hints": _extract_recruiter_hints(jd_text),
        "keywords": _extract_from_list(jd_text, _KEYWORD_RES),
        "domain_terms": _extract_from_list(jd_text, _DOMAIN_RES),
    }


def _merge_llm_over_regex(regex_hints: dict, llm_output) -> dict:
    """LLM output wins on non-empty fields; regex hints fill the rest."""
    merged = dict(regex_hints)
    if not llm_output:
        return merged
    if isinstance(llm_output, str):
        try:
            llm_output = json.loads(llm_output)
        except (json.JSONDecodeError, ValueError):
            return merged
    if not isinstance(llm_output, dict):
        return merged
    for key, value in llm_output.items():
        if key in merged and value:
            merged[key] = value
    return merged


def llm_jd_hints(jd_text: str, llm_call) -> dict:
    """Merge an injected LLM call's JSON output over the regex hints.

    ``llm_call`` may be sync or async; it receives the JD text and returns a
    JSON dict (or JSON string) with any subset of the hint keys. Non-empty LLM
    fields override the regex extraction; everything else passes through.
    No network here — the callable is fully injected.
    """
    regex_hints = extract_jd_hints(jd_text)
    if not callable(llm_call):
        return regex_hints
    result = llm_call(jd_text)
    if inspect.isawaitable(result):
        # asyncio.run() unsets the thread's current event loop on exit, which
        # breaks later event-loop-dependent imports (e.g. NiceGUI under
        # Python 3.9) in the same interpreter. Use a private loop instead and
        # leave global loop state untouched.
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(result)
        finally:
            loop.close()
    return _merge_llm_over_regex(regex_hints, result)
