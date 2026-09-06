#!/usr/bin/env python3
"""LLM-guided ingest placement for the Profile page.

Given an inbox item's raw content, ask the configured LLM chain (same
providers as ``tailor_from_jd.llm_chat``) WHERE the information belongs in
``profile_info/`` and WHAT structured YAML should be merged there. The
proposal is always reviewed by a human before ``apply_proposal`` writes
anything — canonical facts still require explicit provenance.

Public surface::

    propose_placement(name, text) -> dict   # never raises on LLM failure
    apply_proposal(proposal, root=None) -> Path
    merge_yaml(existing_text, snippet_text) -> str

Fallback: when no LLM responds, ``propose_placement`` degrades gracefully to
the deterministic heuristics from ``ingest_lib`` so the UI flow never breaks.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

try:
    from scripts import config_lib
except ImportError:  # pragma: no cover - direct-script import shape
    import config_lib  # type: ignore

try:
    from scripts import tailor_from_jd as tfj
except ImportError:  # pragma: no cover
    import tailor_from_jd as tfj  # type: ignore

try:
    from scripts import ingest_lib
except ImportError:  # pragma: no cover
    import ingest_lib  # type: ignore

import yaml

CANONICAL_SECTIONS = [
    "experience", "education", "skills", "projects",
    "accomplishments", "publications_patents", "research",
    "preferences", "application_answers",
]

SYSTEM_PROMPT = (
    "You are the knowledge curator for a job-application agent. You classify "
    "candidate-supplied documents into canonical profile sections and emit "
    "structured YAML. You NEVER invent facts — you only restructure what is "
    "literally present in the source text. Output ONLY minified JSON."
)

PROMPT_TEMPLATE = """Classify this document into the candidate's profile knowledge bank.

=== DOCUMENT NAME ===
{name}

=== DOCUMENT TEXT (truncated) ===
{text}

=== CANONICAL SECTIONS ===
{sections}

Rules:
- Pick the ONE best-matching section from the list above (or "notes" only if nothing fits).
- Extract the durable facts into YAML matching the section's natural shape
  (e.g. experience -> a list of role entries with company/title/dates/highlights;
   skills -> categories of skills; education -> degree entries). Preserve exact
   numbers, dates and claims verbatim. Drop boilerplate/formatting noise.
- Set confidence between 0.0 and 1.0.

Return ONLY minified JSON with keys:
  "section": "<one of: {sections} | notes>",
  "confidence": <float>,
  "rationale": "<one sentence>",
  "yaml": "<YAML string with the extracted facts>"
"""


def _llm_available() -> bool:
    try:
        return bool(tfj.llm_config())
    except Exception:  # noqa: BLE001
        return False


def propose_placement(name: str, text: str,
                      use_llm: bool = True) -> dict:
    """Ask the LLM where ``text`` belongs and what YAML to extract.

    Returns a proposal dict::

        {name, section, target_file, confidence, rationale, yaml_snippet,
         engine: "llm"|"heuristic", error: str|None}

    Never raises: on failure falls back to ``ingest_lib`` heuristics.
    """
    fallback_section = Path(
        ingest_lib.SECTION_FOR_KIND.get(
            ingest_lib.classify_kind(text or ""), "notes.yaml")).stem
    fallback = {
        "name": name,
        "section": fallback_section,
        "target_file": f"{fallback_section}.yaml",
        "confidence": 0.3,
        "rationale": "Heuristic keyword classification (no LLM).",
        "yaml_snippet": "",
        "engine": "heuristic",
        "error": None,
    }
    clean = (text or "").strip()
    if not clean:
        return {**fallback, "rationale": "Empty document.", "confidence": 0.0}
    if not use_llm or not _llm_available():
        return fallback
    prompt = PROMPT_TEMPLATE.format(
        name=name, text=clean[:12000], sections=", ".join(CANONICAL_SECTIONS))
    try:
        raw = tfj.llm_chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], temperature=0.1)
    except Exception as exc:  # noqa: BLE001 - degrade, don't break UI
        return {**fallback, "rationale": f"LLM unavailable: {exc}"}

    # Tolerate markdown-fenced JSON.
    body = raw.strip()
    if body.startswith("```"):
        body = body.strip("`")
        body = body[body.find("{"):]
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            return {**fallback, "rationale": "LLM returned non-JSON."}
        try:
            parsed = json.loads(body[start:end + 1])
        except json.JSONDecodeError:
            return {**fallback, "rationale": "LLM returned unparsable JSON."}

    section = str(parsed.get("section") or "").strip().lower()
    if section.endswith(".yaml"):
        section = section[: -len(".yaml")]
    if section not in CANONICAL_SECTIONS + ["notes"]:
        return {**fallback,
                "rationale": f"LLM proposed unknown section '{section}'."}
    snippet = str(parsed.get("yaml") or "").strip()
    try:
        validate_snippet(snippet)
    except ValueError as exc:
        return {**fallback,
                "rationale": f"LLM YAML invalid ({exc}); rejected."}
    try:
        confidence = float(parsed.get("confidence") or 0.5)
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "name": name,
        "section": section,
        "target_file": f"{section}.yaml",
        "confidence": max(0.0, min(1.0, confidence)),
        "rationale": str(parsed.get("rationale") or ""),
        "yaml_snippet": snippet,
        "engine": "llm",
        "error": None,
    }


def validate_snippet(snippet: str) -> dict:
    """Snippet must parse as a non-empty YAML mapping."""
    parsed = yaml.safe_load(snippet)
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("snippet must be a non-empty YAML mapping")
    return parsed


def merge_yaml(existing_text: str, snippet_text: str) -> tuple[str, list[str]]:
    """Deep-merge ``snippet_text`` into ``existing_text``; returns (new, added).

    Mapping values merge recursively, lists append, scalars overwrite.
    """
    base = yaml.safe_load(existing_text) if existing_text.strip() else {}
    if not isinstance(base, dict):
        base = {"value": base}
    incoming = validate_snippet(snippet_text)
    added: list[str] = []

    def _merge(dst: dict, src: dict, prefix: str = "") -> None:
        for key, value in src.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in dst:
                dst[key] = value
                added.append(path)
            elif isinstance(dst[key], dict) and isinstance(value, dict):
                _merge(dst[key], value, path)
            elif isinstance(dst[key], list) and isinstance(value, list):
                dst[key] = dst[key] + [v for v in value if v not in dst[key]]
                added.append(path)
            else:
                dst[key] = value
                added.append(path)

    _merge(base, incoming)
    return yaml.safe_dump(base, sort_keys=False, allow_unicode=True), added


def apply_proposal(proposal: dict, root: Path | None = None,
                   write=None) -> Path:
    """Merge a reviewed proposal into ``<data_root>/profile_info/<section>.yaml``
    with provenance metadata, then remove the inbox item. Returns target path."""
    directory = ingest_lib.profile_info_dir(root)
    target = directory / proposal["target_file"]
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    merged, _added = merge_yaml(existing, proposal["yaml_snippet"])
    doc = yaml.safe_load(merged)
    meta = doc.setdefault("_ai_ingest", [])
    if not isinstance(meta, list):
        meta = doc["_ai_ingest"] = [meta]
    meta.append({
        "source_file": proposal["name"],
        "engine": proposal.get("engine"),
        "confidence": proposal.get("confidence"),
        "provenance": "unverified",
        "applied_at": datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    final_text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    if write is None:
        target.write_text(final_text, encoding="utf-8")
    else:
        write(target, final_text)
    try:
        ingest_lib.discard_item(proposal["name"], root)
    except Exception:  # noqa: BLE001 - inbox cleanup is best-effort
        pass
    return target


def main(argv=None) -> int:  # CLI: propose for one inbox item
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item", required=True,
                        help="inbox filename to propose placement for")
    parser.add_argument("--apply", action="store_true",
                        help="apply the proposal without review")
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args(argv)

    root = config_lib.data_root()
    items = {i["name"]: i for i in ingest_lib.list_inbox(root)}
    item = items.get(args.item)
    if not item:
        print(f"FATAL: no inbox item named {args.item}")
        return 1
    source = ingest_lib.inbox_dir(root) / args.item
    text = (source.read_text(encoding="utf-8", errors="replace")
            if source.exists() else item.get("raw_excerpt", ""))
    proposal = propose_placement(args.item, text)
    print(json.dumps({k: v for k, v in proposal.items()}, indent=2,
                     default=str)[:4000])
    if args.apply and args.dry_run is False and proposal["yaml_snippet"]:
        target = apply_proposal(proposal, root)
        print(f"APPLIED -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
