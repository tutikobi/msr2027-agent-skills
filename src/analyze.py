"""Main analysis for the MSR 2027 Mining Challenge study on GitSkills.

Usage: python3 -I src/analyze.py <path/to/agent_skills_sample.db> <out_dir>

RQ1  What security-relevant capabilities do SKILL.md instructions request?
RQ2  How often do skills bundle executable scripts, and what do those scripts do?
RQ3  Are capability-bearing skills reused (copied) more or less than others,
     and does AI co-authorship of the skill's commits relate to them?
"""
import collections
import json
import os
import re
import sqlite3
import sys

import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detectors import INSTRUCTION, SCRIPT, SCRIPT_EXT, scan  # noqa: E402

DB, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

AI_TRAILER = re.compile(
    r"Co-authored-by:\s*(?:Claude|Copilot|GitHub Copilot|Cursor|Codex|Gemini|"
    r"Devin|Aider|Windsurf|Amp|OpenCode|Junie)", re.I)
GENERATED = re.compile(r"Generated with \[?(?:Claude Code|Cursor|Codex)", re.I)

# ---------------------------------------------------------------- skills
skills = pd.read_sql_query(
    """SELECT a.repo_full_name, a.path, a.file_sha, a.location_class,
              a.frontmatter_valid, a.body_chars, a.sibling_count,
              a.has_scripts, a.has_references, a.content,
              r.stars, r.language
       FROM artifacts a LEFT JOIN repos r ON r.full_name = a.repo_full_name
       WHERE a.dedup_primary = 1""", con)

# copies / repos / owners per distinct content (complete in the sample)
reuse = pd.read_sql_query(
    """SELECT file_sha, COUNT(*) AS copies,
              COUNT(DISTINCT repo_full_name) AS repos,
              COUNT(DISTINCT substr(repo_full_name, 1, instr(repo_full_name,'/')-1)) AS owners
       FROM artifacts GROUP BY file_sha""", con)
skills = skills.merge(reuse, on="file_sha", how="left")

# AI co-authorship over every occurrence of the content that has history
hist = pd.read_sql_query(
    """SELECT file_sha, first_commit_message, last_commit_message,
              first_commit_author_type, last_commit_author_type
       FROM artifacts WHERE history_fetched = 1""", con)
def ai_flag(row):
    msg = f"{row.first_commit_message or ''}\n{row.last_commit_message or ''}"
    bot = "Bot" in (row.first_commit_author_type, row.last_commit_author_type)
    return bool(AI_TRAILER.search(msg) or GENERATED.search(msg)), bot
hist[["ai_coauthored", "bot_author"]] = hist.apply(lambda r: pd.Series(ai_flag(r)), axis=1)
hist_agg = hist.groupby("file_sha")[["ai_coauthored", "bot_author"]].any().reset_index()
hist_agg["has_history"] = True
skills = skills.merge(hist_agg, on="file_sha", how="left")
skills["has_history"] = skills["has_history"].fillna(False).astype(bool)

# symlink skills carry a path, not instructions
skills["is_symlink"] = skills["content"].fillna("").str.len().lt(200) & \
    skills["content"].fillna("").str.match(r"^\.{0,2}/?[\w./-]+$")
skills = skills[~skills.is_symlink & skills.content.notna()].copy()

cats_i = list(INSTRUCTION)
flags = skills["content"].apply(lambda t: pd.Series(scan(t, "instruction")))
skills = pd.concat([skills, flags.add_prefix("i_")], axis=1)
risky_i = [c for c in cats_i if c not in ("shell_exec", "injection_phrase")]
skills["any_risky_instr"] = skills[[f"i_{c}" for c in risky_i]].any(axis=1)

# skills that live in test fixtures, benchmarks or research corpora (incl.
# deliberately poisoned ones) rather than in operational projects
FIXTURE = re.compile(r"(?i)(?:^|/)(?:tests?|fixtures?|__tests__|datasets?|benchmarks?|"
                     r"baselines?|evals?|corpus|samples?|examples?)/|poison|malicious|"
                     r"jailbreak|red-?team|injection")
skills["fixture_context"] = (skills.path.str.contains(FIXTURE) |
                             skills.repo_full_name.str.split("/").str[1].str.contains(FIXTURE))

# ---------------------------------------------------------------- scripts
sib = pd.read_sql_query(
    """SELECT s.repo_full_name, s.artifact_path, s.entry_name, s.entry_size, s.content
       FROM artifact_siblings s WHERE s.entry_type = 'file'""", con)
sib["ext"] = sib.entry_name.str.extract(r"(\.[A-Za-z0-9]+)$")[0].str.lower()
scripts = sib[sib.ext.isin(SCRIPT_EXT)].copy()
scripts_txt = scripts[scripts.content.notna()].copy()
cats_s = list(SCRIPT)
sflags = scripts_txt["content"].apply(lambda t: pd.Series(scan(t, "script")))
scripts_txt = pd.concat([scripts_txt, sflags.add_prefix("s_")], axis=1)

key = ["repo_full_name", "artifact_path"]
per_skill_scripts = scripts.groupby(key).size().rename("n_scripts").reset_index()
per_skill_flags = scripts_txt.groupby(key)[[f"s_{c}" for c in cats_s]].any().reset_index()
skills = skills.merge(per_skill_scripts, left_on=["repo_full_name", "path"],
                      right_on=key, how="left").drop(columns=["artifact_path"])
skills = skills.merge(per_skill_flags, left_on=["repo_full_name", "path"],
                      right_on=key, how="left", suffixes=("", "_y"))
skills = skills.drop(columns=[c for c in skills.columns if c.endswith("_y") or c == "artifact_path"])
skills["n_scripts"] = skills["n_scripts"].fillna(0).astype(int)
for c in cats_s:
    skills[f"s_{c}"] = skills[f"s_{c}"].fillna(False).astype(bool)
skills["ships_scripts"] = skills.n_scripts > 0
skills["any_risky_script"] = skills[[f"s_{c}" for c in cats_s]].any(axis=1)

# does SKILL.md mention the bundled script it ships? (disclosure)
def mentions_script(row):
    if not row.ships_scripts:
        return None
    names = scripts[(scripts.repo_full_name == row.repo_full_name) &
                    (scripts.artifact_path == row.path)].entry_name
    base = {os.path.basename(n) for n in names}
    return any(b in row.content for b in base)
skills["mentions_script"] = skills.apply(mentions_script, axis=1)

# ---------------------------------------------------------------- results
N = len(skills)
R = {"N_distinct_skills": N,
     "N_occurrences": int(skills.copies.sum()),
     "N_valid_frontmatter": int(skills.frontmatter_valid.sum())}

def prev(df, col):
    return int(df[col].sum()), round(100 * df[col].mean(), 1)

rq1 = []
for c in cats_i:
    k, p = prev(skills, f"i_{c}")
    kv, pv = prev(skills[skills.frontmatter_valid == 1], f"i_{c}")
    occ = int(skills.loc[skills[f"i_{c}"], "copies"].sum())
    rq1.append({"category": c, "distinct": k, "pct": p,
                "pct_valid_fm": pv, "occurrences": occ})
R["RQ1"] = rq1
R["RQ1_any_risky"] = prev(skills, "any_risky_instr")
R["RQ1_n_categories_dist"] = skills[[f"i_{c}" for c in risky_i]].sum(axis=1).value_counts().sort_index().to_dict()
fx, op = skills[skills.fixture_context], skills[~skills.fixture_context]
R["RQ1_fixture_context"] = {
    "n": int(len(fx)), "pct": round(100 * len(fx) / N, 1),
    "risky_pct_fixture": round(100 * fx.any_risky_instr.mean(), 1),
    "risky_pct_operational": round(100 * op.any_risky_instr.mean(), 1),
    "rce_fixture": int(fx.i_remote_code_exec.sum()), "rce_total": int(skills.i_remote_code_exec.sum()),
    "inj_fixture": int(fx.i_injection_phrase.sum()), "inj_total": int(skills.i_injection_phrase.sum()),
    "per_category_operational_pct": {c: round(100 * op[f"i_{c}"].mean(), 2) for c in cats_i}}
R["RQ1_by_location"] = skills.groupby("location_class")["any_risky_instr"].agg(["count", "mean"]).round(3).to_dict("index")

R["RQ2_ships_scripts"] = prev(skills, "ships_scripts")
R["RQ2_scripts_files"] = int(len(scripts))
R["RQ2_scripts_with_text"] = int(len(scripts_txt))
R["RQ2_ext"] = scripts.ext.value_counts().head(8).to_dict()
sk_s = skills[skills.ships_scripts]
rq2 = []
for c in cats_s:
    k, p = prev(sk_s, f"s_{c}")
    rq2.append({"category": c, "skills": k, "pct_of_script_skills": p,
                "files": int(scripts_txt[f"s_{c}"].sum())})
R["RQ2"] = rq2
R["RQ2_any_risky_script"] = prev(sk_s, "any_risky_script")
ms = sk_s.mentions_script.dropna().astype(bool)
R["RQ2_script_mentioned_in_skillmd_pct"] = round(100 * ms.mean(), 1)
undisclosed = sk_s[(sk_s.any_risky_script) & (sk_s.mentions_script == False)]  # noqa: E712
R["RQ2_risky_undisclosed"] = (len(undisclosed), round(100 * len(undisclosed) / max(1, sk_s.any_risky_script.sum()), 1))

# RQ3 reuse
def compare(df, col):
    a, b = df.loc[df[col], "copies"], df.loc[~df[col], "copies"]
    u = stats.mannwhitneyu(a, b, alternative="two-sided")
    # rank-biserial (Cliff's delta equivalent)
    delta = 2 * u.statistic / (len(a) * len(b)) - 1
    copied = lambda s: round(100 * (s > 1).mean(), 1)
    return {"n_true": int(len(a)), "mean_copies_true": round(a.mean(), 2),
            "mean_copies_false": round(b.mean(), 2),
            "pct_copied_true": copied(a), "pct_copied_false": copied(b),
            "p": float(f"{u.pvalue:.3g}"), "cliffs_delta": round(delta, 3)}
R["RQ3_copies"] = {c: compare(skills, c) for c in
                   ["any_risky_instr", "ships_scripts", "any_risky_script"] +
                   [f"i_{c}" for c in risky_i]}
top = skills.nlargest(100, "copies")
R["RQ3_top100_any_risky_instr_pct"] = round(100 * top.any_risky_instr.mean(), 1)
R["RQ3_top100_ships_scripts_pct"] = round(100 * top.ships_scripts.mean(), 1)
R["RQ3_risky_occurrences"] = int(skills.loc[skills.any_risky_instr | skills.any_risky_script, "copies"].sum())
R["RQ3_copies_dist"] = skills.copies.describe().round(2).to_dict()

h = skills[skills.has_history].copy()
h["ai_coauthored"] = h["ai_coauthored"].fillna(False).astype(bool)
R["RQ3_history_n"] = int(len(h))
R["RQ3_ai_coauthored"] = prev(h, "ai_coauthored")
ct = pd.crosstab(h.ai_coauthored, h.any_risky_instr)
chi = stats.chi2_contingency(ct) if ct.shape == (2, 2) else None
R["RQ3_ai_vs_risky"] = {
    "risky_pct_ai": round(100 * h.loc[h.ai_coauthored, "any_risky_instr"].mean(), 1),
    "risky_pct_human": round(100 * h.loc[~h.ai_coauthored, "any_risky_instr"].mean(), 1),
    "chi2_p": float(f"{chi.pvalue:.3g}") if chi else None}

# stars of hosting repo (representative)
R["RQ3_stars_risky_vs_not"] = {
    "median_risky": float(skills.loc[skills.any_risky_instr, "stars"].median()),
    "median_other": float(skills.loc[~skills.any_risky_instr, "stars"].median()),
    "p": float(f"{stats.mannwhitneyu(skills.loc[skills.any_risky_instr,'stars'].dropna(), skills.loc[~skills.any_risky_instr,'stars'].dropna()).pvalue:.3g}")}

with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(R, f, indent=2, default=str)
cols = [c for c in skills.columns if c != "content"]
skills[cols].to_csv(os.path.join(OUT, "skills_flags.csv"), index=False)
scripts_txt.drop(columns=["content"]).to_csv(os.path.join(OUT, "scripts_flags.csv"), index=False)
print(json.dumps(R, indent=2, default=str))
