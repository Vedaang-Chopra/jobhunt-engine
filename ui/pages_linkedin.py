"""LinkedIn Posts page — the hiring-post discovery workspace (/linkedin-posts).

Sections:
1. Automation health — every-2h cron status + recent sweep runs.
2. Manual sweeps — feed sweep (stop-after-5-dupes) + adaptive keyword search,
   both CDP-driven against your logged-in Chrome, with live logs.
3. Keyword learning table — per-query yield so the sweep gets smarter.
4. Posts table — canonical tracking/hiring_posts/hiring_posts.csv rows with
   one-click hyperlinks (post opens in a new tab) and per-row actions.

Read-only on LinkedIn: never likes/comments/connects (rule 06).
"""
from __future__ import annotations

import sys

import pandas as pd
from nicegui import ui

from ui import data as data_layer
from ui.components import (
    empty_state,
    filter_bar,
    kpi_grid,
    section_card,
    table_wrap,
)
from ui.runs import RUNS

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]

FEED_COMPONENT = "linkedin_posts_feed"
KEYWORDS_COMPONENT = "linkedin_posts_keywords"

POSTER_TYPE_OPTIONS = [
    ("", "All poster types"),
    ("recruiter", "Recruiters"),
    ("hiring_manager", "Hiring managers"),
    ("engineer_researcher", "Engineers/Researchers"),
]
STATUS_OPTIONS = ["new", "reviewed", "connected", "dismissed"]
ROLE_FAMILY_OPTIONS = [
    ("", "All families"), ("agentic_ai", "Agentic AI"),
    ("ml_training_arch", "ML Training/Arch"), ("applied_ml", "Applied ML"),
    ("agent_reasoning", "Agent Reasoning"), ("eval_inference", "Eval & Inference"),
    ("ai_security", "AI Security"), ("other", "Other"),
]
TABLE_COLUMNS = [
    ("posted_date", "Posted"),
    ("poster_name", "Poster"),
    ("company", "Company"),
    ("roles_mentioned", "Roles"),
    ("priority", "Priority"),
    ("role_family", "Family"),
    ("status", "Status"),
]


def _sweep_cmd(mode: str, queries: int) -> list[str]:
    cmd = [sys.executable, str(REPO / "scripts" / "linkedin_posts_sweep.py")]
    if mode == "feed":
        return cmd + ["feed"]
    return cmd + ["keywords", "--queries", str(queries)]


def _start_run(component: str, cmd: list[str]) -> None:
    try:
        RUNS.start(component, cmd)
        ui.notify("Sweep started — watch the log below.", type="positive")
    except RuntimeError as exc:
        ui.notify(str(exc), type="warning")


def _automation_health() -> None:
    cron = data_layer.cron_health()
    with section_card(
            "Automation health",
            "Every-2h cruncher (linkedin-people-posts-2h) runs the feed pass "
            "+ web-search rotation automatically; manual buttons below are for "
            "on-demand sweeps."):
        if not cron.get("available"):
            empty_state("Cron store not found — automation state unknown.",
                        icon="schedule")
        else:
            lag = cron.get("heartbeat_lag_s")
            hb_ok = lag is not None and lag < 600
            hb_txt = ("scheduler heartbeat OK" if hb_ok
                      else f"heartbeat stale ({lag}s)" if lag is not None
                      else "scheduler heartbeat unknown")
            with ui.row().classes("w-full items-center q-gutter-sm flex-wrap"):
                ui.badge(hb_txt,
                         color="positive" if hb_ok else "negative").props(
                    "outline dense")
                for job in cron.get("jobs", []):
                    status = job["last_status"] or "never run"
                    color = ("positive" if job.get("healthy")
                             else "warning" if status == "error" else "grey-6"
                             ) if job["enabled"] else "grey-6"
                    ui.badge(f"{job['name']}: {job['schedule']} · {status} · "
                             f"next {str(job.get('next_run_at') or '')[:16]}",
                             color=color).props("outline dense")

    runs = data_layer.recent_post_sweep_runs(limit=6)
    with section_card("Recent sweep runs",
                      "lhp_* = 2h cron · lpf_* = feed sweep · lpk_* = keyword sweep."):
        if not runs:
            empty_state("No sweep runs logged yet.", icon="history")
            return
        cols = [{"name": c, "label": c.replace("_", " ").title(), "field": c,
                 "align": "left"} for c in runs[0]]
        rows = [{k: ("" if v is None or str(v) == "nan" else str(v))
                 for k, v in r.items()} for r in runs]
        with table_wrap():
            ui.table(columns=cols, rows=rows, row_key="run_id",
                     pagination={"rowsPerPage": 0}).classes("w-full").props("flat")


def _sweep_controls() -> None:
    feed_status: dict = {"notified": None}
    kw_queries: dict = {"n": 6}
    component_labels = {FEED_COMPONENT: "Feed sweep",
                        KEYWORDS_COMPONENT: "Keyword sweep"}

    def _poll(component: str, label: ui.label, btn: ui.button) -> None:
        if btn.is_deleted or label.is_deleted:
            return
        run_id = RUNS.latest(component)
        if run_id is None:
            return
        st = RUNS.status(run_id)
        lines = RUNS.tail(run_id, 5)
        tail_txt = ("\n" + "\n".join(lines[-3:])) if lines else ""
        if st["state"] == "running":
            label.set_text(f"{run_id}: running{tail_txt}")
            btn.disable()
            return
        btn.enable()
        rc = st.get("returncode")
        label.set_text(f"{run_id}: {st['state']} (exit {rc}){tail_txt}")
        if feed_status["notified"] == run_id:
            return
        feed_status["notified"] = run_id
        if rc == 0:
            ui.notify(f"{component_labels.get(component, component)} "
                      f"finished — new posts appended.", type="positive")
            ui.navigate.reload()

    # --- Feed sweep ---------------------------------------------------------
    with section_card(
            "Feed sweep",
            "Scrolls your LinkedIn home feed and extracts hiring posts until "
            "5 already-seen posts in a row appear (or the scroll cap). "
            "Read-only — never likes, comments, or connects. Requires Chrome "
            "running with --remote-debugging-port=9222."):
        with ui.row().classes("w-full items-center q-gutter-sm flex-wrap"):
            feed_btn = ui.button("Sweep my feed", icon="swipe_up",
                                 on_click=lambda: _start_run(
                                     FEED_COMPONENT,
                                     _sweep_cmd("feed", 0))).props("unelevated")
            ui.badge("stops after 5 dup posts", color="info").props(
                "outline dense")
        feed_log = ui.label("").classes("text-caption text-grey-6") \
            .style("white-space: pre-wrap; font-family: monospace; "
                   "user-select: text")
        ui.timer(1.0, lambda: _poll(FEED_COMPONENT, feed_log, feed_btn))

    # --- Keyword sweep ------------------------------------------------------
    with section_card(
            "Keyword search",
            "Runs LinkedIn post searches (search bar → Posts filter → Past "
            "Week). Query selection adapts: keywords that historically "
            "yielded new posts are tried first."):
        with ui.row().classes("w-full items-center q-gutter-sm flex-wrap"):
            kw_btn = ui.button("Run keyword sweep", icon="search",
                               on_click=lambda: _start_run(
                                   KEYWORDS_COMPONENT,
                                   _sweep_cmd("keywords",
                                              kw_queries["n"]))).props(
                "unelevated")
            ui.number("Queries this run", value=6, min=1, max=12,
                      on_change=lambda e: kw_queries.update(
                          n=int(e.value or 6))).classes("w-32") \
                .props("outlined dense")
        kw_log = ui.label("").classes("text-caption text-grey-6") \
            .style("white-space: pre-wrap; font-family: monospace; "
                   "user-select: text")
        ui.timer(1.0, lambda: _poll(KEYWORDS_COMPONENT, kw_log, kw_btn))


def _keyword_learning() -> None:
    yields = data_layer.keyword_yields()
    with section_card(
            "Keyword learning",
            "Which search phrases actually produce new posts. The keyword "
            "sweep picks the top scorers each run; low-yield phrases sink."):
        if not yields:
            empty_state("No yield history yet — run a keyword sweep to start "
                        "learning.", icon="school")
            return
        cols = [{"name": "query", "label": "Query", "field": "query",
                 "align": "left"},
                {"name": "runs", "label": "Runs", "field": "runs",
                 "align": "left"},
                {"name": "new_posts", "label": "New posts", "field": "new_posts",
                 "align": "left"},
                {"name": "yield_per_run", "label": "Yield/run",
                 "field": "yield_per_run", "align": "left"}]
        with table_wrap():
            ui.table(columns=cols, rows=yields, row_key="query",
                     pagination={"rowsPerPage": 10}).classes("w-full") \
                .props("flat")


def _posts_table() -> None:
    df = data_layer.load_hiring_posts()
    stats = data_layer.hiring_post_stats(df)
    state: dict = {
        "search": "", "poster_type": "", "role_family": "",
        "status": "", "max_age": None, "sort_by": "posted_date",
        "sort_desc": True,
    }

    kpi_grid([
        (str(stats["total"]), "Tracked posts", "rss_feed", "primary"),
        (str(stats["last_7d"]), "New last 7 days", "fiber_new", "accent"),
        (str(stats["high_priority"]), "High priority (recruiter/HM)",
         "priority_high", "warning"),
        (str(stats["new"]), "Awaiting review", "pending_actions", "info"),
    ])

    with section_card("Hiring posts", "Click a poster name or the post link "
                                        "to open it in a new tab. Row actions "
                                        "update the canonical CSV in place."):

        def current_rows() -> list[dict]:
            filtered = data_layer.filter_hiring_posts(
                df, state["search"], state["poster_type"],
                state["role_family"], state["status"], state["max_age"])
            col = state["sort_by"]
            if col in filtered.columns:
                ascending = not state["sort_desc"]
                series = filtered[col].astype(str)
                numbers = pd.to_numeric(series, errors="coerce")
                key = numbers if numbers.notna().any() else \
                    series.fillna("").str.lower()
                filtered = (filtered.assign(_k=key)
                            .sort_values("_k", ascending=ascending,
                                         na_position="last")
                            .drop(columns="_k"))
            return filtered.fillna("").to_dict("records")

        def refresh() -> None:
            rows = current_rows()
            count_label.set_text(f"{len(rows)} of {len(df)} posts")
            container.clear()
            with container:
                if not rows:
                    empty_state("No posts match the current filters.",
                                icon="rss_feed")
                    return
                columns = [{"name": n, "label": lbl, "field": n,
                            "sortable": False, "align": "left"}
                           for n, lbl in TABLE_COLUMNS]
                with table_wrap():
                    table = ui.table(columns=columns, rows=rows,
                                     row_key="post_id",
                                     pagination={"rowsPerPage": 25}
                                     ).classes("w-full").props("flat")
                # Poster name -> clickable new-tab link to the post/profile.
                table.add_slot("body-cell-poster_name", """
                    <q-td key="poster_name" :props="props">
                      <a v-if="props.row.post_url" :href="props.row.post_url"
                         target="_blank" style="text-decoration: underline">
                        {{ props.value }}</a>
                      <span v-else>{{ props.value }}</span>
                    </q-td>
                """)
                # Application URL column: compact "Apply" hyperlink.
                table.add_slot("body-cell-company", """
                    <q-td key="company" :props="props">
                      {{ props.value }}
                      <a v-if="props.row.application_url"
                         :href="props.row.application_url" target="_blank"
                         style="margin-left: 6px; font-size: 11px;
                                text-decoration: underline">[apply]</a>
                    </q-td>
                """)
                table.add_slot("body-cell-priority", """
                    <q-td key="priority" :props="props">
                      <q-badge outline dense
                        :color="props.value === 'high' ? 'orange' : 'grey-6'"
                        :label="props.value" />
                    </q-td>
                """)

        def _live(key: str, e):
            value = getattr(e, "value", None)
            if value is None:
                value = getattr(e, "args", e)
            if key == "max_age":
                try:
                    state[key] = float(value) if value not in ("", None) else None
                except (TypeError, ValueError):
                    state[key] = None
            elif isinstance(value, (list, tuple)):
                state[key] = str(value[0]) if value else ""
            else:
                state[key] = "" if value in (None, "All") else str(value)
            refresh()

        def _clear():
            state.update(search="", poster_type="", role_family="",
                         status="", max_age=None)
            search_input.set_value(None)
            type_select.set_value("")
            family_select.set_value("")
            status_select.set_value("")
            age_input.set_value(None)
            refresh()

        with filter_bar():
            with ui.row().classes("w-full q-gutter-sm items-center no-wrap"):
                search_input = ui.input(
                    placeholder="Search poster, company, roles…").classes(
                    "grow").props(
                    "outlined dense clearable aria-label='Search posts'"
                ).on("update:model-value", lambda e: _live("search", e))
                type_select = ui.select(
                    dict(POSTER_TYPE_OPTIONS), label="Poster type", value="",
                    on_change=lambda e: _live("poster_type", e),
                ).classes("col-grow").props("outlined dense clearable")
                family_select = ui.select(
                    dict(ROLE_FAMILY_OPTIONS), label="Role family", value="",
                    on_change=lambda e: _live("role_family", e),
                ).classes("col-grow").props("outlined dense clearable")
                status_select = ui.select(
                    STATUS_OPTIONS, label="Status", value=None,
                    on_change=lambda e: _live("status", e),
                ).classes("col-grow").props("outlined dense clearable")
                age_input = ui.number(
                    label="Max age (days)", format="%.0f",
                    on_change=lambda e: _live("max_age", e),
                ).classes("col-grow").props("outlined dense")
                ui.button("Clear", icon="filter_alt_off",
                          on_click=_clear).props("outline dense")

        count_label = ui.label("").classes("text-caption text-grey-6")
        container = ui.column().classes("w-full")
        refresh()


def render_linkedin_posts_page() -> None:
    """Entry point registered by ui/app.py at /linkedin-posts."""
    _automation_health()
    _sweep_controls()
    _keyword_learning()
    _posts_table()
