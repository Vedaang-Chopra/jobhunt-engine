"""Spec 003 Phase 2 safety tests for the /profile surface.

Smoke-imports ``ui.pages_profile`` with NiceGUI off (no server), asserts
the render entry points are importable, and pins the ``make_save_handler``
confirm-param contract that keeps old unit tests valid while the page wires
a real confirmation flow with diff preview.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_pages_profile_imports_without_nicegui_server():
    """Module import works with NiceGUI off (plain import, no server)."""
    import importlib

    mod = importlib.import_module("ui.pages_profile")
    assert mod is not None


def test_render_entry_points_importable():
    from ui.pages_profile import render_profile, render_upload_card  # noqa: F401

    assert callable(render_profile)
    assert callable(render_upload_card)


def test_make_save_handler_confirm_param_contract():
    """confirm defaults to None (write-direct); original_text optional."""
    from ui.pages_profile import make_save_handler

    sig = inspect.signature(make_save_handler)
    assert "confirm" in sig.parameters
    assert sig.parameters["confirm"].default is None
    # Backward-compatible injection kwargs preserved.
    for name in ("notify", "write", "base_dir"):
        assert name in sig.parameters
    assert "original_text" in sig.parameters


def test_confirm_dialog_helper_available_for_page_use():
    """The page consumes the shared confirm_dialog + state primitives."""
    from ui.components import confirm_dialog  # noqa: F401
    from ui.states import ViewState, state_view  # noqa: F401
    from ui.data import clear_load_issues, get_load_issues  # noqa: F401

    assert ViewState.PARTIAL.value == "partial"
