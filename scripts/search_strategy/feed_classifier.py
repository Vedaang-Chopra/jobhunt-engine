"""Semantic classifier for LinkedIn feed posts.

Implements the feed semantic classifier (Task 9) as per the plan.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

# Constants for the ladder stages
STAGE_HIRING_SIGNAL = 'hiring_signal'
STAGE_ROLE_RELEVANT = 'role_relevant'
STAGE_COMPANY_RELEVANT = 'company_relevant'
STAGE_GEO_OK = 'geo_ok'
STAGE_REAL_OPPORTUNITY = 'real_opportunity'
STAGE_KNOWN = 'known'
STAGE_SAVED = 'saved'

# Verdict dataclass
@dataclass
class Verdict:
    post_key: str
    is_signal: bool
    stage: str
    reason: str
    verdict_source: str  # 'llm' | 'keyword_fallback' | 'dedup'


# Keyword fallback patterns (degraded mode)
# Hiring language regexes (case-insensitive)
HIRE_PATTERNS = [
    r"we're hiring",
    r"we are hiring",
    r"hiring",
    r"join our team",
    r"growing our team",
    r"expanding our .*team",
    r"looking for",
]

# Role/domain terms (small embedded list) - we'll use a few from the ontology for demonstration
# In practice, these would come from the ontology, but we avoid importing ontology to keep it simple.
# We'll use a small set of role terms that are likely to appear in posts.
ROLE_TERMS = [
    "research engineer",
    "machine learning engineer",
    "ai engineer",
    "llm engineer",
    "agentic ai",
    "training engineer",
    "inference engineer",
]

# Combined pattern for keyword fallback: either hiring language or role terms
KEYWORD_FALLBACK_PATTERN = re.compile(
    r"(" + "|".join(HIRE_PATTERNS) + r")|(" + "|".join(ROLE_TERMS) + r")",
    re.IGNORECASE
)


def _keyword_fallback_classify(text: str) -> Tuple[bool, str, str]:
    """Keyword-based fallback classification.

    Returns (is_signal, stage, reason)
    """
    match = KEYWORD_FALLBACK_PATTERN.search(text)
    if match:
        # We found either hiring language or a role term.
        # For simplicity, we treat any match as at least a hiring signal.
        # In a more sophisticated version, we could differentiate.
        return True, STAGE_HIRING_SIGNAL, "Keyword fallback matched hiring language or role term"
    return False, STAGE_HIRING_SIGNAL, "No keyword fallback match"


class FeedClassifier:
    """Feed semantic classifier with LLM primary and keyword fallback.

    Parameters
    ----------
    judge_fn : callable, optional
        Function that takes a list of post texts and returns a JSON string
        representing a list of verdict dicts (one per text). If None, keyword fallback is used.
    record_sink : callable, optional
        Function that takes a dict (verdict data) for persistence. If None, no persistence.
    """

    def __init__(
        self,
        judge_fn: Optional[Callable[[List[str]], str]] = None,
        record_sink: Optional[Callable[[Dict], None]] = None,
    ):
        self.judge_fn = judge_fn
        self.record_sink = record_sink

    def classify(self, text: str, ctx: Dict) -> Verdict:
        """Classify a single post.

        Parameters
        ----------
        text : str
            The post text.
        ctx : dict
            Context with keys: post_key, company, location, post_url (at least post_key).

        Returns
        -------
        Verdict
        """
        post_key = ctx.get('post_key', '')
        # For single classification, we still use the batch method but with a list of one.
        verdicts = self.classify_batch([{'text': text, 'post_key': post_key}])
        return verdicts[0]

    def classify_batch(
        self,
        items: List[Dict],
        seen_urls: Optional[Set[str]] = None,
    ) -> List[Verdict]:
        """Classify a batch of posts.

        Parameters
        ----------
        items : list of dict
            Each dict must contain 'text' and 'post_key'.
            May also contain 'post_url' for dedupe checking.
        seen_urls : set of str, optional
            Set of post URLs that have been seen before. If provided, items with
            post_url in this set are skipped (dedupe short-circuit).

        Returns
        -------
        list of Verdict
        """
        # We'll maintain a set of seen URLs that starts with seen_urls (if provided)
        # and grows as we process items in the batch.
        # If a post_url is already in this set when we check it, we short-circuit as deduped.
        seen_urls_set: Set[str] = set() if seen_urls is None else set(seen_urls)
        
        # We'll process items in order, handling dedupe first.
        # We'll split items into: deduped (known) and to be processed.
        deduped_verdicts: List[Tuple[int, Verdict]] = []  # (index, verdict) for deduped items
        items_to_process: List[Tuple[int, Dict]] = []     # (index, item) for items to process

        for idx, item in enumerate(items):
            post_url = item.get('post_url', '')
            if post_url and post_url in seen_urls_set:
                # Deduped: stage='known', verdict_source='dedup', is_signal=False (not a new signal)
                verdict = Verdict(
                    post_key=item.get('post_key', ''),
                    is_signal=False,
                    stage=STAGE_KNOWN,
                    reason="Post URL already seen",
                    verdict_source='dedup',
                )
                deduped_verdicts.append((idx, verdict))
            else:
                # Not deduped (yet), add to items to process
                items_to_process.append((idx, item))
                # Add this URL to our seen set so that duplicates later in the batch are caught
                if post_url:
                    seen_urls_set.add(post_url)

        # If there are no items to process, we can return the deduped verdicts in order.
        if not items_to_process:
            # Sort deduped_verdicts by index and extract verdicts
            deduped_verdicts.sort(key=lambda x: x[0])
            return [v for _, v in deduped_verdicts]

        # Extract texts and post_keys for the items to process
        texts = [item['text'] for _, item in items_to_process]
        post_keys = [item.get('post_key', '') for _, item in items_to_process]

        # We'll attempt to use the LLM judge_fn if provided.
        llm_verdicts: List[Dict] = [{} for _ in items_to_process]  # placeholder for results
        llm_used = False
        if self.judge_fn is not None:
            # Try up to two times (original + one retry) to get valid JSON from the judge_fn.
            for attempt in range(2):
                try:
                    # The judge_fn is expected to return a JSON string.
                    json_str = self.judge_fn(texts)
                    # Parse the JSON string.
                    parsed = json.loads(json_str)
                    # Expect parsed to be a list of dicts, each with keys: 'is_signal', 'stage', 'reason'
                    # Optionally, they might include 'verdict_source' but we'll override.
                    if isinstance(parsed, list) and len(parsed) == len(items_to_process):
                        # Validate each element is a dict with the required keys.
                        valid = True
                        for elem in parsed:
                            if not isinstance(elem, dict):
                                valid = False
                                break
                            if not all(k in elem for k in ('is_signal', 'stage', 'reason')):
                                valid = False
                                break
                        if valid:
                            llm_used = True
                            # Convert each parsed dict to a Verdict (we'll set verdict_source later)
                            for i, elem in enumerate(parsed):
                                llm_verdicts[i] = elem
                            break
                    # If we get here, the parsed JSON was not valid for our needs.
                except (json.JSONDecodeError, TypeError, AttributeError):
                    # If we encounter an error, we will retry (if attempt == 0) or fall back.
                    pass
                # If we are here and attempt == 0, we will retry. If attempt == 1, we fall back after the loop.
            # End retry loop

        # If LLM was not used or failed, we fall back to keyword fallback for all items to process.
        if not llm_used:
            for i, (_, item_dict) in enumerate(items_to_process):
                text = item_dict['text']
                is_signal, stage, reason = _keyword_fallback_classify(text)
                llm_verdicts[i] = {
                    'is_signal': is_signal,
                    'stage': stage,
                    'reason': reason,
                }

        # Now we have llm_verdicts filled with dicts for each item to process.
        # We'll convert them to Verdict objects, setting the post_key and verdict_source.
        # For items that came from LLM, verdict_source is 'llm'; for keyword fallback, it's 'keyword_fallback'.
        # However, we don't track which came from which in llm_verdicts. We'll need to know.
        # We'll adjust: we'll create two separate lists for LLM and keyword fallback results.
        # But for simplicity, we'll assume that if llm_used is True, then all items to process used LLM.
        # If llm_used is False, then all used keyword fallback.
        # This is acceptable because we either use LLM for the whole batch or keyword fallback for the whole batch.

        verdict_source_for_items_to_process = 'llm' if llm_used else 'keyword_fallback'

        # Build the final list of verdicts in the original order.
        final_verdicts: List[Verdict] = [None] * len(items)  # type: ignore

        # Fill in the deduped verdicts
        for idx, verdict in deduped_verdicts:
            final_verdicts[idx] = verdict

        # Fill in the processed items verdicts
        for i, (idx, item_dict) in enumerate(items_to_process):
            # At this point, llm_verdicts[i] is guaranteed to be a dict.
            verdict_dict = llm_verdicts[i]
            verdict = Verdict(
                post_key=item_dict.get('post_key', ''),
                is_signal=verdict_dict['is_signal'],
                stage=verdict_dict['stage'],
                reason=verdict_dict['reason'],
                verdict_source=verdict_source_for_items_to_process,
            )
            final_verdicts[idx] = verdict

        # At this point, there should be no None entries.
        # But just in case, we'll replace any None with a safe fallback.
        for i in range(len(final_verdicts)):
            if final_verdicts[i] is None:
                final_verdicts[i] = Verdict(
                    post_key=items[i].get('post_key', ''),
                    is_signal=False,
                    stage=STAGE_HIRING_SIGNAL,  # default to hiring_signal? Actually, we don't know.
                    reason="Classifier failed to produce a verdict",
                    verdict_source='keyword_fallback',
                )

        # If record_sink is provided, call it for each verdict.
        if self.record_sink is not None:
            for verdict in final_verdicts:
                # Convert the verdict to a dict for persistence.
                # We'll include the fields that are relevant for persistence.
                # The spec says: record_sink receives one dict per verdict for persistence by caller (mode='feed').
                # We'll pass a dict with the verdict's fields.
                verdict_dict = {
                    'post_key': verdict.post_key,
                    'is_signal': verdict.is_signal,
                    'stage': verdict.stage,
                    'reason': verdict.reason,
                    'verdict_source': verdict.verdict_source,
                }
                self.record_sink(verdict_dict)

        return final_verdicts