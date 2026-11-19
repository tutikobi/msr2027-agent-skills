"""Build a blind annotation kit for two human annotators.

  precision_A.csv / precision_B.csv  the 184 validation hits, shuffled, WITHOUT
                                     the model's labels (same rows, same ids)
  recall_negatives.csv + recall_texts/  100 random skills that NO risky
                                     instruction detector flagged, full text
Usage: python3 -I src/make_annotation_kit.py <db> <results_dir> <kit_dir>
"""
import os
import sqlite3
import sys

import pandas as pd

DB, RES, KIT = sys.argv[1], sys.argv[2], sys.argv[3]
SEED = 2027
os.makedirs(os.path.join(KIT, "recall_texts"), exist_ok=True)
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

v = pd.read_csv(os.path.join(RES, "validation_labeled.csv"))
v = v.sample(frac=1, random_state=SEED).reset_index(drop=True)
v.insert(0, "id", [f"P{i:03d}" for i in range(len(v))])
blind = v[["id", "table", "category", "repo", "path", "snippet"]].copy()
blind["label_TP_FP"] = ""
blind["note"] = ""
for who in ("A", "B"):
    blind.to_csv(os.path.join(KIT, f"precision_{who}.csv"), index=False)
# private key mapping ids to the model's labels; open only AFTER annotating
v[["id", "label"]].rename(columns={"label": "model_label"}).to_csv(
    os.path.join(KIT, "_model_labels_DO_NOT_OPEN_BEFORE.csv"), index=False)

sk = pd.read_csv(os.path.join(RES, "skills_flags.csv"))
neg = sk[~sk.any_risky_instr].sample(100, random_state=SEED).reset_index(drop=True)
rows = []
for i, r in neg.iterrows():
    rid = f"R{i:03d}"
    txt = con.execute("SELECT content FROM artifacts WHERE repo_full_name=? AND path=?",
                      (r.repo_full_name, r.path)).fetchone()[0]
    with open(os.path.join(KIT, "recall_texts", f"{rid}.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    rows.append({"id": rid, "repo": r.repo_full_name, "path": r.path, "chars": len(txt),
                 "network": "", "remote_code_exec": "", "destructive": "", "privilege": "",
                 "secrets": "", "confirmation_bypass": "", "annotator": "", "note": ""})
pd.DataFrame(rows).to_csv(os.path.join(KIT, "recall_negatives.csv"), index=False)
print(len(blind), "precision rows;", len(rows), "recall skills")
