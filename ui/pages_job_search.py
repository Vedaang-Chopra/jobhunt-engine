"""Job Search page: one place to trigger every discovery source.

Per-source cards wrap ``ui.triggers.RunPanel`` components (shared RUNS
registry). Live/destructive sweeps sit behind confirm dialogs; the hiring-post
automation deep-links into the dedicated /linkedin-posts page.
"""

from __future__ import annotations

from nicegui import ui

from ui import triggers
from ui.components import confirm_dialog, section_card


def _run_panel_confirmed(label: str, component: str, cmd_builder, body: str,
                         icon: str = "play_arrow") -> None:
    """A RunPanel whose start button first asks for confirmation."""
    def _launch() -> None:
        triggers.RunPanel(component, cmd_builder)

    def _ask() -> None:
        confirm_dialog(label, body, on_confirm=_launch).open()

    with ui.row().classes("w-full items-center q-gutter-sm no-wrap"):
        ui.button(f"Run: {label}", icon=icon, on_click=_ask).props(
            "outline dense")
        ui.label("").classes("text-caption text-grey-6 grow")


def render_job_search_page() -> None:
    """Body of the /job-search page (page_shell is applied by the caller)."""
    # --- LinkedIn jobs -------------------------------------------------------
    with section_card(
        "LinkedIn",
        "Canonical agent workflow (same definition the 2h cron fires) plus "
        "legacy collection/ingest helpers. One live run per workflow.",
    ):
        # CANONICAL AGENT WORKFLOW: real Hermes session, shared persistent
        # browser, tracked in the unified run store (/runs page).
        triggers.AgentWorkflowPanel("linkedin-discovery",
                                    label="Run LinkedIn Discovery (agent)")
        triggers.RunPanel("linkedin_guest_sweep",
                          triggers.linkedin_live_sweep_cmd)
        with ui.row().classes("w-full flex-wrap q-gutter-sm items-center"):
            triggers.RunPanel("linkedin_ingest", triggers.linkedin_ingest_cmd)
            ui.link("Open LinkedIn Posts workspace →",
                    "/linkedin-posts").classes("text-caption text-primary")

    # --- Logged-in portal sweeps ---------------------------------------------
    with section_card(
        "LinkedIn Portal Sweeps (logged-in)",
        "Interactive sweeps through your logged-in browser profile. Skipped "
        "automatically when no interactive session is available.",
    ):
        triggers.RunPanel("linkedin_portal_sweep",
                          triggers.linkedin_portal_live_cmd)
        triggers.RunPanel("linkedin_recommended_sweep",
                          triggers.linkedin_recommended_live_cmd)

    # --- Career portals ------------------------------------------------------
    with section_card(
        "Career Portals (career-ops)",
        "Zero-token portal scan across configured company career sites, then "
        "import into the canonical table and rescore. Import-only reuses the "
        "last scan history.",
    ):
        triggers.RunPanel("career_ops_sweep", triggers.career_ops_sweep_cmd)
        triggers.RunPanel("career_ops_import", triggers.career_ops_import_cmd)

    # --- Wellfound -----------------------------------------------------------
    with section_card(
        "Wellfound",
        "Daily Wellfound crawler for Tier-1 AI/ML startup roles.",
    ):
        triggers.RunPanel("wellfound_crawler", triggers.wellfound_cmd)

    # --- Freshness -----------------------------------------------------------
    _run_panel_confirmed(
        "Freshness & expiry pass",
        "freshness_live",
        triggers.freshness_live_cmd,
        "Runs freshness_check.py --live: reseeds the referral registry, "
        "spot-checks URLs by priority tier, and may expire stale rows in "
        "tracking/jobs/jobs.csv. Continue?",
        icon="verified",
    )

    _run_panel_confirmed(
        "Profile-fit backlog cleanup",
        "qualify_sweep",
        triggers.qualify_sweep_cmd,
        "Applies profile-fit rules and the score floor to every open job, "
        "archives disqualified/low-priority jobs, and dismisses unreviewed "
        "hiring posts older than 14 days. Records are retained with their "
        "new status; nothing is deleted. Continue?",
        icon="cleaning_services",
    )

    _run_panel_confirmed(
        "AI review & conservative cleanup",
        "ai_backlog_review",
        triggers.ai_backlog_review_cmd,
        "Uses the configured LLM to review each open job and new hiring post "
        "individually. Only explicit ARCHIVE/DISMISS verdicts are applied; "
        "invalid or failed model responses leave that record unchanged. The "
        "verdict and reason are saved for audit. Continue?",
        icon="psychology",
    )
