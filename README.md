# Replication package — Security-capability census of GitSkills

Code and data for the MSR 2027 Mining Challenge paper
"What Do Agent Skills Ask Agents to Do? A Security-Capability Census of GitSkills".

## Data
GitSkills sample (`agent_skills_sample.zip`) from
https://github.com/giuseppedestefanis/gitskills-sample, commit `fff3df93beeee51a5444450891751f143e38da3e`
(12 Sep 2026). Unzip it into its own folder to obtain `agent_skills_sample.db`.
The queries run unchanged on the full dataset (Zenodo DOI 10.5281/zenodo.21875637).

## Reproduce
Python 3.11+, pandas, scipy, statsmodels, matplotlib.

```bash
python3 -I src/analyze.py      /path/to/agent_skills_sample.db results
python3 -I src/extra_stats.py  results
python3 -I src/figures.py      results figs
python3 -I src/domain_adjust.py  /path/to/agent_skills_sample.db results        # RQ3 robustness (domain, language)
python3 -I src/validate_sample.py /path/to/agent_skills_sample.db results 15   # draws the validation sample
python3 -I src/make_annotation_kit.py /path/to/agent_skills_sample.db results annotation  # blind human kit
python3 -I src/agreement.py annotation                                         # kappa, consensus precision, recall
cd paper && latexmk -pdf main.tex
```

## Contents
| Path | What |
|---|---|
| `src/detectors.py` | Regular-expression detectors (8 instruction + 6 script categories) |
| `src/analyze.py` | RQ1–RQ3 analysis; writes `results/results.json`, per-skill and per-script flags |
| `src/extra_stats.py` | Holm correction, Fisher test, length-adjusted logistic regression |
| `src/validate_sample.py` | Reproducible sample of detector hits (seed 2027) |
| `src/domain_adjust.py` | Logistic regressions adjusted for keyword-based domain and language |
| `src/make_annotation_kit.py`, `src/agreement.py` | Blind double-annotation kit and scoring (Cohen's κ, Wilson CI) |
| `annotation/` | The kit: 184 precision rows (no model labels), 100 unflagged skills for recall |
| `results/validation_labeled.csv` | 184 labelled hits (TP/FP), first LLM-assisted pass |
| `results/precision.csv` | Per-category precision |
| `figs/prevalence.pdf` | Figure 1 |
| `paper/` | LaTeX source |

Bundled scripts from the dataset were never executed.
