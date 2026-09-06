"""Guard: run outputs must live under the data root, never the repo root.

Root cause this file exists: sweeps, ops health, digests and apply runs all
wrote into ``<repo>/execution_results/`` — a repo-root dump with personal
data (fill plans contain application answers). The canonical location is
``<data_root>/execution_results/`` (registered in config_lib.PATHS). Any
regression is a privacy leak into the public engine repo.

The rules enforced here:
  1. No script under ``scripts/`` and no module under ``ui/`` may construct
     a repo-root ``execution_results`` path (REPO / "execution_results").
  2. config_lib must register the canonical run-output dirs.
  3. A repo-root ``execution_results/`` or ``tracking/`` directory must not
     exist at test time (it would mean someone dumped there again).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import config_lib  # noqa: E402

# Repo-root relative path patterns that are FORBIDDEN as output targets.
_REPO_ROOT_DUMP_RE = re.compile(
    r"""REPO_ROOT?\s*/\s*["']execution_results["']"""
    r"""|REPO\s*/\s*["']execution_results["']"""
    r"""|os\.path\.join\(\s*ROOT\s*,\s*["']execution_results["']"""
)

REQUIRED_PATH_KEYS = (
    "execution_results_dir",
    "reviews_dir",
    "digests_dir",
    "ops_dir",
    "linkedin_posts_dir",
    "cleanup_reports_dir",
    "apply_runs_dir",
)


def test_config_lib_registers_run_output_dirs():
    for key in REQUIRED_PATH_KEYS:
        p = config_lib.path(key)
        assert str(config_lib.data_root()) in str(p), f"{key} not under data_root: {p}"


def test_no_script_writes_to_repo_root_execution_results():
    offenders: list[str] = []
    for base in ("scripts", "ui"):
        for py in (REPO_ROOT / base).rglob("*.py"):
            if "legacy" in py.parts:
                continue  # legacy scripts are frozen, not executed by crons
            text = py.read_text(encoding="utf-8", errors="replace")
            # strip comments and docstrings crudely: enough for a guard
            code = "\n".join(
                ln for ln in text.splitlines()
                if not ln.strip().startswith("#")
            )
            for m in _REPO_ROOT_DUMP_RE.finditer(code):
                offenders.append(f"{py.relative_to(REPO_ROOT)}: ...{m.group(0)}...")
    assert not offenders, (
        "Repo-root execution_results dump detected (move to config_lib.path(...)):\n"
        + "\n".join(offenders)
    )


def test_no_repo_root_dump_directories_exist():
    """A repo-root execution_results/ or tracking/ dir means a regression."""
    for name in ("execution_results", "tracking", "profile_info"):
        assert not (REPO_ROOT / name).exists(), (
            f"{REPO_ROOT / name} exists — run outputs/personal data leaked to "
            "the repo root. Migrate it into <data_root> and delete it."
        )


def test_repo_root_has_no_stray_working_files():
    """Random one-off files at the repo root are a provenance hazard."""
    allowed = {
        ".gitignore", "AGENTS.md", "CONVENTIONS.md", "CRON_MANIFEST.md",
        "Dockerfile", "README.md", "config.example.yaml",
        "docker-compose.yml", "pyproject.toml", "service.sh", "start.sh",
        "stop.sh",
        # pointer file resolving the data root (gitignored, never committed)
        "config.yaml",
        # rolling session state the user maintains at the root (tracked)
        "session_state.md",
    }
    allowed_prefixes = ("setup.cfg", "poetry.lock", "uv.lock", "requirements")
    strays: list[str] = []
    for entry in REPO_ROOT.iterdir():
        if entry.is_file() and not entry.name.startswith("."):
            if entry.name in allowed:
                continue
            if any(entry.name.startswith(p) for p in allowed_prefixes):
                continue
            strays.append(entry.name)
    assert not strays, (
        f"Stray files at repo root: {strays}. Move into docs/, scripts/ or "
        "archive/, or extend the allowlist deliberately."
    )
