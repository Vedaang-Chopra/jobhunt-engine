"""Tests for spec 003 Phase 3 IA cutover in ui/app.py.

Covers: route function presence (off-server import smoke), the permanent
redirect map, truthful KPI labels consuming data_layer.LABEL_RENAMES, and the
four-stage application board (Closed removed as a display stage).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="module")
def ui_app():
    """Import ui.app off-server (registers pages via decorators at import)."""
    pytest.importorskip("nicegui")
    import ui.app as mod

    return mod


# ---------------------------------------------------------------------------
# Import + route registry
# ---------------------------------------------------------------------------


def test_import_ui_app_off_server_smoke(ui_app):
    """Module imports cleanly and exposes the seven-area route functions."""
    for name in (
        "today", "jobs", "applications", "network",
        "operations", "insights",
    ):
        assert callable(getattr(ui_app, name, None)), f"missing route fn: {name}"


def test_build_app_rerun_is_safe(ui_app):
    """build_app() must not double-register owned routes or crash on rerun."""
    ui_app.build_app()  # second call after import-time registration


def test_redirect_map_completeness(ui_app):
    redirects = dict(ui_app.ROUTE_REDIRECTS)
    assert redirects["/"] == "/today"
    assert redirects["/queue"] == "/today"
    assert redirects["/pipeline"] == "/applications"
    assert redirects["/outreach"] == "/network"
    # No redirect collides with a distinct registered path of its own.
    assert all(old != new for old, new in redirects.items())


def test_owned_routes_cover_redirect_sources_and_targets(ui_app):
    owned = ui_app._OWNED_ROUTES
    for old, new in ui_app.ROUTE_REDIRECTS.items():
        assert old in owned
        assert new in owned


# ---------------------------------------------------------------------------
# Truthful labels (spec 003 §6.2)
# ---------------------------------------------------------------------------


def test_today_kpi_labels_use_truthful_renames(ui_app):
    from ui import data as d

    labels = ui_app.today_kpi_labels()
    assert len(labels) == 4
    # Consumes the data-layer rename map where keys match.
    assert labels[2] == d.LABEL_RENAMES["Applications Sent"]
    assert labels[3] == d.LABEL_RENAMES["Connections Pending"]
    assert "Submitted (local status)" in labels
    assert "Awaiting outreach (ledger)" in labels
    # The misleading legacy labels are gone.
    assert "Applications Sent" not in labels
    assert "Connections Pending" not in labels


def test_today_kpi_labels_fall_back_to_literals(ui_app, monkeypatch):
    """If LABEL_RENAMES lost a key, the truthful literal is still used."""
    monkeypatch.setattr(ui_app.data_layer, "LABEL_RENAMES", {})
    labels = ui_app.today_kpi_labels()
    assert labels[2] == "Submitted (local status)"
    assert labels[3] == "Awaiting outreach (ledger)"


def test_network_page_uses_rename_for_ledger_heading(ui_app):
    from ui import data as d

    assert ui_app._rename(
        "Connections Pending", "Awaiting outreach (ledger)") == \
        d.LABEL_RENAMES["Connections Pending"]


# ---------------------------------------------------------------------------
# Applications board: stage ≠ outcome
# ---------------------------------------------------------------------------


def test_application_display_stages_exclude_closed(ui_app):
    from ui import data as d

    stages = ui_app.application_stages()
    assert stages == ["Saved", "Preparing", "Applied", "Interviewing"]
    assert "Closed" not in stages
    assert set(stages) <= set(d.PIPELINE_STAGES)


def test_stage_outcome_split_feeds_board_columns():
    from ui import data as d

    # Active rows land on a stage with no outcome; terminal rows carry one.
    assert d.stage_outcome_split("submitted") == ("Applied", "")
    stage, outcome = d.stage_outcome_split("rejected")
    assert stage == "Closed" and outcome == "rejected"
