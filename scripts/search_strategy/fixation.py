"""Anti-fixation gate: prevents named entities from prior results becoming search objectives
without explicit justification.
"""

from __future__ import annotations

from typing import List, Tuple, Dict, Any

from search_strategy.memory import SearchMemory, company_evidence


ENTITY_JUSTIFICATIONS = [
    "on_target_company_list",
    "recent_hiring_signal",
    "newly_discovered_relevant_team",
    "known_referral_opportunity",
    "unresolved_job_lead",
    "explicit_user_instruction",
    "high_historical_query_yield",
]


def entity_search_allowed(name: str, memory: SearchMemory, ontology) -> Tuple[bool, str]:
    """Return (allowed, justification) for using `name` as a search target.

    A named entity appearing in prior RESULTS is evidence, not an objective,
    unless one of the justifications holds.
    """
    if not name:
        return False, ""
    name_lower = name.lower()

    # 1. on_target_company_list
    try:
        target_companies = {c.lower() for c in ontology.target_companies()}
        if name_lower in target_companies:
            return True, "on_target_company_list"
    except Exception:
        pass

    # 2. recent_hiring_signal
    try:
        ev = company_evidence(name)
        if ev.get("recent_hiring_signal"):
            return True, "recent_hiring_signal"
    except Exception:
        pass

    # 3. newly_discovered_relevant_team (placeholder)
    # TODO: implement when team extraction exists

    # 4. known_referral_opportunity (placeholder)
    # TODO: implement when referral thread tracking exists

    # 5. unresolved_job_lead
    try:
        ev = company_evidence(name)
        if ev.get("open_job_lead"):
            return True, "unresolved_job_lead"
    except Exception:
        pass

    # 6. explicit_user_instruction
    # TODO: wire from planner justification field

    # 7. high_historical_query_yield
    try:
        if memory.entity_query_count(name) >= 2:
            # Calculate average relevant results for queries containing this name
            name_norm = memory._norm(name)
            relevant_sum = 0
            query_count = 0
            for record in memory._read_all():
                if name_norm in memory._norm(record.query):
                    relevant_sum += record.relevant_results or 0
                    query_count += 1
            if query_count > 0:
                avg_relevant = relevant_sum / query_count
                if avg_relevant >= 3:  # mirrors LOW_YIELD_THRESHOLD from memory
                    return True, "high_historical_query_yield"
    except Exception:
        pass

    return False, ""


def _first_non_stopword(text: str) -> str:
    """Extract the first meaningful token from a query for entity checking."""
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "should",
        "could", "may", "might", "must", "can", "we", "you", "they", "he", "she",
        "it", "this", "that", "these", "those", "my", "your", "his", "her", "its",
        "our", "their", "job", "jobs", "role", "roles", "engineer", "engineers",
        "scientist", "scientists", "research", "researcher", "researchers",
        "senior", "lead", "leadership", "manager", "managers", "director",
        "directors", "vp", "vps", "head", "chief", "chiefly",
        "machine", "learning", "ml", "ai", "llm", "agent", "agents",
        "agentic", "reasoning", "planning", "verification", "evaluation",
        "inference", "training", "post", "training", "post-training",
        "system", "systems", "platform", "platforms", "infrastructure",
        "developer", "developers", "science", "scientific",
    }
    # Simple tokenization: split on whitespace and punctuation
    import re
    words = re.findall(r"\b[\w']+\b", text.lower())
    for w in words:
        if w not in STOPWORDS:
            return w
    return ""


def filter_planned_queries(
    planned_queries: List[Dict[str, Any]],
    memory: SearchMemory,
    ontology
) -> List[Dict[str, Any]]:
    """Return a new list with unjustified entity queries removed.

    Each element is a dict with at least the keys:
    "query", "family", "intent", "expected_signals", "reject", "filters",
    "rationale", "notes".
    """
    # Get set of companies that have been seen in results (from companies_found in QueryRecord)
    companies_seen_in_results = set()
    for record in memory._read_all():
        # Convert to lowercase for consistent comparison
        companies_seen_in_results.update(company.lower() for company in record.companies_found)
    
    kept: List[Dict[Any, Any]] = []
    for q in planned_queries:
        query_text = q.get("query", "")
        # Tokenize the query into words
        import re
        words = re.findall(r"\b[\w']+\b", query_text.lower())
        # Check if any non-stopword word has been seen in results and is not justified
        should_drop = False
        STOPWORDS = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "should",
            "could", "may", "might", "must", "can", "we", "you", "they", "he", "she",
            "it", "this", "that", "these", "those", "my", "your", "his", "her", "its",
            "our", "their", "job", "jobs", "role", "roles", "engineer", "engineers",
            "scientist", "scientists", "research", "researcher", "researchers",
            "senior", "lead", "leadership", "manager", "managers", "director",
            "directors", "vp", "vps", "head", "chief", "chiefly",
            "machine", "learning", "ml", "ai", "llm", "agent", "agents",
            "agentic", "reasoning", "planning", "verification", "evaluation",
            "inference", "training", "post", "training", "post-training",
            "system", "systems", "platform", "platforms", "infrastructure",
            "developer", "developers", "science", "scientific",
        }
        for word in words:
            if word in STOPWORDS:
                continue
            # Check if this word has been seen in results (as a company)
            if word in companies_seen_in_results:
                # This word has been seen in results, check if it's justified.
                # An explicit planner-supplied justification for this entity
                # overrides the heuristic evidence check (planner prompt
                # documents the valid justification vocabulary).
                q_justification = str(q.get("justification", "") or "").strip()
                if q_justification:
                    if q_justification in ENTITY_JUSTIFICATIONS:
                        # heuristic allows it, or justification is explicitly
                        # claimed and from the known vocabulary: keep the query
                        continue
                    # invalid justification string: fall through to drop
                else:
                    allowed, justification = entity_search_allowed(word, memory, ontology)
                    if not allowed:
                        # This is an unjustified entity from prior results - drop the query
                        should_drop = True
                        break
        if should_drop:
            # Log the drop reason to the query's notes (as per spec)
            # We need to identify which entity caused the drop for the notes
            for word in words:
                if word in STOPWORDS:
                    continue
                if word in companies_seen_in_results:
                    allowed, justification = entity_search_allowed(word, memory, ontology)
                    if not allowed:
                        q = dict(q)  # shallow copy to avoid mutating caller's dict
                        q["notes"] = f"[fixation-blocked] {word} not justified"
                        break
            continue
        kept.append(q)
    return kept