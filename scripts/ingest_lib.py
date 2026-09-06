"""Upload/ingest extraction pipeline (Layer 4 pure-ish core).

Deterministic, LLM-free heuristics that turn an uploaded document (or pasted
text) into a structured summary so the Profile page can queue it for human
review. Canonical facts still live in ``<data_root>/profile_info/`` YAML with
explicit provenance; nothing here writes a canonical fact without review.

Public surface::

    extract_upload(path_or_text) -> dict
    inbox_dir() / save_to_inbox(filename, data) / list_inbox()
    accept_item(name) / discard_item(name)
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

try:  # Layer 4 stays importable without heavy deps.
    import yaml
except ImportError:  # pragma: no cover - yaml is a hard dep of the repo
    yaml = None

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".yaml", ".yml", ".csv"}

SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "go", "rust", "sql",
    "react", "vue", "angular", "node", "django", "flask", "fastapi",
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy",
    "spark", "kafka", "airflow", "docker", "kubernetes", "terraform",
    "aws", "gcp", "azure", "postgresql", "mysql", "mongodb", "redis",
    "machine learning", "deep learning", "nlp", "computer vision",
    "llm", "reinforcement learning", "mlops", "etl", "rest api", "graphql",
]

JD_SIGNALS = [
    "we are looking for", "responsibilities", "requirements",
    "you will", "the ideal candidate", "about the role", "qualifications",
    "what you'll do", "apply now", "our team is", "job description",
]

RESUME_SIGNALS = [
    "work experience", "education", "skills", "summary of qualifications",
    "professional experience", "certifications", "projects", "curriculum vitae",
    "resume", "references available",
]

NOTES_SIGNALS = [
    "todo", "note to self", "follow up", "remember to", "checklist",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    """Resolve via scripts/config_lib (env var -> config.yaml -> legacy)."""
    try:
        from scripts import config_lib
    except ImportError:  # pragma: no cover - direct-script import shape
        import config_lib  # type: ignore
    return config_lib.data_root()


def profile_info_dir(root: Path | None = None) -> Path:
    return (root or data_root()) / "profile_info"


def inbox_dir(root: Path | None = None) -> Path:
    path = profile_info_dir(root) / "inbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def known_companies(root: Path | None = None) -> set[str]:
    """Company names from tracking/companies CSVs (best effort, lowercase)."""
    names: set[str] = set()
    base = (root or data_root()) / "tracking" / "companies"
    if not base.is_dir():
        return names
    for csv_path in sorted(base.glob("*.csv")):
        try:
            with csv_path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    for key in ("company", "company_name", "name"):
                        value = (row.get(key) or "").strip()
                        if len(value) >= 2:
                            names.add(value.lower())
                            break
        except (OSError, csv.Error):
            continue
    return names


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _pdf_text(path: Path) -> str | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001 - corrupted/unreadable PDFs
        return None


def _docx_text(path: Path) -> str | None:
    """Extract docx text via stdlib zip + XML strip (no python-docx needed)."""
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def read_source(source: Union[str, Path]) -> tuple[str, dict]:
    """Return (text, flags). Unreadable binaries yield '' + needs_manual."""
    flags: dict = {}
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source
                                    and Path(source).exists()):
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = _pdf_text(path)
            if text is None:
                flags["needs_manual"] = True
                text = ""
        elif suffix == ".docx":
            text = _docx_text(path)
            if text is None:
                flags["needs_manual"] = True
                text = ""
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        return text, flags
    return str(source), flags


# ---------------------------------------------------------------------------
# Heuristic classification & entity extraction
# ---------------------------------------------------------------------------

def extract_entities(text: str, companies: set[str] | None = None) -> dict:
    emails = sorted(set(re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))
    phones = sorted(set(re.findall(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", text)))
    skills = []
    lowered = text.lower()
    for skill in SKILL_KEYWORDS:
        pattern = r"\b" + re.escape(skill).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, lowered):
            skills.append(skill)
    found_companies = []
    if companies:
        for name in sorted(companies):
            if re.search(r"\b" + re.escape(name) + r"\b", lowered):
                found_companies.append(name)
    return {
        "emails": emails,
        "phones": phones,
        "skills": skills,
        "companies": found_companies,
    }


def classify_kind(text: str) -> str:
    lowered = text.lower()
    scores = {
        "jd": sum(1 for s in JD_SIGNALS if s in lowered),
        "resume": sum(1 for s in RESUME_SIGNALS if s in lowered),
        "notes": sum(1 for s in NOTES_SIGNALS if s in lowered),
    }
    best = max(scores, key=lambda k: scores[k])
    mapping = {"jd": "jd", "resume": "resume", "notes": "notes"}
    kind = mapping[best] if scores[best] > 0 else "unknown"
    # Emails + education/experience signals lean resume even without headers.
    if kind == "unknown" and re.search(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        kind = "resume"
    return kind


SECTION_FOR_KIND = {
    "resume": "experience.yaml",
    "jd": "preferences.yaml",
    "notes": "notes.yaml",
}


# ---------------------------------------------------------------------------
# Public pipeline API
# ---------------------------------------------------------------------------

def extract_upload(source: Union[str, Path], root: Path | None = None) -> dict:
    """Extract a structured summary from a file path or raw text."""
    text, flags = read_source(source)
    entities = extract_entities(text, known_companies(root))
    kind = classify_kind(text) if text.strip() else "unknown"
    excerpt = "\n".join(text.strip().splitlines()[:20])[:2000]
    return {
        "kind": kind,
        "entities": entities,
        "needs_manual": bool(flags.get("needs_manual")),
        "suggested_section": SECTION_FOR_KIND.get(kind, "notes.yaml"),
        "raw_excerpt": excerpt,
    }


def unique_inbox_path(directory: Path, filename: str) -> Path:
    """Collision-safe target: suffix a timestamp when the name exists."""
    target = directory / filename
    if target.exists():
        stem, suffix = target.stem, target.suffix or ""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        target = directory / f"{stem}_{stamp}{suffix}"
    return target


def save_to_inbox(filename: str, data: bytes | str, root: Path | None = None) -> Path:
    """Persist an upload into <data_root>/profile_info/inbox/, collision-safe."""
    safe = Path(filename).name or f"upload_{datetime.now():%Y%m%dT%H%M%S}.txt"
    if Path(safe).suffix.lower() not in ALLOWED_SUFFIXES:
        safe += ".txt"
    target = unique_inbox_path(inbox_dir(root), safe)
    if isinstance(data, str):
        target.write_text(data, encoding="utf-8")
    else:
        target.write_bytes(data)
    return target


def meta_path_for(file_path: Path) -> Path:
    return file_path.parent / (file_path.name + ".meta.json")


def write_meta(file_path: Path, result: dict) -> Path:
    meta_path = meta_path_for(file_path)
    payload = {"file": file_path.name, **result}
    meta_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return meta_path


def process_upload(filename: str, data: bytes | str, root: Path | None = None) -> dict:
    """Full ingestion: save + extract + write sidecar meta. Returns summary."""
    target = save_to_inbox(filename, data, root)
    result = extract_upload(target, root)
    write_meta(target, result)
    return {"path": target.name, **result}


def list_inbox(root: Path | None = None) -> list[dict]:
    """Pending-review items with their extracted summaries."""
    items = []
    for meta_file in sorted(inbox_dir(root).glob("*.meta.json")):
        source = Path(str(meta_file)[: -len(".meta.json")])
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        items.append({
            "name": source.name,
            "meta": meta.get("meta", meta),
            "kind": meta.get("kind", "unknown"),
            "entities": meta.get("entities", {}),
            "suggested_section": meta.get("suggested_section", "notes.yaml"),
            "needs_manual": meta.get("needs_manual", False),
            "raw_excerpt": meta.get("raw_excerpt", ""),
        })
    return items


def load_yaml(path: Path) -> dict:
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required")
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        return {}
    loaded = yaml.safe_load(text)
    return loaded if isinstance(loaded, dict) else {}


def validate_yaml(text: str) -> dict:
    """Parse-and-return helper used by the edit UI; raises ValueError on bad YAML."""
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required")
    parsed = yaml.safe_load(text)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("Profile sections must be a YAML mapping.")
    return parsed


def accept_item(name: str, root: Path | None = None) -> Path:
    """Append an inbox item's content into its suggested profile_info YAML
    under an explicit 'unverified' provenance marker (CONVENTIONS.md rule),
    then remove the pending file + meta."""
    directory = inbox_dir(root)
    source = directory / Path(name).name
    meta_file = meta_path_for(source)
    meta = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    text = source.read_text(encoding="utf-8", errors="replace") \
        if source.exists() else str(meta.get("raw_excerpt", ""))
    section = meta.get("suggested_section", "notes.yaml")
    section_path = profile_info_dir(root) / section
    entry = {
        "content": text[:4000],
        "provenance": "unverified",
        "source_file": source.name,
        "ingested_at": datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "extracted_kind": meta.get("kind", "unknown"),
    }
    existing = load_yaml(section_path)
    entries = existing.setdefault("unverified_entries", [])
    if not isinstance(entries, list):
        entries = existing["unverified_entries"] = [entries]
    entries.append(entry)
    section_path.parent.mkdir(parents=True, exist_ok=True)
    assert yaml is not None  # load_yaml above already enforced this
    section_path.write_text(
        yaml.safe_dump(existing, sort_keys=False, allow_unicode=True),
        encoding="utf-8")
    discard_item(name, root, remove_meta_only=not source.exists())
    return section_path


def discard_item(name: str, root: Path | None = None,
                 remove_meta_only: bool = False) -> None:
    """Remove an inbox item's file and sidecar meta."""
    directory = inbox_dir(root)
    source = directory / Path(name).name
    meta_file = meta_path_for(source)
    if not remove_meta_only and source.exists():
        source.unlink()
    if meta_file.exists():
        meta_file.unlink()
