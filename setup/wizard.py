"""CLI onboarding wizard for the job-hunt workspace (Task 2.3 skeleton).

Each step function takes user answers and returns a plan dict describing the
filesystem writes it *would* perform. The CLI defaults to dry-run: it prints
the plan without touching disk. Only ``--apply`` performs the writes.

Logging is used for all non-interactive output; ``print`` is allowed only for
interactive wizard prompts.
"""

import argparse
import getpass
import logging
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running as a script as well as a module.
try:
    from scripts.config_lib import data_root
except ImportError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.config_lib import data_root

logger = logging.getLogger(__name__)

CANONICAL_DIRS = [
    "profile_info",
    "profile_info/inbox",
    "tracking",
    "tracking/jobs",
    "tracking/applications",
    "tracking/contacts",
    "tracking/companies",
    "linkedin",
    "messaging",
]


def choose_data_root(answer: Optional[str] = None) -> Dict[str, Any]:
    """Resolve and validate the data root directory.

    Returns a plan dict with the resolved path and JOBHUNT_HOME guidance.
    Raises SystemExit/ValueError via validation when the path is not usable.
    """
    if answer:
        root = Path(answer).expanduser().resolve()
        current = data_root()
        env_hint = (
            "JOBHUNT_HOME already set" if os.environ.get("JOBHUNT_HOME")
            else f'set export JOBHUNT_HOME="{root}" to pin this data root'
        )
    else:
        root = data_root()
        env_hint = (
            "JOBHUNT_HOME already set"
            if os.environ.get("JOBHUNT_HOME")
            else f'set export JOBHUNT_HOME="{root}" to pin this data root'
        )

    # Validate writability by probing a temp file when the dir exists;
    # otherwise verify the nearest existing ancestor is writable so that
    # apply mode can create the tree.
    probe_dir = root
    while not probe_dir.exists():
        parent = probe_dir.parent
        if parent == probe_dir:
            break
        probe_dir = parent

    writable = False
    try:
        test_file = probe_dir / ".wizard_write_probe"
        test_file.write_text("probe", encoding="utf-8")
        test_file.unlink()
        writable = True
    except OSError as exc:
        logger.warning("Data root %s is not writable: %s", root, exc)

    plan = {
        "step": "choose_data_root",
        "data_root": str(root),
        "writable": writable,
        "jobhunt_home_guidance": env_hint,
        "writes": [],
    }
    logger.info("Data root selected: %s (writable=%s)", root, writable)
    return plan


def seed_structure(data_root_path: Path) -> Dict[str, Any]:
    """Plan creation of canonical directories plus placeholder READMEs.

    Never overwrites existing files. Returns a plan of writes; execution is
    shared with :func:`apply_plan`.
    """
    root = Path(data_root_path)
    dirs = [root / rel for rel in CANONICAL_DIRS]
    files = [(d / "README.md") for d in dirs]

    mkdirs: List[str] = []
    writes: List[Dict[str, Any]] = []
    skips: List[str] = []

    for d in dirs:
        if not d.is_dir():
            mkdirs.append(str(d))

    for f in files:
        if f.exists():
            skips.append(str(f))
        else:
            writes.append({
                "path": str(f),
                "content": f"# {f.parent.relative_to(root).as_posix()}\n\nPlaceholder created by setup wizard.\n",
                "mode": 0o644,
            })

    return {
        "step": "seed_structure",
        "data_root": str(root),
        "mkdirs": sorted(set(mkdirs)),
        "write_files": writes,
        "skip_existing": skips,
        "writes": [str(w["path"]) for w in writes],
    }


def ingest_resume(path: Optional[str] = None) -> Dict[str, Any]:
    """Stub: copy a resume into ``<data>/profile_info/inbox/``.

    Returns a plan with a single copy operation; never overwrites an existing
    file in the inbox.
    """
    plan: Dict[str, Any] = {"step": "ingest_resume", "copies": [], "writes": []}
    if not path:
        logger.info("No resume provided; skipping ingest step.")
        return plan

    src = Path(path).expanduser()
    dest_dir = data_root() / "profile_info" / "inbox"
    dest = dest_dir / src.name
    if dest.exists():
        logger.info("Resume already present at %s; will not overwrite.", dest)
        plan["skip_existing"] = [str(dest)]
    else:
        plan["copies"].append({"src": str(src), "dest": str(dest)})
        plan["writes"] = [str(dest)]
    return plan


def configure_llm_keys() -> Dict[str, Any]:
    """Stub: prompt for LLM API keys via getpass and write config.yaml.

    Placeholders only in this skeleton. The target file gets chmod 600 and
    values are never echoed or logged.
    """
    plan: Dict[str, Any] = {
        "step": "configure_llm_keys",
        "config_path": str(data_root() / "config.yaml"),
        "chmod": 0o600,
        "keys": ["openai_api_key", "anthropic_api_key"],
        "values": {},  # never stored/logged
        "writes": [],
    }
    return plan


FRESHNESS_CHECK = Path(__file__).resolve().parent.parent / "scripts" / "freshness_check.py"
SMOKE_TEST_TIMEOUT_S = 120


def smoke_test() -> Dict[str, Any]:
    """Read-only health check of the configured workspace.

    Verifies (1) the data tree exists with canonical directories, (2) the
    data-root config.yaml parses as YAML (missing file is tolerated; malformed
    is not), and (3) ``scripts/freshness_check.py --dry-run`` completes as a
    subprocess without error. Never writes anything.
    """
    import yaml

    result: Dict[str, Any] = {"step": "smoke_test", "checks": [], "ok": True}
    root = data_root()

    # 1. Data tree exists.
    missing = [rel for rel in CANONICAL_DIRS if not (root / rel).is_dir()]
    result["checks"].append({
        "name": "data_tree",
        "ok": not missing,
        "detail": "all canonical dirs present" if not missing
        else f"missing: {', '.join(missing)}",
    })

    # 2. config.yaml parseable (missing file tolerated, malformed is a failure).
    cfg_path = root / "config.yaml"
    if not cfg_path.exists():
        result["checks"].append({"name": "config_parse", "ok": True,
                                 "detail": "config.yaml absent (defaults in use)"})
    else:
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                yaml.safe_load(f)
            result["checks"].append({"name": "config_parse", "ok": True,
                                     "detail": str(cfg_path)})
        except Exception as exc:
            result["checks"].append({"name": "config_parse", "ok": False,
                                     "detail": f"unparseable: {exc}"})

    # 3. Freshness check dry-run as a subprocess.
    if FRESHNESS_CHECK.is_file():
        try:
            proc = subprocess.run(
                [sys.executable, str(FRESHNESS_CHECK), "--dry-run"],
                capture_output=True, text=True, timeout=SMOKE_TEST_TIMEOUT_S,
            )
            ok = proc.returncode == 0
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-5:])
            result["checks"].append({
                "name": "freshness_dry_run",
                "ok": ok,
                "detail": f"exit={proc.returncode}",
                "output_tail": tail,
            })
        except subprocess.TimeoutExpired:
            result["checks"].append({
                "name": "freshness_dry_run", "ok": False,
                "detail": f"timed out after {SMOKE_TEST_TIMEOUT_S}s",
            })
    else:
        result["checks"].append({
            "name": "freshness_dry_run", "ok": False,
            "detail": f"script not found: {FRESHNESS_CHECK}",
        })

    result["ok"] = all(c["ok"] for c in result["checks"])
    for c in result["checks"]:
        (logger.info if c["ok"] else logger.error)(
            "smoke_test %s: %s (%s)", "PASS" if c["ok"] else "FAIL",
            c["name"], c["detail"])
    logger.info("smoke_test overall: %s", "PASS" if result["ok"] else "FAIL")
    return result


def apply_plan(plan: Dict[str, Any]) -> None:
    """Execute a plan produced by a step function."""
    step = plan.get("step")

    if step == "seed_structure":
        root = Path(plan["data_root"])
        for rel in CANONICAL_DIRS:
            (root / rel).mkdir(parents=True, exist_ok=True)
        for entry in plan.get("write_files", []):
            p = Path(entry["path"])
            if p.exists():  # safety net: never overwrite
                continue
            p.write_text(entry["content"], encoding="utf-8")
            os.chmod(p, entry["mode"])

    elif step == "ingest_resume":
        for entry in plan.get("copies", []):
            src, dest = Path(entry["src"]), Path(entry["dest"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                continue
            shutil.copy2(src, dest)

    elif step == "configure_llm_keys":
        cfg = Path(plan["config_path"])
        cfg.parent.mkdir(parents=True, exist_ok=True)
        if not cfg.exists():
            cfg.write_text("# LLM keys (placeholders)\n", encoding="utf-8")
        os.chmod(cfg, stat.S_IRUSR | stat.S_IWUSR)

    else:
        logger.info("Nothing to apply for step %r", step)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Job-hunt onboarding wizard.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform writes (default is dry-run preview).",
    )
    parser.add_argument("--data-root", help="Override the data root path.")
    parser.add_argument("--resume", help="Path to resume file to ingest.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    apply_mode = bool(args.apply)
    print(f"Wizard mode: {'APPLY' if apply_mode else 'DRY-RUN (no writes)'}")  # interactive prompt output

    plans: List[Dict[str, Any]] = []

    answer = args.data_root
    if not answer:
        answer = input(f"Data root [{data_root()}]: ").strip() or None
    root_plan = choose_data_root(answer)
    plans.append(root_plan)
    if not root_plan["writable"]:
        logger.error("Chosen data root is not writable; aborting.")
        return 1

    seed_plan = seed_structure(Path(root_plan["data_root"]))
    plans.append(seed_plan)
    plans.append(ingest_resume(args.resume))
    plans.append(configure_llm_keys())
    smoke = smoke_test()
    logger.info("Smoke test: %s", "PASS" if smoke["ok"] else "FAIL")

    for plan in plans:
        writes = plan.get("writes") or plan.get("mkdirs") or []
        logger.info("PLAN %s: %d change(s)%s", plan.get("step"), len(writes),
                    (": " + ", ".join(writes)) if writes else "")
        if apply_mode:
            apply_plan(plan)

    logger.info("Done (%s).", "applied" if apply_mode else "dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
