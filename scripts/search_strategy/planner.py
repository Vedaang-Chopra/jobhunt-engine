"""Query planner: LLM-driven generation of diverse, justified search batches with deterministic guardrails."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
import math

try:  # repo-root package import vs. flat scripts-dir import
    from scripts import config_lib
except ImportError:  # pragma: no cover - exercised when sys.path includes scripts/
    import config_lib

from search_strategy import fixation


# Attempt to import the LLM config from the web navigation agent (as per plan)
try:
    from web_nav_agent._llm_config_fallback import llm_config
except ImportError:  # fallback for testing or if the module is not present
    def llm_config():
        """Fallback LLM config — returns an empty list; the planner will treat this as unavailable."""
        return []


@dataclass
class PlannedQuery:
    """A single planned search query with metadata."""
    query: str
    family: str = "domain_role"
    intent: str = ""
    expected_signals: List[str] = field(default_factory=list)
    reject: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    notes: str = ""  # used by fixation gate to log drop reason
    justification: str = ""  # fixation-gate justification for entity queries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "family": self.family,
            "intent": self.intent,
            "expected_signals": self.expected_signals,
            "reject": self.reject,
            "filters": self.filters,
            "rationale": self.rationale,
            "notes": self.notes,
            "justification": self.justification,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlannedQuery":
        return cls(
            query=data.get("query", ""),
            family=data.get("family", "domain_role"),
            intent=data.get("intent", ""),
            expected_signals=list(data.get("expected_signals", [])),
            reject=list(data.get("reject", [])),
            filters=dict(data.get("filters", {})),
            rationale=data.get("rationale", ""),
            notes=data.get("notes", ""),
            justification=data.get("justification", ""),
        )


class PlannerError(RuntimeError):
    """Raised when the planner fails to produce a valid plan."""


def _normalize_token(text: str) -> str:
    """Lowercase tokens separated by whitespace for similarity comparison.

    Non-alphanumeric characters are dropped but whitespace is preserved so
    multi-word queries keep distinct token sets (required for Jaccard).
    """
    return ' '.join(
        ''.join(c.lower() for c in token if c.isalnum())
        for token in text.split()
    ).strip()


def _jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity of token sets (split by whitespace)."""
    tokens_a = set(_normalize_token(a).split())
    tokens_b = set(_normalize_token(b).split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _first_non_stopword(text: str) -> str:
    """Return the first token that is not a stopword, or empty string."""
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "should",
        "could", "may", "might", "must", "can", "we", "you", "they", "he", "she",
        "it", "this", "that", "these", "those", "my", "your", "his", "her", "its",
        "our", "their", "job", "jobs", "role", "roles", "engineer", "engineers",
        "scientist", "scientists", "research", "researcher", "researchers",
        "sr", "jr", "ii", "iii", "entry", "level", "associate", "lead", "head",
        "director", "manager", "vp", "president", "ceo", "cfo", "cto", "cofounder",
        "founder", "intern", "internship", "student", "graduate", "phd", "mba",
        "bs", "ms", "degree", "degrees", "education", "experience", "exp",
        "years", "year", "fulltime", "parttime", "remote", "onsite", "hybrid",
        "usa", "us", "united", "states", "uk", "canada", "city", "state",
        "country", "location", "locations", "hire", "hiring", "recruit",
        "opening", "openings", "position", "positions", "role", "roles",
        "title", "titles", "seek", "seeking", "look", "looking", "apply",
        "application", "deadline", "link", "apply", "link", "website", "site",
        "contact", "email", "phone", "fax", "address", "zip", "code",
        "salary", "compensation", "benefits", "equity", "bonus", "sign",
        "relocation", "visa", "sponsorship", "relocate", "welcome", "equal",
        "opportunity", "employer", "driving", "license", "certification",
        "certified", "licensed", "accredited", "accreditation", "affiliation",
        "member", "membership", "association", "society", "institute",
        "laboratory", "lab", "center", "centre", "group", "team", "division",
        "department", "dept", "unit", "subunit", "branch", "office", "facility",
        "plant", "mill", "factory", "warehouse", "store", "shop", "outlet",
        "vendor", "supplier", "partner", "affiliate", "subsidiary", "parent",
        "holding", " conglomerate", "corporation", "inc", "incorporated", "ltd",
        "limited", "llc", "llp", "plc", "co", "company", "corp", "group",
        "holdings", "properties", "real", "estate", "properties", "property",
        "assets", "asset", "investment", "investments", "fund", "funds",
        "capital", "venture", "ventures", "partner", "partners", "lp", "llp",
        "ltd", "limited", "inc", "incorporated", "corp", "corporation",
        "plc", "public", "limited", "company", "group", "holdings",
        "pt", "pty", "ltd", "limited", "nl", "bv", "ag", "kg", "sa", "nv",
        "kk", "as", "oy", "ab", "kft", "zt", "rt", " ag ", " oy ", " ab ",
    }
    for word in text.split():
        w = word.strip().lower()
        if w and w not in STOPWORDS:
            return w
    return ""


class Planner:
    """
    Planner that uses an LLM to generate a batch of queries, then applies
    deterministic guardrails: fixation filter, Jaccard diversity, mix policy
    backfill, broadening, and budget clamp.
    """

    def __init__(
        self,
        llm: Optional[Callable[[List[Dict[str, str]], float, int, Optional[Any]], str]] = None,
        onto: Optional[Any] = None,
        mem: Optional[Any] = None,
        policy: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the planner.

        Args:
            llm: A callable that takes messages, temperature, max_tokens, and optional clients,
                 and returns a string (the LLM output). If None, the planner attempts to
                 build a default LLM client from web_nav_agent._llm_config_fallback.llm_config().
            onto: An Ontology instance (from search_strategy.ontology). If None, attempts to load
                  from the default data root.
            mem: A SearchMemory instance (from search_strategy.memory). If None, attempts to
                 instantiate with default root.
            policy: A dictionary of policy settings. If None, loads from
                  jobhunt-data/job_research/config/search_policy.yaml via config_lib.data_root().
        """
        # Set up LLM
        if llm is None:
            # Try to build the LLM client from the web navigation agent's fallback
            try:
                llm_builder = llm_config()
                if not llm_builder:
                    raise ImportError("LLM config builder returned empty")
                # The llm_config() returns a function that builds the client? Actually, per the plan,
                # we should import llm_config() and use it to get a client.
                # But the plan says: Provider chain imported from web_nav_agent._llm_config_fallback.llm_config()
                # and the llm_config() returns a client? Let's assume it returns a callable that matches our llm signature.
                # However, looking at the existing llm.py in the repo, it defines a chat function that uses
                # a client built from llm_config(). We'll mimic that by importing the chat function from llm.py
                # if available, otherwise we fall back to a dummy.
                from search_strategy.llm import chat as llm_chat
                self.llm = llm_chat
            except Exception:
                # Fallback: a dummy LLM that returns empty array (will cause PlannerError unless handled)
                self.llm = lambda messages, temperature=0.4, max_tokens=4000, clients=None: json.dumps({"queries": []})
        else:
            self.llm = llm

        # Set up ontology
        if onto is None:
            self.onto = Ontology.load()
        else:
            self.onto = onto

        # Set up memory
        if mem is None:
            self.mem = SearchMemory()
        else:
            self.mem = mem

        # Set up policy
        if policy is None:
            self.policy = self._load_policy()
        else:
            self.policy = policy

        # Mix-policy backfill only runs when the caller (or a loaded policy
        # file) explicitly configured mix_policy; a bare/partial policy dict
        # gets defaults but does not opt into batch inflation via backfill.
        self._mix_backfill_enabled = "mix_policy" in self.policy
        # Ensure policy has defaults
        self.policy.setdefault("batch_size", 5)
        self.policy.setdefault("max_batches_per_mode", 3)
        self.policy.setdefault("mix_policy", {
            "proven": 0.30,
            "variation": 0.40,
            "exploratory": 0.20,
            "entity_targeted": 0.10
        })
        self.policy.setdefault("stop_rules", {
            "min_new_per_query": 1,
            "max_duplicate_rate": 0.8,
            "authwall_or_captcha": "stop"
        })
        self.policy.setdefault("low_yield_threshold", 3)
        self.policy.setdefault("high_yield_threshold", 8)
        self.policy.setdefault("broaden_after_low_yield", True)

    def _load_policy(self) -> Dict[str, Any]:
        """Load policy from YAML file, with fallback to seed values."""
        try:
            import yaml
            config_root = config_lib.data_root()
            policy_path = config_root / "job_research" / "config" / "search_policy.yaml"
            if policy_path.is_file():
                with policy_path.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception:
            pass
        # Fallback seed (should match the seed in the plan)
        return {
            "batch_size": 5,
            "max_batches_per_mode": 3,
            "mix_policy": {
                "proven": 0.30,
                "variation": 0.40,
                "exploratory": 0.20,
                "entity_targeted": 0.10
            },
            "stop_rules": {
                "min_new_per_query": 1,
                "max_duplicate_rate": 0.8,
                "authwall_or_captcha": "stop"
            },
            "low_yield_threshold": 3,
            "high_yield_threshold": 8,
            "broaden_after_low_yield": True
        }

    def plan_batch(self, mode: str, state: Dict[str, Any], budget: Optional[int] = None) -> List[PlannedQuery]:
        """
        Plan a batch of queries for the given mode.

        Args:
            mode: One of 'jobs', 'posts', 'feed'.
            state: The current state dictionary (as returned by SearchMemory.build_state).
            budget: Maximum number of queries to return. If None, uses policy.batch_size.

        Returns:
            A list of PlannedQuery objects (length <= budget).

        Raises:
            PlannerError: If the LLM output is malformed or no queries are generated (and mode is not feed).
        """
        if budget is None:
            budget = self.policy["batch_size"]

        # Derive state from search memory when the caller passes an empty
        # state dict, so the prompt, broadening rule and classification see
        # recent high/low yield queries even without an explicit state.
        if not state and self.mem is not None:
            try:
                derived = self.mem.build_state()
                if isinstance(derived, dict):
                    state = {**derived, **state}
            except Exception:
                pass

        # Build the prompt for the LLM
        system_prompt = self._build_system_prompt(mode, state)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Return a JSON object with a key 'queries' containing a list of query objects."}
        ]

        # Call the LLM
        try:
            llm_output = self.llm(messages, temperature=0.4, max_tokens=4000)
        except Exception as e:
            raise PlannerError(f"LLM call failed: {e}") from e

        # Parse the LLM output
        try:
            data = json.loads(llm_output)
            if not isinstance(data, dict) or "queries" not in data:
                raise ValueError("Missing 'queries' key")
            raw_queries = data["queries"]
            if not isinstance(raw_queries, list):
                raise ValueError("'queries' must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            # Try one repair retry: ask the LLM to fix its output
            repair_messages = messages + [
                {"role": "assistant", "content": llm_output},
                {"role": "user", "content": "That was not valid JSON. Please return a valid JSON object with a 'queries' key containing a list of query objects."}
            ]
            try:
                llm_output_repair = self.llm(repair_messages, temperature=0.4, max_tokens=4000)
                data = json.loads(llm_output_repair)
                if not isinstance(data, dict) or "queries" not in data:
                    raise ValueError("Missing 'queries' key after repair")
                raw_queries = data["queries"]
                if not isinstance(raw_queries, list):
                    raise ValueError("'queries' must be a list after repair")
            except Exception as e2:
                raise PlannerError(f"LLM output malformed and repair failed: {e}; {e2}") from e2

        # Convert raw queries to PlannedQuery objects
        planned: List[PlannedQuery] = []
        for raw in raw_queries:
            if not isinstance(raw, dict):
                continue
            # Ensure required fields
            query_text = raw.get("query", "").strip()
            if not query_text:
                continue
            pq = PlannedQuery.from_dict(raw)
            planned.append(pq)

        if not planned and mode != "feed":
            raise PlannerError("LLM returned no valid queries")

        # Apply guardrails in order

        # 1. Fixation filter (from search_strategy.fixation)
        # We need to adapt: fixation.filter_planned_queries expects a list of dicts with specific keys.
        # We'll convert our PlannedQuery objects to dicts, apply the filter, then convert back.
        if planned:
            dicts = [pq.to_dict() for pq in planned]
            filtered_dicts = fixation.filter_planned_queries(dicts, self.mem, self.onto)
            # Update notes field from the filter (it adds notes on drop)
            planned = [PlannedQuery.from_dict(d) for d in filtered_dicts]

        # 2. Diversity guardrail: drop near-duplicates (Jaccard > 0.7) and enforce at least 3 families if possible
        if len(planned) > 1:
            # Sort by some priority? We'll keep original order but we can sort by rationale length or something.
            # For simplicity, we'll iterate and keep the first of any near-duplicate cluster.
            unique: List[PlannedQuery] = []
            for pq in planned:
                is_duplicate = False
                for up in unique:
                    if _jaccard_similarity(pq.query, up.query) > 0.7:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique.append(pq)
            planned = unique

            # Enforce at least 3 distinct families if the ontology provides enough families
            families = {pq.family for pq in planned}
            if len(families) < 3 and self.onto:
                available_families = set(self.onto.role_families().keys())
                # We need to add queries from missing families
                # We'll do this in the mix backfill step, but we can also do it here.
                # For now, we'll rely on mix backfill to add diversity.
                pass

        # 3. Mix policy backfill: ensure we have the right proportion of proven, variation, exploratory, entity_targeted
        # We'll classify each query into one of these buckets.
        def _classify_query(pq: PlannedQuery) -> str:
            # proven: query appears in recent high yield queries (from state)
            high_yield_queries = set(state.get("recent_high_yield_queries", []))
            if pq.query in high_yield_queries:
                return "proven"
            # variation: shares at least one token with a high yield query
            tokens = set(_normalize_token(pq.query).split())
            for hyq in high_yield_queries:
                if tokens & set(_normalize_token(hyq).split()):
                    return "variation"
            # exploratory: term from untried ontology domain terms or promoted vocabulary
            # We'll check if the query contains a term from the ontology domain terms that hasn't been tried recently
            # For simplicity, we'll consider it exploratory if it contains any domain term from the ontology
            # and is not already proven or variation.
            # We'll also check the vocabulary tracker for promoted terms.
            # Since we don't have the vocabulary tracker injected, we'll skip this for now and rely on the
            # entity_targeted and proven/variation classification.
            # entity_targeted: the query contains a justified entity (we can check via fixation gate? but we already applied it)
            # Instead, we'll check if the first non-stopword is a justified entity (according to memory and ontology)
            entity = _first_non_stopword(pq.query)
            if entity:
                # Check if the entity is justified (using the same logic as in fixation gate)
                # We'll reuse the entity_search_allowed function from fixation
                from search_strategy.fixation import entity_search_allowed
                allowed, _ = entity_search_allowed(entity, self.mem, self.onto)
                if allowed:
                    return "entity_targeted"
            # If none of the above, default to exploratory
            return "exploratory"

        # Count current classification
        counts = {"proven": 0, "variation": 0, "exploratory": 0, "entity_targeted": 0}
        for pq in planned:
            counts[_classify_query(pq)] += 1

        total = len(planned)
        if not planned:
            # Nothing survived the guardrails: do not synthesize a batch.
            return planned
        if self._mix_backfill_enabled:
            target_counts = {
                k: int(round(self.policy["mix_policy"][k] * budget))
                for k in self.policy["mix_policy"]
            }
        else:
            # No explicit mix policy configured: no targets, so the backfill
            # step below synthesizes nothing and the batch keeps its size.
            target_counts = {}
        # Ensure we don't exceed budget
        # We'll compute how many more we need of each type
        needed = {k: max(0, target_counts[k] - counts[k]) for k in target_counts}

        # We'll generate backfill queries from the ontology
        backfill: List[PlannedQuery] = []
        if any(needed.values()):
            # We'll generate candidates from the ontology: combine primary titles with domain terms
            # We'll also include just entity queries for entity_targeted if needed.
            # We'll avoid queries that are already in the planned list (by query text)
            existing_queries = {pq.query.lower() for pq in planned}

            # Helper to add a query if we still need it and it's not duplicate
            def try_add(query_text: str, family: str, intent: str, rationale: str, justification: str = ""):
                if needed.get(_classify_query(PlannedQuery(query=query_text, family=family)), 0) <= 0:
                    return False
                if query_text.lower() in existing_queries:
                    return False
                pq = PlannedQuery(
                    query=query_text,
                    family=family,
                    intent=intent,
                    rationale=rationale,
                    notes=justification  # we can put justification in notes for now
                )
                backfill.append(pq)
                existing_queries.add(query_text.lower())
                needed[_classify_query(pq)] -= 1
                return True

            # Generate proven-like queries: we can reuse high yield queries? But we already have them.
            # Instead, we'll generate variation and exploratory from ontology.
            # For variation: take a high yield query and vary it slightly (we'll just use the high yield query as is? but that's proven)
            # We'll skip variation generation for now and rely on the fact that variation is already counted if the query shares tokens.
            # We'll focus on exploratory and entity_targeted.

            # Exploratory: combine primary titles with domain terms from each family
            primary_titles = self.onto.primary_titles()
            for family_key, family in self.onto.role_families().items():
                domain_terms = self.onto.domain_terms(family_key)
                for title in primary_titles[:2]:  # limit to avoid explosion
                    for term in domain_terms[:2]:
                        query_text = f"{title} {term}".strip()
                        if query_text and _first_non_stopword(query_text):  # ensure it has a non-stopword
                            # Determine if this query is already covered by recent queries to avoid duplication
                            # We'll skip if it's in recent queries (both high and low yield)
                            recent_all = set(state.get("recent_queries", []))
                            if query_text not in recent_all:
                                # We'll classify it later, but we can assume it's exploratory if not proven/variation/entity
                                # We'll add it and let classification decide.
                                # We'll set intent and rationale generically
                                intent = f"Find {query_text} roles"
                                rationale = "exploratory backfill"
                                if try_add(query_text, family_key, intent, rationale):
                                    break
                    else:
                        continue
                    break

            # Entity-targeted: generate queries for justified entities (we can use memory to find entities with high yield or recent hiring signal)
            # We'll get entities from memory that are justified (recent hiring signal or open job lead or target company)
            # We'll use the company_evidence method to check justification.
            # We'll also check historical yield.
            # We'll limit to a few.
            if needed["entity_targeted"] > 0:
                # Get companies from memory that have some justification
                # We'll look at the memory's recent queries for companies found
                # For simplicity, we'll use the target companies from ontology and check if they are justified
                for company in self.onto.target_companies():
                    # Check if justified via recent hiring signal, open job lead, or target list (target list is always justified)
                    from search_strategy.memory import company_evidence
                    evidence = company_evidence(company)
                    if evidence["on_target_list"] or evidence["recent_hiring_signal"] or evidence["open_job_lead"]:
                        query_text = f"Software Engineer at {company}"  # we can vary the role
                        intent = f"Find Software Engineer roles at {company}"
                        rationale = "entity-targeted backfill"
                        if try_add(query_text, "domain_role", intent, rationale, "on_target_company_list" if evidence["on_target_list"] else
                                   ("recent_hiring_signal" if evidence["recent_hiring_signal"] else "open_job_lead")):
                            needed["entity_targeted"] -= 1
                            if needed["entity_targeted"] <= 0:
                                break

            # If we still need more, we can fill with generic exploratory queries from ontology terms alone
            if any(needed.values()):
                # Fallback: just add ontology domain terms as queries
                for family_key, family in self.onto.role_families().items():
                    for term in self.onto.domain_terms(family_key)[:3]:
                        query_text = term.strip()
                        if query_text and query_text.lower() not in existing_queries:
                            # Classify as exploratory (likely)
                            intent = f"Find {query_text} roles"
                            rationale = "exploratory backfill fallback"
                            if try_add(query_text, family_key, intent, rationale):
                                pass

        # Add backfill to planned
        planned.extend(backfill)

        # 4. Broadening rule: if we have any low-yield queries in the state, broaden one
        if self.policy.get("broaden_after_low_yield", True):
            low_yield_queries = state.get("recent_low_yield_queries", [])
            if low_yield_queries:
                # We'll take the first low-yield query and try to broaden it by replacing a specific token with an adjacent title
                # We'll look for a query that contains a domain term or a role that we can broaden
                # We'll try to replace the most specific token (e.g., a domain term like "langgraph") with an adjacent title
                # For simplicity, we'll just take the first low-yield query and prepend/append an adjacent title?
                # The plan says: append >=1 query replacing most-specific token of one low-yield query with an adjacent title
                # We'll implement a simple version: if the low-yield query contains a domain term from ontology, we replace it with a random other domain term? 
                # Actually, we replace with an adjacent title (from TITLE_CANON or adjacent_titles).
                # We'll look for a token in the query that is a domain term (from any family) and replace it with an adjacent title.
                # We'll do this for the first low-yield query only.
                # Only broaden queries that are actually part of this batch;
                # unrelated historical low-yield queries do not expand the
                # current plan.
                batch_low = [
                    pq.query for pq in planned
                    if pq.query in set(low_yield_queries)
                ]
                if not batch_low:
                    low_yield_queries = []
                    low_yield_query = None
                else:
                    low_yield_query = batch_low[0]
            if low_yield_queries and low_yield_query:
                tokens = low_yield_query.split()
                # We'll try to find a token that is a domain term (case-insensitive)
                replaced = False
                for i, token in enumerate(tokens):
                    token_lower = token.lower().strip('.,:;!?')
                    # Check if this token is a domain term in any family
                    for family_key, family in self.onto.role_families().items():
                        if token_lower in [dt.lower() for dt in self.onto.domain_terms(family_key)]:
                            # We found a domain term, try to replace with an adjacent title
                            # Get adjacent titles for the family? Actually, adjacent_titles is for a given title.
                            # We'll instead replace with a random title from TITLE_CANON that is not already in the query.
                            for title in self.onto.primary_titles():
                                if title.lower() not in low_yield_query.lower():
                                    new_tokens = tokens.copy()
                                    new_tokens[i] = title
                                    broadened_query = " ".join(new_tokens)
                                    # Add this as a new planned query
                                    pq = PlannedQuery(
                                        query=broadened_query,
                                        family="domain_role",  # we could guess family, but default is fine
                                        intent=f"Find {broadened_query} roles",
                                        rationale=f"broaden: replaced '{token}' with '{title}'",
                                        notes="broadening"
                                    )
                                    # Avoid duplicates
                                    if broadened_query.lower() not in {pq.query.lower() for pq in planned}:
                                        planned.append(pq)
                                    replaced = True
                                    break
                            if replaced:
                                break
                    if replaced:
                        break
                # If we couldn't replace a domain term, we'll just add an adjacent title to the query (as a fallback)
                if not replaced:
                    # Add an adjacent title from the first family's first title? We'll just add "Research Engineer" if not present
                    if "research engineer" not in low_yield_query.lower():
                        broadened_query = f"Research Engineer {low_yield_query}"
                        pq = PlannedQuery(
                            query=broadened_query,
                            family="domain_role",
                            intent=f"Find {broadened_query} roles",
                            rationale="broaden: added Research Engineer",
                            notes="broadening"
                        )
                        if broadened_query.lower() not in {pq.query.lower() for pq in planned}:
                            planned.append(pq)

        # 5. Budget clamp: trim to budget
        if len(planned) > budget:
            planned = planned[:budget]

        return planned

    def _build_system_prompt(self, mode: str, state: Dict[str, Any]) -> str:
        """Build the system prompt for the LLM, including mode-specific instructions and state."""
        # Mode-specific query style guidance
        if mode == "jobs":
            mode_guidance = (
                "For LinkedIn Jobs search, generate queries that are typically a role title followed by optional "
                "domain terms or company filters. Examples: 'Software Engineer agentic', 'Research Scientist at Anthropic'. "
                "You may include filters in the 'filters' field (e.g., {'geo': 'United States', 'recency': 'past month'})."
            )
        elif mode == "posts":
            mode_guidance = (
                "For LinkedIn Posts (hiring posts) search, generate queries that are hiring-intent phrases combined with "
                "domain terms or company names. Examples: 'we're hiring agentic engineer', 'join our team for ML roles', "
                "'expanding our AI team'. Focus on phrases that indicate a company is looking to hire. "
                "You may include filters similarly."
            )
        elif mode == "feed":
            mode_guidance = (
                "For LinkedIn Feed search, we do not use keyword queries; instead we rely on a semantic classifier. "
                "Return an empty queries list."
            )
        else:
            mode_guidance = f"Generate queries for mode '{mode}'."

        # Build a compact state summary (we'll include only the most relevant fields to keep prompt short)
        state_summary = []
        if state.get("recent_high_yield_queries"):
            state_summary.append(f"Recent high yield queries: {', '.join(state['recent_high_yield_queries'][:5])}")
        if state.get("recent_low_yield_queries"):
            state_summary.append(f"Recent low yield queries: {', '.join(state['recent_low_yield_queries'][:5])}")
        if state.get("already_seen_companies"):
            state_summary.append(f"Already seen companies: {', '.join(state['already_seen_companies'][:5])}")
        if state.get("coverage_gaps"):
            state_summary.append(f"Coverage gaps (families with no recent queries): {', '.join(state['coverage_gaps'])}")
        if state.get("remaining_search_budget") is not None:
            state_summary.append(f"Remaining search budget: {state['remaining_search_budget']}")

        state_text = "\n".join(state_summary) if state_summary else "No state information available."

        prompt = f"""You are a search query planner for an adaptive LinkedIn job search system.
Your goal is to generate a diverse, justified batch of search queries that will yield relevant job posts.
Mode: {mode}

{mode_guidance}

Current state:
{state_text}

Instructions:
- Return a JSON object with a single key "queries" whose value is a list of query objects.
- Each query object must have the following fields:
  - "query": string, the search query text.
  - "family": string, the role family (e.g., "agentic-ai", "domain_role"). Default: "domain_role".
  - "intent": string, a brief description of the intent behind the query.
  - "expected_signals": list of strings, signals that would indicate a relevant result (e.g., ["hiring", "open role"]).
  - "reject": list of strings, signals that would indicate an irrelevant result (e.g., ["ads", "internship"]).
  - "filters": object, key-value pairs for any filters (e.g., {{"geo": "United States", "recency": "past month"}}).
  - "rationale": string, explaining why this query was chosen.
  - "justification": string, one of the justification entities from the fixation gate (e.g., "on_target_company_list", "recent_hiring_signal", etc.). This is used by the fixation gate to allow entity queries.
- The fixation gate will drop any query whose primary entity (first non-stopword) is not justified unless the justification field is set appropriately.
- Aim for a batch size of about {self.policy['batch_size']} queries.
- Ensure diversity in the batch: avoid near-duplicate queries and aim for multiple role families.
- Follow the mix policy: {self.policy['mix_policy']['proven']*100}% proven (queries with high historical yield), 
  {self.policy['mix_policy']['variation']*100}% variation (shares tokens with high-yield queries), 
  {self.policy['mix_policy']['exploratory']*100}% exploratory (untried ontology terms or promoted vocabulary), 
  {self.policy['mix_policy']['entity_targeted']*100}% entity-targeted (justified entity queries).
- If there are recent low-yield queries, consider broadening: replace a specific token in a low-yield query with an adjacent title to explore related areas.
- Do not exceed the budget of {self.policy['batch_size']} queries per batch (unless instructed otherwise by the caller).
- If you cannot generate any queries for the given mode (e.g., feed mode), return an empty list.
- Output ONLY the JSON object, no additional text before or after it.
"""
        return prompt