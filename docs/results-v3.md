# Results: model v3 against model v2

Written by `scripts/verify/results_v3.py` from the result files in
`data/generated/eval/v3study/` (not committed); every number below is from those files
and names the machine it was measured on. Scores are with the evidence guard, as the
pipeline runs (D-EVID-1), on each set's main set: notes stuck in a loop are left out
(D-V3-29).
Macro-F1 is over the line decisions APPROVE, PEND and DENY. All claims are synthetic. The
demo uses `claimsense-decision:v3` (D-V3-34).

- Messy notes, Kaggle, T4 GPU (Ollama 0.34.1): 12 claims left out as looping.

## Line-decision macro-F1

| Set | Notes | Claims | Measured on | v2 | v3 | v3 - v2, 95% interval |
|---|---|---:|---|---:|---:|---|
| Clean notes | the v2 test set; notes from the v1 and v2 templates | 300 | the demo laptop (Ollama 0.34.1) | 0.849 | 0.898 | not computed |
| Clean notes | the v2 test set; notes from the v1 and v2 templates | 300 | Kaggle, T4 GPU (Ollama 0.34.1) | 0.839 | 0.904 | +0.016 to +0.116 |
| Messy notes | v3's test set; abbreviations, typos, long histories | 588 | Kaggle, T4 GPU (Ollama 0.34.1) | 0.646 | 0.832 | +0.139 to +0.233 |
| Unseen writing style | messy notes by a writer v3 never trained on | 151 | Kaggle, T4 GPU (Ollama 0.34.1) | 0.623 | 0.816 | +0.103 to +0.281 |
| Human-style notes | written by a local LLM as a physician would (D-V3-15) | 65 | Kaggle, T4 GPU (Ollama 0.34.1) | 0.514 | 0.807 | +0.143 to +0.440 |

The intervals are paired bootstrap intervals over the claims (2,000 draws); one above zero means v3 is better on that set beyond chance.

## Each measure

| Set | Measured on | Model | Valid output | Line accuracy | DENY precision | Wrong approvals | Criterion accuracy |
|---|---|---|---:|---:|---:|---:|---:|
| Clean notes | the demo laptop (Ollama 0.34.1) | v2 | 0.980 | 0.868 | 1.000 | 28 | 0.926 |
| Clean notes | the demo laptop (Ollama 0.34.1) | v3 | 0.973 | 0.904 | 0.988 | 20 | 0.949 |
| Clean notes | Kaggle, T4 GPU (Ollama 0.34.1) | v2 | 0.980 | 0.858 | 1.000 | 30 | 0.924 |
| Clean notes | Kaggle, T4 GPU (Ollama 0.34.1) | v3 | 0.967 | 0.906 | 0.988 | 19 | 0.957 |
| Messy notes | Kaggle, T4 GPU (Ollama 0.34.1) | v2 | 0.912 | 0.705 | 0.770 | 68 | 0.863 |
| Messy notes | Kaggle, T4 GPU (Ollama 0.34.1) | v3 | 0.961 | 0.869 | 0.880 | 48 | 0.932 |
| Unseen writing style | Kaggle, T4 GPU (Ollama 0.34.1) | v2 | 0.901 | 0.680 | 0.742 | 22 | 0.866 |
| Unseen writing style | Kaggle, T4 GPU (Ollama 0.34.1) | v3 | 0.974 | 0.874 | 0.833 | 17 | 0.919 |
| Human-style notes | Kaggle, T4 GPU (Ollama 0.34.1) | v2 | 0.846 | 0.582 | 0.500 | 5 | 0.820 |
| Human-style notes | Kaggle, T4 GPU (Ollama 0.34.1) | v3 | 0.877 | 0.827 | 0.929 | 2 | 0.919 |

Wrong approvals: lines approved that should have been pended or denied. Valid output:
answers the pipeline can use; an unusable answer pends its lines and sends the claim to
FULL review. v3's valid output is under D-MODEL-3's gate; the team accepted it (D-V3-34).

## Time per claim

D-MODEL-5's 30 claims on the demo laptop, with the stack running:

| Model | Median | p95 | File |
|---|---:|---:|---|
| v2 | 3.6 s | 7.6 s | `v2_laptop30-clean.json` |
| v3 | 4.9 s | 9.8 s | `v3_best_laptop30-clean.json` |

## Result files

- Clean notes, the demo laptop (Ollama 0.34.1): `v2_laptop-clean.json`, `v3_best_laptop-clean.json`
- Clean notes, Kaggle, T4 GPU (Ollama 0.34.1): `v2-clean.json`, `v3_best-clean.json`, `compare-v3_best-clean.json`
- Messy notes, Kaggle, T4 GPU (Ollama 0.34.1): `v2-test_messy.json`, `v3_best-test_messy.json`, `compare-v3_best-test_messy.json`
- Unseen writing style, Kaggle, T4 GPU (Ollama 0.34.1): `v2-test_unseen_style.json`, `v3_best-test_unseen_style.json`, `compare-v3_best-test_unseen_style.json`
- Human-style notes, Kaggle, T4 GPU (Ollama 0.34.1): `v2-human_style.json`, `v3_best-human_style.json`, `compare-v3_best-human_style.json`
