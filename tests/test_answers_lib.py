"""TDD tests for scripts/answers_lib.py — saved-answers store (apply-plan Task 1)."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from answers_lib import (  # noqa: E402
    ASK_USER,
    GATED,
    answers_for_labels,
    get_answer,
    is_gated,
    load_answers,
    set_answer,
)

from scripts import config_lib

# Tests run against a SYNTHETIC answers store (never the real personal one —
# personal values must not leak into the public test suite). The store lives
# in tmp fixtures created per-test via `store` below; tests that need the
# repo-local canonical path shape use `synthetic_store_file`.

_SYNTHETIC_ANSWERS = """\
meta:
  created: '2026-08-23'
  canonical: false
  synthetic: true
identity:
  first_name:
    value: Test
    verified_by: synthetic fixture
  last_name:
    value: Candidate
    verified_by: synthetic fixture
  full_name:
    value: Test Candidate
    verified_by: synthetic fixture
  email:
    value: test.candidate@example.edu
    verified_by: synthetic fixture
  phone:
    value: +1 (555) 000-0000
    verified_by: synthetic fixture
  university:
    value: Example University
    verified_by: synthetic fixture
education:
  university:
    value: Example University
    verified_by: synthetic fixture
reusable_answers:
  willing_to_relocate:
    value: 'Yes'
    verified_by: synthetic fixture
  how_did_you_hear:
    value: LinkedIn
    verified_by: synthetic fixture
label_aliases:
  firstname: identity.first_name
  lastname: identity.last_name
  fullname: identity.full_name
  name: identity.full_name
  email: identity.email
  phonenumber: identity.phone
  phone: identity.phone
  location: identity.location
  university: education.university
  school: education.university
  degree: education.degree
  areyouwillingtorelocate: reusable_answers.willing_to_relocate
  willingtorelocate: reusable_answers.willing_to_relocate
  howdidyouhearaboutus: reusable_answers.how_did_you_hear
  howdidyouhearaboutthisrole: reusable_answers.how_did_you_hear
"""


@pytest.fixture
def store(tmp_path):
    f = tmp_path / "answers.yaml"
    f.write_text(_SYNTHETIC_ANSWERS)
    return load_answers(f)


# ---------- load_answers ----------

def test_load_answers_returns_dict(store):
    assert isinstance(store, dict)
    assert "identity" in store


def test_load_answers_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_answers(tmp_path / "nope.yaml")


# ---------- get_answer ----------

def test_get_answer_phone_formatted(store):
    assert get_answer(store, "phone") == "+1 (555) 000-0000"


def test_get_answer_unknown_key_returns_none(store):
    assert get_answer(store, "no_such_key") is None


# ---------- set_answer ----------

def test_set_answer_mutates_and_persists(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("identity:\n  first_name: Test\n")
    s = load_answers(p)
    set_answer(s, "identity", "first_name", "V", verified_by="test")
    assert s["identity"]["first_name"]["value"] == "V"
    assert load_answers(p)["identity"]["first_name"]["value"] == "V"


def test_set_answer_records_verified_by(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("identity:\n  first_name: Test\n")
    s = load_answers(p)
    set_answer(s, "identity", "first_name", "V", verified_by="user 2026-08-23")
    reloaded = load_answers(p)
    assert reloaded["identity"]["first_name"]["value"] == "V"
    assert "2026-08-23" in reloaded["identity"]["first_name"]["verified_by"]


# ---------- is_gated ----------

@pytest.mark.parametrize("label", [
    "What are your salary expectations?",
    "Desired compensation",
    "Gender",
    "Are you Hispanic or Latino?",
    "Race/Ethnicity",
    "Are you a protected veteran?",
    "Do you have a disability?",
    "I attest that all information is true",
])
def test_is_gated_true(label):
    assert is_gated(label) is True


@pytest.mark.parametrize("label", [
    "First Name",
    "Are you legally authorized to work in the US?",
    "Willing to relocate",
])
def test_is_gated_false(label):
    assert is_gated(label) is False


# ---------- answers_for_labels ----------

def test_maps_identity_labels(store):
    out = answers_for_labels(
        ["First Name", "Last Name", "Email", "Phone", "University"],
        store,
    )
    assert out["First Name"] == "Test"
    assert out["Email"] == "test.candidate@example.edu"
    assert out["Phone"] == "+1 (555) 000-0000"


def test_fuzzy_normalization_matches(store):
    out = answers_for_labels(["first_name *", "  FIRST   NAME  "], store)
    assert out["first_name *"] == "Test"
    assert out["  FIRST   NAME  "] == "Test"


def test_unmatched_label_returns_ask_user(store):
    out = answers_for_labels(["What is your favorite color?"], store)
    assert out["What is your favorite color?"] is ASK_USER


def test_work_auth_stays_ask_user(store):
    out = answers_for_labels(
        ["Are you legally authorized to work in the US?"], store)
    assert out["Are you legally authorized to work in the US?"] is ASK_USER


def test_gated_labels_return_gated_even_if_in_store(store):
    out = answers_for_labels(
        ["What are your salary expectations?", "Gender"], store)
    assert out["What are your salary expectations?"] is GATED
    assert out["Gender"] is GATED


def test_reusable_answers_resolved(store):
    out = answers_for_labels(
        ["Are you willing to relocate?", "How did you hear about us?"], store)
    assert out["Are you willing to relocate?"] == "Yes"
    assert out["How did you hear about us?"] == "LinkedIn"
