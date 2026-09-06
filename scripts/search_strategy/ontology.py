"""Ontology loader — role/domain/seniority/location vocabulary from config.

Single source of truth: ``<data_root>/job_research/config/{role-keywords,
target-companies,location-preferences}.yaml``. No keyword lists are duplicated
in code; the only hard-coded title vocabulary is ``TITLE_CANON`` (a cross-family
title canon, not a search list).

Usage::

    onto = Ontology.load()                 # via config_lib.data_root()
    onto = Ontology.load(data_root=tmp)    # explicit root (tests)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:  # repo-root package import vs. flat scripts-dir import
    from scripts import config_lib
except ImportError:  # pragma: no cover - exercised when sys.path includes scripts/
    import config_lib

# Cross-family title canon — defined ONCE here by design. This is a *title*
# vocabulary for planner variation/broadening, not a search-keyword list.
TITLE_CANON = [
    "Research Engineer",
    "Research Scientist",
    "Applied Scientist",
    "ML Engineer",
    "AI Engineer",
    "LLM Engineer",
]

_TITLE_MARKERS = ("engineer", "scientist", "researcher")

CONFIG_DIR = ("job_research", "config")

DATA_ROOT_DEFAULT: Path = config_lib.data_root()


@dataclass
class RoleFamily:
    """One entry from role-keywords.yaml ``role_families``."""

    key: str
    name: str = ""
    priority: int = 99
    primary_keywords: list[str] = field(default_factory=list)
    secondary_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    target_companies: list[str] = field(default_factory=list)


def _dedupe(items) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


class Ontology:
    """In-memory view over the preference configs."""

    def __init__(self, families: dict[str, RoleFamily], companies: list[str],
                 location_tiers: dict, source_files: list[Path]) -> None:
        self._families = families
        self._companies = companies
        self._location_tiers = location_tiers
        self._source_files = source_files

    # -- loading ------------------------------------------------------------
    @classmethod
    def load(cls, data_root=None) -> "Ontology":
        """Load ontology from ``<data_root>/job_research/config/*.yaml``.

        ``data_root=None`` resolves through ``config_lib.data_root()``
        ($JOBHUNT_HOME -> config.yaml pointer -> legacy repo-local default).
        Missing optional files are tolerated (empty contributions).
        """
        if data_root is None:
            root = config_lib.data_root()
        else:
            root = Path(data_root)
        cfg_dir = root.joinpath(*CONFIG_DIR)

        families: dict[str, RoleFamily] = {}
        companies: list[str] = []
        location_tiers: dict = {}
        source_files: list[Path] = []

        rk_path = cfg_dir / "role-keywords.yaml"
        if rk_path.is_file():
            source_files.append(rk_path)
            data = _load_yaml(rk_path) or {}
            fams = data.get("role_families", data)
            if isinstance(fams, dict):
                for fam_key, spec in fams.items():
                    spec = spec if isinstance(spec, dict) else {}
                    families[str(fam_key)] = RoleFamily(
                        key=str(fam_key),
                        name=str(spec.get("name", "")),
                        priority=int(spec.get("priority", 99) or 99),
                        primary_keywords=[str(k) for k in
                                          spec.get("primary_keywords", []) or []],
                        secondary_keywords=[str(k) for k in
                                            spec.get("secondary_keywords", []) or []],
                        exclude_keywords=[str(k) for k in
                                          spec.get("exclude_keywords", []) or []],
                        seniority=[str(s) for s in spec.get("seniority", []) or []],
                        locations=[str(l) for l in spec.get("locations", []) or []],
                        target_companies=[str(c) for c in
                                          spec.get("target_companies", []) or []],
                    )

        tc_path = cfg_dir / "target-companies.yaml"
        if tc_path.is_file():
            source_files.append(tc_path)
            data = _load_yaml(tc_path) or {}
            items = data.get("companies", data if isinstance(data, list) else [])
            for item in items:
                name = ""
                if isinstance(item, dict):
                    name = str(item.get("company") or item.get("name") or "")
                elif isinstance(item, str):
                    name = item
                if name:
                    companies.append(name)

        lp_path = cfg_dir / "location-preferences.yaml"
        if lp_path.is_file():
            source_files.append(lp_path)
            data = _load_yaml(lp_path) or {}
            tiers = data.get("location_tiers", {})
            if isinstance(tiers, dict):
                location_tiers = tiers

        return cls(families, _dedupe(companies), location_tiers, source_files)

    # -- accessors ----------------------------------------------------------
    def role_families(self) -> dict[str, RoleFamily]:
        """All role families keyed by their yaml key."""
        return dict(self._families)

    def domain_terms(self, family: str) -> list[str]:
        """Domain vocabulary for a family (primary + secondary keywords)."""
        fam = self._families[family]
        return _dedupe(fam.primary_keywords + fam.secondary_keywords)

    def primary_titles(self) -> list[str]:
        """Title vocabulary: TITLE_CANON + title-like yaml primary keywords.

        Title-like = a primary keyword containing engineer/scientist/researcher.
        """
        titles = list(TITLE_CANON)
        for fam in self._families.values():
            for kw in fam.primary_keywords:
                low = kw.lower()
                if any(marker in low for marker in _TITLE_MARKERS):
                    titles.append(kw.strip().title() if low == kw else kw.strip())
        return _dedupe(titles)

    def adjacent_titles(self, title: str) -> list[str]:
        """Other TITLE_CANON titles appearing in a family that also lists ``title``."""
        t_low = (title or "").lower()
        adjacent: list[str] = []
        for fam in self._families.values():
            sen_low = [s.lower() for s in fam.seniority]
            if t_low not in sen_low:
                continue
            for canon in TITLE_CANON:
                if canon.lower() != t_low and canon.lower() in sen_low:
                    adjacent.append(canon)
        return _dedupe(adjacent)

    def seniority_levels(self) -> list[str]:
        """Union of every family's seniority levels, first-seen order."""
        levels: list[str] = []
        for fam in self._families.values():
            levels.extend(fam.seniority)
        return _dedupe(levels)

    def locations(self) -> list[str]:
        """Tier names + cities from location-preferences.yaml (plus per-family)."""
        locs: list[str] = []
        for tier in self._location_tiers.values():
            if isinstance(tier, dict):
                locs.append(str(tier.get("name", "")))
                locs.extend(str(c) for c in tier.get("cities", []) or [])
        for fam in self._families.values():
            locs.extend(fam.locations)
        return _dedupe(locs)

    def target_companies(self) -> list[str]:
        """Company names from target-companies.yaml."""
        return list(self._companies)

    def source_files(self) -> list[Path]:
        """Config files actually read, in load order."""
        return list(self._source_files)


def _load_yaml(path: Path):
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
