"""Figure for the paper: prevalence of each capability (Fig. 1).

Usage: python3 -I src/figures.py <results_dir> <fig_dir>
Single-hue horizontal bars (magnitude), direct value labels, print-friendly.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES, FIG = sys.argv[1], sys.argv[2]
os.makedirs(FIG, exist_ok=True)
R = json.load(open(os.path.join(RES, "results.json")))
P = {r["category"]: r["pct"] for r in R["RQ1"]}
S = {r["category"]: r["pct_of_script_skills"] for r in R["RQ2"]}

ilabels = {"shell_exec": "Shell execution", "secrets": "Credentials/secrets",
           "network": "Network access", "privilege": "Privilege/permission",
           "destructive": "Destructive ops", "remote_code_exec": "Remote code piped to shell",
           "confirmation_bypass": "Confirmation bypass"}
slabels = {"network": "Network access", "proc_exec": "Process execution",
           "secrets": "Reads secrets from env", "destructive_fs": "Recursive deletion",
           "dynamic_code": "Dynamic code (eval/exec)", "obfuscation": "Encoded payload + exec"}

LANG = sys.argv[3] if len(sys.argv) > 3 else "en"
SUFFIX = "" if LANG == "en" else f"_{LANG}"
if LANG == "pt":
    ilabels = {"shell_exec": "Execução de shell", "secrets": "Credenciais/segredos",
               "network": "Acesso à rede", "privilege": "Privilégio/permissão",
               "destructive": "Operações destrutivas", "remote_code_exec": "Código remoto via shell",
               "confirmation_bypass": "Dispensa de confirmação"}
    slabels = {"network": "Acesso à rede", "proc_exec": "Execução de processos",
               "secrets": "Lê segredos do ambiente", "destructive_fs": "Deleção recursiva",
               "dynamic_code": "Código dinâmico (eval/exec)", "obfuscation": "Payload codificado + exec"}

INK, MUTED, BAR = "#0b0b0b", "#52514e", "#2a78d6"
plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "font.family": "serif", "font.serif": ["TeX Gyre Termes", "Liberation Serif", "DejaVu Serif"], "font.size": 7.5, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": INK})
fig, axes = plt.subplots(1, 2, figsize=(7.16, 1.85), gridspec_kw={"wspace": 0.95})
for ax, data, lab, title in [
        (axes[0], P, ilabels, f"(a) SKILL.md instructions (% of {R['N_distinct_skills']:,} skills)" if LANG == "en"
         else f"(a) Instruções do SKILL.md (% de {R['N_distinct_skills']:,} skills)".replace(",", ".")),
        (axes[1], S, slabels, f"(b) Bundled scripts (% of {R['RQ2_ships_scripts'][0]:,} skills with scripts)" if LANG == "en"
         else f"(b) Scripts empacotados (% de {R['RQ2_ships_scripts'][0]:,} skills com scripts)".replace(",", "."))]:
    items = sorted(((lab[k], data[k]) for k in lab), key=lambda x: x[1])
    names, vals = zip(*items)
    ax.barh(names, vals, color=BAR, height=0.62)
    for y, v in enumerate(vals):
        lbl = f"{v:.1f}" if LANG == "en" else f"{v:.1f}".replace(".", ",")
        ax.text(v + max(vals) * 0.015, y, lbl, va="center", fontsize=7, color=INK)
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_title(title, fontsize=7.5, loc="left", color=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, color="#e4e3df", linewidth=0.5)
    ax.set_axisbelow(True)
fig.savefig(os.path.join(FIG, f"prevalence{SUFFIX}.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(FIG, f"prevalence{SUFFIX}.png"), bbox_inches="tight", dpi=220)
print("ok")
