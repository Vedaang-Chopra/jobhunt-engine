"""State system + shared shell primitives (spec 003 §6.1, §7).

``state_view`` renders one of the eight canonical view states with the right
semantic (icon, color, detail lines). Pure render helper — unit-testable
without a running server via the NiceGUI-off import pattern used across
tests/ui.
"""

from __future__ import annotations

from enum import Enum

from nicegui import ui


class ViewState(str, Enum):
    LOADING = "loading"
    EMPTY = "empty"
    STALE = "stale"
    PARTIAL = "partial"
    ERROR = "error"
    SUCCESS = "success"
    DISABLED = "disabled"
    GATED = "gated"


# state -> (badge color, icon)
_STATE_STYLE: dict[ViewState, tuple[str, str]] = {
    ViewState.LOADING: ("info", "hourglass_top"),
    ViewState.EMPTY: ("grey-7", "inbox"),
    ViewState.STALE: ("warning", "schedule"),
    ViewState.PARTIAL: ("warning", "content_cut"),
    ViewState.ERROR: ("negative", "error_outline"),
    ViewState.SUCCESS: ("positive", "check_circle"),
    ViewState.DISABLED: ("grey-7", "block"),
    ViewState.GATED: ("info", "lock"),
}


def state_view(
    state: ViewState,
    message: str,
    icon: str = "",
    detail: str = "",
    recovery_hint: str = "",
) -> None:
    """Render one canonical view-state block.

    ``detail`` carries diagnostics (failed path for ERROR, last-refresh
    timestamp for STALE, failed-source list for PARTIAL). ``recovery_hint``
    is shown for GATED/ERROR as the suggested next step. The default
    ``icon`` argument only applies to EMPTY-style neutral rendering; each
    state otherwise picks its own semantic icon unless overridden here.
    """
    color, state_icon = _STATE_STYLE.get(state, ("grey-7", "inbox"))
    with ui.column().classes("jh-empty w-full items-center q-py-lg"):
        badge_label = state.value.upper()
        ui.badge(badge_label, color=color).props("outline dense").classes(
            "jh-badge")
        ui.icon(icon or state_icon).classes("text-h4 text-grey-7 q-mt-sm")
        ui.label(message).classes("text-subtitle1 text-grey-6 text-center")
        if detail:
            ui.label(detail).classes(
                "text-caption text-grey-6 text-center").style(
                "white-space: pre-wrap; user-select: text")
        if recovery_hint and state in (ViewState.GATED, ViewState.ERROR):
            ui.label(f"Next step: {recovery_hint}").classes(
                "text-caption text-info text-center")


def unavailable_card(title: str, explanation: str, pointer: str = "") -> None:
    """Honest 'this workflow is not UI-executable' card (spec §6.2)."""
    with ui.card().classes("jh-card w-full q-pa-md"):
        with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
            ui.icon("lock_outline").classes("text-grey-6")
            ui.label(title).classes("text-subtitle1 text-weight-bold")
        ui.label(explanation).classes("text-body2 text-grey-6 q-mt-xs")
        if pointer:
            ui.label(pointer).classes("text-caption text-grey-6")
