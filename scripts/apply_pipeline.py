#!/usr/bin/env python3
"""Apply pipeline: job id -> fit check -> tailored resume -> fill plan -> approval gate.

Stages:
  1. LOAD      read canonical job row from tracking/jobs (or --jd file)
  2. FIT       run scripts/score_jobs_v2.py scoring config against the JD
  3. RESUME    select role family + base variant; generate application dir with
               resume.tex (delegates to resume_custom rules; compile is manual/
               agent-driven per RESUME_GENERATION_RULES.md)
  4. FILLPLAN  fetch the live application form, extract field labels, classify
               each via match_application_fields.py
  5. GATE      print fill plan: AUTO_FILL / USE_SAVED_ANSWER / ASK_USER and stop.
               Nothing is submitted without explicit user approval.

Usage:
  python3 scripts/apply_pipeline.py <job_id> [--jd path/to/jd.txt] [--stage GATE]
  python3 scripts/apply_pipeline.py <job_id> --url https://boards.greenhouse.io/acme/jobs/12345

This script never submits. Submission is a separate, human-approved action.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import config_lib  # noqa: E402
from match_application_fields import classify, load_answers, resolve  # noqa: E402

APPLY_RUNS_DIR = config_lib.path("apply_runs_dir")


def find_job(job_id: str):
    """Locate job record by stable identifier in tracking/jobs."""
    jobs_dir = os.path.join(ROOT, "tracking", "jobs")
    for dirpath, _dirs, files in os.walk(jobs_dir):
        for f in files:
            if f.endswith((".md", ".json")) and job_id.lower() in f.lower():
                return os.path.join(dirpath, f)
    # fall back: search inside files
    hits = subprocess.run(
        ["grep", "-ril", job_id, jobs_dir], capture_output=True, text=True
    ).stdout.split()
    return hits[0] if hits else None


def stage_fillplan(job_id: str, url: str | None, auto_extract: bool = False):
    """Produce the fill plan. Form fields come from either a saved snapshot
    (execution_results/apply_runs/<job_id>_fields.json) or must be captured
    live by the browser tooling (agent-driven; this prints instructions)."""
    snap = APPLY_RUNS_DIR / f"{job_id}_fields.json"
    answers = load_answers()
    if not os.path.exists(snap) and auto_extract and url:
        print(f"No field snapshot at {snap}; --auto-extract given, running "
              "form_extractor (agent-driven capture).", file=sys.stderr)
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "form_extractor.py"),
             url, "--out", snap],
            env={**os.environ, "APPLY_JOB_ID": job_id})
        if not os.path.exists(snap):
            print("form_extractor produced no snapshot; stopping.", file=sys.stderr)
            return None
    if os.path.exists(snap):
        fields_doc = json.load(open(snap))
        if fields_doc.get("needs_manual"):
            print(f"NEEDS MANUAL ({fields_doc.get('reason')}): {url or '(no url)'}",
                  file=sys.stderr)
            return None
        # snapshots written by form_extractor wrap fields under "fields"
        fields = fields_doc.get("fields", fields_doc)
    else:
        print(f"No field snapshot at {snap}. Re-run with --auto-extract --url <app-url>.",
              file=sys.stderr)
        print("Agent step: open the application URL with the browser tooling, "
              "extract all visible form labels+types, save to:", file=sys.stderr)
        print(f"  {snap}", file=sys.stderr)
        print('Format: [{"label": "...", "type": "text|select|radio|checkbox|file|textarea"}, ...]',
              file=sys.stderr)
        if url:
            print(f"Application URL: {url}", file=sys.stderr)
        return None

    plan = []
    for f in fields:
        c = classify(f.get("label", ""), answers)
        val = resolve(c["key"], answers) if c["key"] else None
        c["field_type"] = f.get("type", "text")
        c["required"] = f.get("required", False)
        if isinstance(val, str) and val == "ASK_USER":
            c["action"], c["value"] = "ASK_USER", None
        elif isinstance(val, dict) and isinstance(val.get("default"), str):
            c["value"] = val["default"]
        else:
            c["value"] = val if isinstance(val, str) else None
        plan.append(c)

    out = str(APPLY_RUNS_DIR / f"{job_id}_fillplan.json")
    json.dump(plan, open(out, "w"), indent=1)

    auto = [r for r in plan if r["action"] == "AUTO_FILL"]
    ask = [r for r in plan if r["action"] == "ASK_USER"]
    print(f"\n=== FILL PLAN {job_id} ===")
    for r in plan:
        mark = {"AUTO_FILL": "[fill]", "USE_SAVED_ANSWER": "[saved]",
                "ASK_USER": "[ ASK ]"}[r["action"]]
        req = "*" if r.get("required") else " "
        print(f" {mark} {req} ({r['field_type']:9}) {r['label'][:70]}")
        if r["value"]:
            print(f"           -> {r['value'][:80]}")
    print(f"\nauto-fillable: {len(auto)}  need-you: {len(ask)}")
    print(f"plan saved: {out}")
    print("\nSTOPPED at approval gate. Answer the [ASK] items, then an agent may "
          "fill AUTO_FILL fields. Submission requires your explicit go-ahead.")
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job_id")
    ap.add_argument("--jd", help="path to raw job description text")
    ap.add_argument("--url", help="application URL for the fill stage")
    ap.add_argument("--auto-extract", action="store_true",
                    help="when <job_id>_fields.json is missing, run "
                         "scripts/form_extractor.py to capture the form fields")
    ap.add_argument("--execute", action="store_true",
                    help="EXECUTE stage: write through ready_to_apply + "
                         "date_resume_ready to tracking/applications/"
                         "applications.csv (append row if job_id absent)")
    args = ap.parse_args()

    APPLY_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    job_path = find_job(args.job_id) if not args.jd else None
    print(f"job record: {job_path or '(using --jd file)'}")

    # Stage hooks: scoring and resume generation are documented workflows run by
    # the agent (score_jobs_v2.py + resume_custom rules); this driver wires the
    # mechanical parts and enforces the gate.
    plan = stage_fillplan(args.job_id, args.url, args.auto_extract)

    if args.execute:
        stage_execute(args.job_id)


def stage_execute(job_id: str):
    """EXECUTE stage: after an agent has driven form_filler against the live
    form (browser tooling), mark the application ready_to_apply with today's
    date_resume_ready. Appends the row if absent; never deletes rows."""
    import datetime

    from form_filler import APPLICATIONS_CSV, update_applications_csv

    n = update_applications_csv(
        APPLICATIONS_CSV, job_id,
        status="ready_to_apply",
        date_resume_ready=datetime.date.today().isoformat(),
        date_last_status_change=datetime.date.today().isoformat(),
        current_stage="ready_to_apply")
    print(f"[EXECUTE] applications.csv: {n} row(s) updated for {job_id} "
          "-> ready_to_apply")
    print("[EXECUTE] Browser filling is agent-driven via Playwright MCP "
          "(scripts/form_filler.py provides decisions/summaries). "
          "STOP before any Submit button.")


if __name__ == "__main__":
    main()
