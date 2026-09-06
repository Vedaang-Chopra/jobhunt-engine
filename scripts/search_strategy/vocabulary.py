"""Candidate-vocabulary learning with gated promotion (plan Task 6).

Tracks terminology observed in search results (job titles, post role lines)
in ``<root>/job_research/search_memory/candidate_vocabulary.csv`` and promotes
terms into the planner's exploratory pool only with evidence:

- status lifecycle: observed -> promoted | rejected (terminal)
- promotion gate (deterministic): confidence >= 0.7 AND relevance_hits >= 2
- confidence rule (documented, all-or-nothing cells):
      confidence = min(1.0, (0.8 if relevance_hits >= 2 else 0.4)
                            + (0.2 if distinct_source_queries >= 2 else 0))
  i.e. 1.0 when both conditions hold, 0.8 on strong relevance alone,
  0.6 on breadth alone, 0.4 otherwise.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

__all__ = [
    "VocabHit",
    "VocabularyTracker",
    "NotPromotable",
    "extract_candidate_terms",
]

CSV_REL_PATH = Path("job_research") / "search_memory" / "candidate_vocabulary.csv"
CSV_HEADER = [
    "term", "source_query", "first_seen", "last_seen", "frequency",
    "relevance_hits", "successful_searches", "confidence", "status",
]

STATUS_OBSERVED = "observed"
STATUS_PROMOTED = "promoted"
STATUS_REJECTED = "rejected"

PROMOTE_MIN_CONFIDENCE = 0.7
PROMOTE_MIN_RELEVANCE_HITS = 2


class NotPromotable(Exception):
    """Raised by VocabularyTracker.promote() when the gate fails."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class VocabHit:
    """One observation of a term surfaced under a source query."""

    term: str
    source_query: str
    relevant: bool
    first_seen: Optional[str] = None  # ISO timestamps; tracker fills defaults
    last_seen: Optional[str] = None
    # reserved for future per-hit weighting (unused by the current gate)
    weight: float = field(default=1.0)


class VocabularyTracker:
    """Persistent CSV-backed term tracker with a deterministic promotion gate.

    Rows are keyed by canonical lowercase term; ``observe()`` upserts,
    incrementing frequency/relevance counters. Rejected terms are terminal:
    further observation never resurrects them into the pool.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.csv_path = self.root / CSV_REL_PATH

    # -- persistence ------------------------------------------------------

    def _load_rows(self) -> dict:
        rows = {}
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    term = row["term"].strip().lower()
                    row["term"] = term
                    # coerce numeric columns so callers get typed values
                    for col in ("frequency", "relevance_hits",
                                "successful_searches"):
                        row[col] = int(float(row.get(col) or 0))
                    row["confidence"] = float(row.get("confidence") or 0.0)
                    rows[term] = row
        return rows

    def _save_rows(self, rows: dict) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(rows.values(), key=lambda r: r["term"])
        with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
            writer.writeheader()
            writer.writerows(ordered)

    @staticmethod
    def _confidence(relevance_hits: int, distinct_sources: int) -> float:
        # Documented rule (see module docstring): simple two-condition cells,
        # capped at 1.0. Deliberately NOT a weighted average — easy to audit.
        base = 0.8 if relevance_hits >= 2 else 0.4
        bonus = 0.2 if distinct_sources >= 2 else 0.0
        return min(1.0, base + bonus)

    def _new_row(self, term: str) -> dict:
        now = _now_iso()
        return {
            "term": term,
            "source_query": "",
            "first_seen": now,
            "last_seen": now,
            "frequency": 0,
            "relevance_hits": 0,
            "successful_searches": 0,
            "confidence": 0.0,
            "status": STATUS_OBSERVED,
        }

    def _upsert_row(self, patch: dict) -> None:
        """Merge a raw row-dict into the store (test/seed helper)."""
        rows = self._load_rows()
        term = str(patch.get("term", "")).strip().lower()
        row = rows.get(term) or self._new_row(term)
        row.update({k: v for k, v in patch.items() if k != "term"})
        rows[term] = row
        self._save_rows(rows)

    # -- public API -------------------------------------------------------

    def observe(self, hits: list) -> None:
        """Upsert one CSV row per distinct term from ``hits``.

        Case-insensitive canonical lowercase terms; frequency increments per
        hit, relevance_hits per relevant hit, last_seen refreshes each time,
        first_seen is set once. Confidence recomputed from the documented
        rule using total relevance_hits and distinct non-empty source queries.
        Rejected terms stay rejected but still accumulate counts.
        """
        updates = {}
        for hit in hits:
            term = hit.term.strip().lower()
            if not term:
                continue
            st = updates.setdefault(term, {"sources": set(), "relevant": 0})
            if hit.source_query:
                st["sources"].add(hit.source_query)
            if hit.relevant:
                st["relevant"] += 1

        if not updates:
            return
        rows = self._load_rows()
        now = _now_iso()
        for term, st in updates.items():
            row = rows.get(term)
            if row is None:
                row = self._new_row(term)
                rows[term] = row
            # frequency counts every hit (relevant or not)
            freq_delta = sum(1 for h in hits if h.term.strip().lower() == term)
            row["frequency"] = int(row["frequency"]) + freq_delta
            row["relevance_hits"] = int(row["relevance_hits"]) + st["relevant"]
            # distinct lifetime source queries kept as a ' | '-joined set
            existing_sources = set(filter(None, row["source_query"].split(" | ")))
            merged = sorted(existing_sources | st["sources"])
            row["source_query"] = " | ".join(merged)
            row["last_seen"] = now
            conf = self._confidence(int(row["relevance_hits"]), len(merged))
            row["confidence"] = f"{conf:.2f}"
        self._save_rows(rows)

    def lookup(self, term: str) -> Optional[dict]:
        """Return the row for ``term`` (case-insensitive) or None."""
        return self._load_rows().get(term.strip().lower())

    def promote(self, term: str) -> None:
        """Promote ``term`` only through the deterministic gate.

        Requires confidence >= 0.7 AND relevance_hits >= 2 AND the term not
        being rejected. Raises NotPromotable otherwise; KeyError if unknown.
        """
        key = term.strip().lower()
        rows = self._load_rows()
        row = rows.get(key)
        if row is None:
            raise KeyError(f"unknown vocabulary term: {term!r}")
        if row["status"] == STATUS_REJECTED:
            raise NotPromotable(f"{key!r} is rejected (terminal)")
        if (float(row["confidence"]) < PROMOTE_MIN_CONFIDENCE
                or int(row["relevance_hits"]) < PROMOTE_MIN_RELEVANCE_HITS):
            raise NotPromotable(
                f"{key!r}: confidence={row['confidence']} "
                f"(<{PROMOTE_MIN_CONFIDENCE}) or "
                f"relevance_hits={row['relevance_hits']} "
                f"(<{PROMOTE_MIN_RELEVANCE_HITS})"
            )
        row["status"] = STATUS_PROMOTED
        self._save_rows(rows)

    def reject(self, term: str) -> None:
        """Mark ``term`` rejected — a terminal state."""
        key = term.strip().lower()
        rows = self._load_rows()
        if key not in rows:
            rows[key] = self._new_row(key)
        rows[key]["status"] = STATUS_REJECTED
        self._save_rows(rows)

    def promoted(self) -> list:
        """All promoted terms, alphabetically."""
        rows = self._load_rows()
        return sorted(t for t, r in rows.items() if r["status"] == STATUS_PROMOTED)

    def pool(self) -> list:
        """Planner exploratory additions: exactly the promoted terms."""
        return self.promoted()


# ---------------------------------------------------------------------------
# Candidate-term extraction
# ---------------------------------------------------------------------------

STOPWORDS = frozenset("""
a about above after again against all am an and any are aren as at be because
been before being below between both but by can cannot could couldn did didn do
does doesn doing don down during each few for from further had hadn has hasn
have haven having he her here hers herself him himself his how i if in into is
isn it its itself just ll me more most mustn my myself no nor not now of off on
once only or other our ours ourselves out over own re s same shan she should
shouldn so some such t than that the their theirs them themselves then there
these they this those through to too under until up ve very was wasn we were
weren what when where which while who whom why will with won would wouldn you
your yours yourself yourselves at company inc ltd corp labs lab group team
join joining hiring seeking looking new opportunity opportunities role position
based greater area greaterarea remote onsite hybrid fulltime parttime contract
years experience etc via apply now us uk canada india bangalore bengaluru sf
nyc seattle austin
""".split())

# Tokens TOO generic alone to be useful search vocabulary unless paired with
# a domain token (e.g. 'machine' carries the signal, 'engineer' does not).
GENERIC_TOKENS = frozenset("""
engineer engineering scientist research researcher science senior staff junior
principal associate lead head chief manager director vp president fellow intern
ml ai llm nlp genai developer software tech technical digital solutions system
systems platform product data learning deep neural artificial
intelligence model models specialist expert consultant analyst architect
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*")


def _normalize_token(tok: str) -> str:
    tok = unicodedata.normalize("NFKC", tok).lower().strip(".")
    return tok


def extract_candidate_terms(texts: list, stopword_path=None) -> list:
    """Deterministic candidate-term scan of job titles / post role lines.

    Returns unigram and bigram candidates containing at least one non-generic
    token, deduped, ordered by frequency desc then alphabetically. Stopwords
    are dropped (stopwords are not search vocabulary); generic tokens
    ('engineer', 'ml', ...) may appear inside bigrams but never as sole
    content. ``stopword_path`` optionally extends the built-in stopword set
    with one term per line.
    """
    stopwords = set(STOPWORDS)
    if stopword_path is not None:
        extra = Path(stopword_path).read_text(encoding="utf-8").split()
        stopwords |= {_normalize_token(w) for w in extra}

    counts: dict = {}
    for text in texts or []:
        tokens = [_normalize_token(t) for t in _TOKEN_RE.findall(text or "")]
        tokens = [t for t in tokens if t and t not in stopwords]
        candidates = list(tokens)
        candidates += [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]
        for cand in candidates:
            parts = cand.split()
            if any(p not in GENERIC_TOKENS for p in parts):
                counts[cand] = counts.get(cand, 0) + 1

    return sorted(counts, key=lambda c: (-counts[c], c))


# expose sets on the function for tests/introspection
extract_candidate_terms.STOPWORDS = STOPWORDS
extract_candidate_terms.GENERIC_TOKENS = GENERIC_TOKENS
