# Training readiness

- [PASS] 1 dataset current
- [PASS] 2 real retrieval: procedure+diagnoses+notes-v1; code filter; top 5; min score 0.0; BAAI/bge-small-en-v1.5; knowledge 36cfc77305a5
- [PASS] 3 record quality checks
- [PASS] 4 retrieval golden target: {'recall@3': 0.9778, 'empty': '5/5'}
- [PASS] 5 train/live parity
- [PASS] 6 retrieval misses: {'train': 0.0, 'validation': 0.0, 'test': 0.0}
- [PASS] 7 lengths: {'train': 2512, 'validation': 2432, 'test': 2418}
- [PASS] 8 blind review retrieval
- [PASS] 9 baseline evaluation: ['baseline-gemma4-e2b']

Team items (record in the place named):

- [x] Contracts approved and frozen (DECISIONS.md 2026-09-22)
- [ ] Prompt decision_v2 read and accepted (DECISIONS.md)
- [ ] 3 policies spot-checked against their LCDs (criteria and which are conditional) (DECISIONS.md)
- [ ] 20 sample records read (notes realistic, evidence, labels): readiness/sample-records.md (DECISIONS.md)
- [ ] Blind-review sheet filled in; disagreements with the labels discussed (tests/golden/blind_review/review_sheet.csv)
- [ ] Visit limits stay out of v1; NCCI bypass modifiers stay XE/XP/XS/XU (DECISIONS.md)
- [ ] Max sequence length 3072 accepted (keeps every record) (DECISIONS.md)
- [ ] Kaggle: phone-verified account, GPU and internet on, Gemma license accepted (team)
- [ ] Dataset uploaded as a PRIVATE Kaggle dataset (team)

Blind review agreement with the labels:

- sheet not filled in yet
