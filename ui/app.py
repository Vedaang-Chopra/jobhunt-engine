"""NiceGUI entry point for the job-hunt desktop UI.

Run with::

    .venv/bin/python -m ui.app

Pages are thin render functions over ``ui.data``; all business logic lives in
the data layer (``ui/data.py``) or in ``scripts/`` libraries.

Spec 003 Phase 3 IA cutover: seven top-level areas —
``/today``, ``/jobs``, ``/applications``, ``/network``, ``/profile``,
``/insights``, ``/operations`` — with permanent 1:1 redirects from the old
URLs (see :data:`ROUTE_REDIRECTS`).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pandas as pd
from nicegui import app, ui

from ui import data as data_layer
from ui import triggers
from ui.runs import RUNS
from ui.components import (
    PAGES,
    confirm_dialog,
    empty_state,
    filter_bar,
    kpi_grid,
    page_shell,
    page_timer,
    section_card,
    server_controls,
    status_badge,
    table_columns,
    table_wrap,
)
from ui.states import ViewState, state_view
from ui.theme import TITLE

QUEUE_SECTIONS = [
    ("fresh_jobs", "Fresh Jobs", "Discovered or refreshed within the last 3 days.", "fiber_new"),
    ("top_queue", "Top Queue", "Highest-priority open jobs (today_queue.py ranking).", "star"),
    ("needing_attention", "Needing Attention", "Stale, thin JD, or missing-data rows.", "warning_amber"),
]

#: Rows shown per queue section on /today — a preview, not the full table.
TODAY_QUEUE_PREVIEW = 12

#: "View all" target per queue section (deep-links into the right workspace).
QUEUE_SECTION_LINKS = {
    "fresh_jobs": "/jobs",
    "top_queue": "/jobs",
    "needing_attention": "/jobs",
}

JOBS_CSV = "tracking/jobs/jobs.csv"

REPO = Path(__file__).resolve().parents[1]

#: Permanent compatibility redirects (spec 003 §4.3): old bookmark -> new area.
ROUTE_REDIRECTS: dict[str, str] = {
    "/": "/today",
    "/queue": "/today",
    "/pipeline": "/applications",
    "/outreach": "/network",
}

# Routes registered directly in this module (pages + redirects). build_app()
# skips these so nothing is ever double-registered.
_OWNED_ROUTES: set[str] = {
    "/", "/today", "/jobs", "/applications", "/network",
    "/operations", "/insights", "/linkedin-posts", "/job-search",
    "/right-people",
    *ROUTE_REDIRECTS,
}


# ---------------------------------------------------------------- job search
@ui.page("/job-search")
def job_search():  # pragma: no cover - requires running server
    """One-click triggers for every discovery source (LinkedIn, career-ops,
    Wellfound, freshness)."""
    from ui.pages_job_search import render_job_search_page

    page_shell(
        "Job Search",
        "Trigger discovery sweeps per source — LinkedIn jobs & hiring posts, "
        "career portals, Wellfound — then ingest and rescore.",
    )
    render_job_search_page()


# ---------------------------------------------------------------- linkedin posts
@ui.page("/linkedin-posts")
def linkedin_posts():  # pragma: no cover - requires running server
    """Hiring-post discovery workspace: automation health, manual sweeps,
    keyword learning, and the canonical posts table."""
    from ui.pages_linkedin import render_linkedin_posts_page

    page_shell(
        "LinkedIn Posts",
        "Hiring-post discovery — 2h auto-cruncher health, on-demand feed & "
        "keyword sweeps, and every tracked post with one-click links.",
    )
    render_linkedin_posts_page()


def _frame(title: str, subtitle: str = ""):
    """Common page shell (kept for backwards compatibility)."""
    page_shell(title, subtitle)


def _rename(label: str, fallback: str) -> str:
    """Truthful display label per data-layer rename map, literal fallback."""
    return data_layer.LABEL_RENAMES.get(label, fallback)


def today_kpi_labels() -> list[str]:
    """Display labels for the /today KPI grid (spec 003 §6.2 truthful names)."""
    return [
        "Fresh Jobs",
        "Queue Depth",
        _rename("Applications Sent", "Submitted (local status)"),
        _rename("Connections Pending", "Awaiting outreach (ledger)"),
    ]


def application_stages() -> list[str]:
    """Display stages for /applications: PIPELINE_STAGES minus 'Closed'.

    Stage and outcome are separate dimensions; terminal rows surface under a
    dedicated Outcomes column via :func:`data_layer.stage_outcome_split`.
    """
    return [s for s in data_layer.PIPELINE_STAGES if s != "Closed"]


# ---------------------------------------------------------------- redirects
def _register_redirect(old_path: str, new_path: str) -> None:
    @ui.page(old_path)
    def redirect(old: str = old_path, new: str = new_path):  # pragma: no cover - requires running server
        ui.navigate.to(new)


for _old, _new in ROUTE_REDIRECTS.items():
    _register_redirect(_old, _new)


# ---------------------------------------------------------------- run health
def _run_health_strip() -> None:
    """Top-of-/today strip: freshness of jobs.csv + per-source mtimes.

    Compact by design: one status line + a collapsed expansion holding the
    raw mtimes — the home page should not open with a wall of timestamps.
    """
    freshness = data_layer.source_freshness(JOBS_CSV)
    health_rows = data_layer.data_health()
    mtimes = "\n".join(
        f"{row['path']}: last modified {row['mtime'] or 'missing'}"
        for row in health_rows
    )
    if not freshness["exists"]:
        state_view(
            ViewState.ERROR,
            f"{JOBS_CSV} is missing.",
            detail=mtimes,
            recovery_hint="run scripts/discovery_run.py to create the tracker.",
        )
        return
    age = freshness.get("age_days")
    age_txt = f" ({age:.1f} days ago)" if age is not None else ""
    detail = f"{JOBS_CSV} last refresh: {freshness['mtime']}{age_txt}\n{mtimes}"
    if freshness["stale"]:
        state_view(ViewState.STALE, "Tracking data is stale.", detail=detail)
        return
    # Healthy: one compact line; raw timestamps tucked into an expansion.
    with ui.row().classes(
            "w-full items-center q-gutter-sm q-py-xs q-px-md jh-card no-wrap") \
            .style("flex-wrap: wrap"):
        ui.icon("check_circle").classes("text-positive")
        ui.label(
            f"Tracking data is fresh — {JOBS_CSV} last refresh: "
            f"{freshness['mtime']}{age_txt}").classes("text-caption text-grey-6")
        with ui.expansion("Details", icon="info").classes("text-caption"):
            ui.label(mtimes).classes("text-caption text-grey-6").style(
                "white-space: pre-wrap; user-select: text")


# ---------------------------------------------------------------- today
@ui.page("/today")
def today():
    """Merged Today workspace: run health + truthful KPIs + queue sections."""
    page_shell("Today", "Your job hunt at a glance — work the highest-priority jobs.")

    _run_health_strip()

    labels = today_kpi_labels()
    counts = data_layer.kpi_counts()
    views = data_layer.load_queue_views()
    kpis = [
        (str(len(views["fresh_jobs"])), labels[0], "fiber_new", "accent"),
        (str(len(views["top_queue"])), labels[1], "star", "warning"),
        (str(counts["submitted"]), labels[2], "send", "positive"),
        (str(data_layer.connections_pending(data_layer.load_contacts())),
         labels[3], "person_add", "info"),
    ]
    kpi_grid(
        kpis,
        links=[
            QUEUE_SECTION_LINKS["fresh_jobs"],
            QUEUE_SECTION_LINKS["top_queue"],
            "/applications",
            "/network",
        ],
    )

    # Queue sections moved here from the former /queue page. No engine
    # trigger buttons on this workspace — those live on /operations.
    # All three sections sit side by side horizontally (responsive:
    # collapses to 1 column on narrow viewports). Each section shows only
    # the top TODAY_QUEUE_PREVIEW rows — this is a home page, not the full
    # tracker; "View all" deep-links into the filtered /jobs table.
    with ui.element("div").classes("jh-today-sections"):
        for key, heading, subtitle, icon in QUEUE_SECTIONS:
            df = views.get(key, pd.DataFrame())
            total = len(df)
            with section_card(heading, subtitle):
                if df.empty:
                    empty_state("No rows available (run scripts/today_queue.py).", icon=icon)
                    continue
                preview = df.head(TODAY_QUEUE_PREVIEW)
                cols = [c for c in ("company", "title", "fit_tier",
                                    "priority_v2", "status")
                        if c in preview.columns]
                rows = preview.replace(pd.NA, "").fillna("").to_dict("records")
                with table_wrap():
                    table = ui.table(
                        columns=table_columns(cols), rows=rows, row_key="job_id",
                        pagination={"rowsPerPage": 0},
                    ).classes("w-full").props("flat")
                    # Clickable provenance: job posting link per row, plus each
                    # referral contact's LinkedIn profile when present.
                    table.add_slot("body-cell-title", """
                        <q-td key="title" :props="props">
                          <a :href="props.row.job_url" target="_blank"
                             style="text-decoration: underline">{{ props.value }}</a>
                        </q-td>
                    """)
                    if any(str(r.get("referral_contact_urls") or "").strip() for r in rows):
                        table.add_slot("body-cell-referral_contacts", """
                            <q-td key="referral_contacts" :props="props">
                              <template v-for="(name, i) in (props.value || '').split(';').filter(s => s.trim())"
                                        :key="i">
                                <a v-if="(props.row.referral_contact_urls || '').split(';')[i]"
                                   :href="props.row.referral_contact_urls.split(';')[i]"
                                   target="_blank" style="text-decoration: underline">{{ name }}</a>
                                <span v-else>{{ name }}</span>
                                <span v-if="i < props.value.split(';').filter(s => s.trim()).length - 1">, </span>
                              </template>
                            </q-td>
                        """)
                        cols.append("referral_contacts")
                        table.columns = table_columns(cols)
                        table.update()
                # "View all" — the home page previews; /jobs holds the rest.
                view_all = QUEUE_SECTION_LINKS.get(key, "/jobs")
                with ui.row().classes("w-full justify-end q-mt-sm"):
                    ui.link(f"View all {total} →", view_all).classes(
                        "text-caption text-primary")


REVIEW_FLAG_BADGE_SLOT = """
    <q-td key="review_flag" :props="props">
      <q-badge v-if="props.value" outline dense
        :color="props.value === 'for_later' ? 'orange' : 'positive'"
        :label="props.value === 'for_later' ? 'for_later' : 'completed'" />
    </q-td>
"""


def _open_job_dialog(record: dict, on_change=None) -> None:
    """Expandable dialog showing all non-empty fields for one job.

    ``on_change`` (optional) is invoked after any successful per-job mutation
    or a completed evaluation run so callers can reload their tables; the
    dialog itself is closed by this function after mutations.
    """
    job_id = str(record.get("job_id", "") or "")
    # Two-step delete arm state (mutable cell survives button re-styling).
    arm = {"delete": False}
    eval_cell: dict = {"run_id": None}

    def _reset_delete_arm() -> None:
        if arm["delete"]:
            arm["delete"] = False
            delete_button.text = "Delete"
            delete_button.props("outline negative", remove="unelevated")

    def _finish(message: str) -> None:
        ui.notify(message, type="positive")
        _reset_delete_arm()
        if on_change:
            try:
                on_change()
            except Exception:  # noqa: BLE001 - callback must not mask the action
                pass
        dialog.close()

    def _run_action(label: str, fn) -> None:
        _reset_delete_arm()
        try:
            fn()
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        except RuntimeError as exc:  # e.g. unknown job id raised as RuntimeError
            ui.notify(str(exc), type="negative")
            return
        _finish(f"{job_id}: {label}")

    def _delete_action() -> None:
        """Two-step delete: first click arms, second click deletes."""
        if not arm["delete"]:
            arm["delete"] = True
            delete_button.text = "Confirm delete"
            delete_button.props("unelevated negative", remove="outline")
            ui.notify("Click again to permanently delete this job.",
                      type="warning")
            return
        try:
            data_layer.delete_job(job_id)
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        _finish(f"{job_id}: deleted")

    def _start_evaluation() -> None:
        _reset_delete_arm()
        try:
            eval_cell["run_id"] = RUNS.start(
                "job_evaluation",
                [sys.executable, str(REPO / "scripts" / "score_jobs_v2.py"),
                 "--job-id", job_id],
            )
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning")
            return
        eval_status.set_text("Evaluating…")

        def _poll() -> None:
            timer = eval_cell.get("timer")
            if timer is not None and getattr(timer, "is_deleted", False):
                return
            run_id = eval_cell.get("run_id")
            if not run_id:
                return
            st = RUNS.status(run_id)
            if st.get("state") == "running":
                return
            rc = st.get("returncode")
            if timer is not None and not timer.is_deleted:
                timer.delete()
            if rc == 0:
                ui.notify(
                    f"{job_id}: evaluation finished (exit 0); scores reloaded.",
                    type="positive")
                if on_change:
                    try:
                        on_change()
                    except Exception:  # noqa: BLE001
                        pass
                if not eval_status.is_deleted:
                    eval_status.set_text("Evaluation done.")
            else:
                ui.notify(
                    f"{job_id}: evaluation failed with exit code {rc}.",
                    type="negative")
                if not eval_status.is_deleted:
                    eval_status.set_text(f"Evaluation failed (exit {rc}).")
            eval_cell["run_id"] = None

        eval_cell["timer"] = ui.timer(1.0, _poll)

    with ui.dialog() as dialog, ui.card().classes("jh-card").style("min-width: min(680px, 92vw)"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(f"{record.get('company', '')} — {record.get('title', '')}").classes(
                "text-h6 text-weight-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense") \
                .props('aria-label="Close job details"').tooltip("Close (Esc)")
        # Provenance links first: posting URL, application page, etc.
        job_links = data_layer.job_links(record)
        if job_links:
            with ui.row().classes("w-full items-center q-gutter-sm no-wrap q-pb-sm"):
                for label, url in job_links:
                    ui.link(label, url, new_tab=True).props("unelevated") \
                        .classes("text-body2").tooltip(url)
        with ui.expansion("Details", icon="info").classes("w-full").props("header-class='text-primary'"):
            with ui.column().classes("w-full"):
                for field, value in data_layer.job_detail(record):
                    with ui.row().classes("w-full items-start q-py-xs"):
                        ui.label(field).classes("text-caption text-grey-6 q-mr-md").style("min-width: 180px")
                        if str(value).lower().startswith(("http://", "https://")) and " " not in value:
                            ui.link(value, value, new_tab=True).classes("text-body2")
                        else:
                            ui.label(value).classes("text-body2").style("white-space: pre-wrap")
        # Score provenance (spec 003 §6.2): where priority_v2 came from.
        raw_score = record.get("priority_v2")
        if raw_score is not None and str(raw_score).strip() not in ("", "nan", "None"):
            with ui.expansion("Score provenance", icon="insights").classes(
                    "w-full").props("header-class='text-primary'"):
                with ui.column().classes("w-full"):
                    for field, value in data_layer.score_provenance(record):
                        with ui.row().classes("w-full items-start q-py-xs"):
                            ui.label(field).classes(
                                "text-caption text-grey-6 q-mr-md").style("min-width: 180px")
                            ui.label(value).classes("text-body2")
        # Full stored job-description file (the canonical JD artifact).
        jd_text = data_layer.load_job_description(record)
        if jd_text:
            with ui.expansion("Full Job Description", icon="description").classes(
                    "w-full").props("header-class='text-primary'"):
                ui.markdown(jd_text).classes("w-full").style(
                    "max-height: 60vh; overflow-y: auto; white-space: pre-wrap")
        elif not record.get("description_file"):
            pass  # no pointer recorded — nothing to show
        else:
            with ui.expansion("Full Job Description", icon="description").classes(
                    "w-full").props("header-class='text-primary'"):
                ui.label("Description file is missing from disk "
                         f"({record.get('description_file')}).").classes("text-caption text-grey-6")
        # --- Parallel application tracking ---------------------------------
        # Applications board state for this job: mirrored status badge + stage
        # control when tracked, a one-click queue button when not.
        try:
            _app_status = data_layer.application_status_for_job(job_id)
        except (FileNotFoundError, ValueError):
            _app_status = None
        _linked_app_id = ""
        _apps_df = data_layer.load_applications()
        if not _apps_df.empty and "job_id" in _apps_df.columns:
            _hits = _apps_df[_apps_df["job_id"].fillna("").astype(str) == job_id]
            if not _hits.empty:
                _linked_app_id = str(_hits.iloc[0].get("application_id") or "")
        with ui.row().classes("w-full items-center q-gutter-sm no-wrap q-py-xs"):
            ui.label("Application tracking").classes(
                "text-caption text-grey-6").style("min-width: 180px")
            if _linked_app_id:
                status_badge(_app_status or "queued")
                _app_stages = [s for s in data_layer.PIPELINE_STAGES
                               if s != "Closed"]

                def _set_stage(e, _aid: str = _linked_app_id) -> None:
                    try:
                        changes = data_layer.update_application_stage(
                            _aid, e.value)
                        ui.notify(f"{_aid}: {'; '.join(changes)}",
                                  type="positive")
                        if on_change:
                            on_change()
                    except (ValueError, OSError) as exc:
                        ui.notify(str(exc), type="negative")

                ui.select(
                    _app_stages,
                    value=data_layer.status_to_stage(_app_status),
                    label="Stage",
                    on_change=_set_stage,
                ).classes("w-full sm:w-44").props("outlined dense")
                ui.link("Open board →", "/applications").classes(
                    "text-caption text-primary")
            else:
                ui.label("Not on the Applications board yet.").classes(
                    "text-caption text-grey-6")

                def _track() -> None:
                    try:
                        data_layer.track_job_as_application(job_id)
                    except ValueError as exc:
                        ui.notify(str(exc), type="negative")
                        return
                    ui.notify(
                        f"{job_id}: queued on the Applications board.",
                        type="positive")
                    if on_change:
                        try:
                            on_change()
                        except Exception:  # noqa: BLE001
                            pass
                    dialog.close()

                ui.button("Track this role", icon="playlist_add",
                          on_click=_track).props("outline dense") \
                    .tooltip("Add to the Applications board (stage: Saved)")
        # Per-job actions + evaluation trigger, then Close.
        with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
            eval_status = ui.label("").classes("text-caption text-grey-6 grow")
            ui.button("Mark completed", icon="check_circle",
                      on_click=lambda: _run_action(
                          "marked completed",
                          lambda: data_layer.set_job_review_flag(job_id, "completed")),
                      ).props("outline dense positive").tooltip("Set review flag: completed")
            ui.button("Mark for later", icon="schedule",
                      on_click=lambda: _run_action(
                          "marked for later",
                          lambda: data_layer.set_job_review_flag(job_id, "for_later")),
                      ).props("outline dense warning").tooltip("Set review flag: for_later")
            ui.button("Mark expired", icon="event_busy",
                      on_click=lambda: _run_action(
                          "status set to expired",
                          lambda: data_layer.set_job_status(job_id, "expired")),
                      ).props("outline dense").tooltip("Set job status to expired")
            delete_button = ui.button(
                "Delete", icon="delete", on_click=lambda: _delete_action()).props(
                "outline dense negative").tooltip("Delete this job (two-step)")
            ui.button("Run evaluation", icon="insights",
                      on_click=_start_evaluation).props("outline dense") \
                .tooltip("Re-run score_jobs_v2.py for this job")
            ui.space()
            ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


# ---------------------------------------------------------------- jobs
# Columns shown in the jobs table (compact view); the dialog shows everything.
# ``priority_v2``/``recommended_action`` may be absent on fresh installs —
# missing columns are simply omitted from the table.
JOBS_TABLE_COLUMNS: list[tuple[str, str]] = [
    ("_sn", "#"),
    ("company", "Company"),
    ("title", "Title"),
    ("source", "Source"),
    ("date_posted", "Posted"),
    ("application_priority", "Priority"),
    ("priority_v2", "Score"),
    ("recommended_action", "Action"),
    ("review_flag", "Review"),
    ("status", "Status"),
    ("fit_tier", "Fit Tier"),
]

STATUS_OPTIONS = ["open", "expired", "filled", "withdrawn", "archived"]
DEFAULT_SORT_BY = "priority_v2"
DEFAULT_SORT_DIR = "desc"


def _jobs_table_columns(df: pd.DataFrame, visible: set[str] | None = None) -> list[dict]:
    """Sortable column defs, restricted to fields present in the data.

    ``_sn`` (serial number) is never sortable — it's the display row index.
    ``visible`` (when provided) restricts to the user's column selection.
    """
    cols = [
        {"name": name, "label": label, "field": name,
         "sortable": name != "_sn", "align": "left"}
        for name, label in JOBS_TABLE_COLUMNS
        if name in df.columns or name == "_sn"
    ]
    if visible is not None:
        cols = [c for c in cols if c["name"] in visible]
    return cols


def _sorted(df: pd.DataFrame, sort_by: str, sort_dir: str) -> pd.DataFrame:
    """Server-side sort; numeric-aware, missing column -> unsorted input."""
    ascending = str(sort_dir or "asc").lower() != "desc"
    if df.empty or not sort_by or sort_by not in df.columns:
        return df
    series = df[sort_by]
    numbers = pd.to_numeric(series, errors="coerce")
    key = numbers if numbers.notna().any() else (
        series.fillna("").astype(str).str.lower())
    return (
        df.assign(_sort_key=key)
        .sort_values("_sort_key", ascending=ascending, na_position="last")
        .drop(columns="_sort_key")
    )


@ui.page("/jobs")
def jobs():
    page_shell("Jobs", "Search and filter the full job tracker. Click a row for full details.")

    state: dict = {
        "search": "", "fit_tier": "", "priority": "",
        "source": "", "status": "", "min_priority": None,
        "role_family": "", "recommended_action": "", "max_age_days": None,
        "sort_by": DEFAULT_SORT_BY, "sort_dir": DEFAULT_SORT_DIR,
    }
    # Bulk-selection state: job_ids picked via table checkboxes.
    selected: dict = {"ids": set()}

    def reload() -> None:
        """Re-read jobs.csv so table reflects mutations (delete/flag/score)."""
        nonlocal jobs_df
        jobs_df = data_layer.load_jobs()

    jobs_df = data_layer.load_jobs()

    # Role-family quick views: chip label -> extra search text (None = clear).
    ROLE_QUICK_VIEWS: list[tuple[str, str | None]] = [
        ("All", None),
        ("Agentic Roles", None),
        ("Agent Reasoning", None),
        ("Post-Training", None),
        ("MLE", None),
        ("Applied Scientist", "applied scientist"),
        ("Eval & Inference", None),
    ]
    # Chip labels whose wording differs from ROLE_FAMILY_OPTIONS display
    # labels (only honored when that value exists in the landed options).
    _ROLE_CHIP_ALIASES = {
        "Agentic Roles": "agentic_ai",
        "MLE": "applied_ml",
    }

    def _role_family_value(label: str) -> str:
        """Map a quick-view chip label to the data layer's role_family value."""
        options: list[tuple[str, str]] = [
            (str(v), str(d))
            for v, d in (getattr(data_layer, "ROLE_FAMILY_OPTIONS", ()) or ())
        ]
        for value, display in options:
            if display.lower() == label.lower():
                return value
        alias = _ROLE_CHIP_ALIASES.get(label)
        if alias and any(v == alias for v, _d in options):
            return alias
        # Fallback for options/chips that haven't matched (e.g. a chip whose
        # family isn't modeled yet): use a slugified label as the value.
        return label.lower().replace(" & ", "_").replace(" ", "_").replace("-", "_")

    def _role_family_options_map() -> dict:
        """"{value: label}" select options from ROLE_FAMILY_OPTIONS."""
        try:
            pairs = data_layer.ROLE_FAMILY_OPTIONS
        except AttributeError:
            pairs = ()
        return {"": "All", **{str(v): str(l) for v, l in pairs}}

    def _options(column: str) -> list[str]:
        if jobs_df.empty or column not in jobs_df.columns:
            return []
        return sorted(
            {str(v).strip() for v in jobs_df[column].fillna("").astype(str)
             if str(v).strip()}
        )

    fit_options = _options("fit_tier")
    priority_options = _options("application_priority")
    source_options = _options("source")
    action_options = _options("recommended_action")
    # Sort targets: only columns actually present in the data.
    sort_columns = [name for name, _label in JOBS_TABLE_COLUMNS
                    if name in jobs_df.columns] or ["company"]

    # Column visibility (chooser): default = every column available.
    visible_cols: dict = {"names": {name for name, _l in JOBS_TABLE_COLUMNS}}

    def _toggle_column(name: str) -> None:
        if name in visible_cols["names"]:
            # Keep at least one column visible.
            if len(visible_cols["names"]) > 1:
                visible_cols["names"].discard(name)
        else:
            visible_cols["names"].add(name)
        refresh()

    AGE_OPTIONS = {
        "": "Any age",
        7: "Last 7 days",
        14: "Last 14 days",
        30: "Last 30 days",
        60: "Last 60 days",
        90: "Last 90 days",
    }
    PAGE_SIZES = [10, 25, 50, 0]  # 0 = All

    def current_rows() -> list[dict]:
        filtered = data_layer.filter_jobs(
            jobs_df,
            state["search"], state["fit_tier"], state["priority"],
            source=state["source"], status=state["status"],
            min_priority=state["min_priority"],
            role_family=state["role_family"],
            recommended_action=state["recommended_action"],
            max_age_days=state["max_age_days"],
        )
        filtered = _sorted(filtered, state["sort_by"], state["sort_dir"])
        records = filtered.replace(pd.NA, "").fillna("").to_dict("records")
        # Serial numbers reflect the CURRENT filter+sort order (1..N).
        for idx, rec in enumerate(records, start=1):
            rec["_sn"] = idx
        return records

    def refresh() -> None:
        rows = current_rows()
        count_label.set_text(f"{len(rows)} of {len(jobs_df)} jobs")
        table_container.clear()
        with table_container:
            if not rows:
                empty_state("No jobs match the current filters.", icon="search_off")
            else:
                with table_wrap():
                    table = ui.table(
                        columns=_jobs_table_columns(jobs_df, visible_cols["names"]),
                        rows=rows,
                        row_key="job_id",
                        selection="multiple",
                        pagination={"rowsPerPage": page_size_select.value or 10},
                        on_select=_on_row_select,
                    ).classes("w-full")
                    table.props("flat")
                    table.on("update:pagination", _on_pagination)
                    table.on("selection", _on_selection)
                    # Client-side sorting stays off; ordering comes from the
                    # server via state['sort_by']/state['sort_dir'] (and the
                    # explicit Sort-by controls) so saved views reproduce it.
                    table.add_slot("body-cell-status", """
                        <q-td key="status" :props="props">
                          <q-badge outline dense color="primary"
                            :label="props.value" />
                        </q-td>
                    """)
                    table.add_slot("body-cell-review_flag", REVIEW_FLAG_BADGE_SLOT)
                    table.on("row-click", _on_row_click)

    def _on_job_changed() -> None:
        """Dialog mutation callback: reload data and re-render the table."""
        reload()
        refresh()

    def _on_row_select(e) -> None:
        rows = e.args if isinstance(e.args, list) else [e.args]
        for row in rows:
            if isinstance(row, dict):
                _open_job_dialog(row, on_change=_on_job_changed)
                break

    def _on_selection(e) -> None:
        """Track checkbox selection for bulk stage changes."""
        rows = e.args if isinstance(e.args, list) else []
        # Quasar emits [newSelection] (or [newSelection, oldSelection]).
        first = rows[0] if rows else []
        selected["ids"] = {
            str(r.get("job_id")) for r in first if isinstance(r, dict)
        }
        _sync_bulk_bar()

    def _on_pagination(e) -> None:
        """Persist the user's page-size choice across table re-renders."""
        try:
            payload = e.args if not isinstance(e.args, dict) else e.args
            if isinstance(payload, list) and payload:
                payload = payload[-1]
            value = (payload or {}).get("rowsPerPage")
            page_size_select.value = int(value) if value is not None \
                else page_size_select.value
        except (TypeError, ValueError, AttributeError):
            pass

    def _on_row_click(e) -> None:
        row = e.args[1] if isinstance(e.args, list) and len(e.args) > 1 else None
        if isinstance(row, dict):
            _open_job_dialog(row, on_change=_on_job_changed)

    def _live_update(key: str, e) -> None:
        # ui.select/ui.number on_change events carry the converted value on
        # ``e.value`` (NiceGUI ValueChangeEventArguments has no ``.args``);
        # generic .on("update:model-value") events carry raw args instead.
        value = getattr(e, "value", None)
        if value is None:
            value = getattr(e, "args", e)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if key == "min_priority":
            try:
                state[key] = float(value) if value not in ("", None) else None
            except (TypeError, ValueError):
                state[key] = None
        elif key == "max_age_days":
            try:
                state[key] = int(value) if value not in ("", None) else None
            except (TypeError, ValueError):
                state[key] = None
        else:
            if value in ("All", None):
                value = ""
            state[key] = str(value)
        refresh()

    def _sync_bulk_bar() -> None:
        n = len(selected["ids"])
        bulk_count.set_text(f"{n} selected" if n else "Select rows for bulk actions")
        for btn in (bulk_status_select, bulk_apply_btn, bulk_applied_btn,
                    bulk_clear_btn):
            (btn.enable if n else btn.disable)()

    def _bulk_set_status() -> None:
        status = bulk_status_select.value
        if not selected["ids"] or not status:
            return
        try:
            changed = data_layer.set_job_status(sorted(selected["ids"]), status)
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        ui.notify(f"{len(changed)} job(s) set to {status}.", type="positive")
        reload()
        refresh()

    def _bulk_mark_applied() -> None:
        if not selected["ids"]:
            return
        ids = sorted(selected["ids"])
        try:
            changed = data_layer.mark_jobs_applied(ids)
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        skipped = len(ids) - len(changed)
        msg = f"{len(changed)} job(s) marked Applied + queued on the board."
        if skipped:
            msg += f" ({skipped} skipped — see notifications.)"
        ui.notify(msg, type="positive")
        reload()
        refresh()

    def _bulk_clear_selection() -> None:
        selected["ids"] = set()
        _sync_bulk_bar()
        refresh()

    def _clear_filters() -> None:
        state.update(search="", fit_tier="", priority="", source="", status="",
                     min_priority=None, role_family="",
                     sort_by=DEFAULT_SORT_BY, sort_dir=DEFAULT_SORT_DIR)
        search_input.set_value(None)
        fit_select.set_value("All")
        priority_select.set_value("All")
        source_select.set_value("All")
        role_select.set_value("")
        status_select.set_value("All")
        min_score_input.set_value(None)
        sort_by_select.set_value(DEFAULT_SORT_BY)
        sort_dir_select.set_value(DEFAULT_SORT_DIR)
        _sync_quick_chips()
        refresh()

    # --- Saved views -------------------------------------------------------
    def _saved_options() -> list[str]:
        return [str(v.get("name", "")) for v in data_layer.list_saved_views()]

    def _save_view() -> None:
        name = (view_name_input.value or "").strip()
        if not name:
            ui.notify("Enter a name to save the view.", type="warning")
            return
        view_kwargs: dict = dict(
            search=state["search"], fit_tier=state["fit_tier"],
            priority=state["priority"], source=state["source"],
            status=state["status"], min_priority=state["min_priority"],
            sort_by=state["sort_by"], sort_dir=state["sort_dir"],
        )
        # Persist role_family once the data layer's save_view supports it
        # (it is being added in parallel; absent support -> silently skipped).
        if "role_family" in inspect.signature(data_layer.save_view).parameters:
            view_kwargs["role_family"] = state.get("role_family", "")
        data_layer.save_view(name, **view_kwargs)
        view_name_input.set_value(None)
        saved_view_select.options = _saved_options()
        saved_view_select.value = name
        ui.notify(f"Saved view '{name}'.", type="positive")

    def _apply_view() -> None:
        name = saved_view_select.value
        view = next((v for v in data_layer.list_saved_views()
                     if v.get("name") == name), None)
        if not view:
            ui.notify("Select a saved view first.", type="warning")
            return
        state.update(
            search=str(view.get("search") or ""),
            fit_tier=str(view.get("fit_tier") or ""),
            priority=str(view.get("priority") or ""),
            source=str(view.get("source") or ""),
            status=str(view.get("status") or ""),
            role_family=str(view.get("role_family") or ""),
            sort_by=str(view.get("sort_by") or DEFAULT_SORT_BY),
            sort_dir=str(view.get("sort_dir") or DEFAULT_SORT_DIR),
        )
        raw_min = str(view.get("min_priority") or "").strip()
        try:
            state["min_priority"] = float(raw_min) if raw_min else None
        except ValueError:
            state["min_priority"] = None

        def _as_all(value: str) -> str:
            return value or "All"

        search_input.set_value(state["search"] or None)
        fit_select.set_value(_as_all(state["fit_tier"]))
        priority_select.set_value(_as_all(state["priority"]))
        source_select.set_value(_as_all(state["source"]))
        role_select.set_value(state["role_family"] or "")
        status_select.set_value(_as_all(state["status"]))
        min_score_input.set_value(state["min_priority"])
        sort_by_select.set_value(
            state["sort_by"] if state["sort_by"] in sort_columns
            else DEFAULT_SORT_BY)
        sort_dir_select.set_value(state["sort_dir"])
        _sync_quick_chips()
        refresh()
        ui.notify(f"Applied view '{name}'.", type="positive")

    def _delete_view() -> None:
        name = saved_view_select.value
        view = next((v for v in data_layer.list_saved_views()
                     if v.get("name") == name), None)
        if not view:
            ui.notify("Select a saved view first.", type="warning")
            return
        view_name = str(name)

        def _do_delete() -> None:
            data_layer.delete_view(str(view.get("view_id")))
            saved_view_select.options = _saved_options()
            saved_view_select.value = None
            ui.notify(f"Deleted view '{view_name}'.", type="info")

        dialog = confirm_dialog(
            "Delete saved view",
            f"Delete saved view '{view_name}'? This cannot be undone.",
            danger=True,
            confirm_label=f"Delete view '{view_name}'",
            on_confirm=_do_delete,
        )
        dialog.open()

    # --- Quick views (chip row above filters) -------------------------------
    chip_buttons: dict[str, ui.button] = {}

    def _sync_quick_chips() -> None:
        """Outline inactive chips; filled/unelevated marks the active one."""
        for label, btn in list(chip_buttons.items()):
            if btn.is_deleted:
                continue
            active = (label == "All" and not state["role_family"]
                      and not state["search"]) or (
                          label != "All"
                          and state["role_family"] == _role_family_value(label))
            if active:
                btn.props("unelevated", remove="outline")
            else:
                btn.props("outline", remove="unelevated")

    def _apply_quick_view(label: str) -> None:
        search = next(s for name, s in ROLE_QUICK_VIEWS if name == label)
        if label == "All":
            state["role_family"] = ""
            state["search"] = ""
        else:
            state["role_family"] = _role_family_value(label)
            state["search"] = search or ""
        search_input.set_value(state["search"] or None)
        role_select.set_value(state["role_family"] or "")
        _sync_quick_chips()
        refresh()

    with ui.row().classes("w-full items-center q-gutter-xs no-wrap q-mb-sm"):
        ui.label("Views:").classes("text-caption text-weight-bold text-grey-7")
        for view_label, _search in ROLE_QUICK_VIEWS:
            chip = ui.button(
                view_label,
                on_click=lambda _e=None, lbl=view_label: _apply_quick_view(lbl),
            ).props("outline dense").tooltip(
                f"Quick filter: {view_label}")
            chip_buttons[view_label] = chip

    with ui.card().classes("jh-card w-full q-pa-md"):
        with filter_bar():
            with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
                search_input = ui.input(placeholder="Search company or title…").classes(
                    "grow").props(
                    "outlined dense clearable aria-label='Search jobs'"
                ).on("update:model-value", lambda e: _live_update("search", e))
                fit_select = ui.select(
                    ["All"] + fit_options,
                    label="Fit tier",
                    value="All",
                    on_change=lambda e: _live_update("fit_tier", e),
                ).classes("col-grow").props("outlined dense clearable")
                priority_select = ui.select(
                    ["All"] + priority_options,
                    label="Priority",
                    value="All",
                    on_change=lambda e: _live_update("priority", e),
                ).classes("col-grow").props("outlined dense clearable")
                source_select = ui.select(
                    ["All"] + source_options,
                    label="Source",
                    value="All",
                    on_change=lambda e: _live_update("source", e),
                ).classes("col-grow").props("outlined dense clearable")
                role_select = ui.select(
                    _role_family_options_map(),
                    label="Role family",
                    value="",
                    on_change=lambda e: _live_update("role_family", e),
                ).classes("col-grow").props("outlined dense clearable").tooltip(
                    "Filter by LLM-categorized role family")
                action_select = ui.select(
                    ["All"] + action_options,
                    label="Action",
                    value="All",
                    on_change=lambda e: _live_update("recommended_action", e),
                ).classes("col-grow").props("outlined dense clearable").tooltip(
                    "Filter by scorer recommended_action")
                age_select = ui.select(
                    AGE_OPTIONS,
                    label="Posted age", value="",
                    on_change=lambda e: _live_update("max_age_days", e),
                ).classes("col-grow").props("outlined dense")
        with filter_bar():
            with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
                status_select = ui.select(
                    ["All"] + STATUS_OPTIONS,
                    label="Status",
                    value="All",
                    on_change=lambda e: _live_update("status", e),
                ).classes("col-grow").props("outlined dense clearable")
                min_score_input = ui.number(
                    label="Min score (priority_v2)", format="%.0f",
                    on_change=lambda e: _live_update("min_priority", e),
                ).classes("col-grow").props("outlined dense")
                page_size_select = ui.select(
                    PAGE_SIZES, label="Rows per page", value=10,
                ).classes("col-grow").props("outlined dense") \
                    .tooltip("0 = show all rows; also updates when you change "
                             "the table's own pagination control")
                sort_by_select = ui.select(
                    sort_columns,
                    label="Sort by", value=(
                        DEFAULT_SORT_BY if DEFAULT_SORT_BY in sort_columns
                        else sort_columns[0]),
                    on_change=lambda e: _live_update("sort_by", e),
                ).classes("col-grow").props("outlined dense")
                sort_dir_select = ui.select(
                    ["asc", "desc"], label="Direction",
                    value=DEFAULT_SORT_DIR,
                    on_change=lambda e: _live_update("sort_dir", e),
                ).classes("col-grow").props("outlined dense")
                ui.button("Clear filters", icon="filter_alt_off",
                          on_click=_clear_filters).props(
                    "outline dense").tooltip("Reset search, filters and sorting")

    with ui.card().classes("jh-card w-full q-pa-md"):
        ui.label("Saved views").classes("text-subtitle1 text-weight-bold")
        with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
            view_name_input = ui.input(placeholder="New view name…").classes(
                "grow").props("outlined dense clearable")
            ui.button("Save view", icon="save", on_click=_save_view).props(
                "outline dense")
        with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
            saved_view_select = ui.select(
                _saved_options(), label="Saved views", value=None,
            ).classes("col-grow").props("outlined dense clearable")
            ui.button("Apply", icon="play_arrow", on_click=_apply_view).props(
                "outline dense").tooltip("Apply the selected saved view")
            ui.button("Delete", icon="delete", on_click=_delete_view).props(
                "outline dense negative").tooltip("Delete the selected saved view")

    # --- LLM categorization trigger -----------------------------------------
    cat_cell: dict = {"notified_run": None}

    def _start_categorize() -> None:
        try:
            RUNS.start(
                "role_categorization",
                [sys.executable, triggers.script("categorize_roles.py"),
                 "--apply"],
            )
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning")
            return
        cat_button.disable()
        cat_status.set_text("Categorizing missing role families…")

    def _poll_categorize() -> None:
        if cat_button.is_deleted or cat_status.is_deleted:
            return  # page elements cleared; stop touching dead widgets
        run_id = RUNS.latest("role_categorization")
        if run_id is None:
            return
        st = RUNS.status(run_id)
        lines = RUNS.tail(run_id, 5)
        tail_txt = (" · " + " | ".join(lines[-2:])) if lines else ""
        if st["state"] == "running":
            cat_status.set_text(f"{run_id}: running{tail_txt}")
            cat_button.disable()
            return
        cat_button.enable()
        rc = st.get("returncode")
        cat_status.set_text(f"{run_id}: {st['state']} (exit {rc}){tail_txt}")
        if cat_cell["notified_run"] == run_id:
            return  # completion already reported for this run
        cat_cell["notified_run"] = run_id
        if rc == 0:
            reload()
            refresh()
            _sync_quick_chips()
            ui.notify("Role categorization finished; jobs reloaded.",
                      type="positive")
        else:
            ui.notify(f"Role categorization failed (exit {rc}).",
                      type="negative")

    # Bulk actions + column chooser (created before the table so handlers can
    # reference the widgets; the bar sits directly above the results).
    with ui.card().classes("jh-card w-full q-pa-md"):
        with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
            bulk_count = ui.label("Select rows for bulk actions").classes(
                "text-caption text-grey-6")
            bulk_status_select = ui.select(
                [""] + STATUS_OPTIONS, label="Set status to…", value="",
            ).classes("col-grow").props("outlined dense")
            bulk_apply_btn = ui.button(
                "Apply", icon="done_all", on_click=_bulk_set_status,
            ).props("outline dense").tooltip(
                "Bulk lifecycle transition (rows are never deleted)")
            bulk_applied_btn = ui.button(
                "Mark Applied", icon="task_alt", on_click=_bulk_mark_applied,
            ).props("outline dense positive").tooltip(
                "Queue on the Applications board at Applied stage and flag "
                "the job completed")
            bulk_clear_btn = ui.button(
                "Clear selection", icon="deselect",
                on_click=_bulk_clear_selection,
            ).props("outline dense")
        with ui.expansion("Columns", icon="view_column").classes("w-full"):
            with ui.row().classes("w-full flex-wrap q-gutter-xs"):
                for name, label in JOBS_TABLE_COLUMNS:
                    ui.button(label, on_click=lambda _e=None, n=name: _toggle_column(n)) \
                        .props("outline dense").tooltip(
                            f"Toggle the {label} column")

    # Results header + table: created last so they render BELOW the filters.
    with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
        count_label = ui.label("").classes("text-caption text-grey-6")
        ui.space()
        cat_status = ui.label("").classes("text-caption text-grey-6")
        cat_button = ui.button(
            "Fill missing role families (LLM)", icon="auto_awesome",
            on_click=_start_categorize,
        ).props("outline dense").tooltip(
            "Run scripts/categorize_roles.py --apply to fill blank "
            "role_family values via LLM")
    table_container = ui.column().classes("w-full")

    _sync_quick_chips()
    refresh()
    page_timer(1.0, _poll_categorize)


# ---------------------------------------------------------------- applications
@ui.page("/applications")
def applications():  # pragma: no cover - requires running server
    page_shell(
        "Applications",
        "Stage board — stage ≠ outcome; terminal rows are listed under Outcomes.",
    )

    # --- Manual tracking widget: add your own roles -----------------------
    # The board is otherwise fed by the discovery pipeline and a future
    # Outlook-email tracking agent; this is the human-in-the-loop entry point.
    with section_card(
            "Track a role",
            "Add any role you want to track manually — it lands on the board "
            "below as a card you can move through stages."):
        with ui.row().classes("w-full items-start q-gutter-sm flex-wrap"):
            company_in = ui.input("Company", placeholder="e.g. Anthropic") \
                .classes("w-full sm:w-56").props("outlined dense")
            role_in = ui.input("Role", placeholder="e.g. Applied AI Engineer") \
                .classes("w-full sm:w-72").props("outlined dense")
            url_in = ui.input("Job URL", placeholder="https://… (optional)") \
                .classes("w-full sm:w-80").props("outlined dense")
            status_opts = ["queued", "ready_to_apply", "submitted", "interview"]
            status_in = ui.select(status_opts, value="queued", label="Status") \
                .classes("w-full sm:w-44").props("outlined dense")
            notes_in = ui.input("Notes", placeholder="optional") \
                .classes("w-full sm:w-72").props("outlined dense")

        def _track_role() -> None:
            if not (company_in.value or "").strip() or not (role_in.value or "").strip():
                ui.notify("Company and Role are required.", type="warning")
                return
            try:
                row = data_layer.add_application(
                    company_in.value,
                    role_in.value,
                    job_url=url_in.value or "",
                    status=status_in.value or "queued",
                    notes=notes_in.value or "",
                )
            except ValueError as exc:
                ui.notify(str(exc), type="negative")
                return
            ui.navigate.reload()
            ui.notify(f"Tracking {row['application_id']}.", type="positive")

        with ui.row().classes("w-full items-end q-gutter-sm flex-wrap"):
            ui.button("Track role", icon="playlist_add", on_click=_track_role) \
                .props("unelevated")

    apps = data_layer.load_applications()
    records: list[dict] = []
    if not apps.empty:
        records = apps.fillna("").to_dict("records")
    if not records:
        empty_state(
            "No tracked roles yet — add one with 'Track a role' above.",
            icon="view_kanban",
        )
        return
    stages = application_stages()

    def _on_stage_change(record: dict, e) -> None:
        new_stage = e.value
        app_id = record.get("application_id") or record.get("job_id") or ""
        old_stage = data_layer.stage_outcome_split(record.get("status"))[0]
        target_status = data_layer.STAGE_TO_STATUS[new_stage]

        def _apply() -> None:
            try:
                changes = data_layer.update_application_stage(app_id, new_stage)
                ui.notify(f"{app_id}: {'; '.join(changes)}", type="positive")
                ui.navigate.reload()
            except (ValueError, OSError) as exc:
                ui.notify(str(exc), type="negative")

        dialog = confirm_dialog(
            "Change stage",
            f"{app_id}: {old_stage} → {new_stage} "
            f"(writes status {target_status} to applications.csv)",
            danger=False,
            confirm_label="Confirm",
            on_confirm=_apply,
        )
        dialog.open()

    def _stage_column(stage: str) -> None:
        stage_rows = [
            r for r in records
            if data_layer.stage_outcome_split(r.get("status")) == (stage, "")
        ]
        with ui.column().classes("col jh-card q-pa-sm").style("min-width: 220px"):
            with ui.row().classes("items-center justify-between no-wrap"):
                ui.label(stage).classes("text-subtitle1 text-weight-bold")
                ui.badge(str(len(stage_rows)), color="primary").props("dense")
            if not stage_rows:
                empty_state("No applications")
            for record in stage_rows:
                _application_card(record, stages, _on_stage_change)

    def _outcomes_column() -> None:
        terminal = [
            r for r in records
            if data_layer.stage_outcome_split(r.get("status"))[1]
        ]
        with ui.column().classes("col jh-card q-pa-sm").style("min-width: 220px"):
            with ui.row().classes("items-center justify-between no-wrap"):
                ui.label("Outcomes").classes("text-subtitle1 text-weight-bold")
                ui.badge(str(len(terminal)), color="grey-7").props("dense")
            if not terminal:
                empty_state("No terminal outcomes recorded")
            for record in terminal:
                _stage, outcome = data_layer.stage_outcome_split(record.get("status"))
                company = str(record.get("company") or "(unknown)")
                role = str(record.get("role") or record.get("job_id") or "")
                with ui.card().classes("w-full q-pa-sm jh-card").style(
                        "border: 1px solid var(--jh-border)"):
                    ui.label(company).classes("text-body1 text-weight-medium")
                    ui.label(role).classes("text-caption text-grey-6")
                    note = data_layer.APPLICATION_OUTCOME_NOTES.get(outcome, "")
                    with ui.row().classes("items-center q-gutter-xs no-wrap"):
                        status_badge(outcome)
                        if note:
                            ui.icon("info_outline", size="xs").classes(
                                "text-grey-6").tooltip(note)

    # Kanban columns keep a readable min-width; the row scrolls horizontally
    # inside its own container so the page itself never overflows.
    with table_wrap():
        with ui.row().classes("w-full q-gutter-sm items-stretch no-wrap"):
            for stage in stages:
                _stage_column(stage)
            _outcomes_column()


def _application_card(record: dict, stages: list[str], on_stage_change) -> None:
    company = str(record.get("company") or "(unknown)")
    role = str(record.get("role") or record.get("job_id") or "")
    date_str = (record.get("date_submitted")
                or record.get("date_queued") or "")
    with ui.card().classes("w-full q-pa-sm jh-card").style(
            "border: 1px solid var(--jh-border)"):
        ui.label(company).classes("text-body1 text-weight-medium")
        ui.label(role).classes("text-caption text-grey-6")
        if date_str:
            with ui.row().classes("items-center q-gutter-xs"):
                ui.icon("event", size="xs").classes("text-grey-6")
                ui.label(str(date_str)).classes("text-caption text-grey-6")
        ui.select(
            stages,
            value=data_layer.status_to_stage(record.get("status")),
            label="Stage",
            on_change=lambda e, rec=record, handler=on_stage_change: handler(rec, e),
        ).classes("w-full").props("outlined dense")


# ---------------------------------------------------------------- right people
@ui.page("/right-people")
def right_people_page():  # pragma: no cover - requires running server
    """Drop a job link -> per-company people directory + email formats."""
    from nicegui import ui as _ui

    from ui.pages_right_people import render_right_people_page

    from nicegui import context as _ctx

    company = ""
    try:
        company = _ctx.client.request.query_params.get("company", "")
    except Exception:  # noqa: BLE001 - no request context (tests)
        company = ""
    page_shell(
        "Right People",
        "Drop a job link or company name — track the right people to "
        "connect with, with email-format candidates and one-click "
        "LinkedIn profiles.",
    )
    render_right_people_page(company_slug=company)


# ---------------------------------------------------------------- network
BADGE_COLOR = {
    "pending": "warning",
    "approved": "info",
    "sent_no_note": "positive",
    "sent_with_note": "positive",
    "connected": "secondary",
    "declined": "grey-7",
    "failed": "negative",
}


SOURCE_LABELS = {
    "ledger": "Outreach ledger",
    "contacts": "Referral research",
    "people_sweep": "People sweep",
    "hiring_post": "Hiring post",
}

STATUS_COLORS = {
    **BADGE_COLOR,
    "not_contacted": "primary",
    "pending_review": "warning",
    "new": "accent",
    "requested": "info",
}


@ui.page("/network")
def network():  # pragma: no cover - requires running server
    page_shell(
        "Network",
        "Everyone the engine recommends connecting with — merged from the "
        "outreach ledger, referral research, people sweeps, and hiring posts. "
        "Approve here; sending happens only via explicit manual steps.",
    )

    # ---------------------------------------------------------- automation
    cron = data_layer.cron_health()
    cron_jobs = {j["name"]: j for j in cron.get("jobs", [])} \
        if cron.get("available") else {}
    with section_card(
            "LinkedIn Automation",
            "The background agent sweep (linkedin-people-posts-2h, every 2h) "
            "scans your feed and LinkedIn searches for hiring posts, active "
            "posters, and relevant people — then lands them in this list.",
    ):
        with ui.row().classes("w-full items-center q-gutter-sm no-wrap") \
                .style("flex-wrap: wrap"):
            posts_job = cron_jobs.get("linkedin-people-posts-2h")
            if not cron.get("available"):
                ui.badge("cron store unavailable", color="grey-6").props(
                    "outline dense")
            elif posts_job:
                last = posts_job["last_status"] or "never run"
                color = ("positive" if posts_job.get("healthy")
                         else "negative" if last == "error" else "grey-6")
                ui.badge(f"every 2h · last run: {last}", color=color).props(
                    "outline dense").tooltip(
                    f"next run {posts_job['next_run_at'][:16]}")
            else:
                ui.badge("linkedin-people-posts-2h not found", color="warning") \
                    .props("outline dense")
            triggers.RunPanel("linkedin_people_sweep",
                              triggers.linkedin_people_sweep_cmd)
            triggers.RunPanel("outreach_draft", triggers.outreach_draft_cmd)

    # ------------------------------------------------------------ KPI strip
    recs = data_layer.network_recommendations()
    counts = data_layer.network_source_counts(recs)
    kpi_grid([
        (str(counts["total"]), "People to connect with", "group", "accent"),
        (str(counts["sources"]["ledger"]), "In outreach ledger",
         "connect_without_contact", "warning"),
        (str(counts["with_email"]), "With email found", "mail", "positive"),
        (str(counts["sources"]["people_sweep"]
             + counts["sources"]["hiring_post"]),
         "From agent sweeps", "smart_toy", "info"),
    ])

    # ------------------------------ combined people directory + outreach queue
    # One dynamic table: every recommended person (ledger rows first) with a
    # why-connect reason, provenance, and inline approve for pending ledger
    # requests. Replaces the former table + separate ledger card list.
    progress = data_layer.send_cap_progress()
    pct = min(progress["sent_today"] / progress["cap"], 1.0)
    with ui.row().classes("w-full items-center q-gutter-sm no-wrap") \
            .style("flex-wrap: wrap"):
        ui.linear_progress(pct).classes("grow").props(
            "rounded color='{}'".format(
                "negative" if pct >= 1 else "primary"))
        ui.label(
            f"{progress['sent_today']} / {progress['cap']} sent today "
            f"({progress['remaining']} remaining)").classes(
            "text-caption text-grey-6")

    with section_card(
            "Recommended connections",
            "Everyone the engine recommends connecting with, in one dynamic "
            "table — outreach-ledger requests first, then fresh contacts and "
            "sweep finds. 'Why connect' explains each recommendation; pending "
            "ledger rows carry an Approve action (sending stays a manual "
            "step). Click a name to open their LinkedIn profile."):
        state: dict = {"search": "", "source": "", "status": ""}

        def _options(field: str) -> list[str]:
            return sorted({p[field] for p in recs if p[field]})

        source_opts = _options("source")
        status_opts = _options("status")

        def filtered_rows() -> list[dict]:
            out = recs
            query = state["search"].strip().lower()
            if query:
                out = [p for p in out if query in
                       " ".join((p["name"], p["company"], p["title"],
                                 p["email"], p["reason"])).lower()]
            if state["source"]:
                out = [p for p in out if p["source"] == state["source"]]
            if state["status"]:
                out = [p for p in out if p["status"] == state["status"]]
            return out

        def refresh() -> None:
            rows = filtered_rows()
            count_label.set_text(f"{len(rows)} of {len(recs)} people")
            table_container.clear()
            with table_container:
                if not rows:
                    empty_state("No people match the current filters.",
                                icon="person_search")
                    return
                cols = [
                    {"name": c, "label": lbl, "field": c, "align": "left",
                     "sortable": True}
                    for c, lbl in (
                        ("name", "Name"), ("title", "Title"),
                        ("company", "Company"), ("email", "Email"),
                        ("reason", "Why connect"),
                        ("source_label", "Found via"), ("status", "Status"),
                        ("date", "Date"),
                    )
                ] + [
                    # Slot-only column: Approve action + post provenance.
                    {"name": "actions", "label": "", "field": "actions",
                     "align": "left", "sortable": False},
                ]
                table_rows = []
                for p in rows:
                    table_rows.append({
                        **p,
                        "source_label": SOURCE_LABELS.get(p["source"],
                                                          p["source"]),
                        "request_id": p.get("request_id", ""),
                        "can_approve": (
                            p["source"] == "ledger"
                            and p["status"].lower() == "pending"
                            and bool(p.get("request_id"))
                        ),
                    })
                with table_wrap():
                    table = ui.table(
                        columns=cols, rows=table_rows,
                        row_key="name",
                        pagination={"rowsPerPage": 25},
                    ).classes("w-full").props("flat")
                    # Name -> LinkedIn profile link.
                    table.add_slot("body-cell-name", """
                        <q-td key="name" :props="props">
                          <a v-if="props.row.linkedin_url"
                             :href="props.row.linkedin_url" target="_blank"
                             style="text-decoration: underline">{{ props.value }}</a>
                          <span v-else>{{ props.value }}</span>
                        </q-td>
                    """)
                    # Title: truncated cell text, full text on hover.
                    table.add_slot("body-cell-title", """
                        <q-td key="title" :props="props">
                          <span v-if="props.value" class="text-caption"
                                style="display:inline-block;max-width:260px;
                                       overflow:hidden;text-overflow:ellipsis;
                                       white-space:nowrap"
                                :title="props.value">{{ props.value }}</span>
                          <span v-else class="text-grey-5">—</span>
                        </q-td>
                    """)
                    # Email shown as mailto text when discovered.
                    table.add_slot("body-cell-email", """
                        <q-td key="email" :props="props">
                          <a v-if="props.value"
                             :href="'mailto:' + props.value"
                             style="text-decoration: underline">{{ props.value }}</a>
                          <span v-else class="text-grey-5">—</span>
                        </q-td>
                    """)
                    # Why-connect: truncated cell text, full text on hover.
                    table.add_slot("body-cell-reason", """
                        <q-td key="reason" :props="props">
                          <span v-if="props.value" class="text-caption"
                                style="display:inline-block;max-width:320px;
                                       overflow:hidden;text-overflow:ellipsis;
                                       white-space:nowrap"
                                :title="props.value">{{ props.value }}</span>
                          <span v-else class="text-grey-5">—</span>
                        </q-td>
                    """)
                    table.add_slot("body-cell-status", """
                        <q-td key="status" :props="props">
                          <q-badge outline dense>{{ props.value }}</q-badge>
                        </q-td>
                    """)
                    # Actions: approve button for pending ledger requests;
                    # post/profile provenance link when available.
                    table.add_slot("body-cell-actions", """
                        <q-td key="actions" :props="props">
                          <q-btn v-if="props.row.can_approve" dense unelevated
                                 color="positive" icon="check" label="Approve"
                                 @click="$parent.$emit('approve', props.row)" />
                          <a v-if="props.row.post_url"
                             :href="props.row.post_url" target="_blank"
                             class="text-caption q-ml-sm"
                             style="text-decoration: underline">post</a>
                        </q-td>
                    """)

                    def _on_approve(e) -> None:
                        # Slot emits a single row dict; unwrap both shapes.
                        args = e.args
                        if isinstance(args, list):
                            args = args[-1] if args else {}
                        row = args.get("row", args) if isinstance(
                            args, dict) else {}
                        rid = str(row.get("request_id") or "")
                        if not rid:
                            ui.notify("no request id on row",
                                      type="negative")
                            return
                        person = str(row.get("name", "") or "(unknown)")
                        company = str(row.get("company", "") or "(unknown)")
                        basis = str(row.get("reason", "") or "")

                        def _do_approve():
                            try:
                                data_layer.approve_request(rid)
                                ui.notify(f"approved {rid}", type="positive")
                                ui.navigate.reload()
                            except (ValueError, OSError) as exc:
                                ui.notify(str(exc), type="negative")

                        dialog = confirm_dialog(
                            "Approve request",
                            f"Approve the connection request to {person} at "
                            f"{company}?" + (f" ({basis})" if basis else ""),
                            danger=False,
                            confirm_label="Approve request",
                            on_confirm=_do_approve,
                        )
                        dialog.open()

                    table.on("approve", _on_approve)

        def _live_update(key: str, e) -> None:
            value = getattr(e, "value", None)
            if value is None:
                value = getattr(e, "args", e)
            if value in ("All", None):
                value = ""
            state[key] = str(value)
            refresh()

        with filter_bar():
            with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
                search_input = ui.input(
                    placeholder="Search name, company, title, email, reason…"
                ).classes("grow").props(
                    "outlined dense clearable aria-label='Search people'"
                ).on("update:model-value",
                     lambda e: _live_update("search", e))
                source_select = ui.select(
                    ["All"] + source_opts, label="Found via", value="All",
                    on_change=lambda e: _live_update("source", e),
                ).classes("col-grow").props("outlined dense clearable")
                status_select = ui.select(
                    ["All"] + status_opts, label="Status", value="All",
                    on_change=lambda e: _live_update("status", e),
                ).classes("col-grow").props("outlined dense clearable")

        with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
            count_label = ui.label("").classes("text-caption text-grey-6")
            ui.space()

        # Table container lives BELOW the filter bar + count row so the page
        # reads: filters -> count -> table (not table first).
        table_container = ui.column().classes("w-full")

        refresh()


# ---------------------------------------------------------------- runs
@ui.page("/runs")
def runs_page():  # pragma: no cover - requires running server
    """Unified run view across agent + script workflows, UI + cron triggers."""
    from ui.pages_runs import render_runs_page

    page_shell(
        "Runs",
        "Every workflow run — Hermes-agent sessions and deterministic "
        "scripts, triggered by cron or the UI. Survives page refreshes.",
    )
    render_runs_page()


@ui.page("/operations")
def operations():  # pragma: no cover - requires running server
    page_shell(
        "Operations",
        "Engine run panels, server lifecycle, and per-source data health.",
    )

    server_controls()

    # LinkedIn job collection + hiring-post automation moved to the dedicated
    # /linkedin-posts page (see linkedin_posts above). Cron health renders there.

    # --- Engine triggers (dry-run, read-only entry points) ---
    with section_card("Engine Triggers",
                      "Dry-run (read-only) engine entry points; one run per component at a time."):
        tier_select = ui.select(
            triggers.TIER_ORDER, label="Min fit tier (discovery summary)",
            value="B").classes("w-full sm:w-64 max-w-full").props("outlined dense")
        triggers.RunPanel(
            "discovery",
            lambda: triggers.discovery_cmd(tier_select.value or ""))
        triggers.RunPanel("freshness", triggers.freshness_cmd)

    # --- Data health: per-source freshness/readability ---
    with section_card("Data Health",
                      "Canonical CSV sources: existence, row counts, and last-modified times."):
        rows: list[dict] = []
        health = {h["path"]: h for h in data_layer.data_health()}
        for rel in data_layer.CANONICAL_SOURCES:
            h = health.get(rel, {"exists": False, "rows": None, "mtime": None})
            fresh = data_layer.source_freshness(rel)
            if not h.get("exists"):
                state_txt, color = "missing", "negative"
            elif not h.get("readable"):
                state_txt, color = "unreadable", "negative"
            elif fresh.get("stale"):
                state_txt, color = "stale", "warning"
            else:
                state_txt, color = "ok", "positive"
            rows.append({
                "path": rel,
                "rows": "" if h.get("rows") is None else h["rows"],
                "mtime": h.get("mtime") or "—",
                "status": state_txt,
                "status_color": color,
            })
        columns = [
            {"name": "path", "label": "Source", "field": "path", "align": "left"},
            {"name": "rows", "label": "Rows", "field": "rows", "align": "left"},
            {"name": "mtime", "label": "Last modified (UTC)", "field": "mtime", "align": "left"},
            {"name": "status", "label": "Status", "field": "status", "align": "left"},
        ]
        with table_wrap():
            table = ui.table(columns=columns, rows=rows, row_key="path",
                             pagination={"rowsPerPage": 0}).classes("w-full").props("flat")
            table.add_slot("body-cell-status", """
                <q-td key="status" :props="props">
                  <q-badge outline dense :color="props.row.status_color"
                    :label="props.row.status" />
                </q-td>
            """)


# ------------------------------------------------- task 3.3 real pages
def _render_analytics():
    from ui.pages_3_3 import render_analytics

    render_analytics()


def _render_companies():
    from ui.pages_3_3 import render_company_research

    render_company_research()


def _render_resume_page():
    from ui.pages_3_3 import render_resume_page

    render_resume_page()


def _render_settings():
    from ui.pages_3_3 import render_settings_page

    render_settings_page()


def _render_profile_page():
    from ui.pages_profile import render_profile

    render_profile()


# /insights: analytics + company research under one shell (spec 003 §4.1 #6).
# /analytics and /companies keep rendering their own pages until T4 rehomes them.
TASK33_PAGES = {
    "/analytics": ("Analytics", _render_analytics),
    "/companies": ("Company Research", _render_companies),
    "/resume": ("Resume", _render_resume_page),
    "/settings": ("Settings", _render_settings),
    "/profile": ("Profile", _render_profile_page),
}


@ui.page("/insights")
def insights():  # pragma: no cover - requires running server
    page_shell("Insights", "Analytics and company research in one place.")
    _render_analytics()
    _render_companies()


def _task33_page(target: str, title: str, renderer) -> None:
    """Factory so ``page`` binds its own ``title``/``renderer`` (no late binding)."""
    @ui.page(target)
    def page(title: str = title, renderer=renderer):  # pragma: no cover - requires running server
        page_shell(title)
        renderer()


def _placeholder_page(title: str):
    @ui.page(f"/{title.lower().replace(' ', '_').replace('&', 'and')}")
    def page(title: str = title):  # pragma: no cover - requires running server
        page_shell(title)
        empty_state("Coming soon.", icon="construction")

    return page


def build_app() -> None:
    """Register routes exactly once.

    Pages and redirects declared above (``_OWNED_ROUTES``) are already
    registered via decorators; this registers the remaining PAGES entries —
    real 3.3 renderers where available, placeholders otherwise. Re-running is
    safe: already-owned targets are skipped so no path is registered twice.
    """
    registered = set(_OWNED_ROUTES)
    for _, target, _icon in PAGES[1:]:
        if target in registered:
            continue
        if target in TASK33_PAGES:
            title, renderer = TASK33_PAGES[target]
            _task33_page(target, title, renderer)
        else:
            label = next(lbl for lbl, tgt, _i in PAGES if tgt == target)
            _placeholder_page(label)
        registered.add(target)


build_app()

# Serve tailored resume packages over HTTP so resume.pdf / cover_letter.pdf
# links on the Resume page open directly in a new browser tab. The directory
# is personal data (private repo) — create it if absent so fresh clones and
# the public engine repo boot cleanly.
_applications_dir = data_layer.applications_dir()
_applications_dir.mkdir(parents=True, exist_ok=True)
app.add_static_files("/resumes", str(_applications_dir))


def main() -> None:  # pragma: no cover - server entry point
    import os

    ui.run(
        title=TITLE,
        dark=True,
        port=8080,
        show=False,
        reload=os.environ.get("JOBHUNT_DEV", "").lower() in {"1", "true", "yes"},
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
