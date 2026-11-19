"""Score the human annotation kit.

Usage: python3 -I src/agreement.py <kit_dir>
Reads precision_A.csv, precision_B.csv (column label_TP_FP = TP or FP),
an optional precision_consensus.csv (same columns, disagreements resolved),
_model_labels_DO_NOT_OPEN_BEFORE.csv and, if filled, recall_negatives.csv
(1 = the skill DOES request that capability, i.e. a missed detection).
"""
import json
import os
import sys

import pandas as pd
from statsmodels.stats.proportion import proportion_confint

KIT = sys.argv[1]
rd = lambda f: pd.read_csv(os.path.join(KIT, f))
A, B = rd("precision_A.csv"), rd("precision_B.csv")
norm = lambda s: s.astype(str).str.strip().str.upper()
A["l"], B["l"] = norm(A.label_TP_FP), norm(B.label_TP_FP)
m = A[["id", "table", "category", "l"]].merge(B[["id", "l"]], on="id", suffixes=("_A", "_B"))
m = m[m.l_A.isin(["TP", "FP"]) & m.l_B.isin(["TP", "FP"])]
po = (m.l_A == m.l_B).mean()
pa, pb = (m.l_A == "TP").mean(), (m.l_B == "TP").mean()
pe = pa * pb + (1 - pa) * (1 - pb)
out = {"n_both": int(len(m)), "observed_agreement": round(po, 3),
       "cohens_kappa": round((po - pe) / (1 - pe), 3) if pe < 1 else None,
       "disagreements": m.loc[m.l_A != m.l_B, "id"].tolist()}

cons_path = os.path.join(KIT, "precision_consensus.csv")
if os.path.exists(cons_path):
    C = rd("precision_consensus.csv")
    C["l"] = norm(C.label_TP_FP)
    C = C[C.l.isin(["TP", "FP"])]
    p = C.groupby(["table", "category"]).l.agg(n="size", tp=lambda x: (x == "TP").sum())
    p["precision"] = (p.tp / p.n).round(2)
    out["precision_consensus"] = {f"{t}/{c}": [int(r.tp), int(r.n), float(r.precision)]
                                  for (t, c), r in p.iterrows()}
    M = rd("_model_labels_DO_NOT_OPEN_BEFORE.csv").merge(C[["id", "l"]], on="id")
    out["model_vs_consensus_agreement"] = round((norm(M.model_label) == M.l).mean(), 3)
    out["model_labels_changed"] = int((norm(M.model_label) != M.l).sum())

R = rd("recall_negatives.csv")
cats = ["network", "remote_code_exec", "destructive", "privilege", "secrets", "confirmation_bypass"]
filled = R[cats].notna().all(axis=1)
if filled.any():
    Rf = R[filled]
    miss = (Rf[cats].astype(int).sum(axis=1) > 0)
    lo, hi = proportion_confint(miss.sum(), len(Rf), method="wilson")
    out["recall_check"] = {"n_negatives_reviewed": int(len(Rf)),
                           "missed_any": int(miss.sum()),
                           "false_negative_rate": round(miss.mean(), 3),
                           "fnr_ci95_wilson": [round(lo, 3), round(hi, 3)],
                           "missed_by_category": {c: int(Rf[c].astype(int).sum()) for c in cats}}
json.dump(out, open(os.path.join(KIT, "agreement_results.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
