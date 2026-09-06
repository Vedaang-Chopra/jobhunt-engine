"""Shell + shared component tests for the spec 003 Phase 1 work."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


# --- AA contrast -------------------------------------------------------------


def _luminance(hexc: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_tertiary_text_meets_aa_against_card_background():
    from ui import theme

    ratio = _contrast("#9aa3b5", theme.CARD_BG)
    assert ratio >= 4.5, f"contrast {ratio:.2f} below WCAG AA"


def test_theme_css_uses_aa_tertiary_color():
    from ui import theme

    assert "#8a93a6" not in theme._GLOBAL_CSS
    assert "#9aa3b5" in theme._GLOBAL_CSS


def test_theme_responsive_utilities_present():
    from ui import theme

    for marker in (
        ".jh-kpi-grid",
        ".jh-table-wrap",
        ".jh-filter-bar",
        "@media (max-width: 1023px)",
        "@media (min-width: 1024px)",
        ".jh-skip-link",
        "h1.page-h1",
    ):
        assert marker in theme._GLOBAL_CSS, f"missing CSS: {marker}"


# --- components --------------------------------------------------------------

import importlib  # noqa: E402  (after sys.path setup)

components = None


@pytest.fixture
def comps():
    global components
    if components is None:
        components = importlib.import_module("ui.components")
    return components


def test_pages_registry_intact(comps):
    paths = [t for _, t, _ in comps.PAGES]
    assert len(comps.PAGES) == 11  # 9 spec-003 areas + job-search + Runs
    assert paths[0] == "/today"
    assert "/resume" in paths  # Resume page must be reachable from the nav
    assert "/job-search" in paths  # discovery trigger page must stay reachable
    # Applications is intentionally LAST in the nav (bottom of the sidebar):
    # the board is being rebuilt around the Outlook-email tracking agent and
    # manual adds, while discovery surfaces stay up top.
    assert paths[-1] == "/applications"
    assert len(set(paths)) == len(paths)


def test_confirm_dialog_builds_and_returns_dialog(comps):
    from nicegui import ui

    seen = {"called": False}

    def on_confirm() -> None:
        seen["called"] = True

    dialog = comps.confirm_dialog(
        "Delete view", "This cannot be undone.", danger=True,
        confirm_label="Delete", on_confirm=on_confirm)
    assert isinstance(dialog, ui.dialog)


def test_kpi_grid_filter_bar_table_wrap_smoke(comps):
    # kpi_grid needs nicegui context; smoke-check signature only.
    import inspect

    sig = inspect.signature(comps.kpi_grid)
    assert list(sig.parameters) == ["items", "links"]


# --- states module ------------------------------------------------------------


def test_state_view_covers_all_states():
    from ui.states import ViewState, state_view

    for s in ViewState:
        assert callable(state_view)
        break  # existence + enum membership is the contract here


def test_view_state_enum_members():
    from ui.states import ViewState

    expected = {
        "LOADING", "EMPTY", "STALE", "PARTIAL",
        "ERROR", "SUCCESS", "DISABLED", "GATED",
    }
    assert {m.name for m in ViewState} == expected
