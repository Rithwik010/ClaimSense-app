"""Task P2.3b checkpoint 2: new golden cases for rules v2 (D-GOLD-2, D-GOLD-6), drafted for an
independent check on sheet G4.

The rules cases (R14 to R20, R15's article readings, an H5 case, a line failing a new rule and
R11, the two same-day regression cases) and the end-to-end changes (E2E-17 and E2E-23 under R15,
and E2E-32, a FINAL_PARTIAL claim in which the model denies a line) follow D-RULE-2 to D-RULE-4 and
D-GOLD-6. Expected values are computed here independently of app/rules (the code they will test,
H12): the v2 checks of scripts/verify/rules_v2_impact.py and R11 to R13 written from assumptions
A-R3, A-R4 and A-R11; every draft also states its expected line results by hand, and the two must
agree.

Outputs, in data/generated/verification/ (not committed):
- new_golden/rules_v2_cases.json: the drafted rules cases by target golden file;
- new_golden/e2e_v2_cases.json: E2E-17 and E2E-23 as they become, and the new E2E-32;
- G4_rules_v2_sheet.md: the blind sheet: inputs, the facts the rules read and the rule text,
  with blank result cells. They go into tests/golden/ only after the independent check.

    uv run python -m scripts.verify.new_rules_cases
"""

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.db import raw
from app.db.curated import CuratedData, billing_articles, load_curated
from scripts.verify.rules_v2_impact import CONFIDENCE_MIN, Hit, Lookups, low_confidence
from scripts.verify.rules_v2_impact import proposed as v2_checks

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "generated" / "verification"
STAGING = OUT_DIR / "new_golden"
RULES_FILE = STAGING / "rules_v2_cases.json"
E2E_FILE = STAGING / "e2e_v2_cases.json"
SHEET_FILE = OUT_DIR / "G4_rules_v2_sheet.md"
E2E_CASES = ROOT / "tests" / "golden" / "e2e" / "cases.json"
REFERENCE = ROOT / "tests" / "golden" / "rules" / "reference.json"

RULE_OF = {
    "DN_NCCI_BUNDLED": "R11",
    "DN_MUE_EXCEEDED": "R12",
    "DN_EXCLUDED": "R13",
    "DN_MULTIPLE_BLOCKS": "R14",
    "DN_DX_NOT_SUPPORTED": "R15",
    "DN_HOME_TEST_PARASOMNIA": "R16",
    "DN_ESI_LEVELS": "R18",
    "DN_FACET_LEVELS": "R19",
}
STATUS = {"PASS": "RECEIVED", "DENY": "DENIED_BY_RULE", "REJECT": "REJECTED"}
DOS, RECEIVED = "2026-10-06", "2026-10-20"
AUTH_WINDOW = ("2026-10-01", "2026-12-31")


@dataclass(frozen=True)
class L:
    """One service line: code, diagnosis pointers, modifiers, units, date of service."""

    code: str
    pointers: str = "A"
    modifiers: tuple[str, ...] = ()
    units: int = 1
    day: str = DOS
    charge: int = 50000


@dataclass(frozen=True)
class Draft:
    case_id: str
    file: str
    title: str
    rules: tuple[str, ...]
    npi: str
    diagnoses: tuple[str, ...]
    lines: tuple[L, ...]
    expect: tuple[str, ...]  # per line: "PASS", "PASS NCS_WITHOUT_EMG", "DENY DN_X DN_Y"
    steps: tuple[str, ...]
    sources: tuple[str, ...] = ()
    member: str = "MBR-G00001"  # PLN-PPO-GOLD
    confidences: Mapping[str, float] = field(default_factory=dict)
    expect_claim: str | None = None  # an H5 REJECT: the claim outcome


PAIN, PRIMARY, CARDIO, GI, RADIOLOGY = (
    "1000000020",
    "1000000012",
    "1000000079",
    "1000000061",
    "1000000038",
)
L33906 = "L33906 cov-027 (D-ESI-3)"
DRAFTS: tuple[Draft, ...] = (
    # --- R14: an ESI with another block on the same date (D-RULE-3) ---
    Draft(
        "R14-01",
        "R14_multiple_blocks.json",
        "Transforaminal ESI and a facet joint injection on the same date",
        ("R14",),
        PAIN,
        ("M5416", "M47816"),
        (L("64483", "A"), L("64493", "B")),
        ("DENY DN_MULTIPLE_BLOCKS", "PASS"),
        (
            "Line 1 64483 is an ESI (transforaminal, lumbar/sacral); line 2 64493 is a facet joint "
            "injection, another block, on the same date.",
            "No facet synovial cyst diagnosis on line 2 -> R14 denies the ESI line 1; the facet "
            "line 2 is not an ESI and passes.",
        ),
        (L33906,),
    ),
    Draft(
        "R14-02",
        "R14_multiple_blocks.json",
        "Near miss: the same ESI and facet injection on different dates",
        ("R14",),
        PAIN,
        ("M5416", "M47816"),
        (L("64483", "A"), L("64493", "B", day="2026-10-13")),
        ("PASS", "PASS"),
        ("Different dates of service: not the same session -> R14 does not apply.",),
        (L33906,),
    ),
    Draft(
        "R14-03",
        "R14_multiple_blocks.json",
        "Exception: the facet injection is for a facet synovial cyst",
        ("R14",),
        PAIN,
        ("M5416", "M7138"),
        (L("64483", "A"), L("64493", "B")),
        ("PASS", "PASS"),
        (
            "Line 2 64493 points at M7138, a facet synovial cyst code (FACET_SYNOVIAL_CYST) -> the "
            "LCD's exception; no other block remains -> line 1 passes.",
        ),
        (L33906,),
    ),
    Draft(
        "R14-04",
        "R14_multiple_blocks.json",
        "Near miss: a transforaminal ESI with its additional-level add-on",
        ("R14", "R18"),
        PAIN,
        ("M5416",),
        (L("64483"), L("64484")),
        ("PASS", "PASS"),
        (
            "64484 is an add-on level code, not another block -> R14 does not apply.",
            "R18: both lines count on both sides (no side modifier): 1 + 1 = 2 levels -> within "
            "the limit of 2.",
        ),
        (L33906, "L33906 cov-032"),
    ),
    Draft(
        "R14-05",
        "R14_multiple_blocks.json",
        "Same ESI code on two lines (right and left) is not another block",
        ("R12", "R14"),
        PAIN,
        ("M5416",),
        (L("64483", modifiers=("RT",)), L("64483", modifiers=("LT",))),
        ("DENY DN_MUE_EXCEEDED", "DENY DN_MUE_EXCEEDED"),
        (
            "R12: 64483 units on the date 1 + 1 = 2 > MUE 1 -> both lines denied (A-R4).",
            "R14: the same code on another line is bilateral use, not another block -> no "
            "DN_MULTIPLE_BLOCKS.",
            "Every line denied -> claim DENY.",
        ),
        (L33906,),
    ),
    Draft(
        "R14-06",
        "R14_multiple_blocks.json",
        "A denied ESI takes its add-on level with it",
        ("R14",),
        PAIN,
        ("M5416", "M47816"),
        (L("64483", "A"), L("64484", "A"), L("64493", "B")),
        ("DENY DN_MULTIPLE_BLOCKS", "DENY DN_MULTIPLE_BLOCKS", "PASS"),
        (
            "64493 is a facet joint injection on the same date as the ESI 64483 -> R14 denies "
            "line 1.",
            "Line 2 64484 is the add-on of the denied 64483 on that date -> denied with it, same "
            "reason (D-RULE-7). The facet line 3 passes.",
            "R18: 64483 + 64484 = 2 levels -> within the limit.",
        ),
        (L33906, "D-RULE-7"),
    ),
    # --- R15: the line's diagnoses against the billing article (D-RULE-4) ---
    Draft(
        "R15-01",
        "R15_diagnosis.json",
        "Stress echo with high blood pressure alone",
        ("R15",),
        CARDIO,
        ("I10",),
        (L("93350"),),
        ("DENY DN_DX_NOT_SUPPORTED",),
        (
            "93350 -> A56625 group 4; I10 is in groups 2 and 3 only -> not supported -> line 1 "
            "denied.",
            "Every line denied -> claim DENY.",
        ),
        ("A56625 group 4",),
    ),
    Draft(
        "R15-02",
        "R15_diagnosis.json",
        "Near miss: stress echo with coronary artery disease",
        ("R15",),
        CARDIO,
        ("I2510",),
        (L("93350"),),
        ("PASS",),
        ("I25.10 is in A56625 group 4 -> supported.",),
        ("A56625 group 4",),
    ),
    Draft(
        "R15-03",
        "R15_diagnosis.json",
        "Complex cataract surgery with a group 1 diagnosis only",
        ("R15",),
        PRIMARY,
        ("H2513",),
        (L("66982"),),
        ("PASS",),
        (
            "66982 -> A56544; R15 requires group 1 only (group 2 is reported 'if applicable', not "
            "checked; D-RULE-4); H25.13 is in group 1 -> supported.",
        ),
        ("A56544 groups 1 and 2",),
    ),
    Draft(
        "R15-04",
        "R15_diagnosis.json",
        "Colonoscopy with the group 2B code first",
        ("R15",),
        GI,
        ("S36500A", "S31609A"),
        (L("45385", "AB"),),
        ("DENY DN_DX_NOT_SUPPORTED",),
        (
            "45385 -> A56456: group 1, or a group 2A primary with a group 2B secondary; the "
            "line's first diagnosis S36500A is 2B, not 2A; no group 1 code -> not supported.",
        ),
        ("A56456 groups 2A and 2B",),
    ),
    Draft(
        "R15-05",
        "R15_diagnosis.json",
        "Near miss: colonoscopy with the group 2A code first",
        ("R15",),
        GI,
        ("S31609A", "S36500A"),
        (L("45385", "AB"),),
        ("PASS",),
        ("First diagnosis S31609A is 2A, a 2B code follows -> supported.",),
        ("A56456 groups 2A and 2B",),
    ),
    Draft(
        "R15-06",
        "R15_diagnosis.json",
        "Routine foot care: a group 2 diagnosis with modifier Q8",
        ("R15",),
        PRIMARY,
        ("E1151",),
        (L("11720", modifiers=("Q8",)),),
        ("PASS",),
        (
            "E11.51 is in A57188 group 2, which counts with Q7, Q8 or Q9; Q8 is billed -> "
            "supported.",
        ),
        ("A57188 group 2",),
    ),
    Draft(
        "R15-07",
        "R15_diagnosis.json",
        "Routine foot care: the same group 2 diagnosis without a class modifier",
        ("R15",),
        PRIMARY,
        ("E1151",),
        (L("11720"),),
        ("DENY DN_DX_NOT_SUPPORTED",),
        (
            "E11.51 is only in A57188 group 2; no Q7, Q8 or Q9 -> group 2 does not count -> not "
            "supported.",
        ),
        ("A57188 group 2",),
    ),
    # --- R16: home sleep test with parasomnia ---
    Draft(
        "R16-01",
        "R16_home_sleep_test.json",
        "Home sleep test for a parasomnia",
        ("R16",),
        PRIMARY,
        ("G4750",),
        (L("95806"),),
        ("DENY DN_HOME_TEST_PARASOMNIA",),
        (
            "95806 is a home sleep test; G47.50 is a parasomnia (G47.50-G47.59) -> R16 denies.",
            "R15 passes: G47.50 is in A56923 group 2.",
        ),
        ("L35050 cov-068",),
    ),
    Draft(
        "R16-02",
        "R16_home_sleep_test.json",
        "Near miss: an in-lab study for the same parasomnia",
        ("R16",),
        PRIMARY,
        ("G4750",),
        (L("95810"),),
        ("PASS",),
        ("95810 is not a home sleep test -> R16 does not apply.",),
        ("L35050 cov-068",),
    ),
    # --- R17: nerve conduction without needle EMG (a flag, D-RULE-2) ---
    Draft(
        "R17-01",
        "R17_nerve_conduction.json",
        "Nerve conduction alone for carpal tunnel",
        ("R17",),
        PRIMARY,
        ("G5601",),
        (L("95910"),),
        ("PASS NCS_WITHOUT_EMG",),
        (
            "No needle EMG line anywhere on the claim -> flag NCS_WITHOUT_EMG (the LCD says "
            "'usually', D-RULE-2); carpal tunnel included; no denial.",
        ),
        ("L34594 cov-037",),
    ),
    Draft(
        "R17-02",
        "R17_nerve_conduction.json",
        "Near miss: needle EMG on the claim, on another date",
        ("R17",),
        PRIMARY,
        ("G5601",),
        (L("95910"), L("95886", day="2026-10-08")),
        ("PASS", "PASS"),
        ("A needle EMG line (95886) is on the claim; any date counts -> no flag.",),
        ("L34594 cov-037",),
    ),
    # --- R18: ESI levels ---
    Draft(
        "R18-01",
        "R18_esi_levels.json",
        "Interlaminar ESI billed bilaterally",
        ("R18",),
        PAIN,
        ("M5416",),
        (L("62323", modifiers=("50",)),),
        ("DENY DN_ESI_LEVELS",),
        ("62323 is an interlaminar or caudal ESI with modifier 50 -> denied (never bilateral).",),
        ("L33906 cov-034",),
    ),
    Draft(
        "R18-02",
        "R18_esi_levels.json",
        "Near miss: the same interlaminar ESI, one side",
        ("R18",),
        PAIN,
        ("M5416",),
        (L("62323"),),
        ("PASS",),
        ("No modifier 50 -> passes.",),
        ("L33906 cov-034",),
    ),
    Draft(
        "R18-03",
        "R18_esi_levels.json",
        "Transforaminal ESI at three levels on the right",
        ("R18",),
        PAIN,
        ("M5416",),
        (L("64483", modifiers=("RT",)), L("64484", modifiers=("RT",), units=2)),
        ("PASS", "DENY DN_ESI_LEVELS"),
        (
            "Right side: 64483 1 + 64484 2 = 3 levels > 2; left side: 0 -> the add-on line on the "
            "right (line 2) is denied; the primary line 1 passes.",
        ),
        ("L33906 cov-032",),
    ),
    Draft(
        "R18-04",
        "R18_esi_levels.json",
        "Bilateral first level, second level on each side",
        ("R18",),
        PAIN,
        ("M5416",),
        (
            L("64483", modifiers=("50",)),
            L("64484", modifiers=("RT",)),
            L("64484", modifiers=("LT",)),
        ),
        ("PASS", "PASS", "PASS"),
        (
            "R18 per side: 64483-50 counts on both sides; right 1 + 64484-RT 1 = 2, left 1 + "
            "64484-LT 1 = 2 -> within 2 on each side, nothing denied (a plain sum of units, 3, "
            "would deny).",
            "R12: 64483 1 unit <= MUE 1; 64484 1 + 1 = 2 units <= MUE 4.",
        ),
        ("L33906 cov-032",),
    ),
    Draft(
        "R18-05",
        "R18_esi_levels.json",
        "Bilateral two levels billed with modifier 50",
        ("R18",),
        PAIN,
        ("M5416",),
        (L("64483", modifiers=("50",)), L("64484", modifiers=("50",))),
        ("PASS", "PASS"),
        (
            "Modifier 50 counts on both sides: right 1 + 1 = 2, left 2 -> within 2.",
            "R12: 64483 1 unit <= MUE 1.",
        ),
        ("L33906 cov-032",),
    ),
    # --- R19: facet levels and regions ---
    Draft(
        "R19-01",
        "R19_facet_levels.json",
        "Facet joint injections at a third level",
        ("R19",),
        PAIN,
        ("M47816",),
        (L("64493"), L("64494"), L("64495")),
        ("PASS", "PASS", "DENY DN_FACET_LEVELS"),
        ("64495 is a third-level facet code (A57787: non-covered) -> line 3 denied.",),
        ("L33930 cov-053", "A57787 CPT group 2"),
    ),
    Draft(
        "R19-02",
        "R19_facet_levels.json",
        "Near miss: facet joint injections at two levels",
        ("R19",),
        PAIN,
        ("M47816",),
        (L("64493"), L("64494")),
        ("PASS", "PASS"),
        ("Two levels -> allowed.",),
        ("L33930 cov-053",),
    ),
    Draft(
        "R19-03",
        "R19_facet_levels.json",
        "Facet injections in two spinal regions on one date",
        ("R19",),
        PAIN,
        ("M47812", "M47816"),
        (L("64490", "A"), L("64493", "B")),
        ("PASS FACET_TWO_REGIONS", "PASS FACET_TWO_REGIONS"),
        (
            "64490 is cervical/thoracic, 64493 lumbar/sacral, same date -> both lines pass with "
            "the flag FACET_TWO_REGIONS (which region is wrong is not on the claim, D-RULE-2).",
        ),
        ("L33930 cov-050",),
    ),
    # --- R20: testing time ---
    Draft(
        "R20-01",
        "R20_testing_time.json",
        "Psychological testing over 8 hours",
        ("R20",),
        PRIMARY,
        ("G3184",),
        (L("96130"), L("96131", units=7), L("96136")),
        ("PASS EXTENDED_TESTING", "PASS EXTENDED_TESTING", "PASS EXTENDED_TESTING"),
        (
            "Minutes: 96130 60 + 96131 7 x 60 + 96136 30 = 510 > 480 -> every testing line passes "
            "with the flag EXTENDED_TESTING.",
            "R12: 96131 7 units <= MUE 7.",
        ),
        ("L34520 cov-046",),
    ),
    Draft(
        "R20-02",
        "R20_testing_time.json",
        "Near miss: exactly 8 hours",
        ("R20",),
        PRIMARY,
        ("G3184",),
        (L("96130"), L("96131", units=7)),
        ("PASS", "PASS"),
        ("Minutes: 60 + 420 = 480, not more than 8 hours -> no flag.",),
        ("L34520 cov-046",),
    ),
    # --- Combinations, regressions, H5 ---
    Draft(
        "X-03",
        "group_c_combinations.json",
        "Two ESI codes on one date: a line fails R11 and R14",
        ("R11", "R14"),
        PAIN,
        ("M5416",),
        (L("62323"), L("64483")),
        ("DENY DN_MULTIPLE_BLOCKS", "DENY DN_NCCI_BUNDLED DN_MULTIPLE_BLOCKS"),
        (
            "R11: NCCI 62323/64483 (modifier indicator 1), no bypass modifier -> column-2 line 2 "
            "denied.",
            "R14: each ESI line has another ESI code on the date -> both lines denied.",
            "Line 2 lists DN_NCCI_BUNDLED then DN_MULTIPLE_BLOCKS (rule order; the first is "
            "primary). Every line denied -> claim DENY.",
        ),
        (L33906,),
    ),
    Draft(
        "X-04",
        "group_c_combinations.json",
        "Regression: head CT and cervical spine MRI on the same date",
        ("R11", "R12"),
        RADIOLOGY,
        ("R519", "M5412"),
        (L("70450", "A"), L("72141", "B")),
        ("PASS", "PASS"),
        (
            "Different body areas; no NCCI edit pairs them and no rule v2 limits imaging -> "
            "both pass.",
        ),
        ("L37373 cov-042 (IMG-001.F2)",),
    ),
    Draft(
        "X-05",
        "group_c_combinations.json",
        "Regression: vein ablation and stab phlebectomy on the same date",
        ("R11",),
        PRIMARY,
        ("I83811",),
        (L("36478", modifiers=("RT",)), L("37765", modifiers=("RT",))),
        ("PASS", "PASS"),
        ("No NCCI edit pairs 36478 and 37765, and no rule v2 limits them -> both pass.",),
        ("L34209 cov-028 (SURG-003.F4)",),
    ),
    Draft(
        "H5-08",
        "h5_low_confidence.json",
        "Diagnosis read below the threshold fails R15",
        ("R15",),
        CARDIO,
        ("I10",),
        (L("93350"),),
        ("DENY DN_DX_NOT_SUPPORTED",),
        (
            "R15 would deny line 1 (I10 not in A56625 group 4), but diagnoses.0 was read with "
            "confidence 0.60 < 0.85 -> REJECT RJ_LOW_CONFIDENCE_FIELD, never DENY (H5).",
        ),
        ("H5",),
        confidences={"diagnoses.0": 0.60},
        expect_claim="REJECT",
    ),
)


# --- Independent computation ---------------------------------------------------------------------


@dataclass(frozen=True)
class V1Tables:
    ncci: Mapping[tuple[str, str], Sequence[Any]]
    mue: Mapping[str, int]
    bypass: frozenset[str]


def v1_line_results(
    claim: Mapping[str, Any], tables: V1Tables, excluded: frozenset[str]
) -> list[list[str]]:
    """R11 to R13 from A-R3 (same date, first active edit, indicator 1 with a bypass modifier
    passes), A-R4 (units of a code on a date against MUE; every line of it) and the exclusions."""
    lines = claim["service_lines"]
    reasons: list[list[str]] = [[] for _ in lines]
    for i, a in enumerate(lines):
        for j, b in enumerate(lines):
            if i == j or a["date_of_service"] != b["date_of_service"]:
                continue
            day = date.fromisoformat(a["date_of_service"])
            edits = tables.ncci.get((a["procedure_code"], b["procedure_code"]), ())
            indicator = next((e.modifier_indicator for e in edits if e.active_on(day)), None)
            if indicator in (None, "9"):
                continue
            bypass = tables.bypass & {*a["modifiers"], *b["modifiers"]}
            if not (indicator == "1" and bypass) and "DN_NCCI_BUNDLED" not in reasons[j]:
                reasons[j].append("DN_NCCI_BUNDLED")
    for i, a in enumerate(lines):
        limit = tables.mue.get(a["procedure_code"])
        units = sum(
            b["units"]
            for b in lines
            if (b["procedure_code"], b["date_of_service"])
            == (a["procedure_code"], a["date_of_service"])
        )
        if limit is not None and units > limit:
            reasons[i].append("DN_MUE_EXCEEDED")
        if a["procedure_code"] in excluded:
            reasons[i].append("DN_EXCLUDED")
    return reasons


def line_results(
    claim: Mapping[str, Any], tables: V1Tables, excluded: frozenset[str], lookups: Lookups
) -> tuple[list[tuple[str, list[str], list[str]]], list[Hit]]:
    v1 = v1_line_results(claim, tables, excluded)
    hits = v2_checks(claim, lookups)
    out = []
    for i, line in enumerate(claim["service_lines"]):
        mine = [h for h in hits if h.line_no == line["line_no"]]
        reasons = v1[i] + [h.reason for h in mine if h.outcome == "DENY"]
        flags = [h.reason for h in mine if h.outcome == "FLAG"]
        out.append(("DENY" if reasons else "PASS", reasons, flags))
    return out, hits


def expected_for(
    draft: Draft, claim: Mapping[str, Any], tables: V1Tables, curated: CuratedData, lookups: Lookups
) -> dict[str, Any]:
    plan = next(m["plan_id"] for m in reference()["members"] if m["member_id"] == draft.member)
    results, hits = line_results(claim, tables, curated.excluded_codes(plan), lookups)
    stated = [(x.split()[0], x.split()[1:]) for x in draft.expect]
    computed = [(o, [*r, *f]) for o, r, f in results]
    if stated != computed:
        raise SystemExit(f"{draft.case_id}: stated {stated} != computed {computed}")
    low = [h for h in hits if h.outcome == "DENY" and low_confidence(h, draft.confidences)]
    if low or draft.expect_claim == "REJECT":
        if not low or draft.expect_claim != "REJECT":
            raise SystemExit(f"{draft.case_id}: H5 stated {draft.expect_claim}, computed {low}")
        failures = [
            {"rule_id": h.rule, "outcome": "REJECT", "reason_code": "RJ_LOW_CONFIDENCE_FIELD"}
            | {"line_no": h.line_no}
            for h in low
        ]
        return {
            "claim_outcome": "REJECT",
            "status": "REJECTED",
            "failures": failures,
            "line_outcomes": None,
            "flags": [],
        }
    outcome = "DENY" if all(o == "DENY" for o, _, _ in results) else "PASS"
    return {
        "claim_outcome": outcome,
        "status": STATUS[outcome],
        "failures": [
            {"rule_id": RULE_OF[r], "outcome": "DENY", "reason_code": r, "line_no": n}
            for n, (_, reasons, _) in enumerate(results, start=1)
            for r in reasons
        ],
        "line_outcomes": [
            {"line_no": n, "outcome": o, "reason_codes": r, "flags": f}
            for n, (o, r, f) in enumerate(results, start=1)
        ],
        "flags": [],
    }


# --- Building the cases ----------------------------------------------------------------------


def reference() -> dict[str, Any]:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def claim_for(draft: Draft) -> dict[str, Any]:
    return {
        "claim_id": f"GR-{draft.case_id}",
        "member_id": draft.member,
        "patient": {
            "first_name": "Jordan",
            "last_name": "Lee",
            "date_of_birth": "1970-05-14",
            "sex": "F",
            "address": {"line1": "12 Elm St", "city": "Austin", "state": "TX", "zip_code": "78701"},
        },
        "subscriber_is_patient": True,
        "billing_npi": draft.npi,
        "billing_tin": "080000009",
        "referring_npi": None,
        "prior_auth_number": None,
        "diagnoses": list(draft.diagnoses),
        "service_lines": [
            {
                "line_no": n,
                "date_of_service": line.day,
                "place_of_service": "11",
                "procedure_code": line.code,
                "modifiers": list(line.modifiers),
                "diagnosis_pointers": list(line.pointers),
                "units": line.units,
                "charge_cents": line.charge,
                "rendering_npi": draft.npi,
            }
            for n, line in enumerate(draft.lines, start=1)
        ],
        "clinical_notes": "",
        "received_date": RECEIVED,
        "frequency_code": "1",
        "other_coverage": None,
    }


def authorizations(draft: Draft, curated: CuratedData) -> list[dict[str, Any]]:
    """One authorization per in-scope code that needs one on the member's plan (R10 passes)."""
    plan = next(m["plan_id"] for m in reference()["members"] if m["member_id"] == draft.member)
    codes = sorted(
        {
            x.code
            for x in draft.lines
            if x.code in curated.scope and curated.auth_required(plan, x.code)
        }
    )
    return [
        {
            "auth_number": f"AUTH-{draft.case_id}-{k}",
            "member_id": draft.member,
            "provider_npi": draft.npi,
            "procedure_code": code,
            "start_date": AUTH_WINDOW[0],
            "end_date": AUTH_WINDOW[1],
            "units_approved": None,
        }
        for k, code in enumerate(codes, start=1)
    ]


def build_case(draft: Draft, tables: V1Tables, curated: CuratedData, lookups: Lookups) -> dict:
    claim = claim_for(draft)
    auths = authorizations(draft, curated)
    return {
        "case_id": draft.case_id,
        "title": draft.title,
        "rules": list(draft.rules),
        "given": {
            "claim": claim,
            "source_format": "SCANNED" if draft.confidences else "JSON",
            "field_confidences": dict(draft.confidences),
            "reference_additions": {"authorizations": auths} if auths else {},
        },
        "expected": expected_for(draft, claim, tables, curated, lookups),
        "worked_steps": [
            *(
                f"R10: authorization {a['auth_number']} covers {a['procedure_code']}."
                for a in auths
            ),
            *draft.steps,
        ],
        "sources": list(draft.sources),
    }


# --- End-to-end changes (D-GOLD-6) ----------------------------------------------------------------

RULE_NOTE = "Rule outcomes are final and never reach review (§8.8)."
E2E_32_NOTES = (
    "Known coronary artery disease, followed yearly. Blood pressure is high, but there are no "
    "heart symptoms and the heart exam is normal. A treadmill stress test last month did not give "
    "a clear answer. Current medications were reviewed and updated. The patient returns after "
    "atrial fibrillation treatment. Monitoring is to look for a return of the irregular rhythm 11 "
    "weeks after a catheter ablation. The episodes happen only about once every 10 days, too "
    "rarely to catch on a 48-hour recording. Plan: heart ultrasound during an exercise or drug "
    "stress test; wearable heart rhythm recording for 2 to 7 days, with analysis and report."
)


def e2e_cases() -> dict[str, dict[str, Any]]:
    cases = {c["case_id"]: c for c in json.loads(E2E_CASES.read_text(encoding="utf-8"))["cases"]}
    r15 = {"rule_id": "R15", "outcome": "DENY", "reason_code": "DN_DX_NOT_SUPPORTED"}

    e17 = copy.deepcopy(cases["E2E-17"])
    e17["given"]["model_answer"] = None
    e17["given"]["review_action"] = None
    e17["expected"] = {
        "rules": {"claim_outcome": "DENY", "failures": [r15 | {"line_no": 1}]},
        "status_after_processing": "DENIED_BY_RULE",
        "recommendation": None,
        "final": {"status": "DENIED_BY_RULE", "note": RULE_NOTE},
    }
    e17["worked_steps"] = [
        e17["worked_steps"][0],
        "Rules: R15: 15822 -> A56439 groups 1 or 2; F41.9 is in neither -> line 1 DENY "
        "DN_DX_NOT_SUPPORTED.",
        "Every line denied by Group C -> claim DENY (DENIED_BY_RULE); the model is not called "
        "and the claim never reaches review.",
    ]

    e23 = copy.deepcopy(cases["E2E-23"])
    e23["given"]["model_answer"]["lines"] = [
        line for line in e23["given"]["model_answer"]["lines"] if line["line_no"] != 1
    ]
    rules = e23["expected"]["rules"]
    rules["failures"] = [r15 | {"line_no": 1}]
    rules["line_outcomes"][0] = {
        "line_no": 1,
        "outcome": "DENY",
        "reason_codes": ["DN_DX_NOT_SUPPORTED"],
        "flags": [],
    }
    rule_line = {
        "line_no": 1,
        "decision": "DENY",
        "source": "RULE",
        "reason_codes": ["DN_DX_NOT_SUPPORTED"],
    }
    e23["expected"]["recommendation"]["line_decisions"][0] = rule_line
    e23["expected"]["final"]["line_decisions"][0] = rule_line
    steps = e23["worked_steps"]
    steps[1] = (
        "Rules: R15: 93350 -> A56625 group 4; I10 is in groups 2 and 3 only -> line 1 DENY "
        "DN_DX_NOT_SUPPORTED; line 2 PASS -> claim continues with line 2."
    )
    steps[2] = (
        "Model answer (stub) validates: line 2 APPROVE DIAGNOSTIC_TESTS; complexity HIGH (the "
        "line decisions differ, the rule-denied line counting as DENY)."
    )
    steps[next(i for i, s in enumerate(steps) if s.startswith("Claim decision"))] = (
        "Claim decision (derived) PARTIAL (line 1 DENY by rule, line 2 APPROVE); review tier: "
        "model line decisions ['APPROVE'], complexity HIGH -> FULL (HIGH complexity)."
    )

    e32 = copy.deepcopy(cases["E2E-23"])
    e32["case_id"] = "E2E-32"
    e32["title"] = "Two policies: one approved, one denied by the model"
    claim = e32["given"]["claim"]
    claim["claim_id"] = "CLM-E2E-32"
    claim["diagnoses"] = ["I2510" if d == "I10" else d for d in claim["diagnoses"]]
    claim["clinical_notes"] = E2E_32_NOTES
    answer_line = e32["given"]["model_answer"]["lines"][0]
    for criterion in answer_line["criteria"]:
        if criterion["criterion_id"] == "POL-CAR-001.c3":
            criterion["evidence"] = (
                "A treadmill stress test last month did not give a clear answer."
            )
    e32["given"]["review_action"]["claim_id"] = "CLM-E2E-32"
    e32["worked_steps"] = [
        step.replace("CLM-E2E-23", "CLM-E2E-32") for step in cases["E2E-23"]["worked_steps"]
    ]
    e32["worked_steps"][1] = (
        "Rules: R15: 93350 -> A56625 group 4; I25.10 is in group 4 -> line 1 PASS; line 2 PASS "
        "-> claim continues to context assembly."
    )
    return {"E2E-17": e17, "E2E-23": e23, "E2E-32": e32}


# --- The blind sheet ---------------------------------------------------------------------------

RULE_TEXT = """\
Group C runs on every line of a claim that passed Groups A and B. Every rule is evaluated on every
line; a line's reason codes and flags are listed in rule order (R11, R12, R13, then R14 to R20) and
the first reason code is the primary one. A line with any reason code is denied; a line with only
flags passes. When every line is denied, the claim is DENY; otherwise PASS. A flag never denies.
D-RULE-2: a rule denies only when the LCD or article is explicit and the check needs nothing beyond
the claim; limits worded "usually"/"rarely" or with a documented exception give a flag.

- R11 (A-R3): for two lines on the same date, the first NCCI edit active that day with line A's
  code in column 1 and line B's in column 2 applies (indicator 9: none). Indicator 1 with a bypass
  modifier (XE, XP, XS, XU) on either line: line B passes with the flag NCCI_BYPASS; otherwise
  line B is denied, DN_NCCI_BUNDLED.
- R12 (A-R4): the units of one code on one date, added over the lines, above the MUE limit deny
  every line of that code and date, DN_MUE_EXCEEDED.
- R13: a code on the plan's exclusion list is denied, DN_EXCLUDED.
- R14 (L33906): an ESI line (62321, 62323, 64479, 64483) is denied, DN_MULTIPLE_BLOCKS, when another
  block is billed on the same date: a different ESI code, or a facet joint injection (64490,
  64493). Not other blocks: add-on level codes (64480, 64484, 64491, 64494), radiofrequency
  denervation (64633-64636), the same code on another line. Exception: a facet injection whose own
  diagnoses include a facet synovial cyst code (M71.30, M71.38) is not a block. Only ESI lines are
  denied; when two ESI codes meet, both are. Every billed line counts, even one another rule denies.
  A denied ESI's own add-on lines on the same date (64480 with 64479, 64484 with 64483) are denied
  with it, DN_MULTIPLE_BLOCKS (D-RULE-7).
- R15 (billing articles): a line's own diagnoses (its pointers) must meet one of its code's
  alternatives; codes with no article are not checked. A group is met when one of the line's
  diagnoses is in it. 66982: group 1 only. Colonoscopy (45378, 45380, 45385): group 1, or the line's
  first diagnosis in group 2A with a group 2B code among the others. Foot care (11720, 11721):
  groups 1, 3 or 4, or group 2 when modifier Q7, Q8 or Q9 is billed. Fails: DN_DX_NOT_SUPPORTED.
- R16 (L35050): a home sleep test line (95800, 95801, 95806, G0398-G0400) with a parasomnia
  diagnosis (G47.50-G47.59) among its own is denied, DN_HOME_TEST_PARASOMNIA.
- R17 (L34594, "usually"): every nerve conduction line (95907-95913) with no needle EMG line
  (95860-95870, 95872, 95885-95887) anywhere on the claim gets the flag NCS_WITHOUT_EMG; carpal
  tunnel included; never a denial.
- R18 (L33906): transforaminal levels per date and region (64483 + add-on 64484; 64479 + 64480),
  counted per side: an RT or LT line counts on its side; modifier 50 or no side modifier on both
  sides. If either side has more than 2 levels, the add-on lines counting on that side are denied,
  DN_ESI_LEVELS. An interlaminar or caudal ESI (62321, 62323) with modifier 50 is denied,
  DN_ESI_LEVELS.
- R19 (L33930, A57787): a third-level facet code (64492, 64495) is denied, DN_FACET_LEVELS. Facet
  codes of both regions on one date (cervical/thoracic 64490-64492, 64633-64634; lumbar/sacral
  64493-64495, 64635-64636) give every facet line that date the flag FACET_TWO_REGIONS.
- R20 (L34520): testing minutes on the claim from 96130 (60 per unit), 96131 (60) and 96136 (30);
  above 480, every testing line gets the flag EXTENDED_TESTING.
- H5: a failing rule whose fields include a field read below 0.85 becomes REJECT
  RJ_LOW_CONFIDENCE_FIELD, never DENY; the claim is then REJECT with no line outcomes. R15 reads
  the line's code, pointers and pointed diagnoses."""


def lettered(diagnoses: Sequence[str]) -> str:
    return ", ".join(f"{chr(65 + i)} {d}" for i, d in enumerate(diagnoses))


def facts(case: Mapping[str, Any], tables: V1Tables, lookups: Lookups) -> list[str]:
    claim = case["given"]["claim"]
    out = []
    codes = [line["procedure_code"] for line in claim["service_lines"]]
    for a in sorted(set(codes)):
        for b in sorted(set(codes)):
            day = date.fromisoformat(claim["service_lines"][0]["date_of_service"])
            active = [e for e in tables.ncci.get((a, b), ()) if e.active_on(day)]
            if a != b and active:
                out.append(f"NCCI {a}/{b}: modifier indicator {active[0].modifier_indicator}")
    out += [f"MUE {c}: {tables.mue[c]}" for c in sorted(set(codes)) if c in tables.mue]
    for code in sorted(set(codes)):
        support = lookups.curated.diagnosis_support.get(code)
        if support is None:
            out.append(f"{code}: no billing article (R15 does not check it)")
            continue
        groups = lookups.covered.get(support.billing_article, {})
        needs = " or ".join(
            " + ".join(f"group {g}" for g in alternative)
            for alternative in support.rule_alternatives
        )
        out.append(f"R15 for {code} ({support.billing_article}): {needs}")
        for dx in claim["diagnoses"]:
            found = sorted(g for g, s in groups.items() if dx in s)
            out.append(f"{code} -> {support.billing_article}: {dx} in groups {found or 'none'}")
    return out


def build_sheet(
    rules_cases: Sequence[Mapping[str, Any]], tables: V1Tables, lookups: Lookups
) -> str:
    out = [
        "# Rules v2 golden cases: independent check (Task G4)",
        "",
        "For one reviewer, or a separate Claude chat that sees only this sheet (D-GOLD-2). Work "
        "out each case from the inputs, the facts and the rule text below, then fill in the "
        "blank cells. **Do not open data/generated/verification/new_golden/ until every cell is "
        "filled.**",
        "",
        "Every claim below passes Groups A and B (eligibility, provider, filing, network, "
        "referral and authorization are in order); only Group C decides.",
        "",
        "## Rule text (D-RULE-2 to D-RULE-4, D-RULE-7)",
        "",
        RULE_TEXT,
        "",
        "Article groups: A56456 group 2 is 2A and group 3 is 2B.",
        "",
        "## Rules cases",
    ]
    for n, case in enumerate(rules_cases, start=1):
        claim = case["given"]["claim"]
        out += ["", f"### Case {n} ({case['case_id']})", ""]
        if case["given"]["field_confidences"]:
            shown = ", ".join(f"{k} {v:.2f}" for k, v in case["given"]["field_confidences"].items())
            out += [f"Read with confidence: {shown}.", ""]
        out += [
            f"Diagnoses: {lettered(claim['diagnoses'])}",
            "",
            "| Line | Date | Code | Units | Modifiers | Pointers |",
            "|---|---|---|---|---|---|",
        ]
        out += [
            f"| {s['line_no']} | {s['date_of_service']} | {s['procedure_code']} | {s['units']} | "
            f"{' '.join(s['modifiers']) or '-'} | {''.join(s['diagnosis_pointers'])} |"
            for s in claim["service_lines"]
        ]
        out += ["", "Facts: " + "; ".join(facts(case, tables, lookups)) + ".", ""]
        out += [
            "Claim outcome (PASS / DENY / REJECT): ____",
            "",
            "| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |",
            "|---|---|---|---|",
        ]
        out += [f"| {s['line_no']} |  |  |  |" for s in claim["service_lines"]]
    out += [
        "",
        "## End-to-end cases",
        "",
        "For each: the rules result, then the line decisions (source RULE for a rule denial, "
        "MODEL for the model's), the claim decision (any PEND -> PEND; all DENY -> DENY; all "
        "APPROVE -> APPROVE; otherwise PARTIAL) and the review tier (FULL when the model output is "
        "invalid, any model line is DENY, or the complexity is HIGH; STANDARD for a PEND, MEDIUM "
        "complexity, a high-dollar or low-confidence claim; QUICK otherwise). Complexity is HIGH "
        "when the line decisions differ, rule-denied lines counting as DENY. A rule-denied claim "
        "never reaches the model or review.",
    ]
    return "\n".join(out) + "\n"


def e2e_sheet(cases: Mapping[str, Mapping[str, Any]], tables: V1Tables, lookups: Lookups) -> str:
    out = []
    for case_id, case in cases.items():
        claim = case["given"]["claim"]
        answer = case["given"].get("model_answer") or {}
        decided = {
            line["line_no"]: f"{line['decision']} ({', '.join(line['reasons']) or 'no reason'})"
            for line in answer.get("lines", [])
        }
        out += ["", f"### {case_id}", ""]
        out += [
            f"Diagnoses: {lettered(claim['diagnoses'])}",
            "",
            "| Line | Code | Pointers | The model's answer if the line reaches it |",
            "|---|---|---|---|",
        ]
        out += [
            f"| {s['line_no']} | {s['procedure_code']} | {''.join(s['diagnosis_pointers'])} | "
            f"{decided.get(s['line_no'], 'no model answer for this line')} |"
            for s in claim["service_lines"]
        ]
        if answer:
            out += ["", f"Model complexity: {answer.get('complexity')}."]
        if case_id == "E2E-32":
            out += [
                "",
                "E2E-32 is a new case. Its amounts and accumulators equal E2E-23's already "
                "verified values (same plan, member, fees and approved line); only the rule "
                "outcome and the decisions are asked here.",
            ]
        out += ["", "Facts: " + "; ".join(facts(case, tables, lookups)) + ".", ""]
        out += [
            "Rules claim outcome: ____ | Status after processing: ____",
            "",
            "| Line | Decision | Source | Reason codes |",
            "|---|---|---|---|",
            *(f"| {s['line_no']} |  |  |  |" for s in claim["service_lines"]),
            "",
            "Claim decision: ____ | Review tier: ____ | Final status after ACCEPT (or N/A): ____",
        ]
    return "\n".join(out) + "\n"


V2_REASONS = {r for r, rule in RULE_OF.items() if rule not in ("R11", "R12", "R13")}
V1_FLAGS = {"NCCI_BYPASS"}


def check_inputs_with_the_v1_engine(cases: Sequence[Mapping[str, Any]]) -> None:
    """Every drafted claim passes Groups A and B on the current (v1) engine, and its R11 to R13
    results equal the drafted ones without the v2 reason codes and flags: the inputs test what
    they are meant to (a sanity check of the inputs, not of the v2 expected values)."""
    from app.db.rules_reference import build_reference, load_code_tables
    from app.rules.engine import evaluate

    shared = reference()
    tables = load_code_tables(frozenset(load_curated().scope))
    for case in cases:
        given = case["given"]
        additions = given["reference_additions"]
        ref = build_reference(
            load_curated(),
            tables,
            shared["members"],
            shared["providers"],
            shared["provider_networks"],
            [*shared["authorizations"], *additions.get("authorizations", [])],
            shared["existing_claims"],
        )
        outcome = evaluate(given["claim"], {}, ref, confidence_min=CONFIDENCE_MIN)
        groups_ab = [r for r in outcome.rule_results if not r.passed and r.line_no is None]
        if groups_ab or len(outcome.line_outcomes) != len(given["claim"]["service_lines"]):
            raise SystemExit(f"{case['case_id']}: stops before Group C: {groups_ab}")
        drafted = case["expected"]["line_outcomes"] or [
            {"reason_codes": [], "flags": []} for _ in outcome.line_outcomes
        ]
        for mine, line in zip(drafted, outcome.line_outcomes, strict=True):
            v1_reasons = [r for r in mine["reason_codes"] if r not in V2_REASONS]
            v1_flags = [f for f in mine["flags"] if f in V1_FLAGS]
            if (line.reason_codes, line.flags) != (v1_reasons, v1_flags):
                raise SystemExit(f"{case['case_id']} line {line.line_no}: v1 engine differs")


def full_tables(curated: CuratedData) -> V1Tables:
    """NCCI edits and MUE limits for every code the drafts and end-to-end cases bill, from the full
    tables in data/raw/ (as the database reference reads them), in published order."""
    codes = {x.code for d in DRAFTS for x in d.lines}
    codes |= {
        line["procedure_code"]
        for case in json.loads(E2E_CASES.read_text(encoding="utf-8"))["cases"]
        for line in case["given"]["claim"].get("service_lines") or []
        if isinstance(line, dict) and isinstance(line.get("procedure_code"), str)
    }
    ncci: dict[tuple[str, str], list[Any]] = {}
    for pair in raw.read_ncci_pairs(codes):
        ncci.setdefault((pair.column1, pair.column2), []).append(pair)
    mue = {code: entry.max_units for code, entry in raw.read_mue(codes).items()}
    return V1Tables(ncci, mue, curated.bypass_modifiers)


def main() -> None:
    if not raw.raw_available():
        raise SystemExit("data/raw/ is required (see SOURCES.md)")
    curated = load_curated()
    tables = full_tables(curated)
    articles = raw.read_article_diagnoses(billing_articles(curated))
    lookups = Lookups(curated, {a: d.covered for a, d in articles.items()})
    rules_cases = [build_case(d, tables, curated, lookups) for d in DRAFTS]
    by_file: dict[str, list[dict[str, Any]]] = {}
    for draft, case in zip(DRAFTS, rules_cases, strict=True):
        by_file.setdefault(draft.file, []).append(case)
    check_inputs_with_the_v1_engine(rules_cases)
    e2e = e2e_cases()
    STAGING.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(by_file, indent=2) + "\n", encoding="utf-8")
    E2E_FILE.write_text(json.dumps(e2e, indent=2) + "\n", encoding="utf-8")
    SHEET_FILE.write_text(
        build_sheet(rules_cases, tables, lookups) + e2e_sheet(e2e, tables, lookups),
        encoding="utf-8",
    )
    print(f"{len(rules_cases)} rules cases in {len(by_file)} files; {len(e2e)} end-to-end cases")
    print(f"wrote {RULES_FILE.relative_to(ROOT)}, {E2E_FILE.relative_to(ROOT)}, ")
    print(f"      {SHEET_FILE.relative_to(ROOT)}")
    print("every drafted claim passes Groups A and B and matches R11 to R13 on the v1 engine")


if __name__ == "__main__":
    main()
