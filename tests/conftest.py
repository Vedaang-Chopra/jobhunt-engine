"""Suite-wide pytest configuration.

Root cause this file exists: ``scripts/config_lib.data_root()`` honors
``$JOBHUNT_HOME`` first. Some tests deliberately point it at temp dirs and not
all of them restore the variable, so ambient env state made results depend on
test order. The autouse fixture below pins ``JOBHUNT_HOME`` to the canonical
repo-local ``jobhunt-data`` dir (the same place humans resolve to when running
the suite in-repo via the config.yaml pointer) and restores the previous
environment afterwards, making the suite deterministic under any ambient env
and any test order.

Opt out for a single test/module by setting::

    @pytest.mark.jobhunt_env_free  # or JOBHUNT_ENV_FREE = True module attr

Tests that need an isolated data root should keep using their own
monkeypatch.setenv inside the test body; the fixture restores whatever they
change when the test finishes.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Tests must never touch real personal data (it lives in the sibling
# jobhunt-data checkout). Pin to a repo-local scratch tree instead;
# tests create whatever fixtures they need under it.
REPO_DATA_ROOT = REPO_ROOT / "tests" / "_data_scratch"


def _opted_out(request) -> bool:
    if request.node.get_closest_marker("jobhunt_env_free") is not None:
        return True
    # Module-level escape hatch: JOBHUNT_ENV_FREE = True
    mod = getattr(request.module, "__dict__", {})
    return bool(mod.get("JOBHUNT_ENV_FREE", False))


import pytest


@pytest.fixture(autouse=True)
def _pin_jobhunt_home(request, monkeypatch):
    """Pin $JOBHUNT_HOME to the repo data root unless the test opts out."""
    original = os.environ.get("JOBHUNT_HOME")
    try:
        if not _opted_out(request):
            monkeypatch.setenv("JOBHUNT_HOME", str(REPO_DATA_ROOT))
        yield
    finally:
        # Restore exact prior state even if the test body mutated os.environ
        # directly (some suites assign os.environ["JOBHUNT_HOME"] bare).
        if original is None:
            os.environ.pop("JOBHUNT_HOME", None)
        else:
            os.environ["JOBHUNT_HOME"] = original
