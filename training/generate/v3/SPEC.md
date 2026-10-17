# Generator v3: realism spec

Training and test claims whose clinical notes look like real notes, for the v3 decision model. Every
value below is a parameter in `training/generate/v3/config.yaml` (named in `code`); the unit tests
check that this file and the config name the same parameters. Synthetic data only: no real patient
data, nothing from the Evernorth or Cigna documents in `data/raw/payer-guides/`, no AMA CPT descriptor
text, and no outside model APIs (the open-weight models run in private Kaggle notebooks).

## Sources

Realism comes only from public sources already in `data/raw/`:

- **Note content.** The LCDs behind the policies (MCD download `mcd/2026-09-21/`). For example
  L33906 (epidural injections) asks for "history, physical examination, and concordant radiological
  image-based diagnostic testing", an objective pain scale at baseline, and documented conservative
  care. This is why a note has history, exam, results (with an embedded imaging report) and plan
  sections, and why prior-procedure responses are dated.
- **Uncertain mentions.** ICD-10-CM Official Guidelines FY2027, Section IV.H: an uncertain diagnosis
  ("probable", "suspected", "rule out") is not coded as confirmed in the outpatient setting. This is
  why a hedged mention never establishes a criterion.
- **Chapter 15 codes.** The same guidelines restrict Chapter 15 codes to the maternal record.
- **Claim form.** NUCC 1500 Claim Form Reference Instruction Manual v13 (p.34: six service lines;
  p.38: up to four modifiers) and the CMS Claims Processing Manual ch.26 (p.15: up to 12 diagnoses;
  p.16: up to four modifiers).

No public sample notes are used.

## Phase 1: what a note looks like

### Structure

The section list is `note.sections`:

1. chief complaint
2. history of present illness (HPI)
3. past history
4. medications
5. allergies
6. social history
7. review of systems
8. exam
9. results
10. assessment
11. plan

A section without a fact appears with probability `note.section_presence.<section>`. A section that
holds a fact always appears. Headers vary (`phrases/sections.yaml` `headers`).

### Length

- Range: 150 to 900 words (`note.length_words.min`, `note.length_words.max`).
- Target median: `note.length_words.target_median`.
- Long tail: a share `note.length_words.long_tail_share` of notes is drawn from
  `note.length_words.long_tail_min` to the maximum.

Length is reached with more history, exam and copied-forward text, never with more criterion facts.

### Embedded reports

A claim still has one note, so a report goes inside it:

- an imaging report (`note.embedded_reports.imaging_report`);
- a therapy summary (`note.embedded_reports.therapy_summary`);
- a prior procedure and its response (`note.embedded_reports.prior_procedure`), for example
  "PRIOR PROCEDURE: transforaminal epidural steroid injection at L5 on 2026-03-02. RESPONSE: 60%
  relief for 3 months".

Each value is the chance that a fact placed in that kind of report is written as a report block.
Which criterion goes where is the `placement` in `phrases/criteria.yaml`. A prior-procedure date is
the visit date minus the interval the fact states.

### Writing style

- **Author habits** (`style_cards.author_habits`): terse and abbreviated, full sentences, dictated
  (run-on dictation phrasing, `note.dictation_style`), or a templated EHR layout.
- **Abbreviations:** pt, c/o, LBP, hx, s/p, w/, x6wks, HNP, SLR and the rest of
  `phrases/abbreviations.yaml`. None of them is on The Joint Commission's "Do Not Use" list.
- **Copy-forward:** a block marked "copied from" an earlier visit appears with probability
  `tricky.copy_forward`.

### Tricky facts

All of these use the v2 labelling (D-POL-3); none adds a labelling rule.

- **Negation.** An exclusion that does not apply may be stated in the negative
  (`tricky.negated_exclusion`, `negated` sentences). It stays NOT_APPLICABLE. Review-of-systems lines
  are negatives. Notes never say "denies" (leakage); they say "reports no", "negative for" or "no".
- **Past vs current.** A dated past episode, resolved and unrelated to the visit's criteria, appears
  with probability `tricky.past_vs_current` (`phrases/sections.yaml` `past_vs_current`).
- **Uncertainty.** A missing criterion may get a hedged mention (`tricky.uncertain_for_missing`,
  `uncertain` sentences). It stays NOT_DOCUMENTED.
- **Contradiction.** A criterion is stated twice with conflicting content (`tricky.contradicted`):
  first as text copied forward from an earlier visit, then as an explicit correction marked with one
  of `tricky.correction_markers`. The correction decides the status, and its sentence is the
  evidence. A contradiction without an explicit correction is not generated: the v2 prompt has no
  rule for it.
- **Distractors.**
  - Unrelated conditions (`tricky.distractor_conditions`), which may also be listed on the claim.
  - Medications (`tricky.distractor_medications`).
  - Allergies and social history.

  Every distractor has topics, and each clinic excludes the topics that touch its own criteria
  (`phrases/sections.yaml` `clinics.<type>.exclude`).
- **Borderline values.** With probability `tricky.borderline`, a criterion with a numeric threshold
  is stated at the edge of it, on the side its state needs:
  - **Above:** the value meets the threshold, so the status is MET.
  - **Below:** it just misses it, so the status is NOT_MET.

  The status is computed from the case's slot values and the threshold (`borderline` in
  `phrases/criteria.yaml`), never written by hand. Thresholds used:

  | Criterion | Threshold | Above (MET) | Below (NOT_MET) |
  |---|---|---|---|
  | POL-PAIN-001.c10 | pain at least 28 days (4 weeks) | 4, 5 weeks; onset 28, 31 days before the visit (as a date) | 3 weeks; onset 24, 26 days before |
  | POL-PAIN-002.c6 | pain at least 3 months | 3 months | 2 months |
  | POL-PAIN-001.c8 | relief at least 50% and lasting at least 3 months | 50% for 3 months, 55% for 3 months | 45% for 3 months, 65% for 2 months; both with the same approach planned again |
  | POL-FOOT-001.c1 | no feeling at 2 or more of 5 sites | 2 of 5 | 1 of 5 |
  | POL-SURG-004.c7 | at least 12 degrees or 30 percent | 12 deg (24%), 10 deg (30%) | 11 deg (25%), 10 deg (22%) |
  | POL-SURG-002.c3 | at least 24 months since the last colonoscopy | 24, 25 months | 22, 23 months |
  | POL-IMG-001.c2 | headache more than 14 days | 15, 16 days | 13, 14 days |
  | POL-SURG-003.c4 | conservative trial at least 13 weeks (3 months) | 13, 14 weeks | 10, 11 weeks (the c2 exclusion's situation then holds too) |

  Numeric thresholds not used, and why:

  - **POL-CAR-002.c4, ejection fraction 40% or less.** These profiles' diagnoses include atrial
    fibrillation, which meets "arrhythmias" on its own.
  - **POL-CAR-002.c5 and c6, 48 hours to 15 days and 30 days.** These are recording lengths, a
    property of the test, not a patient fact.
  - **POL-CAR-001.c6, once a year.** Crossing the line changes whether the conditional applies, not
    whether it is met.
  - **POL-DX-003.c7, under 70 prick, 40 intradermal and up to 80 patch tests.** The counts are the
    claim's units and meet the MUE rule.
  - **POL-PAIN-002.c5, 2 weeks between blocks.** Its met state is the intent to go on to ablation.
  - **POL-PAIN-001.c8's 14-day alternative.** It also needs a changed approach.
  - **POL-SURG-002.c5, 2 cm adenoma and 7 or 15 years of colitis.**
    - Any polyp history already qualifies, so the 2 cm size never decides the case.
    - The colitis durations need IBD diagnoses outside the profile.
  - **POL-FOOT-001.c4, class findings.** These are combinations of findings, not one number.
  - **POL-WOUND-001.c4, 30 days.** Care without improvement does not continue regardless of the day
    count.
  - **POL-REHAB-001.c7.** No number.

### Claim form

Limits:

| Limit | Config key | Source | contracts.py |
|---|---|---|---|
| 6 service lines | `claim_form.max_lines` | NUCC | 50 lines allowed, so no limit was hit |
| 12 diagnoses | `claim_form.max_diagnoses` | | 12 |
| 4 pointers per line | `claim_form.max_pointers_per_line` | | 4 |
| 4 modifiers | `claim_form.max_modifiers` | | 4 |

How claims are drawn:

- **Lines per claim** (`claim_form.lines_per_claim`): mostly 1 or 2. Extra lines are office visits on
  earlier dates (`claim_form.extra_visit_days`), so a claim can have several dates of service.
- **Extra diagnoses** (`claim_form.extra_diagnoses`): distractor conditions, listed after the claim's
  own diagnoses. A share `claim_form.extra_pointer_share` of them are pointed to from a line, after
  the primary pointer.
- **Modifiers:** combinations are v2's (25, 57, 59, XS, XU, RT, LT, Q8). Units come from the profiles.
- **Rules check:** every claim goes through the real rules engine, and one whose rule outcome changes
  is drawn again.

### Noise

Applied to writer A and B notes (Phase 3):

- typos per eligible word (`noise.typo_rate`);
- abbreviation swaps (`noise.abbreviation_swap_rate`);
- two adjacent sections swapped (`noise.section_shuffle`, never the HPI);
- formatting noise (`noise.formatting.*`):
  - upper-case headers;
  - sections run together;
  - double spaces;
  - bullet lists;
  - trailing spaces.

Noise never touches a protected span (`noise.protected`): fact phrases, numbers, dates and negation
words (`noise.negation_words`).

### Target mix

- **Scenario types and weights** (`scenario_weights`): v2's, so the outcome mix matches v2, with the
  tricky facts above layered on.
- **Policies** (`test_unseen_policy_share`): train and validation use the training policies. A third
  of each test set uses the test-only policies (`TEST_ONLY_POLICIES`), as in v2.

## Phase 2: fact sheets and labels

Every claim starts from a fact sheet (JSON). It records:

- the patient (age and sex) and the visit dates;
- a timeline of dated events (prior procedures, prior studies, the start of symptoms);
- the lines;
- for each line and each criterion the lookup shows:
  - its fact status: `documented`, `missing`, `contradicted`, `borderline_below` or
    `borderline_above`, or `absent` (an exclusion, conditional or group member not in play);
  - the label status the status gives;
  - the fact's text, the values that must appear in it, and its placement;
- the distractors and the style card.

How labels come about:

- **Borderline statuses** map to MET or NOT_MET through the threshold checks.
- **Contradicted** facts take the status of their correction.
- **Labels** are computed from the statuses by v2's own code: `app.ml.derive.implied_decision`, as
  `scenarios_v2` does. There is no new labelling logic.
- **Reference data** (members, providers, plans) is generated from the seed files, as in v2, never
  read from a database.

## Phase 3: note writers

- **Writer A (templates).**
  - It draws from the v2 sentences and the extra wordings in `phrases/criteria.yaml`, inside
    clinic-specific sections (`phrases/sections.yaml`).
  - Everything is seeded.
- **Writer B (open-weight model).**
  - The model is `llm.writer_b.model` (licence `llm.writer_b.licence`), run with vLLM
    `llm.vllm.version` in a private Kaggle notebook.
  - Sampling: temperature `llm.writer_b.temperature` and top-p `llm.writer_b.top_p`, up to
    `llm.writer_b.max_tokens` tokens, a fixed seed per note.
  - The prompt gives the fact sheet and a style card.
  - The note must contain every documented fact with its values, none of the missing ones, and the
    contradictions and distractors as specified, and no outcome words.
- **Writer C (held out, test only).**
  - The model is `llm.writer_c.model` (`llm.writer_c.licence`), a family neither A nor B uses.
  - It writes in its own formats (`style_cards.writer_c_formats`).
- **Hand-written set.** 30 fact sheets (`sizes.handwritten`) and a one-page writing guide, for the
  team to write notes from.

The noise layer is applied to A and B notes after the facts are found.

## Phase 4: verification gate

Every note must pass:

1. **Every documented fact is present.** The quote is the sentence that states it, its exact
   character span is recorded, and it contains the fact's values.
2. **No missing fact is present.**
   - Pattern check: no sentence holds `verification.missing_overlap` of a missing fact's content words.
   - Verifier: `llm.verifier.model` (temperature `llm.verifier.temperature`), a family no writer uses,
     quotes the evidence for each criterion. Any evidence found for a missing fact fails the note.
3. **Contradictions and borderline values appear exactly as specified.** Both statements are
   present, the correction comes later, and the exact borderline value is in the quote.
4. **The label recomputed from the verified facts equals the fact sheet's label.**
5. **Leakage scan.** No outcome word and no criterion or policy ID (`leakage.patterns`).
6. **Targets are valid.** The SLMOutput targets' quotes are exact substrings of the note, are at
   least `verification.min_quote_words` words long, and pass the existing output schema and evidence
   guard.
7. **No near-duplicates** across the train, validation and test splits (5-word shingles, Jaccard of
   `verification.near_duplicate_jaccard` or more).

A failing note is regenerated, up to `verification.max_regenerations` times. Pass rates are tracked
per writer. Each split is drawn with `sizes_margin` extra fact sheets, so that sheets still failing
after every regeneration can be dropped and the split keeps its size; the final sets are trimmed to
the sizes above.

## Phase 5: datasets

**Splits:**

| Split | Size | Writers |
|---|---|---|
| train | `sizes.train` | A and B (`writer_mix.train`) |
| validation | `sizes.validation` | A and B (`writer_mix.validation`) |
| messy test | `sizes.test_messy` | A and B (`writer_mix.test_messy`) |
| unseen-style test | `sizes.test_unseen_style` | C (`writer_mix.test_unseen_style`) |
| hand-written | `sizes.handwritten` fact sheets | the team |

The v2 clean test (300) stays unchanged.

**Training mix:** v2 clean train to v3 messy train at `training_mix.v2_clean` : `training_mix.v3_messy`.

**Statistics:**

- note length;
- token length with the real prompt template, against the context limit;
- noise rates;
- outcome and scenario mix;
- lines per claim;
- verification pass rates.

**Check packs (synthetic only):**

- 50 notes with their fact sheets and labels, as a checklist;
- 20 notes without labels, for an optional realism rating.

## Kaggle

- **Estimates first:** GPU hours are estimated before each run (`llm.gpu_hours_estimate`), and the
  estimates are refreshed from the pilots.
- **Engine and precision:** vLLM's V1 engine (`llm.vllm.use_v1_engine`; Kaggle's Python 3.13 image
  needs vLLM 0.10 or later, which has no other) in half precision (`llm.vllm.dtype`). A T4 cannot
  run FlashAttention, so each stage tries the attention backends `llm.vllm.attention_backends` in
  order and records the one that ran. The notebook pins `llm.vllm.pip_pins` next to vLLM (Kaggle's
  image ships a Transformers that vLLM 0.11 cannot use).
- **Hardware:** the two T4s run with tensor parallel `llm.vllm.tensor_parallel_size`, at
  `llm.vllm.max_model_len` tokens and `llm.vllm.gpu_memory_utilization` of memory.
- **Privacy:** the datasets and notebooks are private, because the records hold CPT codes.

## Other parameters

| Parameter | Meaning |
|---|---|
| `version` | The generator version |
| `seed` | The base seed |
| `policy_set` | The labels follow policy set v2 |
| `prompt_version` | The user message uses decision_v3, unchanged |
| `style_cards.length_buckets` | Shares of short, medium and long notes |
| `llm.writer_b.family` | The writer B family, for the different-family checks |
| `llm.writer_c.family` | The writer C family |
| `llm.writer_c.temperature` | Writer C sampling temperature |
| `llm.writer_c.top_p` | Writer C top-p |
| `llm.writer_c.max_tokens` | Writer C token limit |
| `llm.verifier.family` | The verifier family |
| `llm.verifier.max_tokens` | Verifier token limit |
| `llm.verifier.licence` | The verifier licence |
