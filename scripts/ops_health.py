#!/usr/bin/env python3
"""Cron health monitor (master-plan Task 9).

Reads execution_results/ops/health.json (per-source last-status data written
by scripts/discovery_run.py after every run) plus
tracking/search_runs/search_runs.csv (recency of the last run per source).

Rules:
  * failure_streak >= PAUSE_STREAK (2) on any source -> mark that source
    `self-paused` in health.json (if not already) and append one alert line to
    execution_results/ops/alerts.log. Alert lines are de-duplicated per
    streak value via an `alerted_at_streak` field so repeated checks do not
    spam the log; the daily_ops digest surfaces current alerts regardless.
  * Sources absent from search_runs.csv for more than STALE_DAYS days are
    reported as `stale` (informational; they do not pause anything).

CLI:
    python scripts/ops_health.py --check    # exit 1 if any alert/paused source
    python scripts/ops_health.py --report   # human-readable table

No cron jobs are registered here; the parent orchestrator owns scheduling.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
import config_lib

REPO = Path(__file__).resolve().parents[1]
OPS_DIR = config_lib.path("ops_dir")
HEALTH_JSON = OPS_DIR / "health.json"
ALERTS_LOG = OPS_DIR / "alerts.log"
SEARCH_RUNS_CSV = config_lib.path("search_runs_csv")

PAUSE_STREAK = 2
STALE_DAYS = 3


def load_health(path: Path = HEALTH_JSON) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def save_health(health: dict, path: Path = HEALTH_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health, indent=2, sort_keys=True))


def _alert_line(source: str, message: str, log: Path = ALERTS_LOG) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log.open("a") as fh:
        fh.write(f"{ts} ALERT {source}: {message}\n")


def search_runs_recency(path: Path = SEARCH_RUNS_CSV) -> dict[str, int]:
    """Map each source name to days since its last search_runs.csv row."""
    recency: dict[str, int] = {}
    if not path.exists():
        return recency
    today = date.today()
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("date") or "").strip()[:10]
            try:
                d = date.fromisoformat(raw)
            except ValueError:
                continue
            age = (today - d).days
            for src in [s.strip() for s in (row.get("sources") or "").split(",") if s.strip()]:
                if src not in recency or age < recency[src]:
                    recency[src] = age
    return recency


def evaluate(health_path: Path = HEALTH_JSON,
             runs_path: Path = SEARCH_RUNS_CSV,
             log_path: Path = ALERTS_LOG,
             persist: bool = True) -> dict:
    """Check all sources. Returns {alerts, rows, stale}.

    alerts: list of alert strings raised THIS evaluation (also appended to
    alerts.log when persist=True). A source already paused with its alert
    previously emitted is included in `rows` but not re-alerted.
    """
    health = load_health(health_path)
    recency = search_runs_recency(runs_path)
    alerts: list[str] = []
    rows: list[dict] = []
    dirty = False

    for source, entry in sorted(health.items()):
        entry = entry if isinstance(entry, dict) else {}
        try:
            streak = int(entry.get("failure_streak") or 0)
        except (TypeError, ValueError):
            streak = 0
        status = entry.get("status") or ("self-paused" if streak >= PAUSE_STREAK
                                         else "active")
        note = ""
        if streak >= PAUSE_STREAK and entry.get("status") != "self-paused":
            status = "self-paused"
            entry["status"] = status
            dirty = True
        if streak >= PAUSE_STREAK:
            msg = (f"failed {streak}x consecutively — self-paused "
                   f"(reset by editing health.json)")
            alerted_at = entry.get("alerted_at_streak")
            if alerted_at != streak:
                alerts.append(f"{source}: {msg}")
                _alert_line(source, msg, log_path)
                entry["alerted_at_streak"] = streak
                dirty = True
            note = "ALERT"
        elif entry.get("last_result") == "fail":
            note = "last run failed"

        stale_days = recency.get(source)
        stale_flag = ""
        if stale_days is not None and stale_days > STALE_DAYS \
                and status != "self-paused":
            stale_flag = f"stale ({stale_days}d since last search_runs row)"
        rows.append({
            "source": source,
            "status": status,
            "failure_streak": streak,
            "last_result": entry.get("last_result") or "?",
            "last_run": (entry.get("last_run") or "")[:19],
            "runs_recency_days": "" if stale_days is None else str(stale_days),
            "note": "; ".join(x for x in (note, stale_flag) if x),
        })

    # Sources seen in search_runs but never in health.json (informational).
    for src, days in sorted(recency.items()):
        if src not in health:
            note = "no health.json entry"
            if days > STALE_DAYS:
                note += f"; stale ({days}d since last search_runs row)"
            rows.append({
                "source": src, "status": "untracked", "failure_streak": 0,
                "last_result": "-", "last_run": "-",
                "runs_recency_days": str(days),
                "note": note,
            })

    if dirty and persist:
        save_health(health, health_path)
    return {"alerts": alerts, "rows": rows}


def render_report(result: dict) -> str:
    cols = ["source", "status", "failure_streak", "last_result",
            "last_run", "runs_recency_days", "note"]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in result["rows"]))
              for c in cols} if result["rows"] else {c: len(c) for c in cols}
    out = [" | ".join(c.ljust(widths[c]) for c in cols),
           "-+-".join("-" * widths[c] for c in cols)]
    for r in result["rows"]:
        out.append(" | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))
    if result["alerts"]:
        out.append("")
        out += [f"ALERT: {a}" for a in result["alerts"]]
    return "\n".join(out)


def main(argv=None, *, health_path: Path = HEALTH_JSON,
         runs_path: Path = SEARCH_RUNS_CSV,
         log_path: Path = ALERTS_LOG) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="exit non-zero if any source is paused/alerting")
    mode.add_argument("--report", action="store_true",
                      help="print human-readable health table")
    args = ap.parse_args(argv)

    result = evaluate(health_path, runs_path, log_path)
    if args.report:
        print(render_report(result))
        return 0
    # --check
    print(render_report(result))
    bad = [r["source"] for r in result["rows"]
           if r["status"] == "self-paused"]
    if result["alerts"] or bad:
        print(f"\nCHECK FAILED: alerts={len(result['alerts'])} "
              f"paused_sources={bad}")
        return 1
    print("\nCHECK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
