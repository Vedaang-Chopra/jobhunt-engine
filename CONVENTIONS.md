# Project Conventions

These conventions add job-application-specific details to the global agent
governance rules.

## Python

- Target straightforward Python with `pathlib.Path` for filesystem work.
- Resolve paths from an explicit repository root or configuration, never from a
  hard-coded user directory.
- Keep public interfaces thin and typed; keep parsing, scoring, migration, and
  lifecycle logic in focused core functions.
- Scripts must expose a callable entry point and a guarded CLI entry point.
- Destructive lifecycle operations default to preview mode and require an
  explicit `--apply`-style flag.

## CSV and YAML

- Store CSV as UTF-8 with a header matching its documented schema.
- Quote fields correctly; full job descriptions may contain commas, quotes,
  HTML, and newlines.
- Use stable record identifiers and ISO 8601 dates (`YYYY-MM-DD`) or timestamps
  with a timezone.
- Use lowercase `snake_case` column names and controlled lowercase status
  values.
- Treat YAML in `profile_info/` as human-reviewable canonical facts. Each
  material claim must retain provenance or an explicit verification state.
- Do not silently coerce conflicting rows. Record conflicts in a migration or
  validation report.

## Documentation

- Canonical names are `README.md`, `AGENTS.md`, `RULES.md`, and `SCHEMA.md`.
- Consolidate related rules with headings instead of creating one file per
  decision.
- Label current behavior, planned behavior, historical artifacts, and generated
  output distinctly.
- Use repository-relative Markdown links inside repository documents.

## Generated and Archived Material

- Reproducible run output goes to `execution_results/<workflow>/<run_id>/`.
- Canonical workflow state goes to `tracking/`; it is not a generated output.
- Superseded source material goes to an organized archive only after useful
  content is preserved and the move is recorded in a manifest.
- LaTeX auxiliary files, caches, local environments, and OS metadata are not
  tracked.
