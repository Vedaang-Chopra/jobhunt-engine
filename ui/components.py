"""Shared page chrome + reusable UI components.

``page_shell`` renders the branded sidebar (icons, active-page highlight),
a topbar, and the content column. Components here are thin wrappers so pages
stay declarative.
"""

from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui
from nicegui.ui import navigate as _navigate

try:  # NiceGUI >= 3.0: window_open lives on nicegui.ui
    from nicegui.ui import window_open  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - NiceGUI 3.x has no window_open


    def window_open(url: str) -> None:
        """Open ``url`` in a new browser tab (client-side)."""
        _navigate.to(url, new_tab=True)

import ui.server as server_ctl
from ui.theme import TITLE, apply_theme

# (label, path, material icon)
# Spec 003 seven-area IA + LinkedIn Posts. Applications sits at the BOTTOM:
# it is being rebuilt around an Outlook-email tracking agent, so discovery
# surfaces (Today/Jobs) stay up top and manual tracking stays out of the way.
PAGES: list[tuple[str, str, str]] = [
    ("Today", "/today", "today"),
    ("Jobs", "/jobs", "work"),
    ("Job Search", "/job-search", "search"),
    ("LinkedIn Posts", "/linkedin-posts", "rss_feed"),
    ("Network", "/network", "connect_without_contact"),
    ("Profile", "/profile", "person"),
    ("Resume", "/resume", "description"),
    ("Insights", "/insights", "insights"),
    ("Operations", "/operations", "precision_manufacturing"),
    ("Runs", "/runs", "timeline"),
    ("Applications", "/applications", "view_kanban"),
]

STATUS_BADGE_COLOR = {
    "submitted": "positive",
    "applied": "positive",
    "interview": "info",
    "offer": "positive",
    "screening": "secondary",
    "response": "secondary",
    "rejected": "negative",
    "declined": "grey-7",
    "closed": "grey-7",
    "open": "primary",
    "new": "accent",
    # Applications-board engine statuses (mirrored onto jobs.application_status)
    "queued": "accent",
    "ready_to_apply": "warning",
    "acknowledged": "secondary",
    "withdrawn": "grey-7",
}


def page_shell(title: str, subtitle: str = "") -> None:
    """Common page shell: theme + landmarks + responsive nav + content column.

    Emits a skip link as the first focusable element, a persistent desktop
    sidebar (hidden below 1024px), a mobile top-bar menu button + drawer
    (visible only below 1024px), and wraps page content in a ``<main>``
    landmark with a single semantic ``<h1>``.
    """
    apply_theme()
    # The NiceGUI page content container (.nicegui-content) becomes the
    # <main> landmark. The active-nav highlight script below already proves
    # deferred body scripts execute client-side, so we tag the landmark in a
    # second deferred script (setTimeout covers NiceGUI's post-ws mount).
    ui.add_body_html(
        "<script>(function poll(){"
        "var c=document.querySelector('.nicegui-content');"
        "if(c){if(c.id!=='main-content'){c.setAttribute('id','main-content');"
        "c.setAttribute('role','main');}return;}"
        "setTimeout(poll,150);})();</script>"
    )
    # Skip link must be the first focusable element on the page.
    ui.link("Skip to content", "#main-content").classes("jh-skip-link")

    with ui.left_drawer(bordered=True).classes(
            "jh-sidebar jh-desktop-nav bg-dark") \
            .style("display: flex; flex-direction: column; overflow-y: auto"):
        with ui.link(target="/").classes("jh-nav-link q-my-md"):
            ui.icon("rocket_launch").classes("text-primary text-h6")
            ui.label(TITLE).classes("text-subtitle1 text-weight-bold")
        with ui.element("nav").props('aria-label="Primary navigation"') \
                .classes("w-full"):
            for name, target, icon in PAGES[1:]:
                link = ui.link(target=target).classes("jh-nav-link")
                with link:
                    ui.icon(icon)
                    ui.label(name)
        # Highlight the active nav entry client-side after render.
        ui.add_body_html(
            "<script>setTimeout(function(){"
            "var p=location.pathname;"
            "document.querySelectorAll('.jh-nav-link').forEach(function(a){"
            "if(a.getAttribute('href')===p)a.classList.add('active');});},50);"
            "</script>"
        )
        ui.space()
        server_controls()

    # Mobile nav: visible trigger below 1024px; all PAGES links reachable.
    # NiceGUI drawers only support left/right sides, so the below-1024px
    # panel is an expansion (spec allows either) toggled by the menu button.
    mobile_nav: ui.expansion
    with ui.expansion("Menu", icon="menu").classes("jh-mobile-nav w-full") \
            as mobile_nav:
        with ui.element("nav").props('aria-label="Mobile navigation"') \
                .classes("w-full"):
            for name, target, icon in PAGES:
                link = ui.link(target=target).classes("jh-nav-link")
                with link:
                    ui.icon(icon)
                    ui.label(name)
        mobile_nav.close()
        ui.button(
            icon="menu",
            on_click=lambda: (
                mobile_nav.close() if mobile_nav.value else mobile_nav.open()),
        ).props("flat round dense").props('aria-label="Open navigation"')

    heading = ui.label(title).classes(
        "page-h1 text-h4 text-weight-bold jh-section-title")
    heading.tag = "h1"  # semantic single h1 per page
    if subtitle:
        ui.label(subtitle).classes("text-body2 text-grey-6")


def server_controls() -> None:
    """Topbar Start / Stop / Restart buttons + live status pill.

    Stop/Restart kill this web app's own process; a detached helper relaunches
    it, so we warn the user and poll until the port comes back up.
    """
    start_btn: ui.button
    restart_btn: ui.button
    stop_btn: ui.button

    def _refresh() -> None:
        if status_icon.is_deleted or status_label.is_deleted:
            return  # page/client gone; stop touching dead elements
        running = server_ctl.is_running()
        if running:
            status_icon.props('name="circle" color="positive"').style(
                "font-size: 10px; margin-top: 2px")
            status_label.set_text(f"Server running :{server_ctl.PORT}")
        else:
            status_icon.props('name="circle" color="negative"').style(
                "font-size: 10px; margin-top: 2px")
            status_label.set_text("Server stopped")
        (start_btn.enable() if not running else start_btn.disable())
        (stop_btn.enable() if running else stop_btn.disable())
        (restart_btn.enable() if running else restart_btn.disable())

    def _act(action: str) -> None:
        getattr(server_ctl, action)()
        if action == "stop":
            ui.notify("Stopping server…", type="warning")
        else:
            ui.notify("Server will come back shortly; page auto-refreshes.",
                      type="info")
            _wait_and_reload()
        ui.timer(0.5, _refresh, once=True)

    def _wait_and_reload(delay_s: float = 1.5, attempts: int = 25) -> None:
        """Poll the port after a start/restart; reload once it answers."""
        import asyncio
        import time

        async def _poll() -> None:
            await asyncio.sleep(delay_s)
            for _ in range(attempts):
                if server_ctl.is_running():
                    await asyncio.sleep(2.0)  # let the new process settle
                    ui.navigate.reload()
                    return
                await asyncio.sleep(1.0)
            ui.notify("Server did not come back — check /tmp/jobhunt-ui.log",
                      type="negative")

        asyncio.create_task(_poll())

    with ui.card().classes("jh-card jh-server-pill w-full q-py-sm q-px-md") \
            .style("margin-bottom: 12px"):
        with ui.row().classes("w-full items-center q-gutter-xs no-wrap") \
                .style("flex-wrap: wrap"):
            status_icon = ui.icon("circle").style(
                "font-size: 10px; margin-top: 2px")
            status_label = ui.label("checking…") \
                .classes("text-caption text-grey-6")
        with ui.row().classes("w-full justify-between q-mt-xs no-wrap"):
            start_btn = ui.button(icon="play_arrow", on_click=lambda: _act("start")) \
                .props("dense flat positive").props('aria-label="Start server"') \
                .tooltip("Start server")
            restart_btn = ui.button(icon="restart_alt", on_click=lambda: _act("restart")) \
                .props("dense flat").props('aria-label="Restart server (auto-refresh)"') \
                .tooltip("Restart server (auto-refresh)")
            stop_btn = ui.button(icon="stop", on_click=lambda: _act("stop")) \
                .props("dense flat negative").props('aria-label="Stop server"') \
                .tooltip("Stop server")
    ui.timer(3.0, _refresh)
    _refresh()


def kpi_card(value, label: str, icon: str = "", color: str = "primary") -> None:
    """Styled KPI stat card."""
    with ui.card().classes("jh-card jh-kpi items-start q-pa-md"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(str(value)).classes("jh-kpi-value")
            if icon:
                ui.icon(icon).classes(f"text-{color} text-h5 opacity-70")
        ui.label(label).classes("jh-kpi-label")


def empty_state(message: str, icon: str = "inbox") -> None:
    """Accessible empty-state placeholder."""
    with ui.column().classes("jh-empty w-full items-center q-py-lg"):
        ui.icon(icon).classes("text-h4 text-grey-7")
        ui.label(message).classes("text-subtitle1 text-grey-6")


def section_card(title: str = "", description: str = ""):
    """Open a styled section card; use as ``with section_card(...)``."""
    card = ui.card().classes("jh-card w-full q-pa-lg")
    with card:
        if title:
            ui.label(title).classes("text-h5 text-weight-bold jh-section-title")
        if description:
            ui.label(description).classes("text-caption text-grey-6 q-mb-sm")
    return _CardContext(card)


class _CardContext:
    """Re-enterable wrapper so callers can `with` a pre-built card."""

    def __init__(self, element: ui.element) -> None:
        self.element = element

    def __enter__(self):
        self.element.__enter__()
        return self.element

    def __exit__(self, *exc):
        return self.element.__exit__(*exc)


def status_badge(status: str) -> None:
    """Colored badge keyed on known status vocabulary; neutral fallback."""
    s = str(status or "").strip().lower()
    color = STATUS_BADGE_COLOR.get(s, "grey-6")
    ui.badge((status or "—").strip() or "—", color=color).props(
        "outline dense").classes("jh-badge")


def table_columns(names: list[str], sortable: bool = True) -> list[dict]:
    """Build NiceGUI column defs from field names."""
    return [
        {
            "name": c,
            "label": c.replace("_", " ").title(),
            "field": c,
            "align": "left",
            "sortable": sortable,
        }
        for c in names
    ]


def link_row(label: str, url: str) -> None:
    """One labeled, clickable provenance link (opens in a new tab)."""
    with ui.row().classes("w-full items-start q-py-xs no-wrap"):
        ui.label(label).classes("text-caption text-grey-6 q-mr-md").style(
            "min-width: 180px")
        with ui.row().classes("items-center q-gutter-xs no-wrap"):
            ui.link(url, url, new_tab=True).classes("text-body2")
            ui.button(
                icon="open_in_new",
                on_click=lambda _, u=url: window_open(u),
            ).props("flat round dense size=sm").tooltip("Open in new tab")


def links_section(record_or_links) -> None:
    """Render every clickable source link found on a record (or given pairs).

    Accepts either a dict-like record (URL-bearing fields auto-detected via
    ``data_layer.job_links``-style scanning) or prebuilt (label, url) pairs.
    Renders nothing when no links exist.
    """
    if isinstance(record_or_links, dict):
        pairs = [
            (label, str(value or "").strip())
            for label, value in record_or_links.items()
            if str(value or "").strip().lower().startswith(("http://", "https://"))
        ]
    else:
        pairs = [(str(label), str(url)) for label, url in record_or_links]
    if not pairs:
        return
    with ui.expansion(f"Links ({len(pairs)})", icon="link").classes(
            "w-full").props("header-class='text-primary'"):
        for label, url in pairs:
            link_row(label, url)


def confirm_dialog(
    title: str,
    body: str,
    danger: bool = False,
    confirm_label: str = "Confirm",
    on_confirm: "callable | None" = None,
):
    """Build a confirmation dialog and return it; the caller opens it.

    Usage::

        dialog = confirm_dialog("Delete view", "…", danger=True,
                                confirm_label="Delete view 'X'",
                                on_confirm=do_delete)
        dialog.open()

    Escape closes the dialog (Quasar QDialog default: non-persistent, so
    ESC and outside-click both dismiss). When ``danger=True`` the Cancel
    button is placed first so Quasar's default initial focus lands on the
    safe action rather than the destructive one. Pass before/after values
    directly inside ``body`` text when the caller wants a diff preview.
    """
    dialog = ui.dialog()

    def _confirm() -> None:
        if on_confirm is not None:
            on_confirm()
        dialog.close()

    with dialog, ui.card().classes("jh-card"):
        ui.label(title).classes("text-h6 text-weight-bold jh-section-title")
        ui.label(body).classes("text-body2")
        with ui.row().classes("w-full justify-end q-gutter-sm q-mt-md"):
            if danger:  # cancel first -> receives default focus
                ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(confirm_label, on_click=_confirm).props(
                "negative" if danger else "primary")
            if not danger:
                ui.button("Cancel", on_click=dialog.close).props("flat")
    return dialog


def kpi_grid(
    items: list[tuple[str, str, str, str]],
    links: "list[str | None] | None" = None,
) -> None:
    """Responsive KPI grid replacing the old non-wrapping KPI row.

    Each item is ``(value, label, icon, color)`` — same order as
    :func:`kpi_card`. Wrapping/reflow is handled by ``.jh-kpi-grid`` CSS.
    ``links`` (optional) gives one internal href per card; a non-empty
    entry makes that whole card a hyperlink (home-page KPIs jump to the
    workspace they summarize).
    """
    with ui.element("div").classes("jh-kpi-grid"):
        for i, (value, label, icon, color) in enumerate(items):
            href = links[i] if links and i < len(links) and links[i] else None
            if href:
                with ui.link(target=href).classes("jh-kpi-link"):
                    kpi_card(value, label, icon=icon, color=color)
            else:
                kpi_card(value, label, icon=icon, color=color)


def page_timer(interval: float, callback) -> "ui.timer":
    """``ui.timer`` that deletes itself when the page client disconnects.

    NiceGUI 3.x keeps a repeating timer's asyncio task alive after the client
    that owns it disconnects; every subsequent tick then raises
    ``RuntimeError: The parent slot of the element has been deleted`` from
    ``Timer._get_context()`` BEFORE the callback's own ``is_deleted`` guard
    can run (the guard lives inside the callback). Deleting the timer on
    client disconnect cancels the task at the source.
    """
    timer = ui.timer(interval, callback)
    try:
        client = ui.context.client
    except RuntimeError:  # outside a page context (tests)
        return timer

    def _cleanup() -> None:
        if not timer.is_deleted:
            timer.delete()

    client.on_disconnect(_cleanup)
    return timer


@contextmanager
def filter_bar():
    """Open a wrapping filter bar: ``with filter_bar(): …`` controls."""
    with ui.element("div").classes("jh-filter-bar"):
        yield


@contextmanager
def table_wrap():
    """Contain wide tables inside their card: page never overflows."""
    with ui.element("div").classes("jh-table-wrap"):
        yield
