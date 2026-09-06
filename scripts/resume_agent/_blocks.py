"""Evidence-block title normalization shared across stages."""


def _norm_block(title: str) -> str:
    t = title.strip()
    for prefix in ("BLOCK:", "ENTRY:", "UPDATE TO", "NOTE:", "BLOCK UPDATE:"):
        if t.upper().startswith(prefix):
            t = t[len(prefix):].strip(" —-")
            break
    return t.lower()


def iter_blocks(evidence_md: str):
    """Yield (normalized_title, raw_chunk) for every ## block."""
    for chunk in evidence_md.split("## ")[1:]:
        lines = chunk.splitlines()
        if not lines:
            continue
        yield _norm_block(lines[0]), chunk
