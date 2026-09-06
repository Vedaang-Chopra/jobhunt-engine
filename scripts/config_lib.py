"""Layer 5 utility: data-root and config resolution for the job-hunt workspace.

Resolution order for ``data_root()``:
1. ``$JOBHUNT_HOME`` environment variable (explicit override).
2. ``./config.yaml`` pointer file next to this repo root containing a
   ``data_root:`` key.
3. Legacy repo-local default (the directory containing this repository),
   identical to the historical behavior.

``load_config()`` returns a dict from ``<data_root>/config.yaml``; missing
files yield ``{}`` and malformed YAML logs a warning instead of raising.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
POINTER_FILE = REPO_ROOT / "config.yaml"


def data_root() -> Path:
    """Resolve the data root directory.

    Order: $JOBHUNT_HOME env var -> ./config.yaml pointer file ->
    repo-local ``jobhunt-data/`` (created on demand).

    The final fallback is the repo-local ``jobhunt-data`` dir, NOT the repo
    root: run outputs and personal data must never land at the repo root
    (that leaked personal files into the public engine tree once — guarded
    by tests/test_output_hygiene.py). bootstrap.sh creates this layout.
    """
    env_root = os.environ.get("JOBHUNT_HOME")
    if env_root:
        return Path(env_root).expanduser()

    if POINTER_FILE.is_file():
        try:
            import yaml

            with POINTER_FILE.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:  # pragma: no cover - malformed pointer file
            logger.warning("Could not parse %s: %s", POINTER_FILE, exc)
            data = None
        if isinstance(data, dict):
            pointer = data.get("data_root")
            if isinstance(pointer, str) and pointer.strip():
                return Path(pointer).expanduser()

    return REPO_ROOT / "jobhunt-data"


def load_config() -> Dict[str, Any]:
    """Load ``<data_root>/config.yaml``.

    Returns {} when the file is absent; malformed YAML logs a warning and
    returns {} instead of raising.
    """
    config_path = data_root() / "config.yaml"
    if not config_path.is_file():
        return {}
    try:
        import yaml

        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Malformed YAML in %s (%s); using empty config", config_path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def llm_config() -> list[dict]:
    """Canonical LLM provider chain, honoring per-provider ``priority``.

    Config shape (``<data_root>/config.yaml``)::

        llm:
          providers:
            openrouter: {api_key: ..., base_url: ..., model: ..., priority: 1}
            nvidia:     {api_key: ..., base_url: ..., model: ..., priority: 2}
            custom:     {base_url: ..., model: ..., priority: 3}

    Small-model chain: **OpenRouter free models primary -> NVIDIA Build
    nemotron-super backup** (openrouter first, then nvidia, then custom).
    Lower priority number = tried first (1 = highest precedence). Providers
    without a key are skipped. Providers without an explicit priority keep
    their built-in relative order — currently **openrouter first, then
    nvidia, then custom**. Ties resolve the same way.

    Single source of truth: tailor_from_jd, web_nav_agent._llm_config_fallback,
    resume_agent.common, and search_strategy/llm.py all consume this function.
    Built-in per-provider model fallbacks live here and are overridden by any
    explicit ``model`` in config.
    """
    providers = ((load_config().get("llm") or {}).get("providers") or {})
    entries = []
    for default_rank, name in enumerate(("openrouter", "nvidia", "custom")):
        node = providers.get(name) or {}
        if not node.get("api_key"):
            continue
        raw_priority = str(node.get("priority") or "").strip()
        try:
            priority = int(raw_priority)
        except ValueError:
            priority = None  # unparsable -> treat as unset
        if name == "openrouter":
            defaults = {"base_url": "https://openrouter.ai/api/v1",
                        "models": [node.get("model")
                                   or "meta-llama/llama-3.3-70b-instruct:free"]}
        elif name == "nvidia":
            defaults = {"base_url": "https://integrate.api.nvidia.com/v1",
                        "models": [node.get("model") or "openai/gpt-oss-120b",
                                   "meta/llama-3.3-70b-instruct",
                                   "meta/llama-3.1-8b-instruct"]}
        else:
            defaults = {"base_url": node.get("base_url") or "",
                        "models": ([node["model"]] if node.get("model") else [])}
        if not defaults["base_url"] or not defaults["models"]:
            continue  # custom provider missing endpoint/model -> unusable
        entries.append({
            "name": name,
            "base_url": defaults["base_url"],
            "key": node["api_key"],
            "models": defaults["models"],
            "priority": priority if priority is not None else 100 + default_rank,
        })
    # Stable sort keeps built-in order for equal/unset priorities.
    return sorted(entries, key=lambda e: e["priority"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(data_root())
    print(load_config())
    for name in sorted(PATHS):
        print(f"{name:28} {PATHS[name]}")


# ---------------------------------------------------------------------------
# Central path registry — the ONLY place canonical data paths are defined.
#
# Every script/UI module must import paths from here instead of building
# ``REPO / "tracking" ...`` or ``data_root() / "..."`` joins inline. This
# guarantees a single data root (see ``data_root()``) and one definition per
# file. Add new canonical files here, never at the call site.
# ---------------------------------------------------------------------------

def _p(*parts: str) -> Path:
    return data_root().joinpath(*parts)


PATHS: Dict[str, Path] = {
    # tracking
    "jobs_csv":             _p("tracking", "jobs", "jobs.csv"),
    "applications_csv":     _p("tracking", "applications", "applications.csv"),
    "contacts_csv":         _p("tracking", "contacts", "contacts.csv"),
    "companies_csv":        _p("tracking", "companies", "companies.csv"),
    "companies_registry":   _p("tracking", "companies", "companies_registry.csv"),
    "hiring_posts_csv":     _p("tracking", "hiring_posts", "hiring_posts.csv"),
    "search_runs_csv":      _p("tracking", "search_runs", "search_runs.csv"),
    "people_sweep_csv":     _p("tracking", "people_sweeps", "people_sweep.csv"),
    "connection_requests":  _p("tracking", "messages", "connection_requests.csv"),
    "job_descriptions_dir": _p("tracking", "job_descriptions"),
    "jd_active_dir":        _p("tracking", "job_descriptions", "active"),
    "tracking_dir":         _p("tracking"),
    # job_research
    "job_research_dir":     _p("job_research"),
    "jd_features_csv":      _p("job_research", "data", "jd_features.csv"),
    "scored_jobs_json":     _p("job_research", "data", "scored_jobs_v2.json"),
    "role_views_dir":       _p("job_research", "roles"),
    "wellfound_crawler":    _p("job_research", "scripts", "wellfound_crawler.py"),
    # profile / resume / messaging
    "profile_info_dir":     _p("profile_info"),
    "fact_bank_yaml":       _p("profile_info", "resume_fact_bank.yaml"),
    "resume_custom_dir":    _p("resume_custom"),
    "keyword_bank_md":      _p("resume_custom", "rules", "KEYWORD_BANK.md"),
    "evidence_library_md":  _p("resume_custom", "evidence", "EVIDENCE_LIBRARY.md"),
    "role_families_md":     _p("resume_custom", "rules", "ROLE_FAMILIES.md"),
    "generation_rules_md":  _p("resume_custom", "rules", "RESUME_GENERATION_RULES.md"),
    "bullet_patterns_md":   _p("resume_custom", "rules", "BULLET_PATTERNS.md"),
    "base_variants_dir":    _p("resume_custom", "base_variants"),
    "messaging_dir":        _p("messaging"),
    "linkedin_dir":         _p("linkedin"),
    "applications_data_dir": _p("applications"),
    # run outputs (reports, digests, sweep payloads, alerts) — ALL under the
    # data root, never the repo root. Run outputs are personal data.
    "execution_results_dir": _p("execution_results"),
    "reviews_dir":           _p("execution_results", "reviews"),
    "digests_dir":           _p("execution_results", "digests"),
    "ops_dir":               _p("execution_results", "ops"),
    "linkedin_posts_dir":    _p("execution_results", "linkedin_posts"),
    "cleanup_reports_dir":   _p("execution_results", "cleanup_reports"),
    "apply_runs_dir":        _p("execution_results", "apply_runs"),
    "ats_report_json":       _p("job_research", "data", "ats_report.json"),
}


def path(name: str) -> Path:
    """Return a registered canonical path by name. Raises on unknown names."""
    try:
        return PATHS[name]
    except KeyError:
        raise KeyError(
            f"Unknown path '{name}'. Register it in config_lib.PATHS instead of "
            f"building it at the call site."
        ) from None


# ---------------------------------------------------------------------------
# Candidate identity — private data, never hardcode in code.
#
# Source of truth: an ``identity:`` block in <data_root>/config.yaml
# (gitignored). Falls back to profile_info/profile.md markers when the block
# is absent. Public repo exports must contain NO hardcoded personal values —
# if you find one, move it here.
# ---------------------------------------------------------------------------

_DEFAULT_IDENTITY: Dict[str, str] = {
    "full_name": "",
    "first_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "school": "",
    "degree": "",
    "headline_background": "",
    "signature_name": "",
}

_IDENTITY_CACHE: Dict[str, Dict[str, str]] = {}


def identity() -> Dict[str, str]:
    """Return the candidate identity dict (cached per data_root).

    Reads the ``identity:`` block from <data_root>/config.yaml. Every key is
    optional; unknown keys are passed through. Missing values resolve to "".
    """
    root = str(data_root())
    if root in _IDENTITY_CACHE:
        return _IDENTITY_CACHE[root]
    ident = dict(_DEFAULT_IDENTITY)
    try:
        block = (load_config() or {}).get("identity") or {}
        if isinstance(block, dict):
            for k, v in block.items():
                if isinstance(v, str):
                    ident[k] = v.strip()
    except Exception:
        pass
    _IDENTITY_CACHE[root] = ident
    return ident


def identity_line(key: str) -> str:
    """One identity value by key, '' when unset."""
    return identity().get(key, "")
