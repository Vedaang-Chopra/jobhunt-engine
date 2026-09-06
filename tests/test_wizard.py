"""Tests for setup/wizard.py (Task 2.3)."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from setup import wizard


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_HOME", str(tmp_path / "data"))
    return tmp_path / "data"


def test_dry_run_writes_nothing(tmp_root):
    plan = wizard.seed_structure(tmp_root)
    assert plan["step"] == "seed_structure"
    assert plan["write_files"], "plan should describe writes"
    # Planning alone must not touch disk.
    assert not tmp_root.exists()


def test_apply_creates_expected_tree(tmp_root):
    plan = wizard.seed_structure(tmp_root)
    wizard.apply_plan(plan)

    for rel in wizard.CANONICAL_DIRS:
        assert (tmp_root / rel).is_dir()
        readme = tmp_root / rel / "README.md"
        assert readme.is_file()


def test_apply_idempotent(tmp_root):
    plan1 = wizard.seed_structure(tmp_root)
    wizard.apply_plan(plan1)

    before = {
        p: p.read_text(encoding="utf-8") for p in tmp_root.rglob("README.md")
    }
    plan2 = wizard.seed_structure(tmp_root)
    assert plan2["write_files"] == [], "second run should plan no writes"
    assert plan2["skip_existing"], "second run should skip existing files"

    wizard.apply_plan(plan2)
    after = {
        p: p.read_text(encoding="utf-8") for p in tmp_root.rglob("README.md")
    }
    assert before == after


def test_no_overwrite_of_existing_file(tmp_root):
    (tmp_root / "messaging").mkdir(parents=True)
    readme = tmp_root / "messaging" / "README.md"
    readme.write_text("custom content", encoding="utf-8")

    plan = wizard.seed_structure(tmp_root)
    wizard.apply_plan(plan)

    assert readme.read_text(encoding="utf-8") == "custom content"
    assert str(readme) in plan["skip_existing"]


def test_choose_data_root_validates_writable(tmp_root):
    plan = wizard.choose_data_root(str(tmp_root))
    assert plan["step"] == "choose_data_root"
    assert plan["writable"] is True
    assert "JOBHUNT_HOME" in plan["jobhunt_home_guidance"]


def test_choose_data_root_unwritable(tmp_path):
    unwritable = tmp_path / "nope" / "deeper"
    unwritable.mkdir(parents=True)
    os.chmod(unwritable, 0o500)
    try:
        plan = wizard.choose_data_root(str(unwritable / "root"))
        assert plan["writable"] is False
    finally:
        os.chmod(unwritable, 0o700)


def test_ingest_resume_plan(tmp_root, tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_text("resume bytes", encoding="utf-8")
    plan = wizard.ingest_resume(str(resume))
    dest = Path(plan["copies"][0]["dest"])
    assert dest.parent == tmp_root / "profile_info" / "inbox"

    wizard.apply_plan(plan)
    assert dest.is_file()

    plan2 = wizard.ingest_resume(str(resume))
    assert plan2.get("skip_existing") == [str(dest)]
    assert plan2["copies"] == []


def test_ingest_resume_no_path(tmp_root):
    plan = wizard.ingest_resume(None)
    assert plan["copies"] == []


def test_configure_llm_keys_stub(tmp_root):
    plan = wizard.configure_llm_keys()
    assert plan["chmod"] == 0o600
    assert plan["values"] == {}
    assert plan["config_path"].endswith("config.yaml")


def test_smoke_test_pass_on_seeded_tree(tmp_root):
    plan = wizard.seed_structure(tmp_root)
    wizard.apply_plan(plan)
    result = wizard.smoke_test()
    assert result["step"] == "smoke_test"
    assert result["ok"] is True
    names = {c["name"] for c in result["checks"]}
    assert {"data_tree", "config_parse", "freshness_dry_run"} <= names


def test_smoke_test_fails_on_missing_tree(tmp_root):
    result = wizard.smoke_test()
    assert result["ok"] is False
    tree_check = next(c for c in result["checks"] if c["name"] == "data_tree")
    assert tree_check["ok"] is False


def test_smoke_test_malformed_config(tmp_root):
    plan = wizard.seed_structure(tmp_root)
    wizard.apply_plan(plan)
    (tmp_root / "config.yaml").write_text("data_root: [unclosed\n  bad:: yaml", encoding="utf-8")
    result = wizard.smoke_test()
    cfg_check = next(c for c in result["checks"] if c["name"] == "config_parse")
    assert cfg_check["ok"] is False
    assert result["ok"] is False


def test_main_dry_run_default(tmp_root, capsys):
    rc = wizard.main(["--data-root", str(tmp_root)])
    assert rc == 0
    assert not tmp_root.exists(), "default mode must not write"
    out = capsys.readouterr().out
    assert "DRY-RUN" in out


def test_main_apply(tmp_root):
    rc = wizard.main(["--data-root", str(tmp_root), "--apply"])
    assert rc == 0
    for rel in wizard.CANONICAL_DIRS:
        assert (tmp_root / rel).is_dir()
