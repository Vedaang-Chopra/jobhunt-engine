"""Centralized theme + design system for the NiceGUI app.

Single source of truth for dark-mode tokens, brand colors, and the global
stylesheet (buttons, cards, tables, focus rings, reduced motion). Pages and
components should only use these tokens — never hard-code colors.
"""

from __future__ import annotations

# Dark mode is always on for this app.
DARK: bool = True

# Brand color tokens (Quasar palette names / hex values).
PRIMARY = "#5B8DEF"  # brand blue
SECONDARY = "#26A69A"
ACCENT = "#9C6ADE"
POSITIVE = "#21BA45"
NEGATIVE = "#EF5350"
INFO = "#31CCEC"
WARNING = "#F2C037"

# Neutral surface tokens.
BG_DARK = "#0F1115"
CARD_BG = "#1A1D23"
BORDER = "#2A2E37"

# Typography.
TITLE = "Job Hunt Command Center"

_GLOBAL_CSS = """
:root {
  --jh-primary: #5B8DEF;
  --jh-bg: #0F1115;
  --jh-card: #1A1D23;
  --jh-border: #2A2E37;
}

body {
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

/* ---- Cards ---- */
.jh-card {
  background: var(--jh-card);
  border: 1px solid var(--jh-border);
  border-radius: 12px;
}
.jh-section-title { letter-spacing: .02em; }

/* ---- Buttons ---- */
.q-btn {
  border-radius: 8px;
  text-transform: none;
  font-weight: 600;
  letter-spacing: .01em;
}
.q-btn--standard:not(.disabled) { box-shadow: none; }
.q-btn--outline:before { border-color: #3a3f4b; }
.q-btn--rectangle { min-height: 36px; }

/* ---- Inputs & selects ---- */
.q-field--outlined .q-field__control:before {
  border-color: #3a3f4b;
}
.jh-input { min-width: 220px; }

/* ---- Tables ---- */
.q-table {
  border-radius: 10px;
}
.q-table thead th {
  background: rgba(91, 141, 239, .08);
  color: #cfd6e4 !important;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}
.q-table tbody td { border-color: var(--jh-border) !important; }
.q-table tbody tr:hover td { background: rgba(91, 141, 239, .06) !important; }
.jh-clickable-row { cursor: pointer; }
.jh-clickable-row:focus-visible {
  outline: 2px solid var(--jh-primary);
  outline-offset: -2px;
}

/* ---- Sidebar ---- */
.jh-sidebar { border-right: 1px solid var(--jh-border); }
.jh-nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  margin: 2px 8px;
  border-radius: 8px;
  color: #aab3c5 !important;
  text-decoration: none !important;
  font-weight: 500;
  transition: background .15s, color .15s;
}
.jh-nav-link:hover { background: rgba(255,255,255,.06); color: #fff !important; }
.jh-nav-link.active {
  background: rgba(91, 141, 239, .16);
  color: var(--jh-primary) !important;
  font-weight: 600;
}

/* ---- KPI cards ---- */
.jh-kpi { min-width: 170px; flex: 1; }
.jh-kpi-value { font-size: 2.1rem; font-weight: 700; line-height: 1.15; }
.jh-kpi-label {
  color: #9aa3b5;
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: .72rem;
  font-weight: 600;
}
/* Whole-card KPI hyperlinks (home page): inherit card look, add hover. */
.jh-kpi-link {
  display: block;
  min-width: 0;
  text-decoration: none !important;
  color: inherit !important;
  transition: transform .12s, box-shadow .12s;
}
.jh-kpi-link:hover {
  text-decoration: none !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 14px rgba(0,0,0,.35);
}

/* ---- Badges / chips ---- */
.jh-badge { font-weight: 600; letter-spacing: .03em; }

/* ---- Empty states ---- */
.jh-empty {
  border: 1px dashed var(--jh-border);
  border-radius: 10px;
  padding: 22px;
  text-align: center;
  color: #9aa3b5;
}

/* ---- Scrollbars ---- */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: #2A2E37;
  border-radius: 6px;
  border: 2px solid var(--jh-bg);
}
::-webkit-scrollbar-thumb:hover { background: #3a3f4b; }

/* ---- Server control pill (topbar) ---- */
.jh-server-pill {
  box-shadow: 0 2px 10px rgba(0,0,0,.35);
}

/* ---- Page shell: landmarks, h1, skip link ---- */
h1.page-h1 { font-size: 2rem; margin: 0 0 .25rem 0; }
.nicegui-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 24px;
}
/* The Quasar drawer reserves padding on q-page-container even when hidden
   via media query; cancel it below the desktop breakpoint. */
@media (max-width: 1023px) {
  .q-page-container { padding-left: 0 !important; }
}
@media (max-width: 599px) {
  .nicegui-content { padding: 12px 14px; }
}
.jh-skip-link {
  position: absolute;
  left: -9999px;
}
.jh-skip-link:focus {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 2000;
  background: var(--jh-primary);
  color: #fff;
  padding: 8px 14px;
  border-radius: 8px;
}

/* ---- Responsive utilities (spec 003 §4.2) ---- */
.jh-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 767px) {
  .jh-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 479px) {
  .jh-kpi-grid { grid-template-columns: 1fr; }
}
/* /today: all section widgets side by side horizontally. */
.jh-today-sections {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}
@media (max-width: 1023px) {
  .jh-today-sections { grid-template-columns: 1fr; }
}
.jh-today-sections > * { min-width: 0; }
.jh-kpi-grid .jh-kpi { min-width: 0; flex: initial; }
.jh-table-wrap {
  overflow-x: auto;
  max-width: 100%;
}
.jh-table-wrap table { max-width: 100%; }
.jh-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.jh-filter-bar > * { min-width: 180px; flex: 1 1 180px; }

/* Overflow safety net (spec §9: zero page-level horizontal overflow).
   Flex children default to min-width:auto which blows out grids/cards;
   no-wrap rows and wide tables must scroll or wrap instead of pushing
   the document wider than the viewport. */
.jh-card { min-width: 0; }
.nicegui-column.col { min-width: 0; }
.q-table__container { max-width: 100%; }
@media (max-width: 767px) {
  .nicegui-row.no-wrap { flex-wrap: wrap !important; }
  body { overflow-x: hidden; }
}

/* Desktop sidebar nav vs mobile top-bar nav. */
@media (max-width: 1023px) {
  .jh-desktop-nav { display: none !important; }
}
@media (min-width: 1024px) {
  .jh-mobile-nav { display: none !important; }
}


/* ---- Accessibility ---- */
:focus-visible {
  outline: 2px solid var(--jh-primary) !important;
  outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
  }
}
"""


def apply_theme(app=None) -> None:
    """Apply dark-mode, brand colors, and global stylesheet."""
    from nicegui import ui

    ui.dark_mode().enable()
    ui.colors(
        primary=PRIMARY,
        secondary=SECONDARY,
        accent=ACCENT,
        positive=POSITIVE,
        negative=NEGATIVE,
        info=INFO,
        warning=WARNING,
        dark=BG_DARK,
    )
    ui.add_head_html(f"<style>{_GLOBAL_CSS}</style>")
