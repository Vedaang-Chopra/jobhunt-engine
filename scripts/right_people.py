#!/usr/bin/env python3
"""right_people.py — CLI entry point for the "right people" feature.

Two subcommands (the bare top-level form is kept as an alias for `plan`):

    right_people.py plan    --company X|--job-url URL [--json] [--limit N] [--live]
    right_people.py ingest  --company X|--job-url URL --rows rows.json
                            [--cap N] [--queue-drafts] [--json]

`plan` is the plan-only dry run (Task 6): nothing is written to disk.
`ingest` (Tasks 7-9) runs the full pipeline over agent-extracted LinkedIn
rows (raw JSON list of person dicts) — never-twice dedup, weighted scoring,
inspection cap, canonical CSV upserts, ranked Markdown report (stdout +
<company_dir>/connections_report.md), one search_runs.csv run row, and —
only with --queue-drafts — PENDING drafts for P0/P1 (nothing is ever sent).

Browser extraction is AGENT-DRIVEN (canonical people_sweep.py pattern); the
script owns decisions and the ledger. Sibling libs are imported lazily so
the CLI shell degrades with a clear message if they have not landed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MISSING_SIBLINGS_MSG = "sibling libs not landed yet: run tasks 1/2/3/5"

SUBCOMMANDS = ("plan", "ingest")


class TargetNotFound(Exception):
    """Raised when the company/job-url target cannot be resolved."""


def parse_args(argv=None) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    # backward compat: bare top-level args mean `plan`
    command = raw.pop(0) if raw and raw[0] in SUBCOMMANDS else "plan"
    args = _parse_ingest(raw) if command == "ingest" else _parse_plan(raw)
    args.command = command
    return args


def _parse_plan(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="right_people",
        description=(
            "Find the right people to connect with at a company or around a "
            "specific job posting (default: plan-only dry run)."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--company", help="Target company name (e.g. \"Scale AI\").")
    group.add_argument("--job-url", help="Target job posting URL from jobs.csv.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute browser passes against LinkedIn (default: plan-only).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Per-pass result limit (default: 15).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable plan JSON instead of the human table.",
    )
    parser.add_argument(
        "--queue-drafts",
        action="store_true",
        help="Stage P0/P1 candidates into connection_queue as pending drafts.",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=12,
        help="Per-profile inspection cap (default: 12).",
    )
    return parser.parse_args(argv)


def _parse_ingest(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="right_people ingest",
        description=(
            "Ingest agent-extracted LinkedIn person rows: dedup, score, "
            "upsert canonical CSVs, emit the ranked report, and (with "
            "--queue-drafts) stage PENDING drafts for P0/P1. Never sends."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--company", help="Target company name (e.g. \"Scale AI\").")
    group.add_argument("--job-url", help="Target job posting URL from jobs.csv.")
    parser.add_argument(
        "--rows",
        required=True,
        help="Path to a JSON file holding the list of raw person dicts "
             "extracted by the agent from LinkedIn.",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=12,
        help="Per-profile inspection cap; rows beyond it keep score/priority "
             "but are flagged inspect_pending (default: 12).",
    )
    parser.add_argument(
        "--queue-drafts",
        action="store_true",
        help="Stage P0/P1 results as PENDING connection-request drafts "
             "(human approval still required; nothing is sent).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable summary+report JSON instead of Markdown.",
    )
    return parser.parse_args(argv)


def _load_sibling_libs():
    """Import sibling libs lazily; fail with an actionable message."""
    try:
        import right_people_lib  # noqa: F401
        import search_plan_lib  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised by integration
        raise ImportError(MISSING_SIBLINGS_MSG) from exc
    return right_people_lib, search_plan_lib


def _resolve_target(args):
    """Resolve only the target (no plan). Raises TargetNotFound."""
    right_people_lib, _ = _load_sibling_libs()
    flag, value = (
        ("--company", args.company) if args.company else ("--job-url", args.job_url)
    )
    try:
        return right_people_lib.resolve_target(flag, value)
    except right_people_lib.TargetNotFound as exc:
        raise TargetNotFound(str(exc)) from exc


def _resolve_and_plan(args):
    """Resolve the target and build the search plan (real wiring).

    Returns (target, plan). Raises TargetNotFound when the target cannot be
    resolved. Kept as a separate function so tests can monkeypatch it.
    """
    right_people_lib, search_plan_lib = _load_sibling_libs()
    target = _resolve_target(args)

    hints = None
    if target.get("kind") == "job":
        try:
            from jd_hints_lib import extract_jd_hints

            jd_path = target.get("jd_path")
            if jd_path:
                from pathlib import Path

                jd_file = Path(jd_path)
                if jd_file.exists():
                    hints = extract_jd_hints(jd_file.read_text(encoding="utf-8"))
        except ImportError:
            hints = None  # JD hints are optional for planning (Task 2)

    plan = search_plan_lib.build_search_plan(target, hints=hints)
    return target, plan


def _filters_summary(filters) -> str:
    if not isinstance(filters, dict):
        return str(filters)
    return "; ".join(f"{k}={v}" for k, v in filters.items())


def _print_plan_table(target, plan) -> None:
    company = target.get("company") or "?"
    slug = target.get("company_slug") or "?"
    kind = target.get("kind") or "?"
    print(f"target: {company} (slug={slug}, kind={kind})")
    print(f"plan: {len(plan)} passes (filter-first, rule-05 order)")
    print()
    header = f"{'pass_id':>7}  {'family':<24} {'filters':<48} {'limit':>5}"
    print(header)
    print("-" * len(header))
    for p in plan:
        pass_id = p.get("pass_id", "?")
        family = str(p.get("family", "?"))
        summary = _filters_summary(p.get("filters"))
        if len(summary) > 46:
            summary = summary[:43] + "..."
        print(f"{str(pass_id):>7}  {family:<24} {summary:<48} {'':>5}")


def _company_dir(target):
    """Canonical per-company dir: job_research/companies/<slug>/."""
    import config_lib

    slug = target.get("company_slug") or "unknown"
    return Path(config_lib.data_root()) / "job_research" / "companies" / slug


def _run_ingest(args, target) -> int:
    """Full ingest pipeline (Tasks 7-9) over agent-extracted rows."""
    import config_lib
    import right_people_ingest

    rows_path = Path(args.rows)
    if not rows_path.exists():
        print(f"error: rows file not found: {rows_path}", file=sys.stderr)
        return 1
    try:
        rows = json.loads(rows_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: rows file is not valid JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(rows, list):
        print("error: rows file must contain a JSON list of person dicts",
              file=sys.stderr)
        return 1

    today = right_people_ingest._today(None)
    company_dir = _company_dir(target)
    out = right_people_ingest.run_ingest(
        target, rows, cap=args.cap, today=today,
        contacts_path=config_lib.path("contacts_csv"),
        sweep_path=config_lib.path("people_sweep_csv"),
        company_dir=company_dir,
    )

    report = right_people_ingest.render_report(target, out["results"], today=today)
    if args.json:
        print(json.dumps(
            {"target": target, "summary": out["summary"], "results": out["results"],
             "report": report},
            default=str, indent=2))
    else:
        print(report)

    report_path = company_dir / "connections_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    right_people_ingest.log_search_run(
        target, out["results"], summary=out["summary"],
        path=config_lib.path("search_runs_csv"), today=today)

    if args.queue_drafts:
        job = target.get("job") or {}
        staged = right_people_ingest.queue_drafts(
            out["results"],
            _requests_ledger_path(),
            today=today,
            job_ids=job.get("job_id") or "",
        )
        print(f"staged {len(staged)} P0/P1 connection request(s) as PENDING "
              f"drafts (human approval required; nothing sent).")

    summary = out["summary"]
    print(f"ingest: {summary['added']} added, {summary['updated']} updated, "
          f"{summary['skipped_dup']} skipped dups, {summary['inspected']} "
          f"inspected; report -> {report_path}", file=sys.stderr)
    return 0


def _requests_ledger_path():
    """Canonical connection_requests.csv ledger (connection_queue owns it)."""
    try:
        import connection_queue
        return connection_queue.REQ_PATH
    except ImportError:  # pragma: no cover
        import config_lib
        return (Path(config_lib.data_root()) / "tracking" / "messages"
                / "connection_requests.csv")


def main(argv=None) -> int:
    args = parse_args(argv)

    if getattr(args, "command", "plan") == "ingest":
        try:
            target = _resolve_target(args)
        except TargetNotFound as exc:
            print(f"error: target not found: {exc}", file=sys.stderr)
            return 1
        return _run_ingest(args, target)

    try:
        target, plan = _resolve_and_plan(args)
    except TargetNotFound as exc:
        print(f"error: target not found: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"target": target, "plan": plan}, default=str, indent=2))
        return 0

    _print_plan_table(target, plan)

    if args.live:
        # Live execution lands in Task 7; the plan is identical.
        print()
        print("note: --live execution not implemented yet (plan Task 7); "
              "showing plan only.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
