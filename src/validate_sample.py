"""Draw a reproducible sample of detector hits for manual precision checks.

Usage: python3 -I src/validate_sample.py <db> <results_dir> [per_category]
Writes <results_dir>/validation_sample.csv with a context snippet per hit and an
empty `label` column (TP = the text really requests/does the capability,
FP = mention only, e.g. documentation of what NOT to do, or a pattern accident).
"""
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detectors import INSTRUCTION, SCRIPT, first_match  # noqa: E402

DB, RES = sys.argv[1], sys.argv[2]
K = int(sys.argv[3]) if len(sys.argv) > 3 else 15
SEED = 2027
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
sk = pd.read_csv(os.path.join(RES, "skills_flags.csv"))
sc = pd.read_csv(os.path.join(RES, "scripts_flags.csv"))

rows = []
for c in INSTRUCTION:
    if c == "shell_exec":
        continue
    hit = sk[sk[f"i_{c}"]]
    for _, r in hit.sample(min(K, len(hit)), random_state=SEED).iterrows():
        txt = con.execute("SELECT content FROM artifacts WHERE repo_full_name=? AND path=?",
                          (r.repo_full_name, r.path)).fetchone()[0]
        rows.append({"table": "instruction", "category": c, "repo": r.repo_full_name,
                     "path": r.path, "snippet": first_match(txt, c, "instruction"), "label": ""})
for c in SCRIPT:
    hit = sc[sc[f"s_{c}"]]
    for _, r in hit.sample(min(K, len(hit)), random_state=SEED).iterrows():
        txt = con.execute("SELECT content FROM artifact_siblings WHERE repo_full_name=? AND artifact_path=? AND entry_name=?",
                          (r.repo_full_name, r.artifact_path, r.entry_name)).fetchone()[0]
        rows.append({"table": "script", "category": c, "repo": r.repo_full_name,
                     "path": f"{r.artifact_path}::{r.entry_name}",
                     "snippet": first_match(txt, c, "script"), "label": ""})
pd.DataFrame(rows).to_csv(os.path.join(RES, "validation_sample.csv"), index=False)
print(len(rows), "hits written")
