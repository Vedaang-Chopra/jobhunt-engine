"""answers_lib — library wrapper over the canonical saved-answers store.

Canonical store path (repo-relative): profile_info/application_answers.yaml
The legacy bank at profile_info/preferences/application_answers.yaml is
frozen; do not write to it. Every value in the store carries a verified_by
field recording its provenance.

Sentinels:
    ASK_USER  — no verified answer; pause and ask the user.
    GATED     — label is policy-banned from auto-fill (salary, EEO
                demographics, legal attestations) even if a value exists.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from scripts import config_lib
except ImportError:
    import config_lib

import yaml

ASK_USER = "__ASK_USER__"
GATED = "__GATED__"

DEFAULT_STORE_PATH = (
    config_lib.data_root() / "profile_info" / "application_answers.yaml"
)

# Policy-banned categories, matched case-insensitively against labels.
_GATED_PATTERNS = [
    r"salary",
    r"compensation",
    r"\bpay\b",            # pay range / expected pay (but not "paying attention")
    r"expected\s+(pay|comp)",
    r"gender",
    r"hispanic",
    r"latino",
    r"\brace\b",
    r"ethnicit",
    r"veteran",
    r"disabilit",
    r"sexual\s+orientation",
    r"\beeo\b",
    r"equal\s+employment",
    r"attest",
    r"under\s+penalty",
]

_GATED_RE = re.compile("|".join(_GATED_PATTERNS), re.IGNORECASE)
_WS_RE = re.compile(r"[^a-z0-9]+")


def _normalize(label: str) -> str:
    """Fuzzy-normalize a form label: lowercase, strip punctuation/whitespace."""
    return _WS_RE.sub("", str(label).lower())


def load_answers(path=DEFAULT_STORE_PATH) -> dict:
    """Load the answers YAML store as a dict."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"answers store not found: {p}")
    with p.open(encoding="utf-8") as f:
        store = yaml.safe_load(f) or {}
    store["_path"] = str(p.resolve())
    return store


def get_answer(store: dict, key: str):
    """Return the raw value for key anywhere in the store; None if unknown."""
    for section, entries in store.items():
        if section.startswith("_") or not isinstance(entries, dict):
            continue
        entry = entries.get(key)
        if isinstance(entry, dict) and "value" in entry:
            return entry["value"]
        if entry is not None:
            return entry
        # also allow dotted lookups like demographics.ethnicity.race
        parts = key.split(".")
        if len(parts) > 1 and section == parts[0]:
            node = entries
            found = True
            for part in parts[1:]:
                node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    found = False
                    break
            if found:
                return node.get("value") if isinstance(node, dict) else node
    return None


def set_answer(store: dict, section_key: str, key: str, value,
               verified_by: str | None = None) -> None:
    """Mutate the in-memory store and persist it back to disk.

    Values are stored as {value: ..., verified_by: ...} so every entry keeps
    provenance. verified_by defaults to 'unverified' — callers should pass an
    explicit provenance string whenever possible.
    """
    entry = {"value": value,
             "verified_by": verified_by or "unverified"}
    store.setdefault(section_key, {})[key] = entry
    path = Path(store.get("_path", DEFAULT_STORE_PATH))
    serializable = {k: v for k, v in store.items() if not k.startswith("_")}
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(serializable, f, sort_keys=False, allow_unicode=True)


def is_gated(label: str) -> bool:
    """True if this label is policy-banned from auto-fill (salary, EEO
    demographics, legal attestations)."""
    return bool(_GATED_RE.search(str(label)))


def answers_for_labels(labels, store=None) -> dict:
    """Map form labels to answer values via the store's label_aliases.

    - fuzzy-normalizes each label before lookup
    - gated labels -> GATED sentinel (never auto-filled)
    - unmatched labels -> ASK_USER sentinel
    - values that are themselves ASK_USER stay ASK_USER
    """
    if store is None:
        store = load_answers()
    aliases = {
        _normalize(alias): target
        for alias, target in (store.get("label_aliases") or {}).items()
    }
    out = {}
    for label in labels:
        if is_gated(label):
            out[label] = GATED
            continue
        target = aliases.get(_normalize(label))
        if target is None:
            out[label] = ASK_USER
            continue
        value = get_answer(store, target)
        out[label] = ASK_USER if value is None else value
    return out
