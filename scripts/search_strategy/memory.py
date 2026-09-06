"""Search Memory store: persistent query log + derived signals.

Mirrors jobhunt-data/job_research/config/search_policy.yaml thresholds:
LOW_YIELD_THRESHOLD (relevant < 3 -> low), HIGH_YIELD_THRESHOLD (>= 8 -> high),
MAX_DUPLICATE_RATE (0.8) used in stop rules.
"""

from __future__ import annotations

import csv
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

LOW_YIELD_THRESHOLD = 3   # mirror of search_policy.yaml low_yield_threshold
HIGH_YIELD_THRESHOLD = 8  # mirror of search_policy.yaml high_yield_threshold
MAX_DUPLICATE_RATE = 0.8  # mirror of search_policy.yaml stop_rules.max_duplicate_rate


@dataclass
class QueryRecord:
    mode: str = ""
    query: str = ""
    family: str = ""
    filters_json: str = ""           # JSON-encoded filter dict as string
    results_inspected: int = 0
    relevant_results: int = 0
    new_results: int = 0
    duplicate_results: int = 0
    companies_found: list = field(default_factory=list)   # list in memory, ';'-joined in CSV
    roles_found: list = field(default_factory=list)       # list in memory, ';'-joined in CSV
    query_id: str = ""
    timestamp: str = ""
    yield_score: str = ""            # low | medium | high (derived on append)
    duplicate_rate: float = 0.0      # derived on append
    novelty_score: str = ""          # high | medium | low (derived on append)

    CSV_FIELDS = (
        "query_id", "timestamp", "mode", "query", "family", "filters_json",
        "results_inspected", "relevant_results", "new_results", "duplicate_results",
        "companies_found", "roles_found",
        "yield_score", "duplicate_rate", "novelty_score",
    )

    def to_row(self) -> dict:
        row = {}
        for name in self.CSV_FIELDS:
            value = getattr(self, name)
            if isinstance(value, list):
                value = ";".join(str(v) for v in value)
            row[name] = str(value)
        return row

    @classmethod
    def from_row(cls, row: dict) -> "QueryRecord":
        kwargs: dict[str, Any] = {}
        for name in cls.CSV_FIELDS:
            raw = row.get(name, "")
            if raw is None:
                raw = ""
            if name in ("companies_found", "roles_found"):
                value = [v for v in str(raw).split(";") if v]
            elif name == "duplicate_rate":
                try:
                    value = float(raw)
                except ValueError:
                    value = 0.0
            elif name in ("results_inspected", "relevant_results", "new_results",
                          "duplicate_results"):
                try:
                    value = int(float(raw))
                except ValueError:
                    value = 0
            else:
                value = str(raw)
            kwargs[name] = value
        return cls(**kwargs)


def _derive(record: QueryRecord) -> None:
    """Fill derived fields (yield_score, duplicate_rate, novelty_score) in place."""
    inspected = record.results_inspected or 0
    dupes = record.duplicate_results or 0
    rate = (dupes / inspected) if inspected > 0 else 0.0
    record.duplicate_rate = rate

    relevant = record.relevant_results or 0
    if relevant >= HIGH_YIELD_THRESHOLD:
        record.yield_score = "high"
    elif relevant >= LOW_YIELD_THRESHOLD:
        record.yield_score = "medium"
    else:
        record.yield_score = "low"

    if (record.new_results or 0) > 0 and rate < 0.5:
        record.novelty_score = "high"
    elif (record.new_results or 0) > 0 and rate < MAX_DUPLICATE_RATE:
        record.novelty_score = "medium"
    else:
        record.novelty_score = "low"


class SearchMemory:
    """Append-only CSV-backed log of discovery queries with derived quality signals."""

    def __init__(self, root=None):
        root = Path(root) if root is not None else Path(".")
        self.path = root / "job_research" / "search_memory" / "query_log.csv"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ write

    def append(self, record: QueryRecord) -> QueryRecord:
        _derive(record)
        if not getattr(record, "query_id", ""):
            record.query_id = secrets.token_hex(4)
        if not getattr(record, "timestamp", ""):
            record.timestamp = datetime.now().isoformat()
        exists = self.path.exists() and self.path.stat().st_size > 0
        with open(self.path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(QueryRecord.CSV_FIELDS))
            if not exists:
                writer.writeheader()
            writer.writerow(record.to_row())
        return record

    # ------------------------------------------------------------------- read

    def recent(self, window_days: int | None = None,
               limit: int | None = 50) -> list[QueryRecord]:
        records = self._read_all()
        records.sort(key=lambda r: r.timestamp, reverse=True)
        if window_days is not None:
            cutoff = datetime.now() - timedelta(days=window_days)
            kept = []
            for r in records:
                try:
                    ts = datetime.fromisoformat(r.timestamp)
                except ValueError:
                    continue
                if ts >= cutoff:
                    kept.append(r)
            records = kept
        if limit is not None:
            records = records[:limit]
        return records

    def _read_all(self) -> list[QueryRecord]:
        if not self.path.exists():
            return []
        try:
            with open(self.path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except OSError:
            return []
        return [QueryRecord.from_row(r) for r in rows]

    # -------------------------------------------------------------- analytics

    @staticmethod
    def _norm(text: str) -> str:
        return (text or "").strip().lower()

    def yield_stats(self, query: str) -> dict:
        q = self._norm(query)
        runs = [r for r in self._read_all() if self._norm(r.query) == q]
        total = sum(r.relevant_results or 0 for r in runs)
        return {
            "runs": len(runs),
            "total_relevant": total,
            "avg_relevant": round(total / len(runs), 2) if runs else 0.0,
        }

    def entity_query_count(self, name: str) -> int:
        n = self._norm(name)
        return sum(1 for r in self._read_all() if n in self._norm(r.query))

    # ------------------------------------------------------------ build_state

    def build_state(self, onto: Any = None, seen_jobs: dict | None = None,
                    seen_posts: dict | None = None, budget_remaining: int | None = None,
                    window_days: int = 7) -> dict:
        window = self.recent(window_days=window_days, limit=None)

        families_queried = {self._norm(r.family) for r in window if r.family}
        coverage_gaps = []
        candidate_domains: list[str] = []
        target_companies: list[str] = []
        location_preferences: list[str] = []
        candidate_target_roles: list[str] = []
        if onto is not None:
            try:
                role_families = onto.role_families() or {}
            except Exception:
                role_families = {}
            for fam in role_families:
                if self._norm(fam) not in families_queried:
                    coverage_gaps.append(fam)
            getter = getattr(onto, "domain_terms", None)
            if callable(getter):
                for fam in role_families:
                    try:
                        terms = getter(fam) or []
                    except Exception:
                        terms = []
                    for t in terms:
                        if t not in candidate_domains:
                            candidate_domains.append(t)
            for attr, sink in (("primary_titles", candidate_target_roles),
                               ("locations", location_preferences),
                               ("target_companies", target_companies)):
                getter = getattr(onto, attr, None)
                if callable(getter):
                    try:
                        values = getter() or []
                    except Exception:
                        values = []
                    for v in values:
                        if v not in sink:
                            sink.append(v)

        recent_high = []
        recent_low = []
        companies: list[str] = []
        for r in window:
            if r.query and r.query not in recent_high and r.query not in recent_low:
                if r.yield_score == "high":
                    recent_high.append(r.query)
                elif r.yield_score == "low":
                    recent_low.append(r.query)
            for c in (r.companies_found or []):
                if c and c not in companies:
                    companies.append(c)

        return {
            "candidate_target_roles": candidate_target_roles,
            "candidate_domains": candidate_domains,
            "location_preferences": location_preferences,
            "recent_queries": [r.query for r in window],
            "recent_high_yield_queries": recent_high,
            "recent_low_yield_queries": recent_low,
            "already_seen_jobs": dict(seen_jobs or {}),
            "already_seen_posts": dict(seen_posts or {}),
            "already_seen_companies": companies,
            "target_companies": target_companies,
            "recent_hiring_signals": [],
            "coverage_gaps": coverage_gaps,
            "remaining_search_budget": budget_remaining,
        }


# --------------------------------------------------------------------- helpers

def _default_jobs_csv():
    try:
        from scripts.search_strategy import config_lib  # type: ignore
    except ImportError:
        try:
            from . import config_lib  # type: ignore
        except ImportError:
            try:
                import config_lib  # type: ignore
            except ImportError:
                return None
    try:
        return config_lib.data_root() / "tracking" / "jobs" / "jobs.csv"
    except Exception:
        return None


def _default_hiring_posts_csv():
    jobs = _default_jobs_csv()
    if jobs is None:
        return None
    return jobs.parent.parent / "hiring_posts" / "hiring_posts.csv"


def _target_list_names() -> set[str]:
    try:
        import yaml
    except ImportError:
        return set()
    path = _repo_root() / "jobhunt-data" / "target-companies.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    section = data.get("companies")
    names: set[str] = set()
    if isinstance(section, dict):
        keys = section.keys()
    elif isinstance(section, list):
        keys = section
    else:
        keys = []
    for item in keys:
        if isinstance(item, str):
            names.add(item.strip().lower())
        elif isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]).strip().lower())
    return names


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def company_evidence(name: str, jobs_csv: Path | None = None,
                     hiring_posts_csv: Path | None = None) -> dict:
    """Tolerant read-only evidence lookup for a company. Never writes."""
    if jobs_csv is None:
        jobs_csv = _default_jobs_csv()
    if hiring_posts_csv is None:
        hiring_posts_csv = _default_hiring_posts_csv()

    n = (name or "").strip().lower()

    # --- on_target_list: target-companies.yaml OR >=3 open rows in jobs.csv ---
    on_target_list = False
    if n and n in _target_list_names():
        on_target_list = True
    open_rows = 0
    if not on_target_list and jobs_csv is not None and n:
        try:
            with open(jobs_csv, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    company = (row.get("company") or "").strip().lower()
                    status = (row.get("status") or "").strip().lower()
                    if n in company and status == "open":
                        open_rows += 1
                        if open_rows >= 3:
                            break
        except Exception:
            open_rows = 0
    if open_rows >= 3:
        on_target_list = True

    # --- recent_hiring_signal: fresh non-rejected hiring post ---------------
    recent_hiring_signal = False
    if hiring_posts_csv is not None and n:
        try:
            cutoff = datetime.now() - timedelta(days=14)
            with open(hiring_posts_csv, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    company = (row.get("company") or "").strip().lower()
                    if n not in company:
                        continue
                    status = (row.get("status") or "").strip().lower()
                    if status in {"rejected", "discarded"}:
                        continue
                    try:
                        discovered = datetime.fromisoformat(
                            str(row.get("discovered_date") or ""))
                    except ValueError:
                        continue
                    if discovered >= cutoff:
                        recent_hiring_signal = True
                        break
        except Exception:
            recent_hiring_signal = False

    # --- open_job_lead: open row with priority_v2 >= 55 ----------------------
    open_job_lead = False
    if jobs_csv is not None and n:
        try:
            with open(jobs_csv, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    company = (row.get("company") or "").strip().lower()
                    if n not in company:
                        continue
                    status = (row.get("status") or "").strip().lower()
                    if status != "open":
                        continue
                    try:
                        priority = float(row.get("priority_v2") or 0.0)
                    except (TypeError, ValueError):
                        continue
                    if priority >= 55.0:
                        open_job_lead = True
                        break
        except Exception:
            open_job_lead = False

    return {
        "on_target_list": bool(on_target_list),
        "recent_hiring_signal": bool(recent_hiring_signal),
        "open_job_lead": bool(open_job_lead),
    }
