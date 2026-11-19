"""RQ3 robustness: is the AI co-authorship association explained by the
skill's functional domain or the repository language?

Domains are keyword flags over the skill's front-matter name + description
(non-exclusive). Usage:
  python3 -I src/domain_adjust.py <db> <results_dir>
"""
import json
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

DB, RES = sys.argv[1], sys.argv[2]
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
meta = pd.read_sql_query(
    "SELECT repo_full_name, path, name, description FROM artifacts WHERE dedup_primary = 1", con)
sk = pd.read_csv(os.path.join(RES, "skills_flags.csv")).merge(meta, on=["repo_full_name", "path"], how="left")

DOMAINS = {
    "devops_cloud": r"deploy|docker|kubernetes|k8s|terraform|aws|azure|gcp|cloud|ci/cd|pipeline|infra|server|ssh|nginx|helm",
    "api_integration": r"\bapi\b|webhook|sdk|oauth|integrat|slack|github|notion|jira|stripe|telegram|email",
    "security": r"secur|pentest|vulnerab|exploit|audit|threat|ctf|malware|red.?team",
    "data_ml": r"\bdata|sql|database|analytic|machine learning|\bml\b|model|pandas|etl",
    "writing_docs": r"writ|document|blog|copy|content|summar|translat|essay|markdown|slide",
    "frontend_ui": r"react|frontend|\bui\b|css|design|component|tailwind|vue|svelte",
}
text = (sk["name"].fillna("") + " " + sk["description"].fillna("")).str.lower()
for d, p in DOMAINS.items():
    sk[f"d_{d}"] = text.str.contains(p, regex=True)

h = sk[sk.has_history].copy()
h["ai"] = h.ai_coauthored.fillna(False).astype(bool).astype(int)
h["log_body"] = np.log1p(h.body_chars.fillna(0))
top_lang = h.language.value_counts().head(6).index
lang = pd.get_dummies(h.language.where(h.language.isin(top_lang), "Other").fillna("Other"),
                      prefix="lang", drop_first=True, dtype=int)

def fit(cols, extra=None):
    X = h[cols].astype(float)
    if extra is not None:
        X = pd.concat([X, extra], axis=1)
    X = sm.add_constant(X)
    m = sm.Logit(h.any_risky_instr.astype(int), X).fit(disp=0)
    ci = np.exp(m.conf_int().loc["ai"])
    return {"OR": round(float(np.exp(m.params["ai"])), 2),
            "ci95": [round(float(ci[0]), 2), round(float(ci[1]), 2)],
            "p": float(f"{m.pvalues['ai']:.3g}")}

dcols = [f"d_{d}" for d in DOMAINS]
out = {
    "n": int(len(h)),
    "domain_share_pct": {d: round(100 * sk[f"d_{d}"].mean(), 1) for d in DOMAINS},
    "domain_share_ai_vs_human_pct": {d: [round(100 * h.loc[h.ai == 1, f"d_{d}"].mean(), 1),
                                         round(100 * h.loc[h.ai == 0, f"d_{d}"].mean(), 1)] for d in DOMAINS},
    "M1_length": fit(["ai", "log_body"]),
    "M2_length_domain": fit(["ai", "log_body"] + dcols),
    "M3_length_domain_language": fit(["ai", "log_body"] + dcols, lang),
}
json.dump(out, open(os.path.join(RES, "domain_adjust.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
