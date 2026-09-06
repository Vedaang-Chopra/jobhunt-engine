"""Profile page (/profile): canonical profile view + AI-assisted ingest.

Layout:
  1. Identity header card (name / contact / links / visa) with click-to-edit.
  2. Section cards (experience, skills, …) rendered as readable key/value
     rows; clicking a card opens a right-side drawer with full details,
     per-field inline editing, and a validate-then-write save.
  3. Upload/Paste ingestion backed by ``scripts/ingest_lib.py`` plus an LLM
     placement engine (``scripts/ingest_ai.py``): each inbox item gets an
     AI proposal (target section + extracted YAML) that the user reviews in
     a diff dialog before anything is merged into canonical YAML.

Backward compatibility: ``load_sections``, ``make_save_handler``,
``render_section_editor``, ``_diff_preview``, ``EMPTY_STATES`` and
``render_upload_card`` keep their existing signatures/behavior.
"""

from __future__ import annotations

import difflib

import yaml
from nicegui import ui
from nicegui import run

from scripts import config_lib
from scripts import ingest_lib
from scripts import ingest_ai
from ui.components import confirm_dialog, empty_state, section_card
from ui.data import clear_load_issues, get_load_issues
from ui.states import ViewState, state_view

ALLOWED = ".pdf,.docx,.txt,.md,.yaml,.yml,.csv"

EMPTY_STATES = {
    "profile": "No canonical profile yet. Upload documents or paste text to "
               "build your profile — accepted items appear here as unverified "
               "claims.",
    "inbox": "Inbox is empty — upload documents or paste text to build your "
             "profile.",
}

SECTION_ICONS = {
    "experience": "work", "education": "school", "skills": "psychology",
    "projects": "terminal", "accomplishments": "emoji_events",
    "publications_patents": "article", "research": "science",
    "preferences": "tune", "application_answers": "fact_check",
}

# Fields shown in the identity header, read from any section's YAML.
HEADER_KEYS = [
    ("full_name", "Name"), ("name", "Name"), ("email", "Email"),
    ("phone", "Phone"), ("location", "Location"),
    ("linkedin", "LinkedIn"), ("github", "GitHub"),
    ("visa_status", "Visa"), ("work_authorization", "Work auth"),
]


def load_sections(root=None) -> list[tuple[str, str]]:
    """(section_name, raw_yaml_text) pairs for every profile_info YAML file."""
    base = ingest_lib.profile_info_dir(root)
    sections: list[tuple[str, str]] = []
    if not base.is_dir():
        return sections
    for path in sorted(p for p in base.rglob("*.yaml") if p.is_file()
                       and "inbox" not in p.parts):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = path.relative_to(base)
        name = str(rel.with_suffix("")) if rel.suffix == ".yaml" else str(rel)
        sections.append((name, text))
    return sections


def _flatten(value, prefix: str = "") -> list[tuple[str, str, str]]:
    """Yield (path, label, display_value) rows from nested YAML values."""
    rows: list[tuple[str, str, str]] = []
    skip = {"provenance", "verification", "verified"}
    if isinstance(value, dict):
        for key, val in value.items():
            if key in skip or key == "_ai_ingest":
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(val, (dict, list)):
                rows.extend(_flatten(val, path))
            else:
                rows.append((path, key, "" if val is None else str(val)))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            path = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                rows.extend(_flatten(item, path))
            else:
                rows.append((path, f"item {i}", "" if item is None else str(item)))
    return rows


def _provenance_badge(entry: dict) -> None:
    marker = str(
        entry.get("provenance")
        or entry.get("verification")
        or entry.get("verified")
        or ""
    )
    if not marker:
        return
    color = "warning" if "unverified" in marker.lower() else "positive"
    ui.badge(str(marker), color=color).props("outline dense")


# ---------------------------------------------------------------------------
# Section drawer: rendered detail view + per-field editing
# ---------------------------------------------------------------------------

class SectionDrawer:
    """Right-side drawer showing one section with editable fields."""

    def __init__(self, name: str, text: str, drawer=None):
        self.name = name
        self.text = text
        self.dirty = False
        self.parse_error = None
        if drawer is None:
            # Fallback for standalone/test use. On the live page always pass
            # the page-level drawer: NiceGUI requires layout elements like
            # right_drawer to be direct children of the page content, so
            # creating one inside a click handler's slot raises
            # RuntimeError and the drawer never opens.
            self.drawer = ui.right_drawer(value=False, bordered=True).props(
                'behavior="persistent" breakpoint=0 :width=560'
            ).classes("jh-drawer").style("max-width: 92vw")
        else:
            self.drawer = drawer
        self._build()

    def _build(self) -> None:
        parsed = self._parse()
        self.drawer.clear()  # repopulate the shared page-level drawer
        with self.drawer, ui.column().classes("q-pa-lg w-full gap-1"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(self.name.replace("_", " ").title()).classes(
                    "text-h6 text-weight-bold jh-section-title")
                ui.button(icon="close", on_click=self.close).props("flat round dense")
            if not parsed:
                empty_state("(empty section)", icon="inbox")
            self._render_fields(parsed)
            ui.separator().classes("q-my-md")
            self._build_editor(parsed)

    def _parse(self) -> dict:
        try:
            parsed = yaml.safe_load(self.text) or {}
        except yaml.YAMLError as exc:
            self.parse_error = str(exc)
            return {}
        self.parse_error = None
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    def _render_fields(self, parsed: dict) -> None:
        rows = _flatten(parsed)
        if not rows and not parsed:
            return
        with ui.element("div").classes("w-full"):
            if isinstance(parsed, dict):
                for top_key, value in parsed.items():
                    if top_key == "_ai_ingest":
                        continue
                    ui.label(str(top_key).replace("_", " ").title()).classes(
                        "text-subtitle1 text-weight-medium q-mt-md q-mb-xs")
                    entries = value if isinstance(value, list) else [value]
                    for entry in entries:
                        self._render_entry(entry)
            else:
                self._render_entry(parsed)

    def _render_entry(self, entry) -> None:
        with ui.card().classes("w-full q-pa-sm jh-card"):
            if isinstance(entry, dict):
                _provenance_badge(entry)
                for key, val in entry.items():
                    if key in {"provenance", "verification", "verified"}:
                        continue
                    label = str(key).replace("_", " ").title()
                    text_val = yaml.safe_dump(val, sort_keys=False,
                                              allow_unicode=True).strip() \
                        if isinstance(val, (dict, list)) else str(val)
                    with ui.row().classes("w-full items-start q-py-xs").style(
                            "gap: 12px"):
                        ui.label(label).classes("text-caption text-grey-6").style(
                            "min-width: 120px; flex-shrink: 0; padding-top: 3px")
                        ui.label(text_val).classes("text-body2").style(
                            "white-space: pre-wrap; flex: 1; word-break: break-word")
            else:
                ui.label(str(entry)).classes("text-body2").style(
                    "white-space: pre-wrap")

    def _build_editor(self, parsed: dict) -> None:
        ui.label("Edit raw YAML").classes("text-subtitle2 text-grey-6")
        self.area = ui.textarea(self.text).classes("w-full").props(
            "outlined dense input-class='font-mono' type=textarea")
        self.area.on("update:model-value", self._mark_dirty)

        def _confirm_flow(**kwargs):
            confirm_dialog(**kwargs).open()

        with ui.row().classes("q-mt-sm"):
            ui.button(
                "Save changes", icon="save",
                on_click=make_save_handler(self.name, self.area,
                                           confirm=_confirm_flow,
                                           original_text=self.text),
            ).props("unelevated dense")
            self.revert_btn = ui.button(
                "Revert", icon="undo",
                on_click=self._revert).props("flat dense")

    def _mark_dirty(self, _e=None) -> None:
        self.dirty = True
        try:
            self.revert_btn.classes(replace="text-orange")
        except Exception:  # noqa: BLE001
            pass

    def _revert(self) -> None:
        self.area.value = self.text
        self.dirty = False
        ui.notify("Reverted to saved version", type="info")

    async def open(self) -> None:
        self.drawer.set_value(True)

    def close(self) -> None:
        self.drawer.set_value(False)


# ---------------------------------------------------------------------------
# Save handler (validate-then-write) — kept API-compatible
# ---------------------------------------------------------------------------

def _diff_preview(original: str, new_text: str, limit: int = 20) -> str:
    """Short unified diff (original vs normalized save text), ~20 lines."""
    diff_lines = list(difflib.unified_diff(
        original.splitlines(), new_text.splitlines(),
        fromfile="original", tofile="saved", lineterm=""))
    if not diff_lines:
        return "(no textual differences)"
    shown = "\n".join(diff_lines[:limit])
    extra = len(diff_lines) - limit
    if extra > 0:
        shown += f"\n… ({extra} more diff lines)"
    return shown


def make_save_handler(section: str, area, notify=ui.notify, write=None,
                      base_dir=None, confirm=None, original_text=None):
    """Validate-then-write handler factory for one section's textarea.

    Parses the textarea content as YAML before accepting; invalid YAML is
    rejected with a negative notification and nothing is written. When
    ``confirm`` is provided the write is deferred into the dialog's
    on_confirm callback with a unified-diff preview of the change.
    """
    _original = original_text if original_text is not None else ""

    def _write(path, text):  # default real writer (overridable in tests)
        path.write_text(text, encoding="utf-8")

    def handler() -> None:
        try:
            parsed = ingest_lib.validate_yaml(area.value or "")
        except (ValueError, yaml.YAMLError) as exc:
            notify(f"Invalid YAML — not saved: {exc}", type="negative")
            return
        target = (base_dir or ingest_lib.profile_info_dir()) / f"{section}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        save_text = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)

        def _do_write() -> None:
            (write or _write)(target, save_text)
            notify(f"Saved {target.name} — reloading", type="positive")
            try:  # reload only when served by a live NiceGUI app
                from nicegui import core
                if core.loop is not None:
                    ui.navigate.reload()
            except Exception:  # noqa: BLE001 - test/offline context
                pass

        if confirm is None:
            _do_write()
            return
        diff = _diff_preview(_original, save_text)
        confirm(
            title=f"Save section {section}",
            body=f'"""\n{diff}\n"""\n\nWrites {target}.',
            danger=False,
            confirm_label="Save section",
            on_confirm=_do_write,
        )

    return handler


def render_section_editor(name: str, initial_text: str):
    area = ui.textarea(initial_text).classes("w-full").props(
        "outlined dense input-class='font-mono'")

    def _confirm_flow(**kwargs):
        dialog = confirm_dialog(**kwargs)
        dialog.open()

    ui.button(
        "Save section", icon="save",
        on_click=make_save_handler(name, area, confirm=_confirm_flow,
                                   original_text=initial_text),
    ).props("unelevated dense")
    return area


# ---------------------------------------------------------------------------
# Identity header
# ---------------------------------------------------------------------------

def _collect_header_fields(sections: list[tuple[str, str]]) -> dict:
    """Scan all sections for identity-ish scalar fields."""
    found: dict[str, tuple[str, str]] = {}  # field -> (label, value)
    for name, text in sections:
        try:
            doc = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict):
            continue
        candidates = {k: v for k, v in doc.items()
                      if not isinstance(v, (dict, list)) or k == "identity"}
        pool: dict[str, object] = {}
        for key, val in candidates.items():
            if isinstance(val, dict):  # e.g. identity: {...}
                pool.update(val)
            else:
                pool[key] = val
        for key, label in HEADER_KEYS:
            if key in found:
                continue
            val = pool.get(key)
            if isinstance(val, str) and val.strip() and "@" not in key \
                    and len(val) < 200:
                found[key] = (label, val.strip())
    # Prefer application_answers identity block if present.
    for name, text in sections:
        if name != "preferences/application_answers":
            continue
        try:
            ident = (yaml.safe_load(text) or {}).get("identity") or {}
        except yaml.YAMLError:
            break
        mapping = {"full_name": "full_name", "email": "email",
                   "phone": "phone", "location": "location",
                   "linkedin": "linkedin", "github": "github"}
        for header_key, ident_key in mapping.items():
            if isinstance(ident.get(ident_key), str) and ident[ident_key].strip():
                label = dict(HEADER_KEYS)[header_key]
                found[header_key] = (label, ident[ident_key].strip())
        break
    return found


def _header_link(label: str, value: str) -> None:
    if value.startswith("http"):
        with ui.row().classes("items-center q-gutter-xs"):
            ui.icon("link").classes("text-caption")
            ui.link(label or value, value, new_tab=True).classes(
                "text-caption jh-link")
    else:
        # ``label`` arrives already formatted as "Label: value" from
        # _split_link_label — do not prefix it a second time.
        with ui.row().classes("items-center q-gutter-xs"):
            ui.icon(
                {"Email": "mail", "Phone": "call", "Location": "place"}.get(
                    label.split(":", 1)[0], "info")).classes("text-caption")
            ui.label(label).classes("text-caption")


def render_identity_header(sections: list[tuple[str, str]]) -> bool:
    """Top-of-page identity summary; returns False when nothing to show."""
    fields = _collect_header_fields(sections)
    name = fields.pop("full_name", None) or fields.pop("name", None)
    if not fields and not name:
        return False
    with section_card("", ""):
        if name:
            ui.label(name[1]).classes("text-h4 text-weight-bold jh-section-title")
        with ui.row().classes("wrap q-gutter-x-md q-gutter-y-xs q-mt-xs"):
            for label, value in sorted(fields.values(),
                                       key=lambda lv: dict(HEADER_KEYS).get(
                                           lv[0], 99) if False else 0):
                _header_link(*_split_link_label(label, value))
    return True


def _split_link_label(label: str, value: str) -> tuple[str, str]:
    """For links show the domain-ish label; for others 'Label: value'."""
    if value.startswith("http"):
        pretty = value.split("//")[-1].rstrip("/")
        return pretty, value
    return f"{label}: {value}", value


# ---------------------------------------------------------------------------
# Ingestion: upload / paste + AI placement review queue
# ---------------------------------------------------------------------------

def _handle_upload(e, log_container: ui.column, refresh_queue=None) -> None:
    for item in e:
        try:
            summary = ingest_lib.process_upload(item.name, item.content.read())
        except Exception as exc:  # noqa: BLE001 - surface per-item failures
            ui.notify(f"{item.name}: {exc}", type="negative")
            continue
        kind = summary["kind"]
        note = "needs manual extraction" if summary["needs_manual"] else kind
        ui.notify(f"Ingested {summary['path']} ({note})", type="positive")
        with log_container:
            ui.label(
                f"{summary['path']}: kind={note}, "
                f"skills={len(summary['entities'].get('skills', []))}, "
                f"emails={len(summary['entities'].get('emails', []))}"
            ).classes("text-caption text-grey")


def _inbox_source_text(name: str) -> str:
    source = ingest_lib.inbox_dir() / Path(name).name
    if source.exists():
        return source.read_text(encoding="utf-8", errors="replace")
    for item in ingest_lib.list_inbox():
        if item["name"] == name:
            return item.get("raw_excerpt", "")
    return ""


from pathlib import Path  # noqa: E402  (used by helpers above)


def _proposal_dialog(proposal: dict, on_done) -> None:
    """Review dialog: rationale + YAML diff against the target section."""
    target = ingest_lib.profile_info_dir() / proposal["target_file"]
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    try:
        merged, added_paths = ingest_ai.merge_yaml(existing,
                                                   proposal["yaml_snippet"])
    except ValueError as exc:
        ui.notify(f"Proposal invalid: {exc}", type="negative")
        on_done(False)
        return
    diff = _diff_preview(existing or "(new file)", merged, limit=40)

    dialog = ui.dialog().props("maximized=false")
    with dialog, ui.card().classes("jh-card").style(
            "width: min(760px, 94vw); max-height: 88vh"):
        with ui.row().classes("w-full items-center q-gutter-sm"):
            ui.badge(proposal["section"], color="primary").props("dense")
            ui.badge(f"confidence {proposal['confidence']:.0%}",
                     color="teal" if proposal["confidence"] >= 0.6 else "warning"
                     ).props("dense outline")
            if proposal["engine"] == "heuristic":
                ui.badge("no LLM — heuristic guess",
                         color="warning").props("dense outline")
            ui.space()
            ui.button(icon="close", on_click=dialog.close).props(
                "flat round dense")
        ui.label(f'AI says this belongs in **{proposal["section"]}**: '
                 f'{proposal["rationale"]}').classes("text-body2")
        ui.separator()
        ui.label("Proposed change").classes(
            "text-subtitle2 text-weight-bold q-mt-xs")
        ui.code(diff).classes("w-full").style(
            "white-space: pre-wrap; font-size: 12px")
        with ui.expansion("Extracted YAML snippet", icon="data_object"):
            ui.code(proposal["yaml_snippet"]).style("font-size: 12px")
        with ui.row().classes("w-full justify-end q-gutter-sm q-mt-sm"):
            ui.button("Discard item", on_click=lambda: (
                _safe_discard(proposal["name"]), dialog.close(), on_done(True)
            )).props("flat negative dense")
            ui.button("Keep in inbox", on_click=dialog.close).props("flat")
            ui.button("Accept & merge", icon="check_circle",

                      on_click=lambda: (_do_accept(), dialog.close()))

    def _do_accept() -> None:
        try:
            tgt = ingest_ai.apply_proposal(proposal)
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Merge failed: {exc}", type="negative")
            return
        ui.notify(f"Merged into {tgt.name}", type="positive")
        on_done(True)

    def _safe_discard(name: str) -> None:
        try:
            ingest_lib.discard_item(name)
        except Exception:  # noqa: BLE001
            pass
        ui.notify(f"Discarded {name}", type="info")

    dialog.open()


def render_review_queue(queue_holder: ui.column) -> None:
    """Pending items with AI placement proposals (async, non-blocking)."""
    pending = ingest_lib.list_inbox()
    queue_holder.clear()
    with queue_holder:
        if not pending:
            empty_state(EMPTY_STATES["inbox"], icon="upload_file")
            return
        ui.label(f"{len(pending)} item(s) awaiting review").classes(
            "text-caption text-grey-6 q-mb-xs")
        for item in pending:
            name = item["name"]
            row = ui.row().classes("w-full items-center q-py-sm").style(
                "border-top: 1px solid var(--border); gap: 10px")
            with row:
                ui.label(name).classes("text-bold").style(
                    "min-width: 200px; word-break: break-all")
                status_label = ui.label("…").classes(
                    "text-caption text-grey").style("flex: 1")
                propose_btn = ui.button("Review placement", icon="auto_awesome"
                                        ).props("dense unelevated primary")
                discard_btn = ui.button("Discard").props(
                    "dense outline negative")

                def _discard(n=name) -> None:
                    ingest_lib.discard_item(n)
                    ui.notify(f"Discarded {n}", type="info")
                    render_review_queue(queue_holder)

                discard_btn.on_click(_discard)

                def _propose(n=name, lbl=status_label, btn=propose_btn) -> None:
                    btn.disable()
                    lbl.text = "Asking the model where this belongs…"
                    lbl.classes(add="text-italic")

                    async def _run() -> None:
                        proposal = await run.io_bound(
                            ingest_ai.propose_placement,
                            n, _inbox_source_text(n))
                        lbl.text = (f'{proposal["engine"]} → '
                                    f'{proposal["section"]} '
                                    f'({proposal["confidence"]:.0%})')
                        btn.enable()
                        if proposal["yaml_snippet"]:
                            _proposal_dialog(proposal, lambda ok:
                                             render_review_queue(queue_holder))
                        else:
                            ui.notify(proposal["rationale"], type="warning")

                    _run()

                propose_btn.on_click(_propose)


def render_upload_card() -> None:
    """Compact upload/paste controls + AI review queue."""
    with section_card("Add to your knowledge bank",
                      "Upload a document or paste text — the model proposes "
                      "where each fact belongs; you approve before anything "
                      "is written to your profile."):
        log_container = ui.column().classes("w-full")

        def _paste_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("jh-card").style(
                    "min-width: min(560px, 92vw)"):
                ui.label("Paste text").classes("text-h6 text-weight-bold")
                area = ui.textarea(
                    "Paste any text (achievement, notes, resume content...)"
                ).classes("w-full").props("outlined dense")
                name_input = ui.input("Name (optional)").classes(
                    "w-full").props("outlined dense")

                def _save() -> None:
                    text = (area.value or "").strip()
                    if not text:
                        ui.notify("Nothing to save.", type="warning")
                        return
                    name = (name_input.value or "").strip() or "pasted_text.txt"
                    if "." not in name:
                        name += ".txt"
                    try:
                        summary = ingest_lib.process_upload(name, text)
                    except Exception as exc:  # noqa: BLE001
                        ui.notify(str(exc), type="negative")
                        return
                    ui.notify(
                        f"Ingested {summary['path']} ({summary['kind']})",
                        type="positive")
                    dialog.close()
                    render_review_queue(queue_holder)

                with ui.row():
                    ui.button("Save to inbox", on_click=_save)
                    ui.button("Cancel", on_click=dialog.close).props("flat")
            dialog.open()

        with ui.row().classes("q-gutter-md items-center"):
            ui.upload(
                label="Upload documents",
                on_upload=lambda e: _handle_upload(e, log_container,
                                                   refresh_queue=None),
                multiple=True,
                auto_upload=True,
            ).props(f"accept='{ALLOWED}' flat color='primary'")
            ui.button("Paste text", icon="paste",
                      on_click=_paste_dialog).props("outline")

    queue_holder = ui.column().classes("w-full")
    render_review_queue(queue_holder)


# ---------------------------------------------------------------------------
# Page body
# ---------------------------------------------------------------------------

def _open_section_drawer_factory(name: str, text: str, drawer):
    async def _open() -> None:
        await SectionDrawer(name, text, drawer=drawer).open()
    return _open


def render_profile() -> None:
    """Page body renderer (called from ui.app inside the shared shell)."""
    clear_load_issues()
    sections = load_sections()
    issues = get_load_issues()

    if issues:
        detail = "\n".join(
            f"{issue.get('path', '?')} — {issue.get('reason', 'unknown')}"
            for issue in issues)
        state_view(ViewState.PARTIAL,
                   message="Some profile files failed to load",
                   detail=detail)

    # Page-level right drawer: NiceGUI only allows layout elements (drawers)
    # as direct children of page content, so it must be created here — not
    # inside a click handler — and reused for every section card. Under the
    # smoke tests the page body is nested in a ui.column(); there creation
    # is deferred to click time instead of failing the render.
    try:
        section_drawer: ui.right_drawer | None = ui.right_drawer(
            value=False, bordered=True).props(
            'behavior="persistent" breakpoint=0 :width=560'
        ).classes("jh-drawer").style("max-width: 92vw")
    except RuntimeError:  # nested slot context (tests) — defer to click
        section_drawer = None

    has_identity = render_identity_header(sections)

    render_upload_card()

    ui.label("Profile sections").classes("text-h5 text-weight-bold q-mt-lg")
    if not sections:
        empty_state(EMPTY_STATES["profile"], icon="person_off")
        return
    if not has_identity:
        ui.label("Tip: add identity fields (name/email/links) so they appear "
                 "in the header.").classes("text-caption text-grey-6")

    grid = ui.element("div").style(
        "display:grid; grid-template-columns:"
        "repeat(auto-fill, minmax(320px, 1fr)); gap:14px; width:100%")
    for name, text in sections:
        with grid:
            parsed = _safe_parse(text)
            count = sum(len(v) if isinstance(v, list) else 1
                        for k, v in (parsed or {}).items() if k != "_ai_ingest")
            with ui.card().classes("jh-card w-full cursor-pointer").style(
                    "border-left: 3px solid var(--accent)").on(
                    "click", _open_section_drawer_factory(name, text,
                                                          section_drawer)):
                with ui.row().classes("w-full items-center no-wrap q-gutter-sm"):
                    ui.icon(SECTION_ICONS.get(name.split("/")[-1],
                                              "description")).classes("text-h5")
                    with ui.column().classes("grow"):
                        ui.label(name.replace("_", " ").title()).classes(
                            "text-subtitle1 text-weight-bold")
                        ui.label(f"{count} entr{'y' if count == 1 else 'ies'}"
                                 ).classes("text-caption text-grey-6")
                    ui.icon("chevron_right").classes("text-grey")


def _safe_parse(text: str) -> dict | None:
    try:
        parsed = yaml.safe_load(text)
        return parsed if isinstance(parsed, dict) else None
    except yaml.YAMLError:
        return None
