"""Unified Runs page: every workflow run — agent and script, UI or cron."""

from __future__ import annotations

from nicegui import ui

from engine.run_manager import get_manager
from engine.workflows import WORKFLOWS, AGENT
from ui.components import page_timer, section_card, table_wrap

STATUS_COLORS = {
    "RUNNING": "primary",
    "QUEUED": "grey-6",
    "STARTING": "grey-6",
    "WAITING_FOR_AUTH": "warning",
    "WAITING_FOR_USER": "warning",
    "SUCCEEDED": "positive",
    "FAILED": "negative",
    "CANCELLED": "grey-7",
    "INTERRUPTED": "warning",
}


def render_runs_page() -> None:
    manager = get_manager()

    with section_card(
            "Agent Workflows",
            "Canonical Hermes-agent workflows. UI clicks and cron fires run "
            "the identical workflow definition; one live run per workflow.",
    ):
        for name, wf in WORKFLOWS.items():
            if not wf.is_agent:
                continue
            with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
                from ui.triggers import AgentWorkflowPanel
                AgentWorkflowPanel(name)

    # ---------------------------------------------------------- runs table
    columns = [
        {"name": "workflow", "label": "Workflow", "field": "workflow",
         "align": "left"},
        {"name": "execution_type", "label": "Execution", "field":
         "execution_type", "align": "left"},
        {"name": "trigger", "label": "Trigger", "field": "trigger",
         "align": "left"},
        {"name": "status", "label": "Status", "field": "status",
         "align": "left"},
        {"name": "agent_session_id", "label": "Agent session", "field":
         "agent_session_id", "align": "left"},
        {"name": "browser_session_id", "label": "Browser", "field":
         "browser_session_id", "align": "left"},
        {"name": "started_at", "label": "Started (UTC)", "field":
         "started_at", "align": "left"},
        {"name": "finished_at", "label": "Finished (UTC)", "field":
         "finished_at", "align": "left"},
    ]

    container = ui.column().classes("w-full")

    def refresh_table() -> None:
        if container.is_deleted:
            return
        rows = []
        for record in manager.list_runs(limit=50):
            status = record["status"]
            rows.append({
                **{c["name"]: record.get(c["name"]) or "—" for c in columns},
                "run_id": record["run_id"],
                "status_color": STATUS_COLORS.get(status, "grey-6"),
                "live": status in ("RUNNING", "QUEUED", "STARTING",
                                   "WAITING_FOR_AUTH", "WAITING_FOR_USER"),
            })
        container.clear()
        with container:
            with table_wrap():
                table = ui.table(columns=columns, rows=rows,
                                 row_key="run_id",
                                 pagination={"rowsPerPage": 15}
                                 ).classes("w-full").props("flat")
                table.add_slot("body-cell-status", """
                    <q-td key="status" :props="props">
                      <q-badge outline dense
                        :color="props.row.status_color"
                        :label="props.row.status" />
                    </q-td>
                """)
                table.on("rowClick", lambda e: show_detail(e.args))

    detail_card = ui.column().classes("w-full")

    def show_detail(run_id) -> None:
        try:
            record = manager.get(str(run_id))
        except KeyError:
            # Not reattached in memory this session; read from history.
            for candidate in manager.list_runs(limit=500):
                if candidate["run_id"] == str(run_id):
                    record = candidate
                    break
            else:
                ui.notify(f"run {run_id} not found", type="warning")
                return
        detail_card.clear()
        with detail_card, section_card(f"Run {record['run_id']}",
                                       record.get("current_goal") or ""):
            with ui.grid(columns=2).classes("w-full gap-2"):
                for key in ("workflow", "execution_type", "trigger",
                            "status", "agent_session_id",
                            "browser_session_id", "pid", "exit_code",
                            "created_at", "finished_at", "result", "error"):
                    ui.label(key).classes("text-caption text-bold")
                    ui.label(str(record.get(key) or "—")).classes(
                        "text-caption break-all")
            log_lines = manager.tail(record["run_id"], 200)
            ui.label("Logs").classes("text-caption text-bold q-mt-sm")
            ui.label("\n".join(log_lines) or "(no logs)").classes(
                "text-caption").style(
                "white-space: pre-wrap; font-family: monospace; "
                "user-select: text; max-height: 320px; overflow: auto")
            if record["status"] in ("RUNNING", "STARTING", "QUEUED",
                                    "WAITING_FOR_AUTH", "WAITING_FOR_USER"):
                def _stop(rid=record["run_id"]):
                    manager.cancel(rid)
                    ui.notify(f"cancel requested: {rid}")
                    refresh_table()
                    show_detail(rid)
                ui.button("Stop", icon="stop", color="negative",
                          on_click=_stop).props("outline dense")

    page_timer(3.0, refresh_table)
    refresh_table()
