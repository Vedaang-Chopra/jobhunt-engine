"""Right People page (/right-people) — drop a link, track who to connect with.

Sections:
1. Add company card — paste a job URL, LinkedIn post, or company name;
   resolves it against the jobs table / companies registry and opens the
   company's people workspace.
2. Company directory — every tracked company with people counts, email
   pattern status, and report dates; click through to filter people.
3. People table — the selected company's merged people (directory +
   contacts), filterable by search / degree / status, each row with the
   company email-format candidate and a one-click LinkedIn link.

Nothing on this page sends anything: adding rows and drafting notes are
write-to-CSV-only; actual outreach stays manual (human-in-the-loop, rule 10).
"""
from __future__ import annotations

import sys
from pathlib import Path

from nicegui import ui

from ui import data as data_layer
from ui.components import (
    empty_state,
    filter_bar,
    kpi_grid,
    section_card,
    table_wrap,
)

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import right_people_lib  # noqa: E402  (scripts dir on path above)

PATTERN_COLORS = {"confirmed": "positive", "unverified": "warning",
                  "guessed": "grey-6", "unknown": "grey-6"}

_TRUNCATE_CSS = (
    "display:inline-block;max-width:{w}px;overflow:hidden;"
    "text-overflow:ellipsis;white-space:nowrap"
)


def _add_slot_trunc(table, col: str, width: int) -> None:
    """Truncated cell text with the full value on hover; em-dash when empty."""
    table.add_slot(f"body-cell-{col}", f"""
        <q-td key="{col}" :props="props">
          <span v-if="props.value" class="text-caption"
                style="{_TRUNCATE_CSS.format(w=width)}"
                :title="props.value">{{{{ props.value }}}}</span>
          <span v-else class="text-grey-5">—</span>
        </q-td>
    """)


def render_right_people_page(company_slug: str = "") -> None:
    """Full /right-people workspace. ``company_slug`` preselects a company
    (deep link ?company=<slug>)."""
    companies = data_layer.right_people_companies()
    selected = data_layer.right_people_company(company_slug) if company_slug \
        else None

    # ---------------------------------------------------------- add company
    with section_card(
            "Track a company",
            "Paste a job posting URL, a LinkedIn post link, or just type a "
            "company name — it resolves against your jobs table and the "
            "companies registry, then opens the people workspace below."):
        state: dict = {"link": ""}

        async def _add():
            raw = (state["link"] or "").strip()
            if not raw:
                ui.notify("Paste a job URL, LinkedIn link, or company name "
                          "first.", type="warning")
                return
            flag = "--job-url" if raw.startswith("http") else "--company"
            try:
                target = right_people_lib.resolve_target(flag, raw)
            except Exception as exc:  # noqa: BLE001 - surface to the user
                ui.notify(f"Could not resolve {raw!r}: {exc}",
                          type="negative")
                return
            ui.notify(f"Resolved: {target.get('company')} "
                      f"({target.get('company_slug')})", type="positive")
            ui.navigate.to(
                f"/right-people?company={target.get('company_slug')}")

        link_input = ui.input(
            "Job URL / LinkedIn post / company name",
            placeholder="https://…  ·  linkedin.com/posts/…  ·  Scale AI",
        ).classes("w-full").props("dense outlined clearable")
        link_input.bind_value_to(state, "link")
        link_input.on("keydown.enter", _add)
        ui.button("Track this company", icon="person_search", on_click=_add) \
            .props("unelevated color=primary")
        if not companies:
            empty_state("No companies tracked yet — paste a link above to "
                        "start.", icon="group_add")

    # ------------------------------------------------------------- directory
    total_people = sum(c["people_count"] for c in companies)
    total_email = sum(c["with_email"] for c in companies)
    confirmed = sum(1 for c in companies
                    if c["email_pattern_status"] == "confirmed")
    kpi_grid([
        (str(len(companies)), "Companies tracked", "corporate_fare",
         "accent"),
        (str(total_people), "People in directories", "group", "info"),
        (str(total_email), "With an email on file", "mail", "positive"),
        (str(confirmed), "Confirmed email formats", "mark_email_read",
         "warning"),
    ])

    with section_card(
            "Companies",
            "Every company with a people directory. Click a company to "
            "filter the people table below."):
        if not companies:
            empty_state("Nothing tracked yet.", icon="inbox")
        else:
            with table_wrap():
                table = ui.table(
                    columns=[
                        {"name": "company", "label": "Company", "field":
                         "company", "sortable": True, "align": "left"},
                        {"name": "people", "label": "People", "field":
                         "people_count", "sortable": True},
                        {"name": "email", "label": "With email", "field":
                         "with_email", "sortable": True},
                        {"name": "pattern", "label": "Email format",
                         "field": "email_pattern", "align": "left"},
                        {"name": "status", "label": "Format status",
                         "field": "email_pattern_status", "sortable": True},
                        {"name": "updated", "label": "Last updated",
                         "field": "report_date", "sortable": True},
                    ],
                    rows=[{
                        "company": c["company"],
                        "people_count": c["people_count"],
                        "with_email": c["with_email"],
                        "email_pattern": c["email_pattern"] or "—",
                        "email_pattern_status": c["email_pattern_status"],
                        "report_date": c["report_date"] or "—",
                        "slug": c["slug"],
                    } for c in companies],
                    row_key="slug",
                ).classes("w-full").props("flat dense")
                table.add_slot("body-cell-company", """
                    <q-td key="company" :props="props">
                      <a href="" @click.prevent="
                         $parent.$emit('open', props.row)"
                         style="text-decoration: underline; cursor:
                         pointer">{{ props.value }}</a>
                    </q-td>
                """)
                table.add_slot("body-cell-pattern", """
                    <q-td key="pattern" :props="props">
                      <q-badge v-if="props.row.email_pattern"
                               outline dense>{{ props.value }}</q-badge>
                      <span v-else class="text-grey-5">—</span>
                    </q-td>
                """)
                table.add_slot("body-cell-status", """
                    <q-td key="status" :props="props">
                      <q-badge :color="props.row.status_color" outline dense>
                        {{ props.value }}</q-badge>
                    </q-td>
                """)
                table.on("open", lambda e: ui.navigate.to(
                    f"/right-people?company={e.args.get('slug')}"
                    if isinstance(e.args, dict) else "/right-people"))
                for row in table.rows:
                    row["status_color"] = PATTERN_COLORS.get(
                        row["email_pattern_status"], "grey-6")

    # ---------------------------------------------------------------- people
    if selected is None:
        with section_card(
                "People to connect with",
                "Select a company above (or track one with a link) to see "
                "everyone tracked there with contact candidates."):
            empty_state("Pick a company to browse its people.",
                        icon="person_search")
        return

    people = data_layer.right_people_people(selected["slug"])
    pattern_intel = data_layer.right_people_email_pattern(selected["slug"])
    pattern_status = pattern_intel.get("status") or "unknown"

    with ui.row().classes("w-full items-center q-gutter-sm no-wrap") \
            .style("flex-wrap: wrap"):
        ui.badge(selected["company"], color="primary").props("outline dense")
        ui.badge(f"{len(people)} people", color="info") \
            .props("outline dense")
        if pattern_intel.get("pattern"):
            ui.badge(pattern_intel["pattern"],
                     color=PATTERN_COLORS.get(pattern_status, "grey-6")) \
                .props("outline dense").tooltip(
                    "email format: {} — {}".format(
                        pattern_status,
                        pattern_intel.get("source") or "no source"))
        elif pattern_intel.get("error"):
            ui.badge("email intel unavailable", color="grey-6") \
                .props("outline dense").tooltip(pattern_intel["error"])
        ui.space()
        ui.button("Clear selection", icon="close",
                  on_click=lambda: ui.navigate.to("/right-people")) \
            .props("flat dense")

    with section_card(
            f"People at {selected['company']}",
            "Merged from the per-company directory and your contacts. "
            "Email candidates are pattern-derived (format status shown in "
            "the header above); confirmed formats come from observed "
            "addresses in your contacts."):
        filters: dict = {"search": "", "degree": None, "status": None}

        def _options(field: str) -> list[str]:
            return sorted({p[field] for p in people if p[field]})

        def filtered() -> list[dict]:
            out = people
            q = (filters["search"] or "").strip().lower()
            if q:
                out = [p for p in out if q in " ".join(
                    (p["name"], p["title"], p["reason"], p["email"],
                     p["location"])).lower()]
            if filters["degree"]:
                out = [p for p in out if p["degree"] == filters["degree"]]
            if filters["status"]:
                out = [p for p in out if p["status"] == filters["status"]]
            return out

        count_label = ui.label(f"{len(people)} people").classes(
            "text-caption text-grey-6")
        table_container = ui.column().classes("w-full")

        def refresh() -> None:
            rows = filtered()
            count_label.set_text(f"{len(rows)} of {len(people)} people")
            table_container.clear()
            with table_container:
                if not rows:
                    empty_state("No people match these filters.",
                                icon="person_off")
                    return
                with table_wrap():
                    table = ui.table(
                        columns=[
                            {"name": "name", "label": "Name", "field":
                             "name", "sortable": True, "align": "left"},
                            {"name": "title", "label": "Title", "field":
                             "title", "sortable": True, "align": "left"},
                            {"name": "degree", "label": "Degree", "field":
                             "degree", "sortable": True},
                            {"name": "email", "label": "Email candidate",
                             "field": "email", "align": "left"},
                            {"name": "priority", "label": "Priority",
                             "field": "priority", "sortable": True},
                            {"name": "status", "label": "Status", "field":
                             "status", "sortable": True},
                            {"name": "reason", "label": "Why connect",
                             "field": "reason", "align": "left"},
                        ],
                        rows=[dict(p) for p in rows],
                        row_key="linkedin_url",
                        pagination={"rowsPerPage": 25},
                    ).classes("w-full").props("flat dense")
                    # Name -> LinkedIn profile link (mailto when no url).
                    table.add_slot("body-cell-name", """
                        <q-td key="name" :props="props">
                          <a v-if="props.row.linkedin_url"
                             :href="props.row.linkedin_url" target="_blank"
                             style="text-decoration: underline">
                             {{ props.value }}</a>
                          <span v-else>{{ props.value }}</span>
                        </q-td>
                    """)
                    _add_slot_trunc(table, "title", 240)
                    table.add_slot("body-cell-email", """
                        <q-td key="email" :props="props">
                          <a v-if="props.value"
                             :href="'mailto:' + props.value"
                             style="text-decoration: underline">
                             {{ props.value }}</a>
                          <span v-else class="text-grey-5">—</span>
                        </q-td>
                    """)
                    table.add_slot("body-cell-priority", """
                        <q-td key="priority" :props="props">
                          <q-badge v-if="props.value" outline dense>
                            {{ props.value }}</q-badge>
                          <span v-else class="text-grey-5">—</span>
                        </q-td>
                    """)
                    table.add_slot("body-cell-status", """
                        <q-td key="status" :props="props">
                          <q-badge outline dense>{{ props.value }}</q-badge>
                        </q-td>
                    """)
                    _add_slot_trunc(table, "reason", 320)

        refresh()

        def _set_filter(key: str):
            """One handler per filter: read the event's new value, store,
            refresh — immune to bind/event ordering."""
            def _handler(e) -> None:
                value = e.args
                if isinstance(value, list) and value:
                    value = value[-1]
                filters[key] = value if isinstance(value, str) else (
                    "" if value is None else str(value))
                refresh()
            return _handler

        with filter_bar():
            ui.input(placeholder="Search name, title, email…") \
                .classes("w-64").props("dense outlined clearable") \
                .on("update:model-value", _set_filter("search"))
            ui.select(options=_options("degree") or ["—"], label="Degree",
                      value=None).classes("w-40") \
                .props("dense outlined clearable") \
                .on("update:model-value", _set_filter("degree"))
            ui.select(options=_options("status") or ["—"], label="Status",
                      value=None).classes("w-40") \
                .props("dense outlined clearable") \
                .on("update:model-value", _set_filter("status"))
