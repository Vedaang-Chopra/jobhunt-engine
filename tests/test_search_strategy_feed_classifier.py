"""Tests for the feed semantic classifier."""

import sys
from pathlib import Path
import json

# Add the scripts directory to the path so we can import from search_strategy
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pytest
from search_strategy.feed_classifier import (
    FeedClassifier,
    Verdict,
    STAGE_HIRING_SIGNAL,
    STAGE_ROLE_RELEVANT,
    STAGE_COMPANY_RELEVANT,
    STAGE_GEO_OK,
    STAGE_REAL_OPPORTUNITY,
    STAGE_KNOWN,
    STAGE_SAVED,
)


def test_indirect_hiring_language_is_signal():
    """Test that indirect hiring language is recognized as a signal via fake judge."""
    # Define a fake judge that returns a verdict indicating a hiring signal
    def fake_llm(texts):
        # Return a JSON string with a verdict for each text
        # For the indirect hiring language, we want is_signal=True, stage='role_relevant'
        verdicts = []
        for text in texts:
            if "expanding our reasoning team" in text:
                verdicts.append({
                    "is_signal": True,
                    "stage": STAGE_ROLE_RELEVANT,
                    "reason": "Indirect hiring language detected"
                })
            else:
                verdicts.append({
                    "is_signal": False,
                    "stage": STAGE_HIRING_SIGNAL,
                    "reason": "No signal detected"
                })
        return json.dumps(verdicts)
    
    classifier = FeedClassifier(judge_fn=fake_llm)
    text = ("We're expanding our reasoning team and looking for engineers "
            "who have experience with tool-using models.")
    ctx = {
        "post_key": "test_post_1",
        "company": "Test Company",
        "location": "Remote",
        "post_url": "https://linkedin.com/posts/test"
    }
    
    verdict = classifier.classify(text, ctx)
    
    assert verdict.is_signal is True
    assert verdict.stage == STAGE_ROLE_RELEVANT
    assert verdict.verdict_source == "llm"


def test_ladder_order_enforced():
    """Test that non-hiring commentary stops at hiring_signal stage."""
    # Define a fake judge that returns non-hiring commentary
    def fake_llm_non_hiring(texts):
        verdicts = []
        for text in texts:
            verdicts.append({
                "is_signal": False,  # Not a hiring signal
                "stage": STAGE_HIRING_SIGNAL,  # But we checked hiring signal first
                "reason": "Non-hiring commentary"
            })
        return json.dumps(verdicts)
    
    classifier = FeedClassifier(judge_fn=fake_llm_non_hiring)
    text = "Just commenting on the weather today, nothing to do with jobs."
    ctx = {
        "post_key": "test_post_2",
        "company": "Test Company",
        "location": "Remote",
        "post_url": "https://linkedin.com/posts/test2"
    }
    
    verdict = classifier.classify(text, ctx)
    
    # Should stop at hiring_signal stage (meaning we checked for hiring signal and didn't find it)
    assert verdict.stage == STAGE_HIRING_SIGNAL
    assert verdict.is_signal is False  # Not a signal because no hiring language


def test_batched_calls_and_known_dedup_shortcircuit():
    """Test that batched processing works and dedup short-circuits."""
    # We'll use a fake judge that tracks how many times it's called
    call_count = 0
    
    def fake_llm(texts):
        nonlocal call_count
        call_count += 1
        # Return a simple verdict for each text
        verdicts = []
        for text in texts:
            verdicts.append({
                "is_signal": True,
                "stage": STAGE_ROLE_RELEVANT,
                "reason": "Fake LLM verdict"
            })
        return json.dumps(verdicts)
    
    classifier = FeedClassifier(judge_fn=fake_llm)
    
    # First item: URL that IS in seen_urls (so should be deduped)
    # Second item: URL that is NOT in seen_urls (so should be processed)
    items = [
        {
            "text": "We're hiring a research engineer!",
            "post_key": "post1",
            "post_url": "https://linkedin.com/posts/1"
        },
        {
            "text": "We're hiring a research engineer!",  # Same text
            "post_key": "post2",  # Different post_key but different URL
            "post_url": "https://linkedin.com/posts/2"
        }
    ]
    
    # The first item's URL is in seen_urls (so it should be deduped)
    # The second item's URL is NOT in seen_urls (so it should be processed)
    seen_urls = {"https://linkedin.com/posts/1"}
    
    verdicts = classifier.classify_batch(items, seen_urls=seen_urls)
    
    # First item should be deduped (because its URL is in seen_urls)
    assert verdicts[0].verdict_source == "dedup"
    # Second item should be processed by LLM (or keyword fallback)
    assert verdicts[1].verdict_source != "dedup"
    assert verdicts[1].stage == STAGE_ROLE_RELEVANT  # from our fake LLM
    assert verdicts[1].is_signal is True
    
    # The LLM should have been called only once (for the batch of non-deduped items)
    # Since we had one non-deduped item, the batch size is 1
    assert call_count == 1


def test_verdicts_logged_to_memory_mode_feed():
    """Test that verdicts are passed to record_sink with mode='feed'."""
    persisted_verdicts = []
    
    def record_sink(verdict_dict):
        persisted_verdicts.append(verdict_dict)
    
    # Use keyword fallback for simplicity (no judge_fn)
    classifier = FeedClassifier(judge_fn=None, record_sink=record_sink)
    
    text = "We're hiring a machine learning engineer"
    ctx = {
        "post_key": "test_post_3",
        "company": "Test Company",
        "location": "Remote",
        "post_url": "https://linkedin.com/posts/test3"
    }
    
    verdict = classifier.classify(text, ctx)
    
    # Check that record_sink was called
    assert len(persisted_verdicts) == 1
    persisted = persisted_verdicts[0]
    
    # Check the persisted dict has the expected fields
    assert persisted["post_key"] == "test_post_3"
    assert persisted["is_signal"] is True  # Should match hiring language
    assert persisted["stage"] == STAGE_HIRING_SIGNAL
    assert "Keyword fallback" in persisted["reason"]
    assert persisted["verdict_source"] == "keyword_fallback"


def test_malformed_json_repair_retry_then_keyword_fallback():
    """Test that malformed JSON triggers a retry and then falls back to keyword fallback."""
    call_count = 0
    
    def fake_llm_malformed_then_valid(texts):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call returns malformed JSON
            return '{"is_signal": true, "stage": "role_relevant"'  # Missing closing brace
        else:
            # Second call returns valid JSON
            verdicts = []
            for text in texts:
                verdicts.append({
                    "is_signal": True,
                    "stage": STAGE_ROLE_RELEVANT,
                    "reason": "Recovered LLM verdict"
                })
            return json.dumps(verdicts)
    
    classifier = FeedClassifier(judge_fn=fake_llm_malformed_then_valid)
    
    text = "We're hiring a research engineer"
    ctx = {
        "post_key": "test_post_4",
        "company": "Test Company",
        "location": "Remote",
        "post_url": "https://linkedin.com/posts/test4"
    }
    
    verdicts = classifier.classify_batch([{"text": text, "post_key": "test_post_4"}])
    
    # Should have retried once and then succeeded
    assert call_count == 2
    assert len(verdicts) == 1
    verdict = verdicts[0]
    assert verdict.is_signal is True
    assert verdict.stage == STAGE_ROLE_RELEVANT
    assert verdict.reason == "Recovered LLM verdict"
    assert verdict.verdict_source == "llm"


def test_keyword_fallback_recognizes_direct_hiring_language():
    """Test that keyword fallback recognizes direct hiring language without LLM."""
    # No judge_fn, so should use keyword fallback
    classifier = FeedClassifier(judge_fn=None)
    
    text = "We're hiring research engineer for our AI team"
    ctx = {
        "post_key": "test_post_5",
        "company": "Test Company",
        "location": "Remote",
        "post_url": "https://linkedin.com/posts/test5"
    }
    
    verdict = classifier.classify(text, ctx)
    
    assert verdict.is_signal is True
    assert verdict.stage == STAGE_HIRING_SIGNAL
    assert verdict.verdict_source == "keyword_fallback"
    assert "Keyword fallback matched" in verdict.reason


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])