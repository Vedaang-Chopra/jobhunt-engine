"""Task 3.3 pages: Analytics, Company Research, Resume, Settings.

Each builder renders inside a caller-provided container (the page body) so the
shared shell/sidebar in ``ui.app`` stays responsible for chrome.
"""

from __future__ import annotations

import os
import shlex
import sys
import time
from pathlib import Path

import pandas as pd
from nicegui import ui

from ui import data as data_layer
from ui import triggers
from ui.runs import RUNS
from ui.components import confirm_dialog, empty_state, section_card, table_columns


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _df_table(df: pd.DataFrame, columns: list[str], title: str | None = None) -> None:
    if df.empty:
        return
    if title:
        with section_card(title):
            ui.table(
                columns=table_columns(columns),
                rows=df[columns].fillna("").to_dict("records"),
                row_key=columns[0],
            ).classes("w-full").props("flat")


def _bar_chart(labels: list[str], values: list[int], title: str) -> None:
    """Render an echart bar chart; degrade to a table if echarts fails."""
    try:
        ui.echart(
            {
                "title": {"text": title, "textStyle": {"color": "#fff"}},
                "tooltip": {},
                "xAxis": {"type": "category", "data": labels},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": values}],
                "backgroundColor": "transparent",
            }
        ).classes("w-full")
    except Exception:  # noqa: BLE001 - graceful degradation without echarts
        with ui.grid(columns=2).classes("w-full"):
            for label, value in zip(labels, values):
                ui.label(label).classes("text-caption")
                ui.label(str(value)).classes("text-caption")


# ---------------------------------------------------------------------------
# Analytics (/analytics)
# ---------------------------------------------------------------------------


def render_analytics() -> None:
    with section_card("Applications per Week",
                      "Submitted applications grouped by ISO week."):
        weekly = data_layer.weekly_applications()
        if weekly.empty:
            empty_state("No submitted applications yet — the chart appears once applications are logged.",
                        icon="show_chart")
        else:
            _bar_chart(weekly["week"].tolist(), weekly["count"].astype(int).tolist(), "")

    funnel = data_layer.funnel_counts()
    with section_card("Pipeline Funnel", "Applied → Response → Screen → Interview → Offer"):
        if sum(funnel.values()) == 0:
            empty_state("No application pipeline activity recorded yet.", icon="filter_alt")
        else:
            _bar_chart(list(funnel.keys()), list(funnel.values()), "")

    by_source = data_layer.breakdown_by_source()
    if not by_source.empty:
        with section_card("Jobs per Source Board"):
            _bar_chart(by_source["source"].tolist(), by_source["count"].astype(int).tolist(), "")

    by_resume = data_layer.breakdown_by_resume_version()
    if not by_resume.empty:
        _df_table(by_resume, ["resume_variant", "count"], "Applications per Resume Version")
    else:
        with section_card("Applications per Resume Version"):
            empty_state("No resume-variant data recorded on applications yet.", icon="description")


# ---------------------------------------------------------------------------
# Company Research (/companies)
# ---------------------------------------------------------------------------

_INTEL_COLUMNS = [
    "company_name",
    "careers_url",
    "company_tier",
    "company_priority",
    "ats_platform",
    "h1b_sponsor",
    "open_roles_count",
    "contacts_count",
    "notes",
]


def render_company_research() -> None:
    companies = data_layer.company_names()
    if not companies:
        empty_state("No companies tracked yet. Companies appear here once added to tracking/companies/companies.csv.")
        return

    intel_container: ui.column | None = None
    jobs_container: ui.column | None = None

    def show_company(company_name: str) -> None:
        assert intel_container is not None and jobs_container is not None
        intel_container.clear()
        jobs_container.clear()

        row = data_layer.company_row(company_name)
        with intel_container:
            ui.label("Company Intel").classes("text-h6")
            if row is None:
                ui.label("No intel record found.").classes("text-grey")
            else:
                for col in _INTEL_COLUMNS:
                    if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                        value = str(row[col])
                        if col == "careers_url":
                            # Careers page: render clickable, not plain text.
                            ui.label(f"{col.replace('_', ' ').title()}:").classes(
                                "text-body2 inline q-mr-xs")
                            ui.link(value, value, new_tab=True).classes(
                                "text-body2").tooltip(value)
                        else:
                            ui.label(f"{col.replace('_', ' ').title()}: {value}").classes("text-body2")

        jobs = data_layer.company_open_jobs(company_name)
        with jobs_container:
            ui.label(f"Open Jobs ({len(jobs)})").classes("text-h6")
            if jobs.empty:
                ui.label("No open jobs tracked for this company.").classes("text-grey")
            else:
                cols = [c for c in ("job_id", "title", "location", "fit_score", "source") if c in jobs.columns]
                ui.table(
                    columns=[{"name": c, "label": c.replace("_", " ").title(), "field": c} for c in cols],
                    rows=jobs[cols].head(50).to_dict("records"),
                    row_key="job_id",
                ).classes("w-full")

    with ui.row().classes("w-full items-center q-gutter-sm"):
        selector = ui.select(companies, label="Company", with_input=True).classes(
            "w-72").props("outlined dense")
        research_btn = ui.button("Research company")
        research_btn.props("disable")
        research_btn.tooltip(
            "No runnable company-research CLI exists yet — the workflow in "
            "docs/workflows/COMPANY_RESEARCH_WORKFLOW.md is agent-driven "
            "(browser + rule files), so it cannot be launched as a clean "
            "subprocess from the UI.")

    ui.separator()
    with ui.grid(columns=2).classes("w-full q-gutter-md"):
        intel_container = ui.column().classes("jh-card q-pa-md")
        jobs_container = ui.column().classes("jh-card q-pa-md")

    selector.on("update:model-value", lambda e: show_company(e.args))
    show_company(companies[0])


# ---------------------------------------------------------------------------


def render_resume_page() -> None:
    """Tailored resumes: instant JD->resume+cover-letter pipeline + scoring."""
    ui.label("Tailored Resumes").classes("text-h5 text-weight-bold q-mb-sm")
    _render_jd_upload_card()
    _render_ats_scorer()


# ---------------------------------------------------------------------------
# ATS resume scorer widget
# ---------------------------------------------------------------------------

def _scorer_resume_options() -> list[dict]:
    """All scoreable resumes: base variants first, then tailored packages."""
    options: list[dict] = []
    data_root = data_layer._data_root()
    variants = data_root / "resume_custom" / "base_variants"
    if variants.is_dir():
        for pdf in sorted(variants.glob("*.pdf")):
            options.append({"label": f"(base) {pdf.stem}", "path": str(pdf)})
    for pkg in data_layer.list_tailored_packages():
        options.append({"label": f"(tailored) {pkg['package']}",
                        "path": pkg["resume_pdf"]})
    return options


def _render_ats_scorer() -> None:
    """Pick a resume + give a JD -> deterministic ATS + LLM evaluation run."""
    import json as _json

    spec_dir = data_layer.applications_dir() / "_jd_specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    poll: dict = {}

    def _show_result(run_id: str) -> None:
        """Parse SCORE_RESULT_JSON out of the finished run's log and render."""
        import json as _json
        lines = RUNS.tail(run_id, 300)
        blob = next((ln[len("SCORE_RESULT_JSON="):] for ln in lines
                     if ln.startswith("SCORE_RESULT_JSON=")), "")
        if not blob:
            return
        try:
            res = _json.loads(blob)
        except ValueError:
            return
        with result_container:
            with ui.card().classes("w-full jh-card"):
                ui.label(f"Final score: {res['final']}/100").classes(
                    "text-h5 text-weight-bold")
                ui.label(
                    f"ATS keywords {res['ats_keywords']} · "
                    f"LLM fit {res['llm_overall']} — {res['verdict']}"
                ).classes("text-body2")
                if res.get("missing_top"):
                    ui.label("Top missing keywords: "
                             + ", ".join(res["missing_top"])).classes(
                        "text-caption text-grey-7")
                ui.link("Full report (markdown)",
                        Path(res["report_md"]).as_uri()).props("target=_blank")

    def _poll_result() -> None:
        """When the scorer run finishes, render its parsed result once."""
        run_id = RUNS.latest("resume_scorer")
        if run_id is None or poll.get("done") == run_id:
            return
        st = RUNS.status(run_id)
        if st["state"] in ("done", "failed"):
            poll["done"] = run_id
            _show_result(run_id)

    def _run_score(resume_path: str, jd_kind: str, payload: str) -> None:
        """Persist the spec and launch the scorer as a background run."""
        if RUNS.is_running("resume_scorer"):
            ui.notify("A scoring run is already active — wait for it.",
                      type="warning")
            return
        spec = {"kind": jd_kind, "payload": payload, "resume": resume_path}
        spec_path = spec_dir / f"score_spec_{int(time.time())}.json"
        spec_path.write_text(_json.dumps(spec))

        def _cmd(p=str(spec_path)):
            import sys as _sys
            return [_sys.executable,
                    str(triggers.script("resume_scorer.py")),
                    "--spec-file", p]

        RUNS.start("resume_scorer", _cmd())
        with result_container:
            result_container.clear()
            ui.separator()
            ui.label("Scoring run").classes(
                "text-subtitle1 text-weight-bold q-mt-sm")
            triggers.RunPanel("resume_scorer", _cmd)
        ui.notify("Scoring started — see the log panel below.",
                  type="positive")

    def _on_score() -> None:
        resume_path = (resume_select.value or "") \
            if isinstance(resume_select.value, str) else ""
        if not resume_path:
            ui.notify("Select a resume to score.", type="warning")
            return
        url = (scorer_url.value or "").strip()
        text = (scorer_paste.value or "").strip()
        if url.startswith(("http://", "https://")):
            kind, payload = "url", url
        elif len(text) >= 200:
            kind, payload = "text", text
        else:
            ui.notify("Paste the full JD text (or a posting URL) first.",
                      type="warning")
            return
        _run_score(resume_path, kind, payload)

    with section_card(
        "ATS score & evaluation",
        "Score any existing resume against a job description: deterministic "
        "ATS keyword coverage + an LLM rubric (fit, gaps, recommendations). "
        "Nothing is generated or submitted — read-only evaluation.",
    ):
        resume_options = _scorer_resume_options()
        if not resume_options:
            empty_state("No resumes found to score "
                        "(base_variants / all_custom_resumes).",
                        icon="description")
            return
        resume_map = {o["path"]: o["label"] for o in resume_options}
        with ui.row().classes("w-full items-end q-gutter-sm no-wrap"):
            resume_select = ui.select(
                resume_map, label="Resume",
                with_input=True,
            ).classes("col-grow").props("outlined dense")
            ui.button("Score resume", icon="analytics",
                      on_click=_on_score).props("unelevated")
        with ui.tabs().classes("w-full") as stabs:
            spaste_tab = ui.tab("Paste JD", icon="paste")
            surl_tab = ui.tab("Link", icon="link")
        with ui.tab_panels(stabs, value=spaste_tab).classes("w-full"):
            with ui.tab_panel(spaste_tab):
                scorer_paste = ui.textarea(
                    "Job description",
                    placeholder="Paste the complete posting text here…",
                ).classes("w-full").props("outlined type=textarea rows=8")
            with ui.tab_panel(surl_tab):
                scorer_url = ui.input(
                    "Posting URL",
                    placeholder="https://boards.greenhouse.io/…  ·  jobs.lever.co/…",
                ).classes("w-full").props("outlined clearable")

        # Result area: log panel + parsed final-score card.
        result_container = ui.column().classes("w-full")
        from ui.components import page_timer
        page_timer(2.0, _poll_result)


def _render_jd_upload_card() -> None:
    """Upload / paste / link a JD -> auto-runs tailor_from_jd.py."""
    import time

    spec_dir = data_layer.applications_dir() / "_jd_specs"
    spec_dir.mkdir(parents=True, exist_ok=True)

    def _write_spec_and_start(kind: str, payload: str, filename: str) -> None:
        """Persist the JD spec and immediately launch the tailoring run."""
        import json as _json
        # Authoritative guard: the registry itself blocks concurrent runs and
        # frees the slot as soon as one finishes. (A sticky local flag kept
        # blocking ALL later submissions until page reload.)
        if RUNS.is_running("jd_tailor"):
            ui.notify("A generation run is already active on this page.",
                      type="warning")
            return
        spec = {"kind": kind, "company": company_in.value or "",
                "title": title_in.value or ""}
        if kind == "url":
            spec["url"] = payload
        elif kind == "text":
            spec["text"] = payload
        else:
            spec["file"] = payload
        path = spec_dir / f"spec_{int(time.time())}_{filename[:40]}"
        path.write_text(_json.dumps(spec))

        def _cmd(p=str(path)):
            return triggers.tailor_spec_cmd(p)

        panel_holder.clear()
        with panel_holder:
            ui.separator()
            ui.label("Generation run").classes(
                "text-subtitle1 text-weight-bold q-mt-sm")
            panel = triggers.RunPanel("jd_tailor", _cmd)
        # Auto-launch: the whole point is "JD in -> resume out". The RunPanel
        # stays for logs/re-runs; we just don't make the user click it.
        try:
            RUNS.start("jd_tailor", _cmd())
        except RuntimeError:
            pass  # a run is already live — the panel will show its state
        panel.refresh()
        ui.notify("JD received — generating tailored resume + cover letter…",
                  type="positive")

    def _maybe_autostart_paste(e=None) -> None:
        text = (paste_area.value or "").strip()
        if len(text) >= 200:
            if RUNS.is_running("jd_tailor"):
                paste_status.set_text(
                    "⚠ generation already running — paste again when it finishes")
                return
            paste_status.set_text("✓ pasted JD accepted — generation started")
            _write_spec_and_start("text", text, "pasted")

    def _on_upload(e) -> None:  # pragma: no cover - requires running server
        try:
            content = e.content.read()
            name = e.name or "jd_upload.txt"
            suffix = Path(name).suffix.lower()
            if suffix == ".pdf":
                text = _pdf_to_text(content)
                if not text or len(text.strip()) < 200:
                    ui.notify("Could not extract readable text from that PDF — "
                              "paste the text instead.", type="negative")
                    return
                saved = spec_dir / f"upload_{int(time.time())}.txt"
                saved.write_text(text)
                _write_spec_and_start("file", str(saved), name)
                return
            text = content.decode("utf-8", errors="replace")
            if len(text.strip()) < 200:
                ui.notify("That file looks too short to be a full JD.",
                          type="warning")
                return
            saved = spec_dir / f"upload_{int(time.time())}_{Path(name).name}"
            saved.write_text(text)
            _write_spec_and_start("file", str(saved), name)
        except Exception as exc:  # noqa: BLE001 - surface upload errors inline
            ui.notify(f"upload failed: {exc}", type="negative")

    def _on_url_go() -> None:  # pragma: no cover - requires running server
        url = (url_input.value or "").strip()
        if not url.startswith(("http://", "https://")):
            ui.notify("Enter a valid http(s) posting URL.", type="warning")
            return
        _write_spec_and_start("url", url, "link")

    with section_card(
        "Tailor from a job description",
        "Drop a JD file, paste the posting text, or give the link — the tailored "
        "resume + cover letter generate automatically (draft; review before sending).",
    ):
        # --- optional metadata (auto-filled from the JD when left blank) ---
        with ui.row().classes("w-full q-gutter-sm no-wrap"):
            company_in = ui.input("Company (optional)", placeholder="auto-detected"
                                  ).classes("col-grow").props("outlined dense")
            title_in = ui.input("Role title (optional)", placeholder="auto-detected"
                                ).classes("col-grow").props("outlined dense")

        # --- the three input modes -----------------------------------------
        with ui.tabs().classes("w-full") as tabs:
            upload_tab = ui.tab("Upload file", icon="upload_file")
            paste_tab = ui.tab("Paste text", icon="paste")
            url_tab = ui.tab("Link", icon="link")
        with ui.tab_panels(tabs, value=upload_tab).classes("w-full"):
            with ui.tab_panel(upload_tab):
                ui.label(
                    "Drop a .txt / .md / .pdf job description here — generation "
                    "starts the moment the file lands.").classes(
                    "text-caption text-grey-6 q-pb-sm")
                ui.upload(label="Job description file",
                          multiple=False,
                          auto_upload=True,
                          on_upload=_on_upload,
                          ).props(
                    "accept=.txt,.md,.markdown,.pdf,.docx,.rtf filled").classes(
                    "w-full")

            with ui.tab_panel(paste_tab):
                paste_area = ui.textarea(
                    "Paste the full job description",
                    placeholder="Paste the complete posting text here… "
                                "(generation starts automatically)",
                    on_change=_maybe_autostart_paste,
                ).classes("w-full").props("outlined type=textarea rows=10")
                paste_status = ui.label("").classes("text-caption text-grey-6")

            with ui.tab_panel(url_tab):
                url_input = ui.input(
                    "Posting URL",
                    placeholder="https://boards.greenhouse.io/…  ·  jobs.lever.co/…  ·  jobs.ashbyhq.com/…",
                ).classes("w-full").props("outlined clearable")
                ui.label(
                    "Greenhouse / Lever / Ashby links are fetched via their public "
                    "APIs. Workday and login-walled pages are rejected — paste "
                    "those instead.").classes("text-caption text-grey-6")
                ui.button("Fetch posting & generate", icon="auto_fix_high",
                          on_click=_on_url_go).props("unelevated")

        # --- run panel (streams engine logs; one run at a time) ------------
        panel_holder = ui.column().classes("w-full")


def _pdf_to_text(content: bytes) -> str:  # pragma: no cover - requires server
    """Extract text from uploaded PDF bytes via pdftotext (poppler)."""
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(content)
        tmp_pdf = fh.name
    try:
        out = subprocess.run(["pdftotext", tmp_pdf, "-"],
                             capture_output=True, text=True, timeout=30)
        return out.stdout or ""
    except Exception:
        return ""
    finally:
        try:
            os.unlink(tmp_pdf)
        except OSError:
            pass


def _render_tailored_packages() -> None:
    """All tailored files: resume/cover-letter links open in a new tab."""
    packages = data_layer.list_tailored_packages()
    with section_card(
        "All tailored files",
        "Each folder holds resume.tex/pdf, cover_letter.tex/pdf and "
        "evaluation.md. Click resume or cover letter to open the PDF in a "
        "new tab.",
    ):
        if not packages:
            empty_state(
                "No tailored packages yet — drop a JD above and one appears here.",
                icon="auto_awesome")
            return

        def _delete_package(pkg_name: str, refresh_container) -> None:
            def _do_delete() -> None:
                import shutil
                target = data_layer.applications_dir() / pkg_name
                shutil.rmtree(target, ignore_errors=True)
                ui.notify(f"Deleted {pkg_name}", type="warning")
                refresh_container.refresh()
            dialog = confirm_dialog(
                "Delete package",
                f"Permanently delete '{pkg_name}' and all its files? This "
                "cannot be undone.",
                danger=True, confirm_label="Delete package",
                on_confirm=_do_delete)
            dialog.open()

        @ui.refreshable
        def _packages_list() -> None:
            current = data_layer.list_tailored_packages()
            if not current:
                empty_state(
                    "No tailored packages yet — drop a JD above and one appears here.",
                    icon="auto_awesome")
                return
            with ui.list().props("separator").classes("w-full"):
                for pkg in current:
                    name = pkg["package"]
                    with ui.item().classes("w-full"):
                        with ui.item_section().props("avatar"):
                            ui.icon("folder", color="primary")
                        with ui.item_section():
                            ui.item_label(name).classes("font-medium")
                            ui.item_label(f"{pkg['updated']} · {pkg['size_kb']} KB"
                                          ).props("caption")
                        with ui.item_section().classes("items-end gap-1"):
                            with ui.row().classes("items-center q-gutter-xs"):
                                ui.link("resume",
                                        f"/resumes/{name}/resume.pdf"
                                        ).props("target=_blank")
                                if pkg.get("cover_letter") == "yes":
                                    ui.link("cover letter",
                                            f"/resumes/{name}/cover_letter.pdf"
                                            ).props("target=_blank")
                                if pkg.get("evaluation") == "yes":
                                    ui.link("evaluation",
                                            f"/resumes/{name}/evaluation.md"
                                            ).props("target=_blank")
                                ui.button(icon="delete", on_click=lambda
                                          n=name: _delete_package(n, _packages_list)
                                          ).props("flat dense round color=negative"
                                                  ).tooltip("Delete this package")
        _packages_list()

    def _open_resumes_dir() -> None:
        directory = data_layer.applications_dir()
        directory.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            os.system(f"open {shlex.quote(str(directory))}")
        elif os.name == "nt":
            os.system(f"explorer {shlex.quote(str(directory))}")
        else:
            os.system(f"xdg-open {shlex.quote(str(directory))}")

    with ui.row().classes("q-mt-sm items-center"):
        ui.button("Open all_custom_resumes folder", icon="folder_open",
                  on_click=_open_resumes_dir).props("flat dense")


def render_settings_page() -> None:
    """Settings: config status, LLM endpoints, setup wizard."""
    ui.label("Settings").classes("text-h5 text-weight-bold q-mb-sm")
    _render_config_status()
    _render_llm_endpoints()
    _render_setup_wizard_hint()


def _render_resume_section() -> None:
    resumes = data_layer.list_resumes()
    jobs_df = data_layer.load_jobs()
    job_options: list[str] = []
    if not jobs_df.empty and "job_id" in jobs_df.columns:
        job_options = sorted(
            str(v) for v in jobs_df["job_id"].fillna("").astype(str) if str(v).strip()
        )
    selected_job: dict = {"job_id": ""}

    tailor_btn = ui.button("Tailor resume", icon="auto_fix_high",
                           on_click=lambda: dialog.open()).props("unelevated")
    tailor_btn.tooltip(
        "Runs scripts/apply_pipeline.py <job_id> as a background run "
        "(read-only up to the approval gate; nothing is submitted).")

    with ui.dialog() as dialog, ui.card().classes("jh-card").style(
            "min-width: min(560px, 92vw)"):
        ui.label("Tailor resume — pick a job").classes("text-h6 text-weight-bold")
        if job_options:
            job_select = ui.select(
                job_options, label="Job", with_input=True,
                on_change=lambda e: selected_job.update(job_id=e.value or ""),
            ).classes("w-full").props("outlined dense")
            with ui.row().classes("w-full justify-end q-gutter-sm q-mt-sm"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Start tailoring run", icon="play_arrow",
                    on_click=lambda: (
                        dialog.close(),
                        selected_job.update(
                            job_id=job_select.value or selected_job["job_id"]),
                        ui.notify(
                            f"tailor run started for {selected_job['job_id']}"
                            " — see the log panel below",
                            type="positive") if selected_job["job_id"] else
                        ui.notify("select a job first", type="warning"),
                        panel.refresh(),
                    ),
                ).props("unelevated")
        else:
            empty_state("No jobs in tracking/jobs/jobs.csv yet.", icon="work_off")
            ui.button("Close", on_click=dialog.close).props("flat")

    # Streaming log panel for the tailoring run (one run per component).
    panel = triggers.RunPanel(
        "resume_tailor",
        lambda: triggers.tailor_cmd(selected_job["job_id"])
        if selected_job["job_id"] else None,
    )

    if resumes:
        ui.table(
            columns=table_columns(["name", "path", "size_kb"], sortable=False),
            rows=resumes,
            row_key="path",
        ).classes("w-full").props("flat")
    else:
        empty_state(
            "No tailored resumes found under resume_custom/resumes/. "
            "Tailored output will be listed here once generated.",
            icon="description")


def _render_config_status() -> None:
    """Read-only config status; key NAMES only, never values."""
    status = data_layer.config_status()
    with section_card("Config Status (read-only)"):
        ui.label(f"JOBHUNT_HOME / data root: {status['data_root']}").classes("text-body2")
        found = 'found' if status['loaded'] else 'missing'
        ui.badge(f"config file {found}",
                 color="positive" if status['loaded'] else "negative").props(
                     "outline dense").classes("jh-badge")
        ui.table(
            columns=table_columns(["key", "present"], sortable=False),
            rows=[{"key": k["key"], "present": "yes" if k["present"] else "no"}
                  for k in status["keys"]],
            row_key="key",
        ).classes("w-full").props("flat")


def _render_llm_endpoints() -> None:
    """LLM endpoint editor: writes <data_root>/config.yaml.

    Provider selector with presets (OpenRouter, NVIDIA — fixed default
    endpoints) and a Custom option for arbitrary OpenAI-compatible
    endpoints.
    """
    status = data_layer.config_status()
    current = data_layer.llm_provider_config()
    fields: dict[str, dict] = {}
    provider_containers: dict[str, ui.column] = {}

    def _show_provider(prov: str) -> None:
        for name, container in provider_containers.items():
            container.set_visibility(name == prov)

    with section_card(
        "LLM Endpoints",
        f"Edits provider base URLs, models, priorities, and API keys in "
        f"{status['config_path']}. Keys are write-only: they are saved but "
        "never displayed again. Leave a field blank to keep its current "
        "value; preset providers fall back to their default endpoint.",
    ):
        # Live chain preview + per-provider editor rows (all three visible at
        # once so priorities can be compared side by side).
        current_chain = data_layer.llm_provider_chain()

        def _chain_text() -> str:
            chain = data_layer.llm_provider_chain()
            if not chain:
                return "No provider with an API key configured yet."
            return " → ".join(
                f"{i+1}. {name}" for i, name in enumerate(chain))

        ui.label("Current call order:").classes(
            "text-caption text-weight-medium")
        chain_label = ui.label(_chain_text()).classes(
            "text-caption text-grey-6").style("user-select: text")

        provider_rows: dict[str, dict] = {}
        for prov in data_layer.LLM_PROVIDERS:
            cur = current.get(prov, {}) if isinstance(current, dict) else {}
            row_fields: dict = {}
            key_hint = "(stored — enter to replace)" if cur.get(
                "has_api_key") else "(not set)"
            with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
                ui.label(prov).classes("text-body2 text-weight-medium").style(
                    "min-width: 90px")
                row_fields["base_url"] = ui.input(
                    "Base URL", value=cur.get("base_url", "")
                    or data_layer.LLM_PROVIDER_DEFAULTS.get(prov, {}).get(
                        "base_url", ""),
                ).classes("grow").props("outlined dense")
                row_fields["model"] = ui.input(
                    "Model", value=cur.get("model", "")).classes(
                        "grow").props("outlined dense")
                row_fields["priority"] = ui.number(
                    "Priority", value=cur.get("priority") or None,
                    format="%.0f", min=1, max=99,
                ).classes("col-grow").props("outlined dense").tooltip(
                    "Lower number = tried first when several providers are "
                    "configured. Empty = default order.")
                row_fields["api_key"] = ui.input(
                    "API key", placeholder=key_hint,
                ).classes("grow").props(
                    "type=password outlined dense").tooltip(key_hint)
            provider_rows[prov] = row_fields

        status_label = ui.label("").classes("text-caption text-grey-6")

        def _save() -> None:
            updates = {
                prov: {f: (inp.value or "") for f, inp in row.items()}
                for prov, row in provider_rows.items()
            }
            try:
                result = data_layer.update_llm_providers(updates)
            except (ValueError, OSError) as exc:
                ui.notify(f"save failed: {exc}", type="negative")
                return
            # Write-only keys: blank the inputs out immediately; never render.
            for row in provider_rows.values():
                row["api_key"].set_value(None)
            stored = data_layer.llm_provider_config()
            summary = ", ".join(
                f"{p}: key {'set' if stored.get(p, {}).get('has_api_key') else 'unset'}"
                f"{'/pri ' + str(stored[p]['priority']) if stored.get(p, {}).get('priority') != '' else ''}"
                for p in data_layer.LLM_PROVIDERS)
            chain_label.set_text(_chain_text())
            status_label.set_text(f"saved to {result['path']} ({summary})")
            ui.notify("LLM providers saved", type="positive")

        ui.button("Save endpoints", icon="save", on_click=_save).props(
            "unelevated")

    _show_provider("openrouter")


def _render_setup_wizard_hint() -> None:
    with section_card("Setup Wizard",
                      "Run the setup wizard to configure missing keys:"):
        ui.markdown("`python -m setup.wizard`").classes("text-body2")
