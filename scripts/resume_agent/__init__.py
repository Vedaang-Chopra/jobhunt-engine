"""Resume customization agent (spec 004).

Staged pipeline: plan (LLM) -> verify-plan (script) -> draft (LLM)
-> QA gates (scripts) -> cover letter -> evaluation.
Authority files live in <data_root>/resume_custom/. This package holds only
orchestration code; all facts/rules come from the authority files.
"""
