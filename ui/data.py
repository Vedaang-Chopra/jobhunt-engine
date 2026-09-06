"""Thin data-access layer over the tracking CSVs (Task 2.1).

All loaders resolve paths via ``config_lib.data_root()`` and return an empty
DataFrame (with the expected columns when known) instead of raising when the
underlying file is missing — callers get a graceful empty state.
"""

from __future__ import annotations

import csv
import datetime
import os
import re
import sys
import threading
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

# Make ``scripts/`` importable regardless of how the app/test is launched.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import config_lib
except ImportError:  # pragma: no cover - repo layout guarantee
    config_lib = None

try:
    import followups_lib
except ImportError:  # pragma: no cover - repo layout guarantee
    followups_lib = None


def _data_root() -> Path:
    if config_lib is None:
        return Path(__file__).resolve().parent.parent
    return config_lib.data_root()


def load_csv(relative_path: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Load ``<data_root>/<relative_path>`` into a DataFrame.

    Returns an empty DataFrame (with ``columns`` if provided) when the file is
    missing or unreadable. Failures are ALSO recorded into a thread-local
    issue list (spec 003 §6.1: no silent empty tables) — pages opt in by
    calling :func:`get_load_issues` after their loads; existing callers are
    unaffected.
    """
    path = _data_root() / relative_path
    if not path.is_file():
        _record_load_issue({"path": str(path), "reason": "missing"})
        return pd.DataFrame(columns=columns or [])
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 - graceful empty state
        print(f"ui.data: could not read {path}: {exc}")
        _record_load_issue({"path": str(path), "reason": f"read-error: {exc}"})
        return pd.DataFrame(columns=columns or [])
    return df


# --- Load-issue error channel (spec 003 §6.1) -------------------------------
#
# ``load_csv`` never raises; instead every failure appends a
# ``{'path': str, 'reason': str}`` record to per-thread storage so parallel
# NiceGUI user sessions don't bleed issues across requests.

_LOAD_ISSUE_LOCAL = threading.local()


def _load_issue_store() -> list[dict]:
    store = getattr(_LOAD_ISSUE_LOCAL, "issues", None)
    if store is None:
        store = []
        _LOAD_ISSUE_LOCAL.issues = store
    return store


def _record_load_issue(issue: dict) -> None:
    _load_issue_store().append(issue)


def clear_load_issues() -> None:
    """Forget all load issues recorded on this thread."""
    del _load_issue_store()[:]


def get_load_issues() -> list[dict]:
    """Issues recorded by :func:`load_csv` on this thread since last clear."""
    return list(_load_issue_store())


def load_jobs() -> pd.DataFrame:
    """Canonical job records."""
    return load_csv("tracking/jobs/jobs.csv", columns=["job_id", "company", "title", "status", "fit_score"])


# --- Job-state mutations (tracking/jobs/jobs.csv) ----------------------------
#
# Controlled vocabulary from tracking/jobs/SCHEMA.md plus the UI-only review
# flag and role-family taxonomy. The public mutators below go through
# :func:`_mutate_jobs` so every write preserves all columns and untouched rows.

JOB_STATUSES = ("open", "expired", "filled", "withdrawn", "archived")
JOB_REVIEW_FLAGS = ("", "for_later", "completed")
ROLE_FAMILY_OPTIONS = (
    ("agentic_ai", "Agentic AI"),
    ("agent_reasoning", "Agent Reasoning"),
    ("applied_ml", "ML Engineering (MLE)"),
    ("eval_inference", "Eval & Inference"),
    ("post_training", "Post-Training"),
    ("other", "Other"),
)

_JOBS_CSV_REL = Path("tracking") / "jobs" / "jobs.csv"


def _read_jobs_rows() -> tuple[Path, list[str], list[dict]]:
    """Raw csv.DictReader view of the canonical jobs CSV (raises if missing)."""
    path = _data_root() / _JOBS_CSV_REL
    if not path.is_file():
        raise FileNotFoundError(f"jobs CSV not found: {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return path, fieldnames, rows


def _write_jobs_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Atomic CSV write: tmp file in the same dir, then ``os.replace``."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def _mutate_jobs(
    job_ids: str | Iterable[str],
    mutator,
    *,
    ensure_fields: tuple[str, ...] = (),
) -> list[str]:
    """Apply ``mutator(row) -> bool`` to rows whose ``job_id`` matches.

    Writes back atomically only when at least one row changed. ``ensure_fields``
    appends missing columns to the header when a write happens. Unknown ids
    raise ``ValueError`` listing every missing id; a missing jobs.csv raises
    ``FileNotFoundError``. Returns the ids of changed rows.
    """
    requested = [job_ids] if isinstance(job_ids, str) else list(job_ids)
    id_set = set(requested)
    path, fieldnames, rows = _read_jobs_rows()
    fieldnames = list(fieldnames)
    for name in ensure_fields:
        if name not in fieldnames:
            fieldnames.append(name)

    known = {r.get("job_id") for r in rows}
    missing = sorted(id_set - known)
    if missing:
        raise ValueError(f"unknown job_id(s): {', '.join(missing)}")

    changed: list[str] = []
    for row in rows:
        if row.get("job_id") in id_set and mutator(row):
            changed.append(str(row.get("job_id")))
    if changed:
        _write_jobs_rows(path, fieldnames, rows)
    return changed


def set_job_status(job_id: str | Iterable[str], status: str) -> list[str]:
    """Set ``status`` on one or many job rows; stamps ``date_updated``.

    Accepts a single job id or an iterable (bulk stage change from the /jobs
    table). Returns the ids of changed rows.
    """
    if status not in JOB_STATUSES:
        raise ValueError(
            f"unknown job status {status!r}; expected one of {list(JOB_STATUSES)}")

    today_iso = datetime.date.today().isoformat()

    def mutate(row: dict) -> bool:
        row["status"] = status
        row["date_updated"] = today_iso
        return True

    return _mutate_jobs(job_ids=job_id, mutator=mutate)


def mark_jobs_applied(job_ids: Iterable[str]) -> list[str]:
    """Bulk "applied" transition for canonical jobs.

    For each job: create/queue the linked Applications-board row (via
    :func:`track_job_as_application`, then move it to the Applied stage), and
    set the job's own review flag to ``completed``. Rows are never deleted —
    this is a lifecycle transition only. Returns the ids that changed.
    """
    changed: list[str] = []
    errors: list[str] = []
    for job_id in job_ids:
        try:
            apps = load_applications()
            already = (
                not apps.empty
                and "job_id" in apps.columns
                and not apps[
                    apps["job_id"].fillna("").astype(str) == str(job_id)
                ].empty  # type: ignore[union-attr]
            )
            if not already:
                track_job_as_application(job_id, status="submitted")
            else:
                app_id = str(apps.loc[
                    apps["job_id"].fillna("").astype(str) == str(job_id),
                    "application_id",
                ].iloc[0])
                update_application_stage(app_id, "Applied")
            set_job_status(job_id, "open")  # stamp date_updated; status stays open
            set_job_review_flag(job_id, "completed")
            changed.append(str(job_id))
        except (ValueError, OSError) as exc:
            errors.append(f"{job_id}: {exc}")
    if errors and not changed:
        raise ValueError("; ".join(errors))
    return changed


def set_job_review_flag(job_id: str, flag: str) -> None:
    """Set/clear the UI ``review_flag`` column on one job row.

    An empty ``flag`` clears it. The ``review_flag`` header column is always
    ensured after a flag operation.
    """
    if flag not in JOB_REVIEW_FLAGS:
        raise ValueError(
            f"unknown review flag {flag!r}; expected one of {list(JOB_REVIEW_FLAGS)}")

    today_iso = datetime.date.today().isoformat()

    def mutate(row: dict) -> bool:
        row["review_flag"] = flag
        row["date_updated"] = today_iso
        return True

    # ensure_fields guarantees the review_flag header column exists in the
    # written file even when clearing on a file that lacked the column.
    _mutate_jobs([job_id], mutate, ensure_fields=("review_flag",))


def delete_job(job_id: str) -> bool:
    """Remove a job row entirely; True when removed."""
    path, fieldnames, rows = _read_jobs_rows()
    before = len(rows)
    remaining = [r for r in rows if r.get("job_id") != job_id]
    if len(remaining) == before:
        raise ValueError(f"unknown job_id: {job_id}")
    _write_jobs_rows(path, fieldnames, remaining)
    return True


APPLICATIONS_CSV_REL = "tracking/applications/applications.csv"

#: Full canonical header of applications.csv (inline schema per
#: tracking/AGENTS.md). add_application() writes every column so the file
#: stays schema-complete even when it is created from scratch.
APPLICATION_FIELDS: tuple[str, ...] = (
    "application_id", "job_id", "company", "role", "job_url", "status",
    "resume_variant", "referral_contact", "date_queued", "date_resume_ready",
    "date_submitted", "date_acknowledged", "date_last_status_change",
    "current_stage", "rejection_reason", "follow_up_date", "notes",
)


def applications_csv_path() -> Path:
    """Canonical applications.csv under the live data root."""
    if config_lib is None:  # pragma: no cover - repo layout guarantee
        raise RuntimeError("config_lib unavailable; cannot resolve data root")
    return config_lib.data_root() / "tracking" / "applications" / "applications.csv"


def _slug(text: str) -> str:
    """Lowercase underscore slug for manual application ids.

    Matches the repo ``job_id`` convention (``{company_slug}_{title_slug}``,
    tracking/AGENTS.md #2): non-alphanumerics collapse to ``_``.
    """
    out = []
    for ch in str(text or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
        else:
            ch = "_"
            if not out or out[-1] == "_":
                continue
            out.append(ch)
    return "".join(out).strip("_")


def application_id_for(company: str, role: str, today: datetime.date | None = None) -> str:
    """Stable manual-add id: ``{company}_{role}_{date}`` (tracking/AGENTS.md #2)."""
    day = today or datetime.date.today()
    company_part = _slug(company) or "company"
    role_part = _slug(role) or "role"
    return f"{company_part}_{role_part}_{day.isoformat().replace('-', '')}"


def add_application(
    company: str,
    role: str,
    job_url: str = "",
    status: str = "queued",
    notes: str = "",
    apps_path: str | Path | None = None,
    today: datetime.date | None = None,
) -> dict:
    """Append one manually-tracked application row; returns the row written.

    Manual-entry path for /applications (the board is otherwise fed by the
    discovery pipeline / future Outlook-email agent). Writes through
    ``csv.DictWriter`` with the full :data:`APPLICATION_FIELDS` header so a
    missing/empty file is created schema-complete. Raises ``ValueError`` on
    blank company/role or an unknown status.
    """
    company = str(company or "").strip()
    role = str(role or "").strip()
    if not company or not role:
        raise ValueError("company and role are required")
    status = str(status or "queued").strip().lower() or "queued"
    if status not in STATUS_TO_STAGE:
        raise ValueError(
            f"unknown status {status!r}; expected one of {sorted(STATUS_TO_STAGE)}")

    day = today or datetime.date.today()
    app_id = application_id_for(company, role, day)
    path = Path(apps_path) if apps_path else applications_csv_path()

    rows: list[dict] = []
    fieldnames = list(APPLICATION_FIELDS)
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = [dict(r) for r in reader]
            if reader.fieldnames:
                seen = set(fieldnames)
                fieldnames = list(reader.fieldnames) + [
                    f for f in fieldnames if f not in seen
                ]
    if any((r.get("application_id") or r.get("job_id")) == app_id for r in rows):
        raise ValueError(f"application already tracked today: {app_id}")

    row = {f: "" for f in fieldnames}
    row.update({
        "application_id": app_id,
        "job_id": app_id,
        "company": company,
        "role": role,
        "job_url": str(job_url or "").strip(),
        "status": status,
        "current_stage": status,
        "date_queued": day.isoformat(),
        "date_last_status_change": day.isoformat(),
        "notes": str(notes or "").strip(),
    })
    rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return row


def load_applications() -> pd.DataFrame:
    """Application pipeline rows."""
    return load_csv(
        APPLICATIONS_CSV_REL,
        columns=["application_id", "job_id", "company", "role", "status",
                 "date_submitted"],
    )


# --------------------------------------------------------------- jobs sync
#: Add-only jobs.csv column mirroring the linked application's engine status.
#: Written by :func:`sync_job_application_status`; read by the /jobs dialog.
APPLICATION_STATUS_COL = "application_status"


def sync_job_application_status(
    job_id: str,
    status: str,
) -> bool:
    """Mirror an application's engine status onto its linked jobs.csv row.

    Writes the add-only ``application_status`` column (never the job
    ``status`` lifecycle column, which is discovery-state, not application
    state). Missing jobs.csv or unknown job_id is tolerated silently — the
    application board must keep working for manually-tracked roles that have
    no canonical job row. Returns True when a row was updated.
    """
    status = (status or "").strip().lower()
    if not status:
        return False

    def mutate(row: dict) -> bool:
        if row.get(APPLICATION_STATUS_COL) == status:
            return False
        row[APPLICATION_STATUS_COL] = status
        return True

    try:
        _mutate_jobs([job_id], mutate, ensure_fields=(APPLICATION_STATUS_COL,))
        return True
    except (ValueError, FileNotFoundError):
        # No canonical job row (manual entry) — nothing to mirror.
        return False


def application_status_for_job(job_id: str) -> str | None:
    """Read the mirrored application status for one job row ('' -> None)."""
    path, fieldnames, rows = _read_jobs_rows()
    if APPLICATION_STATUS_COL not in fieldnames:
        return None
    for row in rows:
        if row.get("job_id") == job_id:
            value = (row.get(APPLICATION_STATUS_COL) or "").strip()
            return value or None
    return None


def load_contacts() -> pd.DataFrame:
    """Networking contacts."""
    return load_csv("tracking/contacts/contacts.csv", columns=["contact_id", "name", "company"])


def load_companies() -> pd.DataFrame:
    """Company research records."""
    return load_csv(
        "tracking/companies/companies.csv",
        columns=["company_slug", "company_name", "status", "notes"],
    )


# ---------------------------------------------------------------------------
# Analytics aggregations (Task 3.3)
# ---------------------------------------------------------------------------

FUNNEL_STAGES = ["applied", "response", "screen", "interview", "offer"]

# Substring -> canonical funnel stage. Matched case-insensitively against the
# application's ``status`` and ``current_stage`` columns.
_STAGE_KEYWORDS = {
    "offer": "offer",
    "interview": "interview",
    "screen": "screen",
    "response": "response",
    "reply": "response",
    "applied": "applied",
    "submitted": "applied",
}


def _stage_of(value: str) -> str | None:
    text = str(value).strip().lower()
    if not text or text == "nan":
        return None
    for keyword, stage in _STAGE_KEYWORDS.items():
        if keyword in text:
            return stage
    return None


def weekly_applications() -> pd.DataFrame:
    """Applications per ISO week from ``date_submitted``.

    Returns a DataFrame with ``week`` and ``count`` columns; empty when no
    submissions are recorded yet.
    """
    apps = load_applications()
    cols = ["week", "count"]
    if apps.empty or "date_submitted" not in apps.columns:
        return pd.DataFrame(columns=cols)
    dates = pd.to_datetime(apps["date_submitted"], errors="coerce")
    valid = dates.dropna()
    if valid.empty:
        return pd.DataFrame(columns=cols)
    weekly = (
        valid.dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d").value_counts().sort_index()
    )
    return pd.DataFrame({"week": weekly.index.astype(str), "count": weekly.values})


def funnel_counts() -> dict[str, int]:
    """Applied -> response -> screen -> interview -> offer counts."""
    counts = {stage: 0 for stage in FUNNEL_STAGES}
    apps = load_applications()
    if apps.empty:
        return counts
    # Per row, ``current_stage`` wins; fall back to ``status`` when the stage
    # is blank/unmapped so each application counts at most once.
    for _, row in apps.iterrows():
        stage = None
        for col in ("current_stage", "status"):
            if col in row.index:
                stage = _stage_of(row[col])
                if stage:
                    break
        if stage:
            counts[stage] += 1
    return counts


def breakdown_by_source() -> pd.DataFrame:
    """Open-jobs-per-source-board breakdown (jobs CSV ``source`` column)."""
    jobs = load_jobs()
    cols = ["source", "count"]
    if jobs.empty or "source" not in jobs.columns:
        return pd.DataFrame(columns=cols)
    counts = jobs["source"].fillna("unknown").astype(str).value_counts()
    return pd.DataFrame({"source": counts.index, "count": counts.values})


def breakdown_by_resume_version() -> pd.DataFrame:
    """Applications per resume variant (applications ``resume_variant`` column)."""
    apps = load_applications()
    cols = ["resume_variant", "count"]
    if apps.empty or "resume_variant" not in apps.columns:
        return pd.DataFrame(columns=cols)
    series = apps["resume_variant"].dropna().astype(str)
    series = series[series.str.strip() != ""]
    if series.empty:
        return pd.DataFrame(columns=cols)
    counts = series.value_counts()
    return pd.DataFrame({"resume_variant": counts.index, "count": counts.values})


# ---------------------------------------------------------------------------
# Company research (Task 3.3)
# ---------------------------------------------------------------------------


def company_names() -> list[str]:
    """Sorted display names of companies present in company tracking."""
    companies = load_companies()
    if companies.empty or "company_name" not in companies.columns:
        return []
    names = companies["company_name"].dropna().astype(str)
    return sorted(n.strip() for n in names.unique() if n.strip())


def company_row(company_name: str) -> pd.Series | None:
    """The intel row in ``companies.csv`` for ``company_name``, else None."""
    companies = load_companies()
    if companies.empty or "company_name" not in companies.columns:
        return None
    match = companies[companies["company_name"].astype(str) == company_name]
    if match.empty:
        return None
    return match.iloc[0]


def company_open_jobs(company_name: str) -> pd.DataFrame:
    """Open job rows at ``company_name`` from the canonical jobs CSV."""
    jobs = load_jobs()
    cols = list(jobs.columns) if not jobs.empty else ["job_id", "title", "status"]
    if jobs.empty or "company" not in jobs.columns:
        return pd.DataFrame(columns=cols)
    mask = jobs["company"].astype(str).str.lower() == str(company_name).lower()
    open_jobs = jobs[mask & jobs.get("status", pd.Series(dtype=str)).eq("open")]
    return open_jobs.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Resumes + Settings (Task 3.3)
# ---------------------------------------------------------------------------


def resumes_dir() -> Path:
    return _data_root() / "resume_custom" / "resumes"


def applications_dir() -> Path:
    """Custom resume packages now live inside the repo."""
    return Path(__file__).resolve().parent.parent / "all_custom_resumes"


def list_tailored_packages() -> list[dict]:
    """Generated application packages (resume + cover letter + evaluation).

    Each row is one ``applications/{company}_{role}_{YYYYMMDD}/`` folder that
    contains a compiled resume.pdf; cover-letter/evaluation presence is noted.
    Sorted newest-first.
    """
    directory = applications_dir()
    if not directory.is_dir():
        return []
    rows: list[dict] = []
    # Newest-first by resume.pdf mtime (NOT folder name — alphabetical order
    # put e.g. tessera_* above a same-day-but-newer scaleai_* package).
    pkg_dirs = [
        pkg
        for pkg in directory.iterdir()
        if pkg.is_dir() and (pkg / "resume.pdf").exists()
    ]
    pkg_dirs.sort(
        key=lambda pkg: (pkg / "resume.pdf").stat().st_mtime, reverse=True
    )
    for pkg in pkg_dirs:
        resume_pdf = pkg / "resume.pdf"
        stat = resume_pdf.stat()
        rows.append(
            {
                "package": pkg.name,
                "resume_pdf": str(resume_pdf),
                "cover_letter": "yes" if (pkg / "cover_letter.pdf").exists() else "—",
                "evaluation": "yes" if (pkg / "evaluation.md").exists() else "—",
                "updated": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size_kb": round(stat.st_size / 1024, 1),
            }
        )
    return rows


def list_resumes() -> list[dict]:
    """Tailored resume files under ``resume_custom/resumes/``."""
    directory = resumes_dir()
    if not directory.is_dir():
        return []
    entries = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".pdf", ".tex", ".md", ".docx"}:
            stat = path.stat()
            entries.append(
                {
                    "name": path.name,
                    "path": str(path.relative_to(directory)),
                    "size_kb": round(stat.st_size / 1024, 1),
                }
            )
    return entries


# Expected config key names. Only NAMES are ever surfaced in the UI — never
# values — since config.yaml can contain credentials.
EXPECTED_CONFIG_KEYS = [
    "llm",
    "llm.api_key",
    "llm.base_url",
    "llm.model",
    "notifications.email",
    "job_search.keywords",
    "job_search.locations",
]


def llm_provider_config() -> dict:
    """Non-secret current values for the Settings LLM endpoint editor.

    API keys are never returned — only whether one is set per provider.
    """
    if config_lib is None:
        return {}
    raw = config_lib.load_config()
    llm = raw.get("llm") if isinstance(raw.get("llm"), dict) else {}
    providers = llm.get("providers") if isinstance(
        llm.get("providers"), dict) else {}
    out = {}
    for prov in LLM_PROVIDERS:
        node = providers.get(prov) if isinstance(
            providers.get(prov), dict) else {}
        out[prov] = {
            "base_url": str(node.get("base_url") or ""),
            "model": str(node.get("model") or ""),
            "priority": int(node["priority"]) if str(
                node.get("priority") or "").strip().isdigit() else "",
            "has_api_key": bool(node.get("api_key")),
        }
    return out


# Providers the UI editor manages. openrouter/nvidia carry fixed default
# endpoints (LLM_PROVIDER_DEFAULTS); "custom" is fully user-supplied.
LLM_PROVIDERS: tuple[str, ...] = ("openrouter", "nvidia", "custom")

LLM_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1"},
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1"},
}


def llm_provider_chain() -> list[str]:
    """Provider names in effective call order (priority-aware, read-only).

    Mirrors the ordering rules of ``scripts/tailor_from_jd.llm_config``:
    providers with an explicit numeric ``priority`` come first (lower =
    earlier), the rest follow in built-in order. Providers without an API
    key are excluded — except ``custom``, which is keyless by design and
    included when it has both a base_url and a model.
    """
    if config_lib is None:
        return []
    raw = config_lib.load_config()
    providers = raw.get("llm", {}).get("providers", {}) if isinstance(
        raw.get("llm"), dict) else {}
    entries: list[tuple[int, str]] = []
    for default_rank, name in enumerate(LLM_PROVIDERS):
        node = providers.get(name) if isinstance(
            providers.get(name), dict) else {}
        has_key = bool(node.get("api_key"))
        usable_custom = (name == "custom" and bool(node.get("base_url"))
                         and bool(node.get("model")))
        if not (has_key or usable_custom):
            continue
        raw_priority = str(node.get("priority") or "").strip()
        priority = int(raw_priority) if raw_priority.isdigit() else (
            100 + default_rank)
        entries.append((priority, name))
    entries.sort(key=lambda e: e[0])  # stable: ties keep built-in order
    return [name for _p, name in entries]


def update_llm_providers(updates: dict) -> dict:
    """Persist provider endpoint edits into ``<data_root>/config.yaml``.

    ``updates`` maps provider name -> {base_url, model, priority?, api_key?}.
    Empty strings leave existing values untouched; keys are write-only (they
    are saved but never rendered back). ``priority`` is a positive integer
    where 1 = tried first (lower number = higher precedence); ties fall back
    to the built-in provider order. For preset providers an empty base_url
    falls back to the fixed default endpoint. The file is written with
    chmod 600 so the next ``config_lib.load_config()`` call picks the
    values up.
    """
    if config_lib is None:
        raise RuntimeError("config_lib unavailable")
    config_path = config_lib.data_root() / "config.yaml"
    raw = config_lib.load_config()
    llm = raw.setdefault("llm", {})
    if not isinstance(llm, dict):
        raise ValueError("config 'llm' section is not a mapping")
    providers = llm.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("config 'llm.providers' section is not a mapping")

    for prov in LLM_PROVIDERS:
        changes = updates.get(prov)
        if not isinstance(changes, dict):
            continue
        node = providers.setdefault(prov, {})
        for field in ("base_url", "model"):
            value = str(changes.get(field) or "").strip()
            if value:
                node[field] = value
            elif field == "base_url" and prov in LLM_PROVIDER_DEFAULTS:
                # Preset provider: empty means "use the fixed endpoint".
                node[field] = LLM_PROVIDER_DEFAULTS[prov]["base_url"]
        raw_priority = changes.get("priority")
        raw_priority = "" if raw_priority is None else str(raw_priority).strip()
        if raw_priority:
            try:
                # ui.number yields floats ("1.0"); accept both int and float text.
                parsed = int(float(raw_priority))
            except ValueError:
                raise ValueError(
                    f"priority for provider '{prov}' must be a whole number, "
                    f"got {raw_priority!r}")
            if parsed != float(raw_priority):
                raise ValueError(
                    f"priority for provider '{prov}' must be a whole number, "
                    f"got {raw_priority!r}")
            if parsed < 1 or parsed > 99:
                raise ValueError(
                    f"priority for provider '{prov}' must be between 1 and 99, "
                    f"got {parsed}")
            node["priority"] = parsed
        key = changes.get("api_key")
        if isinstance(key, str) and key.strip():
            node["api_key"] = key.strip()

    import os
    import yaml

    text = yaml.safe_dump(raw, sort_keys=False, default_flow_style=False)
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass
    return {"path": str(config_path),
            "providers": sorted(providers.keys())}


def config_status() -> dict:
    """Read-only view of which expected keys exist in ``load_config()``."""
    import config_lib as cfg

    root = cfg.data_root()
    raw = cfg.load_config()

    def has(key: str) -> bool:
        node: object = raw
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return True

    return {
        "data_root": str(root),
        "config_path": str(root / "config.yaml"),
        "keys": [{"key": k, "present": has(k)} for k in EXPECTED_CONFIG_KEYS],
        "extra_keys": sorted(k for k in raw.keys() if isinstance(k, str)),
        "loaded": bool(raw),
    }


# ---------------------------------------------------------------- pipeline
# UI-level Kanban stages mapped onto engine-layer application statuses.
PIPELINE_STAGES: tuple[str, ...] = (
    "Saved", "Preparing", "Applied", "Interviewing", "Closed",
)

STAGE_TO_STATUS: dict[str, str] = {
    "Saved": "queued",
    "Preparing": "ready_to_apply",
    "Applied": "submitted",
    "Interviewing": "interview",
    "Closed": "withdrawn",
}

STATUS_TO_STAGE: dict[str, str] = {
    "queued": "Saved",
    "saved": "Saved",
    "": "Saved",
    "ready_to_apply": "Preparing",
    "preparing": "Preparing",
    "resume_ready": "Preparing",
    "submitted": "Applied",
    "acknowledged": "Applied",
    "applied": "Applied",
    "interview": "Interviewing",
    "interviewing": "Interviewing",
    "rejected": "Closed",
    "withdrawn": "Closed",
    "closed": "Closed",
}


def status_to_stage(status: str | None) -> str:
    """Map a raw application CSV status to a Kanban stage label."""
    return STATUS_TO_STAGE.get((status or "").strip().lower(), "Saved")


def update_application_stage(
    application_id: str,
    stage: str,
    apps_path: str | Path | None = None,
    today: datetime.date | None = None,
) -> list[str]:
    """Thin UI wrapper around the engine-layer status transition.

    Resolves ``application_id`` (matches either ``application_id`` or
    ``job_id``), translates the UI stage to the canonical engine status and
    delegates to ``scripts/application_sync.mark_status`` / ``write_apps``.
    The page never touches the CSV directly. Returns the change log.
    """
    import application_sync as app_sync

    if stage not in STAGE_TO_STATUS:
        raise ValueError(f"unknown pipeline stage {stage!r}")
    path = Path(apps_path) if apps_path else app_sync.APPS_CSV
    today = today or datetime.date.today()

    rows = app_sync.read_apps(path)
    row = next(
        (r for r in rows
         if r.get("application_id") == application_id
         or r.get("job_id") == application_id),
        None,
    )
    if row is None:
        raise ValueError(f"application not found: {application_id}")

    target_status = STAGE_TO_STATUS[stage]
    if target_status in app_sync.VALID_STATUSES:
        changes = app_sync.mark_status(row, target_status, today)
    else:
        # Pre-submission stages (Saved/Preparing) have no dedicated engine
        # transition; record them through the engine's own readers/writers so
        # locking/formatting stays consistent.
        current = (row.get("status") or "").strip().lower() or "(empty)"
        row["status"] = target_status
        row["current_stage"] = target_status
        row["date_last_status_change"] = today.isoformat()
        changes = [f"status {current} -> {target_status}"]

    app_sync.write_apps(rows, path=path)

    # Parallel tracking: mirror the new engine status onto the canonical job
    # row (add-only ``application_status`` column). Manual rows whose job_id
    # is their application_id simply find no job row and skip silently.
    sync_job_application_status(str(row.get("job_id") or application_id),
                                target_status)

    return changes


def track_job_as_application(job_id: str, status: str = "queued") -> dict:
    """Create an application row linked to a canonical jobs.csv row.

    Pulls company/role/url from the job record so the /jobs dialog can queue
    a role onto the Applications board in one click, then mirrors the status
    onto the job row. Raises ``ValueError`` for unknown job ids and re-raises
    ``add_application`` validation errors (blank company/title).
    """
    path, _fieldnames, rows = _read_jobs_rows()
    job = next((r for r in rows if r.get("job_id") == job_id), None)
    if job is None:
        raise ValueError(f"unknown job_id: {job_id}")
    # Guard against double-tracking: one open application per job.
    existing = load_applications()
    if not existing.empty and "job_id" in existing.columns:
        already = existing[
            existing["job_id"].fillna("").astype(str) == job_id]  # type: ignore[union-attr]
        if not already.empty:
            statuses = ", ".join(sorted(set(
                already["status"].fillna("queued").astype(str))))
            raise ValueError(
                f"already tracked on the Applications board (status: {statuses})")
    row = add_application(
        company=str(job.get("company") or "").strip(),
        role=str(job.get("title") or "").strip(),
        job_url=str(job.get("canonical_application_url")
                    or job.get("job_url") or "").strip(),
        status=status,
    )
    # Link the application back to the canonical job id (add_application
    # defaults both ids to the slug; the canonical job id wins here).
    apps = applications_csv_path()
    with apps.open(newline="", encoding="utf-8") as fh:
        all_rows = list(csv.DictReader(fh))
    for app_row in all_rows:
        if app_row.get("application_id") == row["application_id"]:
            app_row["job_id"] = job_id
            break
    fieldnames = list(APPLICATION_FIELDS)
    if all_rows:
        seen = set(fieldnames)
        fieldnames = list(all_rows[0].keys()) + [
            f for f in fieldnames if f not in seen]
    with apps.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    sync_job_application_status(job_id, status)
    return {**row, "job_id": job_id}


# ---------------------------------------------------------------- outreach
DAILY_SEND_CAP = 25  # docs/rules/OUTREACH_RULES.md §8: ≤25 sends/day

_SENT_STATUSES = ("sent_no_note", "sent_with_note")


def load_connection_requests(requests_path: str | Path | None = None) -> list[dict]:
    """Ledger rows via the engine loader (missing file -> empty list).

    The default path is re-resolved through :func:`_data_root` on every call
    (``connection_queue`` bakes ``REQ_PATH`` in at import time, which goes
    stale across JOBHUNT_HOME changes / long-lived processes).
    """
    import connection_queue as cq

    path = Path(requests_path) if requests_path else (
        _data_root() / "tracking" / "messages" / "connection_requests.csv")
    try:
        return cq.read_requests(path)
    except Exception as exc:  # noqa: BLE001 - graceful empty state
        print(f"ui.data: could not read {path}: {exc}")
        return []


def load_requests_df(requests_path: str | Path | None = None) -> pd.DataFrame:
    """DataFrame view of the connection-request ledger."""
    cols = ["request_id", "person_name", "company", "send_status", "date_queued", "date_sent"]
    rows = load_connection_requests(requests_path)
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    # Normalize the verbose header names used by the engine ledger.
    rename = {
        "note_basis(hiring_post|shared_ctx|job_specific|generic)": "note_basis",
        "send_status(pending|approved|sent_no_note|sent_with_note|connected|declined|failed)": "send_status",
    }
    return df.rename(columns=rename)


def approve_request(
    request_id: str,
    requests_path: str | Path | None = None,
    today: datetime.date | None = None,
) -> dict:
    """Thin UI wrapper around the engine's approve interlock.

    Only ``pending`` rows may be approved (append-only ledger enforced by
    ``connection_queue._set_status``); the engine primitives do the actual
    validation and write. Returns the updated row.
    """
    import connection_queue as cq

    path = Path(requests_path) if requests_path else cq.REQ_PATH
    today = today or datetime.date.today()
    rows = cq.read_requests(path)
    try:
        row = cq._find(rows, request_id)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    if cq._status(row) != "pending":
        raise ValueError(
            f"approve requires pending status, got {cq._status(row)!r}")
    cq._set_status(row, "approved")
    row["notes"] = (row["notes"] + "; " if row["notes"] else "") + \
                   f"approved {today.isoformat()}"
    cq.write_requests(rows, path=path)
    return row


def send_cap_progress(
    requests_path: str | Path | None = None,
    today: datetime.date | None = None,
) -> dict[str, int]:
    """Daily-send cap meter computed from the ledger."""
    today_iso = (today or datetime.date.today()).isoformat()
    rows = load_connection_requests(requests_path)
    sent_today = 0
    for r in rows:
        status = str(r.get("send_status") or r.get(
            "send_status(pending|approved|sent_no_note|sent_with_note|"
            "connected|declined|failed)", "")).split("(")[0].strip()
        if status.startswith("sent_") and (r.get("date_sent") or "").strip() == today_iso:
            sent_today += 1
    return {"sent_today": sent_today, "cap": DAILY_SEND_CAP, "remaining": max(DAILY_SEND_CAP - sent_today, 0)}


# --- Recommended-connections directory (/network) ---------------------------
#
# One merged view over every person-source the sweeps produce:
#   1. connection_requests.csv ledger (queued/approved/sent/connected)
#   2. contacts.csv (referral research output)
#   3. people_sweeps/people_sweep.csv (agent LinkedIn people sweep)
#   4. hiring_posts/hiring_posts.csv (hiring-post posters not yet queued)
#
# Rows are keyed by normalized LinkedIn slug when present, else by
# (normalized name, company). Ledger state always wins so a person queued in
# the ledger never reappears as a bare recommendation.

_PERSON_SOURCES = ("ledger", "contacts", "people_sweep", "hiring_post")

_LEDGER_RANK = {s: i for i, s in enumerate(
    ("pending", "approved", "sent_no_note", "sent_with_note",
     "connected", "declined", "failed"))}


def _norm_person_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", str(name or "").lower())


def _linkedin_slug(url: str) -> str:
    m = re.search(r"linkedin\.com/in/([a-z0-9\-_%]+)", str(url or "").lower())
    return m.group(1) if m else ""


def _ledger_reason(r: dict) -> str:
    """Human 'why connect' line for a ledger row (basis + score + note)."""
    basis = str(
        r.get("note_basis")
        or r.get("note_basis(hiring_post|shared_ctx|job_specific|generic)")
        or "generic"
    ).strip()
    parts = [f"{basis} note drafted"]
    if r.get("score"):
        parts.append(f"score {r['score']}")
    draft = str(r.get("note_draft") or "").strip()
    if draft:
        parts.append(f"{len(draft)}-char note ready")
    return " · ".join(parts)


def _person_row(*, name: str, company: str = "", title: str = "",
                linkedin_url: str = "", email: str = "", person_type: str = "",
                status: str = "", source: str = "", reason: str = "",
                post_url: str = "", date_str: str = "",
                request_id: str = "") -> dict:
    row = {
        "name": name, "company": company, "title": title,
        "linkedin_url": linkedin_url, "email": email,
        "person_type": person_type, "status": status, "source": source,
        "reason": reason, "post_url": post_url, "date": date_str,
    }
    if request_id:
        # Ledger rows carry their ledger id so the UI can act on them.
        row["request_id"] = request_id
    return row


def _ledger_people() -> list[dict]:
    rows = []
    for r in load_connection_requests():
        raw_status = str(r.get("send_status") or "")
        rows.append(_person_row(
            name=str(r.get("person_name") or ""),
            company=str(r.get("company") or ""),
            title=str(r.get("person_type") or ""),
            linkedin_url=str(r.get("linkedin_url") or ""),
            email=str(r.get("email") or ""),
            person_type=str(r.get("person_type") or ""),
            status=raw_status.split("(")[0].strip() or "pending",
            source="ledger",
            reason=_ledger_reason(r),
            post_url=str(r.get("source_post_url") or ""),
            date_str=str(r.get("date_queued") or ""),
            request_id=str(r.get("request_id") or ""),
        ))
    return rows


def _clean(value, limit: int = 0) -> str:
    """Stringify a pandas cell; blank/NaN cells become '' (not 'nan')."""
    text = str(value if value is not None else "").strip()
    if text.lower() in ("nan", "none"):
        text = ""
    return text[:limit] if limit else text


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value) -> str:
    """Email cell; legacy rows with shifted columns yield '' (not prose)."""
    text = _clean(value)
    return text if _EMAIL_RE.match(text) else ""


_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _clean_url(value) -> str:
    """URL cell; non-URL junk (shifted columns like 'London') yields ''."""
    text = _clean(value)
    return text if _URL_RE.match(text) else ""


def _contacts_people() -> list[dict]:
    contacts = load_contacts()
    if contacts.empty:
        return []
    rows = []
    for _, c in contacts.iterrows():
        status = _clean(c.get("outreach_status")).lower()
        rows.append(_person_row(
            name=_clean(c.get("name")),
            company=_clean(c.get("company")),
            title=_clean(c.get("role")),
            linkedin_url=_clean_url(c.get("linkedin_url")),
            email=_clean_email(c.get("email")),
            person_type=_clean(c.get("role")),
            status=status or "not_contacted",
            source="contacts",
            reason=_clean_reason(c.get("reason_to_contact")),
        ))
    return rows


def _people_sweep_rows() -> list[dict]:
    df = load_csv("tracking/people_sweeps/people_sweep.csv")
    if df.empty:
        return []
    rows = []
    for _, p in df.iterrows():
        rows.append(_person_row(
            name=_clean(p.get("name")),
            company=_clean(p.get("company")),
            title=_clean(p.get("title")),
            linkedin_url=_clean_url(p.get("linkedin_url")),
            person_type=_clean(p.get("person_type")),
            status=_clean(p.get("status")) or "pending_review",
            source="people_sweep",
            reason=_clean_reason(p.get("why_relevant")),
            post_url=_clean_url(p.get("post_url")),
            date_str=_clean(p.get("date")),
        ))
    return rows


def _hiring_post_people(queued_names: set[str]) -> list[dict]:
    df = load_csv("tracking/hiring_posts/hiring_posts.csv")
    if df.empty:
        return []
    rows = []
    for _, p in df.iterrows():
        name = _clean(p.get("poster_name"))
        # Company pages are not connectable people.
        if not name or "(company page)" in name.lower():
            continue
        name_key = _norm_person_key(name)
        if name_key in queued_names:
            continue
        post_url = _clean_url(p.get("post_url"))
        roles = _clean(p.get("roles_mentioned"), 100)
        reason = ("hiring post · roles: " + roles) if roles else ""
        if reason.lower() in ("", "unknown"):
            reason = ""
        rows.append(_person_row(
            name=name,
            company=_clean(p.get("company")),
            title=_clean(p.get("poster_headline")),
            linkedin_url=post_url,
            person_type=_clean(p.get("poster_type")),
            status=_clean(p.get("status")) or "new",
            source="hiring_post",
            reason=reason,
            post_url=post_url,
            date_str=(_clean(p.get("posted_date"))
                      or _clean(p.get("discovered_date"))),
        ))
    return rows


# Reason strings that carry no signal for the reader.
_JUNK_REASONS = {"", "unknown", "none", "n/a", "na", "-"}


def _clean_reason(value, limit: int = 140) -> str:
    """Why-connect text; placeholder junk like 'Unknown' yields ''."""
    return _clean(value, limit) if _clean(value).lower() \
        not in _JUNK_REASONS else ""


def network_recommendations() -> list[dict]:
    """Merged recommended-connections directory for /network.

    Deduped across all four sources; ledger entries win over raw sweep rows.
    Sorted: actionable ledger states first (pending > approved > sent_*),
    then untouched contacts / fresh sweep rows, then connected/terminal.
    """
    merged: dict[str, dict] = {}

    def key_of(person: dict) -> str:
        slug = _linkedin_slug(person["linkedin_url"])
        if slug:
            return f"slug:{slug}"
        return f"name:{_norm_person_key(person['name'])}:" \
               f"{person['company'].strip().lower()}"

    def put(person: dict) -> None:
        k = key_of(person)
        existing = merged.get(k)
        # Priority order mirrors _PERSON_SOURCES: earlier source wins.
        if existing is None or _PERSON_SOURCES.index(
                existing["source"]) > _PERSON_SOURCES.index(person["source"]):
            merged[k] = person

    ledger_rows = _ledger_people()
    for row in ledger_rows:
        put(row)

    taken_keys = {key_of(r) for r in ledger_rows}
    taken_names = {_norm_person_key(r["name"]) for r in ledger_rows}

    for c in _contacts_people():
        put(c)

    for s in _people_sweep_rows():
        put(s)

    seen_names = {_norm_person_key(p["name"]) for p in merged.values()}
    for h in _hiring_post_people(taken_names | seen_names):
        put(h)

    def rank(p: dict) -> tuple:
        st = p["status"].lower()
        if p["source"] == "ledger":
            return (0, _LEDGER_RANK.get(st, 99))
        if st in ("connected", "contacted", "responded"):
            return (3, p["name"].lower())
        if st in ("not_contacted", "new", "pending_review", ""):
            return (1, p["name"].lower())
        return (2, p["name"].lower())

    out = list(merged.values())
    out.sort(key=rank)
    return out


def network_source_counts(recommendations: list[dict] | None = None) -> dict:
    """Per-source + per-status counts backing the /network KPI strip."""
    recs = recommendations if recommendations is not None \
        else network_recommendations()
    sources = {s: 0 for s in _PERSON_SOURCES}
    statuses: dict[str, int] = {}
    with_email = with_linkedin = actionable = 0
    for p in recs:
        sources[p["source"]] = sources.get(p["source"], 0) + 1
        statuses[p["status"]] = statuses.get(p["status"], 0) + 1
        if p["email"].strip():
            with_email += 1
        if p["linkedin_url"].strip():
            with_linkedin += 1
        if p["source"] == "ledger" or p["status"].lower() in (
                "not_contacted", "new", "pending_review", ""):
            actionable += 1
    return {
        "total": len(recs), "sources": sources, "statuses": statuses,
        "with_email": with_email, "with_linkedin": with_linkedin,
        "actionable": actionable,
    }


def find_cron_job_id(name: str) -> str | None:
    """Look up a Hermes cron job id by name (job-hunt profile store first).

    Returns None when the store is missing/unreadable or the job does not
    exist — callers surface an honest 'automation unavailable' state.
    """
    import json as _json

    home = Path.home()
    candidates = [
        home / ".hermes" / "profiles" / "job-hunt" / "cron" / "jobs.json",
        home / ".hermes" / "cron" / "jobs.json",
    ]
    store_path = next((p for p in candidates if p.exists()), None)
    if store_path is None:
        return None
    try:
        raw = _json.loads(store_path.read_text())
    except (OSError, ValueError):
        return None
    items = raw if isinstance(raw, list) else raw.get("jobs", [])
    for job in items:
        if isinstance(job, dict) and job.get("name") == name:
            return str(job.get("id") or "") or None
    return None


def kpi_counts() -> dict[str, int]:
    """Real KPI counts read straight from the tracking CSVs."""
    jobs = load_jobs()
    apps = load_applications()
    contacts = load_contacts()
    companies = load_companies()

    submitted = 0
    if not apps.empty and "status" in apps.columns:
        submitted = int(apps["status"].astype(str).eq("submitted").sum())

    open_jobs = 0
    if not jobs.empty and "status" in jobs.columns:
        open_jobs = int(jobs["status"].astype(str).eq("open").sum())

    return {
        "jobs": len(jobs),
        "open_jobs": open_jobs,
        "applications": len(apps),
        "submitted": submitted,
        "contacts": len(contacts),
        "companies": len(companies),
    }


# --- Queue views (Task 3.1) ------------------------------------------------
#
# The review CSVs are produced by ``scripts/today_queue.py``. We read its
# outputs rather than duplicating its ranking/filtering logic.

REVIEWS_DIR = "execution_results/reviews"


def load_queue_views() -> dict[str, pd.DataFrame]:
    """Load today's review CSVs written by ``scripts/today_queue.py``.

    Returns a dict with ``fresh_jobs``, ``top_queue`` and ``needing_attention``
    DataFrames (each empty when the underlying file is missing).
    """
    fresh_name = f"fresh_jobs_{datetime.date.today().isoformat()}.csv"
    fresh_rel = f"{REVIEWS_DIR}/{fresh_name}"
    if (_data_root() / fresh_rel).is_file():
        fresh = load_csv(fresh_rel)
    else:
        # Fall back to the most recent fresh-jobs snapshot.
        latest = ""
        reviews = _data_root() / REVIEWS_DIR
        if reviews.is_dir():
            candidates = sorted(p.name for p in reviews.glob("fresh_jobs_*.csv"))
            if candidates:
                latest = candidates[-1]
        fresh = load_csv(f"{REVIEWS_DIR}/{latest}") if latest else pd.DataFrame()
    top = load_csv(f"{REVIEWS_DIR}/top_queue.csv")
    attention = load_csv(f"{REVIEWS_DIR}/needing_attention.csv")

    # Mutually exclusive buckets (/today): each job appears in exactly one
    # section. Precedence order:
    #   1. Top Queue         (highest-priority open jobs)
    #   2. Fresh Jobs        (latest pulled/discovered within last 3 days)
    #   3. Needing Attention (ambiguous / stale / thin-JD leftovers)
    # This keeps "Fresh Jobs" meaningfully *fresh* and reserves "Needing
    # Attention" for jobs not otherwise claimed.
    def _exclude(df: pd.DataFrame, seen_ids: list[str]) -> pd.DataFrame:
        if df.empty or "job_id" not in df.columns or not seen_ids:
            return df
        mask = ~df["job_id"].astype(str).isin(seen_ids)
        return df.loc[mask].copy()

    top_ids = list(top["job_id"].astype(str)) if not top.empty else []
    fresh_excl = _exclude(fresh, top_ids)
    seen = top_ids + (
        list(fresh_excl["job_id"].astype(str))
        if not fresh_excl.empty else [])
    attention_excl = _exclude(attention, seen)

    return {
        "fresh_jobs": fresh_excl,
        "top_queue": top,
        "needing_attention": attention_excl,
    }


def get_followups(today: datetime.date | None = None) -> list[dict]:
    """Follow-up actions derived from loaded applications via followups_lib."""
    apps = load_applications()
    required = {"job_id", "company", "status", "date_submitted"}
    if apps.empty or not required.issubset(set(apps.columns)):
        return []
    if followups_lib is None:
        return []
    try:
        return followups_lib.get_followups(apps, today)
    except ValueError:
        return []


# --- Pure helpers (Task 3.1) -----------------------------------------------

# Fields surfaced first in the job detail dialog, in display order.
JOB_DETAIL_FIELDS = [
    "job_id",
    "company",
    "title",
    "location",
    "status",
    "fit_score",
    "fit_tier",
    "role_family",
    "seniority",
    "priority_v2",
    "application_priority",
    "networking_priority",
    "key_requirements",
    "matching_strengths",
    "main_gaps",
    "resume_variant",
    "source",
    "date_discovered",
    "date_posted",
    "date_updated",
    "last_checked",
    "job_url",
    "canonical_application_url",
    "notes",
]


def filter_jobs(
    jobs: pd.DataFrame,
    search: str = "",
    fit_tier: str = "",
    priority: str = "",
    *,
    source: str = "",
    status: str = "",
    role_family: str = "",
    min_priority: float | None = None,
    recommended_action: str = "",
    max_age_days: int | None = None,
) -> pd.DataFrame:
    """Filter jobs by free-text search plus exact per-column matches.

    Empty filter values mean "no filtering" for that dimension.
    ``source``/``status``/``role_family`` match their columns case-insensitively;
    ``recommended_action`` matches the scorer's action vocabulary;
    ``max_age_days`` keeps rows whose ``date_posted`` (fallback
    ``date_discovered``) is within the last N days;
    ``min_priority`` keeps rows with ``priority_v2 >= min_priority`` (only
    when the column exists and the value is not None).
    """
    if jobs.empty:
        return jobs
    out = jobs
    query = (search or "").strip().lower()
    if query:
        mask = out.apply(
            lambda col: col.astype(str).str.lower().str.contains(query, regex=False)
        ).any(axis=1)
        out = out[mask]
    if fit_tier:
        if "fit_tier" in out.columns:
            out = out[out["fit_tier"].astype(str).str.lower() == fit_tier.lower()]
        else:
            return out.iloc[0:0]
    if priority:
        if "application_priority" in out.columns:
            out = out[
                out["application_priority"].astype(str).str.lower()
                == priority.lower()
            ]
        else:
            return out.iloc[0:0]
    if source:
        if "source" in out.columns:
            out = out[out["source"].astype(str).str.lower() == source.lower()]
        else:
            return out.iloc[0:0]
    if status:
        if "status" in out.columns:
            out = out[out["status"].astype(str).str.lower() == status.lower()]
        else:
            return out.iloc[0:0]
    if role_family:
        if "role_family" in out.columns:
            out = out[
                out["role_family"].astype(str).str.lower()
                == role_family.lower()
            ]
        else:
            return out.iloc[0:0]
    if min_priority is not None:
        if "priority_v2" in out.columns:
            scores = pd.to_numeric(out["priority_v2"], errors="coerce")
            out = out[scores.notna() & (scores >= float(min_priority))]
        else:
            return out.iloc[0:0]
    if recommended_action:
        if "recommended_action" in out.columns:
            out = out[
                out["recommended_action"].astype(str).str.lower()
                == recommended_action.lower()
            ]
        else:
            return out.iloc[0:0]
    if max_age_days is not None and int(max_age_days) > 0:
        date_col = next(
            (c for c in ("date_posted", "date_discovered", "date_updated")
             if c in out.columns),
            None,
        )
        if date_col:
            dates = pd.to_datetime(out[date_col], errors="coerce")
            cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(
                days=int(max_age_days))
            out = out[dates.notna() & (dates >= cutoff)]
    return out


# --- Saved job views --------------------------------------------------------
#
# Named filter+sort presets persisted as CSV (repo convention — no JSON/DB).
SAVED_VIEWS_COLUMNS = [
    "view_id", "name", "search", "fit_tier", "priority", "source", "status",
    "role_family",
    "min_priority", "sort_by", "sort_dir", "created_at",
]


def _slugify(name: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(name or ""))
    return text.strip("-") or "view"


def _saved_views_path() -> Path:
    return _data_root() / "tracking" / "jobs" / "saved_views.csv"


def list_saved_views() -> list[dict]:
    """All saved job views; missing/corrupt file -> empty list."""
    df = load_csv(str(_saved_views_path().relative_to(_data_root())),
                  columns=SAVED_VIEWS_COLUMNS)
    if df.empty:
        return []
    return df.fillna("").to_dict("records")


def save_view(
    name: str,
    search: str = "",
    fit_tier: str = "",
    priority: str = "",
    source: str = "",
    status: str = "",
    role_family: str = "",
    min_priority: float | None = None,
    sort_by: str = "priority_v2",
    sort_dir: str = "desc",
) -> dict:
    """Create or replace (upsert by name) a saved view; returns the row."""
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("view name must be non-empty")
    row = {
        "view_id": _slugify(clean_name),
        "name": clean_name,
        "search": str(search or ""),
        "fit_tier": str(fit_tier or ""),
        "priority": str(priority or ""),
        "source": str(source or ""),
        "status": str(status or ""),
        "role_family": str(role_family or ""),
        "min_priority": "" if min_priority is None else str(min_priority),
        "sort_by": str(sort_by or "priority_v2"),
        "sort_dir": str(sort_dir or "desc"),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    existing = [v for v in list_saved_views() if v.get("name") != clean_name]
    existing.append(row)
    path = _saved_views_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(existing, columns=SAVED_VIEWS_COLUMNS).to_csv(path, index=False)
    return row


def delete_view(view_id: str) -> bool:
    """Remove the saved view with ``view_id``; True when a row was removed."""
    remaining = [v for v in list_saved_views() if v.get("view_id") != str(view_id)]
    if len(remaining) == len(list_saved_views()):
        return False
    path = _saved_views_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(remaining, columns=SAVED_VIEWS_COLUMNS).to_csv(path, index=False)
    return True


def tier_counts(jobs: pd.DataFrame) -> list[tuple[str, int]]:
    """Count open jobs per fit_tier, sorted by tier name ('' bucket last)."""
    if jobs.empty or "fit_tier" not in jobs.columns or "status" not in jobs.columns:
        return []
    open_jobs = jobs[jobs["status"].astype(str).str.lower() == "open"]
    tiers = open_jobs["fit_tier"].fillna("").astype(str).str.strip()
    counts = tiers.value_counts()
    result = [(str(t), int(c)) for t, c in counts.items()]
    result.sort(key=lambda item: (item[0] == "", item[0]))
    return result


def connections_pending(contacts: pd.DataFrame) -> int:
    """Count contacts whose outreach is still pending (not yet contacted)."""
    if contacts.empty or "outreach_status" not in contacts.columns:
        return 0
    status = contacts["outreach_status"].fillna("").astype(str).str.strip().str.lower()
    return int(status.isin({"", "pending", "queued", "to_contact"}).sum())


def job_detail(record: dict) -> list[tuple[str, str]]:
    """Ordered (field, value) pairs for the job detail dialog.

    Keeps only known fields with non-empty values; unknown extra fields are
    appended afterwards so nothing in the data is hidden.
    """
    known = [(f, str(record[f])) for f in JOB_DETAIL_FIELDS if record.get(f)]
    extras = [
        (k, str(v))
        for k, v in record.items()
        if k not in JOB_DETAIL_FIELDS and v is not None and str(v).strip()
    ]
    return known + extras


# --- Clickable provenance links ---------------------------------------------
#
# Every tracked entity keeps its source URLs in the CSVs (jobs.csv:
# job_url/canonical_application_url, contacts.csv: linkedin_url,
# hiring_posts.csv: post_url/application_url, companies.csv: careers_url).
# These helpers surface them so the UI can render each one clickable.

LINK_FIELD_LABELS = {
    "job_url": "Job posting",
    "canonical_application_url": "Application page",
    "linkedin_url": "LinkedIn profile",
    "source_post_url": "Source LinkedIn post",
    "post_url": "LinkedIn post",
    "application_url": "Application page",
    "careers_url": "Careers page",
}


def job_links(record: dict) -> list[tuple[str, str]]:
    """(label, url) pairs for every known link field set on ``record``.

    Unknown extra fields holding an http(s) URL are appended too, so newly
    tracked link columns become clickable without a code change. Labels are
    human names; duplicates by URL are dropped.
    """
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, value in record.items():
        url = str(value or "").strip()
        if not url.lower().startswith(("http://", "https://")) or " " in url:
            continue
        if url in seen:
            continue
        seen.add(url)
        label = LINK_FIELD_LABELS.get(key, str(key).replace("_", " ").title())
        links.append((label, url))
    return links


def load_job_description(record: dict) -> str:
    """Full job-description text from the row's ``description_file``.

    Paths are repository-relative under the data root (jobs.csv convention);
    returns "" when the pointer is empty or the file is missing/unreadable.
    """
    relative = str(record.get("description_file") or "").strip()
    if not relative:
        return ""
    path = _data_root() / relative
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ui.data: could not read {path}: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Data health & freshness (spec 003 §6.1 stale/partial/error states)
# ---------------------------------------------------------------------------

CANONICAL_SOURCES: tuple[str, ...] = (
    "tracking/jobs/jobs.csv",
    "tracking/applications/applications.csv",
    "tracking/contacts/contacts.csv",
    "tracking/companies/companies.csv",
    "tracking/messages/connection_requests.csv",
)


def _iso_mtime(path: Path) -> str | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return datetime.datetime.fromtimestamp(
        mtime, tz=datetime.timezone.utc).isoformat()


def data_health() -> list[dict]:
    """Per-source health for :func:`CANONICAL_SOURCES` (never raises).

    Each entry: ``{'path': rel, 'exists': bool, 'rows': int|None,
    'mtime': iso8601|None, 'readable': bool}``. ``rows``/``readable`` are
    ``False``/``None`` when the file is missing or unparseable so pages can
    render a partial-state banner naming the failing source.
    """
    report: list[dict] = []
    for rel in CANONICAL_SOURCES:
        path = _data_root() / rel
        exists = path.is_file()
        rows: int | None = None
        readable = False
        if exists:
            try:
                rows = int(len(pd.read_csv(path)))
                readable = True
            except Exception as exc:  # noqa: BLE001 - report, don't raise
                print(f"ui.data: could not read {path}: {exc}")
        report.append({
            "path": rel,
            "exists": exists,
            "rows": rows,
            "mtime": _iso_mtime(path) if exists else None,
            "readable": readable,
        })
    return report


def source_freshness(rel_path: str, stale_days: float = 7) -> dict:
    """Freshness of one tracked CSV vs UTC now.

    Returns ``{'path', 'exists', 'mtime': iso8601|None, 'age_days':
    float|None, 'stale': bool}``. Missing files are reported (never raised);
    they are not marked stale — callers decide how to render non-existent
    sources via ``exists=False``.
    """
    path = _data_root() / rel_path
    exists = path.is_file()
    mtime_iso = _iso_mtime(path) if exists else None
    age_days: float | None = None
    stale = False
    if mtime_iso is not None:
        mtime = datetime.datetime.fromisoformat(mtime_iso)
        age_days = max(
            (datetime.datetime.now(datetime.timezone.utc) - mtime).total_seconds() / 86400.0,
            0.0,
        )
        stale = age_days > float(stale_days)
    return {
        "path": rel_path,
        "exists": exists,
        "mtime": mtime_iso,
        "age_days": age_days,
        "stale": stale,
    }


# ---------------------------------------------------------------------------
# Truthful labels & explicit outcomes (spec 003 §6.2)
#
# Pipeline stage and terminal outcome are SEPARATE dimensions: stages end at
# Applied/Interviewing; rejections, withdrawals etc. are recorded as explicit
# outcomes rather than being conflated into the "Closed" stage.
# ---------------------------------------------------------------------------

#: Explicit terminal outcomes recorded separately from pipeline stage
#: (spec 003 §6.2). These are NOT pipeline stages.
OUTCOMES: tuple[str, ...] = (
    "rejected",
    "withdrawn",
    "role_closed",
    "no_response",
    "offer_declined",
    "other",
)

#: Map each explicit outcome onto the engine's legacy status vocabulary so
#: writes stay compatible with existing scripts until the engine gains an
#: outcome column. ``no_response`` has no dedicated legacy value and falls
#: back to ``withdrawn`` (see APPLICATION_OUTCOME_NOTES).
OUTCOME_TO_LEGACY_STATUS: dict[str, str] = {
    "rejected": "rejected",
    "withdrawn": "withdrawn",
    "role_closed": "closed",
    "no_response": "withdrawn",
    "offer_declined": "declined",
    "other": "closed",
}

#: One-line human explanation per outcome, used in tooltips/confirm dialogs.
APPLICATION_OUTCOME_NOTES: dict[str, str] = {
    "rejected": "The company rejected this application.",
    "withdrawn": "You chose to withdraw from this process.",
    "role_closed": "The role was closed/filled or the posting was removed.",
    "no_response": "No reply after follow-ups — recorded as withdrawn by convention.",
    "offer_declined": "An offer was received and you declined it.",
    "other": "Terminal outcome that fits no other category.",
}

# Inverse of OUTCOME_TO_LEGACY_STATUS for splitting legacy statuses back into
# (stage, outcome). Direct outcome names win over derived ones ('withdrawn'
# resolves to the explicit 'withdrawn' outcome, not 'no_response').
_LEGACY_TO_OUTCOME: dict[str, str] = {}
for _outcome in OUTCOMES:
    _LEGACY_TO_OUTCOME.setdefault(OUTCOME_TO_LEGACY_STATUS[_outcome], _outcome)

#: Display-label rename map (spec 003 §6.2): current label -> truthful label.
#: Pages consume these constants; badge colors in ui/components.py are owned
#: elsewhere and intentionally unchanged here.
LABEL_RENAMES: dict[str, str] = {
    "Applications Sent": "Submitted (local status)",
    "Connections Pending": "Awaiting outreach (ledger)",
    "Closed": "Completed",
}


def stage_outcome_split(status: str | None) -> tuple[str, str]:
    """Split a raw application status into ``(stage, outcome)``.

    Accepts either a legacy engine status ('rejected', 'withdrawn', 'closed',
    'declined') or a direct outcome name ('role_closed', ...). Terminal
    statuses (per the OUTCOME_TO_LEGACY_STATUS inverse) return ``"Closed"``
    plus the explicit outcome; everything else returns the stage with an
    empty outcome string. Unknown statuses fall back to
    :func:`status_to_stage`'s default.
    """
    clean = (status or "").strip().lower()
    if clean in OUTCOMES:
        # An explicit outcome value passed directly.
        return "Closed", clean
    outcome = _LEGACY_TO_OUTCOME.get(clean, "")
    if outcome:
        # Terminal outcomes always land on the terminal stage — including
        # legacy statuses ('role_closed', 'declined') that predate the stage
        # map and have no STATUS_TO_STAGE entry of their own.
        return "Closed", outcome
    return status_to_stage(clean), ""


# ---------------------------------------------------------------------------
# Score provenance (spec 003 §6.2 priority_v2 tooltip)
# ---------------------------------------------------------------------------

#: Scores below this JD-character budget are flagged less reliable.
THIN_JD_CHARS = 500


def _jd_char_budget(record: dict) -> int:
    raw = record.get("jd_chars")
    if raw is None:
        return len(str(record.get("description", "") or ""))
    try:
        return int(str(raw).strip())
    except ValueError:
        return len(str(record.get("description", "") or ""))


def score_provenance(record: dict) -> list[tuple[str, str]]:
    """Tooltip lines explaining where a job's priority_v2 score came from.

    Pure function over the row dict — never touches disk. Lines:
    scale, computation date, scorer inputs, and an input-quality note that
    warns when the underlying JD text is thin.
    """
    thin = _jd_char_budget(record) < THIN_JD_CHARS
    quality = (
        f"thin JD (<{THIN_JD_CHARS} chars) — score less reliable"
        if thin else f"JD length adequate (>={THIN_JD_CHARS} chars)"
    )
    return [
        ("Scale", "priority_v2 0–100"),
        ("Computed", str(record.get("scored_at") or "unknown date")),
        ("Inputs", "12-dimension scorer (scripts/score_jobs_v2.py)"),
        ("Quality", quality),
    ]


# ------------------------------------------------------------- cron automation
CRON_LINKEDIN_JOBS = (
    "discovery-linkedin",
    "linkedin-people-posts-2h",
)


def cron_health() -> dict:
    """Read the LinkedIn cron jobs' state from the Hermes cron store.

    Returns a dict shaped for the /operations panel: per-job schedule,
    enabled flag, last run status/time, next fire time, and an overall
    gateway heartbeat age. Never raises — a missing/unreadable store
    degrades to ``{"available": False}`` so the UI shows an honest
    "unavailable" state instead of crashing the page.
    """
    import json as _json

    home = Path.home()
    candidates = [
        home / ".hermes" / "profiles" / "job-hunt" / "cron" / "jobs.json",
        home / ".hermes" / "cron" / "jobs.json",
    ]
    store_path = next((p for p in candidates if p.exists()), None)
    result: dict = {
        "available": store_path is not None,
        "store": str(store_path) if store_path else "",
        "jobs": [],
        "heartbeat_lag_s": None,
    }
    if store_path is None:
        return result

    try:
        raw = _json.loads(store_path.read_text())
    except (OSError, ValueError):
        result["available"] = False
        return result
    items = raw if isinstance(raw, list) else raw.get("jobs", [])

    now = datetime.datetime.now(datetime.timezone.utc)
    for job in items:
        if not isinstance(job, dict) or job.get("name") not in CRON_LINKEDIN_JOBS:
            continue
        sched = job.get("schedule") or {}
        last_status = str(job.get("last_status") or "")
        entry = {
            "name": job.get("name", ""),
            "schedule": sched.get("display") if isinstance(sched, dict)
            else str(sched),
            "enabled": bool(job.get("enabled")),
            "state": str(job.get("state") or ""),
            "last_status": last_status,
            "last_run_at": str(job.get("last_run_at") or "—"),
            "next_run_at": str(job.get("next_run_at") or "—"),
            "paused_reason": str(job.get("paused_reason") or ""),
        }
        # Heartbeat lag from the profile ticker file (seconds since the
        # scheduler last ticked). None when unreadable.
        hb = store_path.parent / "ticker_heartbeat"
        try:
            age = now.timestamp() - hb.stat().st_mtime
            result["heartbeat_lag_s"] = int(max(0.0, age))
            entry["healthy"] = (
                bool(job.get("enabled"))
                and job.get("state") == "scheduled"
                # Cron store writes "ok"/"completed" on success; "" = never run.
                and last_status in ("", "ok", "completed")
                and result["heartbeat_lag_s"] < 600
            )
        except OSError:
            entry["healthy"] = False
        result["jobs"].append(entry)
    return result


# ------------------------------------------------------------- linkedin posts
HIRED_POSTS_REL = "tracking/hiring_posts/hiring_posts.csv"
KEYWORD_YIELDS_REL = "job_research/config/linkedin_keyword_yields.csv"

POSTER_TYPE_LABELS = {
    "recruiter": "Recruiter",
    "hiring_manager": "Hiring manager",
    "engineer_researcher": "Engineer/Researcher",
}


def load_hiring_posts() -> pd.DataFrame:
    """Canonical hiring-posts table (tracking/hiring_posts/hiring_posts.csv)."""
    df = load_csv(HIRED_POSTS_REL)
    if not df.empty and "posted_date" in df.columns:
        df = df.copy()
        parsed = pd.to_datetime(df["posted_date"], errors="coerce")
        df = df.assign(posted_date=parsed.dt.strftime("%Y-%m-%d").fillna(""))
        df["_recency"] = ((pd.Timestamp.now().normalize()
                           - parsed.dt.normalize()).dt.days)
    return df


def hiring_post_stats(df: pd.DataFrame | None = None) -> dict:
    """Headline counts for the /linkedin-posts KPI grid."""
    if df is None:
        df = load_hiring_posts()
    if df.empty:
        return {"total": 0, "new": 0, "high_priority": 0, "last_7d": 0}
    return {
        "total": int(len(df)),
        "new": int((df.get("status", pd.Series(dtype=str)).fillna("")
                    .str.lower() == "new").sum()),
        "high_priority": int((df.get("priority", pd.Series(dtype=str))
                              .fillna("").str.lower() == "high").sum()),
        "last_7d": int((df.get("_recency", pd.Series(dtype=float))
                        <= 7).sum()),
    }


def keyword_yields() -> list[dict]:
    """Per-query historical yield (runs, new) sorted by yield desc."""
    path = _data_root() / KEYWORD_YIELDS_REL
    if not path.is_file():
        return []
    try:
        raw = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        print(f"ui.data: could not read {path}: {exc}")
        return []
    if raw.empty:
        return []
    agg = (raw.assign(query=raw["query"].astype(str).str.strip().str.lower())
           .groupby("query", as_index=False)
           .agg(runs=("runs", "sum"), new_posts=("new", "sum")))
    agg["yield_per_run"] = (agg["new_posts"] / agg["runs"]).round(2)
    return agg.sort_values(["new_posts", "yield_per_run"],
                           ascending=[False, False]).to_dict("records")


def recent_post_sweep_runs(limit: int = 6) -> list[dict]:
    """Most recent hiring-post sweep run lines from search_runs.csv.

    Covers both run-id families: the 2h cron (``lhp_*``) and the UI-triggered
    sweeps (``lpf_*`` feed, ``lpk_*`` keywords). The canonical file lives
    under the data root; the repo-tree copy is a legacy fallback.
    """
    candidates = [
        _data_root() / "tracking" / "search_runs" / "search_runs.csv",
        Path(__file__).resolve().parent.parent / "tracking" / "search_runs"
        / "search_runs.csv",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            print(f"ui.data: could not read {path}: {exc}")
            continue
        if raw.empty:
            continue
        id_col = next((c for c in ("run_id", "search_id") if c in raw.columns),
                      None)
        if id_col is None:
            continue
        mask = raw[id_col].astype(str).str.match(r"(lhp|lpf|lpk)_", na=False)
        cols = [c for c in ("date", id_col, "sources", "queries",
                            "total_scanned", "results_seen", "new_rows",
                            "new_jobs_found", "status")
                if c in raw.columns]
        return (raw.loc[mask, cols].tail(limit).iloc[::-1]
                .rename(columns={id_col: "run_id"}).to_dict("records"))
    return []


def filter_hiring_posts(
    df: pd.DataFrame,
    search: str = "",
    poster_type: str = "",
    role_family: str = "",
    status: str = "",
    max_age_days: float | None = None,
) -> pd.DataFrame:
    """Server-side filtering for the posts table (mirrors filter_jobs)."""
    out = df
    if out.empty:
        return out
    if search:
        blob = (out.get("poster_name", pd.Series(dtype=str)).fillna("") + " "
                + out.get("company", pd.Series(dtype=str)).fillna("") + " "
                + out.get("roles_mentioned", pd.Series(dtype=str)).fillna("")
                + " " + out.get("notes", pd.Series(dtype=str)).fillna("")).str.lower()
        needle = search.lower()
        out = out[blob.str.contains(needle, regex=False)]
    if poster_type:
        col = out.get("poster_type", pd.Series(dtype=str)).fillna("")
        out = out[col.str.lower() == poster_type.lower()]
    if role_family:
        col = out.get("role_family", pd.Series(dtype=str)).fillna("")
        out = out[col.str.lower() == role_family.lower()]
    if status:
        col = out.get("status", pd.Series(dtype=str)).fillna("")
        out = out[col.str.lower() == status.lower()]
    if max_age_days is not None:
        recency = out.get("_recency", pd.Series(dtype=float))
        out = out[recency.fillna(10**6) <= max_age_days]
    return out


def set_hiring_post_status(post_id: str, new_status: str) -> None:
    """Update the status column of one post row in place (by stable id)."""
    allowed = {"new", "reviewed", "connected", "dismissed"}
    if new_status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    path = _data_root() / HIRED_POSTS_REL
    if not path.is_file():
        raise ValueError(f"{path} is missing")
    import csv as _csv

    with open(path, newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    hits = 0
    for row in rows:
        if row.get("post_id") == post_id:
            row["status"] = new_status
            hits += 1
    if not hits:
        raise ValueError(f"unknown post_id: {post_id}")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
