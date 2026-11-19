"""Secondary statistics: Holm correction for RQ3 tests and length-adjusted
association between AI co-authorship and risky instructions.

Usage: python3 -I src/extra_stats.py <results_dir>
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

RES = sys.argv[1]
R = json.load(open(os.path.join(RES, "results.json")))
sk = pd.read_csv(os.path.join(RES, "skills_flags.csv"))
out = {}

ps = sorted(((k, v["p"]) for k, v in R["RQ3_copies"].items()), key=lambda x: x[1])
m = len(ps)
holm, running = {}, 0.0
for i, (k, p) in enumerate(ps):
    running = max(running, min(1.0, p * (m - i)))
    holm[k] = {"p": p, "p_holm": float(f"{running:.3g}"),
               "cliffs_delta": R["RQ3_copies"][k]["cliffs_delta"]}
out["RQ3_holm"] = holm

h = sk[sk.has_history].copy()
h["ai"] = h.ai_coauthored.fillna(False).astype(bool).astype(int)
t = pd.crosstab(h.ai, h.any_risky_instr)
OR, p = stats.fisher_exact(t.values)
out["RQ3_ai_fisher"] = {"odds_ratio": round(OR, 2), "p": float(f"{p:.3g}"), "table": t.values.tolist()}
X = sm.add_constant(pd.DataFrame({"ai": h.ai, "log_body": np.log1p(h.body_chars.fillna(0))}))
fit = sm.Logit(h.any_risky_instr.astype(int), X).fit(disp=0)
ci = np.exp(fit.conf_int())
out["RQ3_ai_logit"] = {v: {"OR": round(float(np.exp(fit.params[v])), 2),
                           "ci95": [round(float(ci.loc[v, 0]), 2), round(float(ci.loc[v, 1]), 2)],
                           "p": float(f"{fit.pvalues[v]:.3g}")} for v in ["ai", "log_body"]}
out["RQ3_body_chars_median"] = {"ai": float(h.loc[h.ai == 1, "body_chars"].median()),
                                "human": float(h.loc[h.ai == 0, "body_chars"].median())}
json.dump(out, open(os.path.join(RES, "extra_stats.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
