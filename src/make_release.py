"""Build the public, anonymized replication package.

Repository names and paths are replaced by the skill's content hash
(`file_sha`, already public in GitSkills) so that the package does not name
repositories holding risky or malicious skills (see the paper's ethics
section). Everything stays reproducible from the public dataset.

Usage: python3 -I src/make_release.py <project_dir> <out_dir>
"""
import os
import shutil
import sys

import pandas as pd

P, OUT = sys.argv[1], sys.argv[2]
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
for d in ("src", "figs"):
    shutil.copytree(os.path.join(P, d), os.path.join(OUT, d),
                    ignore=shutil.ignore_patterns("__pycache__"))
os.makedirs(os.path.join(OUT, "paper"))
for f in ("main.tex", "refs.bib", "prevalence.pdf"):
    shutil.copy(os.path.join(P, "paper", f), os.path.join(OUT, "paper", f))
shutil.copy(os.path.join(P, "README.md"), OUT)

R, RO = os.path.join(P, "results"), os.path.join(OUT, "results")
os.makedirs(RO)
for f in ("results.json", "extra_stats.json", "domain_adjust.json", "precision.csv"):
    shutil.copy(os.path.join(R, f), RO)

sk = pd.read_csv(os.path.join(R, "skills_flags.csv"))
key = sk.set_index(["repo_full_name", "path"])["file_sha"].to_dict()
sk.drop(columns=["repo_full_name", "path"]).to_csv(os.path.join(RO, "skills_flags.csv"), index=False)

sc = pd.read_csv(os.path.join(R, "scripts_flags.csv"))
sc.insert(0, "skill_sha", [key.get((r, a)) for r, a in zip(sc.repo_full_name, sc.artifact_path)])
sc["entry_name"] = sc.entry_name.map(os.path.basename)
sc.drop(columns=["repo_full_name", "artifact_path"]).to_csv(os.path.join(RO, "scripts_flags.csv"), index=False)


def pseudo(df, repo_col, path_col):
    def sha(row):
        p = row[path_col]
        base, entry = (p.split("::", 1) + [None])[:2] if "::" in p else (p, None)
        s = key.get((row[repo_col], base))
        return f"{s}::{os.path.basename(entry)}" if entry else s
    df = df.copy()
    df.insert(0, "skill_sha", df.apply(sha, axis=1))
    return df.drop(columns=[repo_col, path_col])


v = pd.read_csv(os.path.join(R, "validation_labeled.csv"))
pseudo(v, "repo", "path").to_csv(os.path.join(RO, "validation_labeled.csv"), index=False)

A, AO = os.path.join(P, "annotation"), os.path.join(OUT, "annotation")
os.makedirs(AO)
for f in ("precision_A.csv", "precision_B.csv", "recall_negatives.csv"):
    pseudo(pd.read_csv(os.path.join(A, f)), "repo", "path").to_csv(os.path.join(AO, f), index=False)
shutil.copy(os.path.join(A, "_model_labels_DO_NOT_OPEN_BEFORE.csv"), AO)
shutil.copytree(os.path.join(A, "recall_texts"), os.path.join(AO, "recall_texts"))
with open(os.path.join(AO, "README.md"), "w") as f:
    f.write("# Blind annotation kit\n\n"
            "precision_A.csv / precision_B.csv: the 184 validation hits, shuffled, without the model's labels; "
            "fill label_TP_FP with TP (the text requests/performs the capability) or FP (mention only).\n"
            "recall_negatives.csv + recall_texts/: 100 random skills no risky-instruction detector flagged; "
            "mark 1 per category the skill does request (a missed detection).\n"
            "Score with: python3 -I src/agreement.py annotation\n"
            "Rows are keyed by skill_sha (GitSkills content hash) instead of repository names.\n")
print("ok")
