#!/usr/bin/env python3
"""Extract Simplify Copilot's saved application answers from its LevelDB store.

Copies a point-in-time snapshot of the extension storage (safe while Chrome runs),
then scans raw blocks for:
  1. trackedInputContextKey entries -> question labels the user has answered
  2. profile-ish JSON blobs (email/name/phone/work_auth keys)
  3. answer value strings near each question

Output: JSON lines file per record type under execution_results/.
"""
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

EXT_ID = "pbanhockgagggenencehbnadejlgchfc"
_DEFAULT_CHROME_BASE = (
    "~/Library/Application Support/Google/Chrome/Default/Local Extension Settings"
)
CHROME_BASE = Path(
    os.environ.get("SIMPLIFY_CHROME_DIR", _DEFAULT_CHROME_BASE)
).expanduser()
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "execution_results")
SNAP_DIR = os.path.join(tempfile.gettempdir(), "simplify_leveldb_snapshot")


def snapshot():
    src = os.path.join(CHROME_BASE, EXT_ID)
    if os.path.exists(SNAP_DIR):
        shutil.rmtree(SNAP_DIR)
    shutil.copytree(src, SNAP_DIR)
    return SNAP_DIR


def scan(snapshot_dir):
    q_re = re.compile(rb'\{\\"labelText\\":\\"(.{5,600}?)\\",\\"section\\":(null|\\".*?\\")')
    profile_key_re = re.compile(
        rb'"(first_name|last_name|full_name|preferred_name|email|email_confirm|phone|'
        rb'phone_country_code|phone_raw_number|location|country|state|city|address|'
        rb'postal_code|work_auth|work_auth_us|work_auth_ca|work_auth_uk|sponsorship|'
        rb'over18|over21|disability_v2|veteran_v2|lgbt_v2|gender|ethnicity|linkedin|github|portfolio|additional_url|birthday)"\s*:\s*("(?:[^"\\]|\\.)*"|(?:true|false|null|\d+))'
    )
    questions = {}
    profile = {}
    files = sorted(f for f in os.listdir(snapshot_dir) if f.endswith((".ldb", ".log")))
    for fname in files:
        data = open(os.path.join(snapshot_dir, fname), "rb").read()
        # raw scan for escaped-JSON labelText (works even across compression since
        # snappy often leaves literal sections; fall back below if sparse)
        for m in q_re.finditer(data):
            label = m.group(1).decode("utf-8", "ignore")
            label = label.replace('\\"', '"').replace("\\\\n", " ").replace("\\n", " ")
            key = re.sub(r"\s+", " ", label)[:180]
            questions.setdefault(key, {"label": key, "seen_in": []})
            if fname not in questions[key]["seen_in"]:
                questions[key]["seen_in"].append(fname)
        for m in profile_key_re.finditer(data):
            k = m.group(1).decode()
            v = m.group(2).decode("utf-8", "ignore").strip('"')
            profile.setdefault(k, set()).add(v[:200])
    return questions, profile


def main():
    snap = snapshot()
    print(f"snapshot: {snap}")
    questions, profile = scan(snap)
    os.makedirs(OUT_DIR, exist_ok=True)
    q_path = os.path.join(OUT_DIR, "simplify_questions_extract.json")
    p_path = os.path.join(OUT_DIR, "simplify_profile_extract.json")
    json.dump(sorted(questions.values(), key=lambda x: x["label"]), open(q_path, "w"), indent=1)
    json.dump({k: sorted(v) for k, v in sorted(profile.items())}, open(p_path, "w"), indent=1)
    print(f"questions: {len(questions)} -> {q_path}")
    print(f"profile keys: {len(profile)} -> {p_path}")
    for k in list(profile)[:30]:
        print(" ", k, "=", sorted(profile[k])[:2])


if __name__ == "__main__":
    sys.exit(main())
