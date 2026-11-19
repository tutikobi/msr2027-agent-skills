# Blind annotation kit

precision_A.csv / precision_B.csv: the 184 validation hits, shuffled, without the model's labels; fill label_TP_FP with TP (the text requests/performs the capability) or FP (mention only).
recall_negatives.csv + recall_texts.zip (unzip it to get recall_texts/<id>.md): 100 random skills no risky-instruction detector flagged; mark 1 per category the skill does request (a missed detection).
Score with: python3 -I src/agreement.py annotation
Rows are keyed by skill_sha (GitSkills content hash) instead of repository names.
