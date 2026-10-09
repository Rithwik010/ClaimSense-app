"""Policies v2, checkpoint 1: the author triage of the 22 pass 2 rows of the review sheet.

Author triage by Claude Code, the author of the criteria (2026-10-09): not an independent check.
For each of the 17 rows pass 1 flagged and the 5 random MATCHES rows, one category, a proposed
action (fix or keep), a one-line reason, and for a fix the old and new text (or code list or
source line) with the excerpt words that justify it. The reviewer decides each row; the decisions
go into the sheet's pass 2 columns, recorded as "author triage by Claude Code, decided by
Manideep". Nothing in the policy files changes here.

Every quoted excerpt is checked word for word against its LCD block or manual section in
data/raw (the resolver of scripts/verify/policies_v2_sources.py); the old texts, code lists and
source lines are read from the v2 policy files, never typed.

    uv run python -m scripts.verify.policies_v2_triage write    # the triage file; notes the sheet
    uv run python -m scripts.verify.policies_v2_triage decide   # the reviewer's pass 2 decisions:
    # recorded in the sheet's pass 2 columns, approved fixes applied to the v2 policy files, and
    # any criterion the fixes add appended to the sheet as a new Part A row
"""

import argparse
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from scripts.verify import policy_sources as ps
from scripts.verify.policies_v2_sources import (
    SHEET,
    V2_DIR,
    V2Criterion,
    ama_hits,
    bpm_sections,
    lcds_cited,
    read_v1,
    read_v2,
    row_block,
)
from scripts.verify.policies_v2_sources import (
    check as check_sources,
)

OUT = SHEET.parent / "P2_policies_v2_triage.md"
CATEGORIES = (
    "LIMITING CHANGE",
    "ADDED",
    "MISSING LIMIT",
    "MISSING EXAMPLE",
    "REWORDING",
    "TYPE",
    "OK",
)
FIXED = {"LIMITING CHANGE", "ADDED", "MISSING LIMIT", "TYPE"}
PASS2_BY = (
    "author triage by Claude Code, decided by Manideep with recommendations from the planning chat"
)
PASS2_NOTE = (
    "Pass 2 (2026-10-09): the 22 triaged rows hold the reviewer's decisions on the author "
    f"triage ({PASS2_BY}). Approved fixes are applied to the v2 files; the texts above are the "
    "ones reviewed, and the triage file shows old and new."
)
TRIAGE_NOTE = (
    "Author triage (2026-10-09): Claude Code, the author of the criteria, triaged the 22 pass 2 "
    "rows in P2_policies_v2_triage.md; not an independent check. The pass 2 columns hold the "
    "reviewer's decisions, recorded as 'author triage by Claude Code, decided by Manideep'."
)


@dataclass(frozen=True)
class Entry:
    row: str
    criterion: str
    category: str
    reason: str
    quotes: tuple[tuple[str, str], ...]  # (block or "§290.X", words that appear in it)
    new_text: str | None = None
    new_applies: tuple[str, ...] | None = None
    new_source: str | None = None
    new_criteria: tuple[dict[str, str], ...] = field(default=())  # an added criterion

    @property
    def action(self) -> str:
        return "fix" if self.category in FIXED else "keep"


TRIAGE: tuple[Entry, ...] = (
    Entry(
        "A1",
        "POL-CAR-001.c4",
        "ADDED",
        "The lead-in 'signs or symptoms of, or is being evaluated for' and 'lung disease "
        "affecting the heart' had no cited item; cov-108 and cov-043 support the reworded lead-in "
        "and the pulmonary item. Left out: cov-009's expert-examiner condition, a provider "
        "qualification that claims do not carry (as for DX-001's accreditation, D-V2-1).",
        (
            (
                "L37379-cov-108",
                "Symptoms or an existing condition must be present to meet medical necessity.",
            ),
            ("L37379-cov-108", "ECHO performed for screening purposes is not covered."),
            (
                "L37379-cov-043",
                "Pulmonary heart disease may result from acute changes in the "
                "pulmonary circulation",
            ),
            (
                "L37379-cov-043",
                "Indications include unexplained pulmonary HTN and PE with "
                "suspected clots in the right atrium or ventricle.",
            ),
        ),
        new_text=(
            "A transthoracic echocardiogram is covered when the patient has symptoms of, or an "
            "existing condition in, one of these: weakened heart muscle or cardiomyopathy; "
            "hypertensive heart disease with clinical evidence of heart disease; heart attack or "
            "coronary insufficiency; exposure to drugs or treatments toxic to the heart; heart "
            "transplant or rejection monitoring; native heart valve disease; prosthetic heart "
            "valves; acute endocarditis; pericardial disease; aortic disease; congenital heart "
            "disease; suspected clots or embolic sources in the heart; heart tumors or masses; "
            "critical illness or trauma; arrhythmias or palpitations; fainting (syncope); or "
            "pulmonary heart disease, such as unexplained pulmonary hypertension or a pulmonary "
            "embolism with suspected clots in the right heart."
        ),
        new_source=(
            "LCD L37379 v42 cov-006, cov-007, cov-009, cov-011, cov-012, cov-013, cov-016, "
            "cov-018, cov-020, cov-022, cov-024, cov-026, cov-028, cov-030, cov-032, cov-034, "
            "cov-036, cov-038, cov-040, cov-042, cov-043, cov-108."
        ),
    ),
    Entry(
        "A2",
        "POL-CAR-001.c5",
        "OK",
        "'not covered' and 'without signs or symptoms' are cov-012's words; no number.",
        (
            (
                "L37379-cov-012",
                "When there are no signs or symptoms of heart disease, the use of "
                "TTE is not covered for hypertension (HTN).",
            ),
        ),
    ),
    Entry(
        "A3",
        "POL-CAR-002.c4",
        "ADDED",
        "'known' in 'a known arrhythmia' is in no cited item (cov-007 is 'Arrhythmias') and "
        "narrows it; removed. 'fainting' for 'Syncope (lightheadedness)' is a rewording.",
        (("L34636-cov-007", "Arrhythmias"),),
        new_text=(
            "Recording for up to 48 hours is covered for one or more of: palpitations, fainting or "
            "near fainting, dizziness, chest pain, transient ischemic episodes, shortness of "
            "breath, or arrhythmias; checking the response to antiarrhythmic drugs; heart attack "
            "survivors with an ejection fraction of 40% or less; coronary artery disease with "
            "active symptoms, to correlate chest pain with ST-segment changes; other acute and "
            "subacute forms of ischemic heart disease; or detecting arrhythmias after an ablation "
            "procedure."
        ),
    ),
    Entry(
        "A6",
        "POL-DX-001.c4",
        "OK",
        "'moderate to severe' and the three examples are cov-110's; 'such as' keeps its open "
        "list; 'not covered' rests on cov-109's 'no comorbidities' criterion.",
        (
            (
                "L35050-cov-110",
                "including, but not limited to, moderate to severe pulmonary "
                "disease, neuromuscular disease, or congestive heart failure",
            ),
            (
                "L35050-cov-109",
                "That no comorbidities exist that are contraindications to OCST testing",
            ),
        ),
    ),
    Entry(
        "A10",
        "POL-DX-003.c5",
        "OK",
        "'not covered' matches the list heading above cov-080 (cov-063), which the sheet's "
        "'under' path did not show; cov-058's 'not recommended' is the reason given.",
        (
            (
                "L33261-cov-063",
                "The following tests are considered not medically reasonable and necessary:",
            ),
            ("L33261-cov-080", "Intradermal testing to diagnose food allergy"),
        ),
    ),
    Entry(
        "A11",
        "POL-FOOT-001.c4",
        "OK",
        "Class counts (two B; one B and two C; three trophic changes) and the asterisk rule "
        "match 290.D and 290.F; 'for example' keeps the presumption non-exhaustive, as 290.F "
        "does ('may be applied').",
        (
            ("§290.F", "Two of the Class B findings; or"),
            ("§290.F", "One Class B and two Class C findings."),
            ("§290.F", "(Three required)"),
            (
                "§290.D",
                "routine procedures are covered only if the patient is under the active "
                "care of a doctor of medicine or osteopathy who documents the condition.",
            ),
        ),
    ),
    Entry(
        "A15",
        "POL-PAIN-001.c7",
        "LIMITING CHANGE",
        "'only when a contrast allergy or pregnancy' closes a list the LCD gives as examples of a "
        "contraindication (cov-020, cov-025), and leaves out cov-015's ultrasound fallback. "
        "D-ESI-7 names allergy or pregnancy; the fix reads them as the LCD's examples.",
        (
            ("L33906-cov-020", "unless the patient has a contraindication to contrast"),
            (
                "L33906-cov-025",
                "except in cases of documented contraindication to contrast media "
                "(e.g., allergy, pregnancy)",
            ),
            ("L33906-cov-015", "ultrasound guidance without contrast may be considered"),
        ),
        new_text=(
            "Injections must be done under CT or fluoroscopic guidance with contrast. Without "
            "contrast, for example under ultrasound guidance, they are covered only when a "
            "contraindication to contrast, such as an allergy or pregnancy, is documented. A "
            "procedure code that includes imaging guidance counts as evidence of guidance, but "
            "contrast use, or the documented contraindication, must be in the notes. Interlaminar "
            "and caudal injections are limited to one level, and transforaminal injections to two "
            "levels in one spinal region."
        ),
    ),
    Entry(
        "A17",
        "POL-PAIN-001.c9",
        "ADDED",
        "The gloss '(pain that does not radiate from a nerve root)' is in no coverage item; the "
        "only LCD text for it is in the summary of evidence, which D-ESI-1 does not apply. "
        "Removed; D-ESI-4's reading stays with the cited decision.",
        (("L33906-cov-029", "axial spine pain"),),
        new_text=(
            "Injections are not covered to treat non-specific low back pain, axial spine pain, "
            "complex regional pain syndrome, widespread diffuse pain, pain from neuropathy of "
            "other causes, or cervicogenic headaches."
        ),
    ),
    Entry(
        "A19",
        "POL-REHAB-001.c4",
        "MISSING LIMIT",
        "cov-020 limits coverage to a plan that sets type, frequency and duration; added. The "
        "evaluation sentence (and its missing proviso from cov-112) concerns codes c4 does not "
        "apply to, so it is removed; the code list carries REHAB-001.F1.",
        (
            (
                "L34428-cov-020",
                "PT is only covered when it is rendered under a written plan of treatment",
            ),
            ("L34428-cov-020", "planned out specifically in terms of type, frequency and duration"),
            ("L34428-cov-112", "if the patient's condition showed a need for an evaluation"),
        ),
        new_text=(
            "Treatment must follow a written plan of care, developed from an examination and "
            "evaluation, that sets specific goals and plans the procedures by type, frequency and "
            "duration."
        ),
    ),
    Entry(
        "A20",
        "POL-REHAB-001.c5",
        "ADDED",
        "'who certifies and recertifies' had no cited item; cov-005 and doc-016 say a physician "
        "or NPP certifies the plan and that it need not be the same one, so the text names no "
        "single physician.",
        (
            ("L34428-cov-005", "Such NPPs may certify, order and establish the POC"),
            (
                "L34428-doc-016",
                "It is not required that the same physician/NPP who participated "
                "initially in recommending or planning the patient's care certify and/or recertify "
                "the plans.",
            ),
            ("L34428-doc-019", "the individual is under the care of a physician or NPP"),
        ),
        new_text=(
            "The patient must be under the care of a physician or NPP, and a physician or NPP must "
            "certify the plan of care and recertify it."
        ),
        new_source="LCD L34428 v93 cov-005, cov-018, doc-007, doc-016, doc-019.",
    ),
    Entry(
        "A22",
        "POL-SURG-002.c4",
        "MISSING LIMIT",
        "cov-009 excludes a perianal source too and says 'not thought to be'; cov-010 limits "
        "black stool to 'unknown origin'. The examples in cov-007 and cov-023 stay out "
        "(examples only).",
        (
            ("L34005-cov-009", "Hematochezia not thought to be from rectum or perianal source"),
            ("L34005-cov-010", "Melena of unknown origin;"),
        ),
        new_text=(
            "Colonoscopy to investigate symptoms or findings is covered for: an imaging "
            "abnormality likely to be significant; unexplained bleeding (blood in the stool not "
            "thought to be from a rectal or perianal source, black tarry stool of unknown origin, "
            "or a positive stool blood test); unexplained iron-deficiency anemia; significant "
            "unexplained diarrhea with other findings such as weight loss; examining the whole "
            "colon for synchronous cancer or polyps in a patient with a treatable cancer or "
            "polyp; chronic inflammatory bowel disease when a more precise diagnosis or the extent "
            "of activity will change immediate management; locating during surgery a lesion that "
            "cannot be found by touch or sight; acute colonic ischemia; Streptococcus bovis "
            "endocarditis; unexplained new-onset constipation that does not respond to medical "
            "treatment; an anorectal adenomatous polyp; or infectious colitis."
        ),
    ),
    Entry(
        "A24",
        "POL-SURG-002.c6",
        "LIMITING CHANGE",
        "Not OK: 'unless the record documents why it is needed' is cov-036's clause but was "
        "applied to cov-045's list, which has none; and cov-037's 'unusual exceptions' became "
        "'it may be done'. The fix keeps the two lists apart.",
        (
            (
                "L34005-cov-036",
                "records must have additional documentation indicating the medical "
                "necessity of the procedure for review as needed",
            ),
            (
                "L34005-cov-037",
                "There are unusual exceptions in which colonoscopy may be done to "
                "rule out organic disease",
            ),
            (
                "L34005-cov-045",
                "Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:",
            ),
        ),
        new_text=(
            "Colonoscopy is generally not covered, unless the record documents why it is needed, "
            "for: chronic, stable irritable bowel syndrome or chronic abdominal pain (in unusual "
            "cases it may be done to rule out organic disease, especially when symptoms do not "
            "respond to therapy); acute diarrhea; hemorrhoids; routine follow-up of inflammatory "
            "bowel disease (cancer surveillance in Crohn's disease or chronic ulcerative colitis "
            "excepted); routine examination before elective abdominal surgery for a non-colonic "
            "disease; upper GI bleeding or black tarry stool with a demonstrated upper GI source; "
            "or bright red rectal bleeding with a convincing anorectal source on sigmoidoscopy and "
            "no other symptoms suggesting a source higher up. It is also generally not covered for "
            "fulminant colitis, possible perforation, acute severe diverticulitis, or "
            "diverticulosis as the reason for the test (it may still be reported when it is the "
            "final diagnosis)."
        ),
    ),
    Entry(
        "A26",
        "POL-SURG-004.c5",
        "MISSING LIMIT",
        "cov-039 limits lid retraction or lag to three causes, and cov-040 limits dermatitis to "
        "symptomatic dermatitis of the pretarsal skin; added. Blepharospasm stays as is: "
        "cov-042 names it plainly and 'Primary essential (idiopathic)' describes it.",
        (
            (
                "L33944-cov-039",
                "Lid retraction or lag (due to horizontal lower eyelid laxity "
                "without ectropion or entropion, causing exposure keratopathy and/or epiphora; "
                "due to horizontal upper eyelid laxity, causing floppy eyelid syndrome; "
                "or due to orbital thyroid disease).",
            ),
            (
                "L33944-cov-040",
                "Chronic symptomatic dermatitis of pretarsal skin caused by "
                "redundant upper eyelid skin.",
            ),
            ("L33944-cov-042", "Relief of eye symptoms associated with blepharospasm."),
        ),
        new_text=(
            "Eyelid surgery is covered when it corrects visual impairment caused by excess eyelid "
            "skin weighing down the lashes (dermatochalasis), blepharochalasis, drooping of the "
            "eyelid (blepharoptosis) or drooping of the brow. It is also covered as "
            "reconstruction: to repair defects caused by disease (including thyroid disease and "
            "cranial nerve palsies), trauma or tumor surgery; for ectropion or entropion, "
            "epiblepharon, lagophthalmos, congenital ectropion, entropion, lagophthalmos or "
            "ptosis; for lid retraction or lag caused by horizontal laxity of the lower eyelid "
            "without ectropion or entropion (with exposure keratopathy or tearing), by horizontal "
            "laxity of the upper eyelid (with floppy eyelid syndrome), or by orbital thyroid "
            "disease; for chronic symptomatic dermatitis of the pretarsal skin caused by "
            "redundant upper eyelid skin; or, when other treatments have failed or cannot be "
            "used, to relieve blepharospasm. For these reconstructive conditions, the record must "
            "document the patient's complaints and the examination findings."
        ),
    ),
    Entry(
        "A27",
        "POL-SURG-004.c6",
        "LIMITING CHANGE",
        "cov-024's list is open ('include (but are not limited to)'); the text closed it. "
        "'such as' reopens it.",
        (("L33944-cov-024", "These include (but are not limited to):"),),
        new_text=(
            "For dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis, the record "
            "must document the patient's complaints of functional problems, such as vision "
            "blocked above or to the side, trouble reading because the upper field is lost, or "
            "looking through the eyelashes or seeing eyelid skin. The reconstructive conditions "
            "are exempt."
        ),
    ),
    Entry(
        "A30",
        "POL-WOUND-001.c4",
        "LIMITING CHANGE",
        "cov-082 limits the no-continued-care rule to care aimed at healing ('However, if ... "
        "the goal of care is not wound healing ... palliative care standards'), and cov-118 "
        "says 'should' and 'expected healing'; restored.",
        (
            ("L38902-cov-082", "Optimally, the overall goal of care is healing"),
            (
                "L38902-cov-082",
                "However, if it is determined that the goal of care is not wound healing",
            ),
            (
                "L38902-cov-082",
                "the patient should be managed following appropriate palliative care standards",
            ),
            (
                "L38902-cov-118",
                "Failure to document expected healing after 30 days should "
                "necessitate a revision in the Plan of Care",
            ),
        ),
        new_text=(
            "How often debridement is done depends on the wound. When the goal of care is "
            "healing, a given type of wound care is not continued if the record does not show "
            "improvement leading to healing, and when the expected healing is not documented "
            "after 30 days the plan of care should be revised. When the goal of care is not "
            "healing, the patient is managed under palliative care standards."
        ),
    ),
    Entry(
        "B4",
        "POL-CAR-001.c2",
        "TYPE",
        "The yearly limit is the LCD's rule for TTE (sections A and F); shown on 93350 it could "
        "deny a repeat stress echo by the TTE rule. Code list: the TTE codes.",
        (
            ("L37379-cov-021", "more frequently than annually"),
            ("L37379-cov-021", "imminent valvular surgery"),
        ),
        new_applies=("93306", "93308"),
    ),
    Entry(
        "B17",
        "POL-IMG-001.c3",
        "REWORDING",
        "Type question; pass 1 too strict: as a requirement, silent notes give NOT_DOCUMENTED, "
        "right for 'need a documented reason', and the repeat-scan clause only bites when the "
        "notes show a second contrast scan, which then gives NOT_MET either way.",
        (
            (
                "L37373-cov-030",
                "More than one contrast CT scan per episode of illness adds no "
                "information with the following exceptions:",
            ),
        ),
    ),
    Entry(
        "B18",
        "POL-IMG-001.c4",
        "TYPE",
        "An exclusion about brain imaging shown on the cervical spine MRI (72141) invites a "
        "wrong NOT_MET when the notes mention cancer staging; silent notes are unaffected. Code "
        "list: the head and brain codes.",
        (("L37373-cov-041", "in the absence of symptoms of brain involvement"),),
        new_applies=("70450", "70551", "70553"),
    ),
    Entry(
        "B27",
        "POL-PAIN-002.c3",
        "REWORDING",
        "Type question; pass 1 too strict: the LCD makes the absence one of the criteria that "
        "ALL must be met (cov-015, cov-018, cov-019), so the record must show it; requirement "
        "(silent notes give NOT_DOCUMENTED) is right.",
        (
            ("L33930-cov-015", "in patients who meet ALL of the following criteria:"),
            ("L33930-cov-018", "Absence of untreated radiculopathy or neurogenic claudication"),
        ),
    ),
    Entry(
        "B29",
        "POL-REHAB-001.c3",
        "TYPE",
        "A requirement of restorative potential on the evaluation codes gives NOT_DOCUMENTED "
        "(PEND) on an evaluation with silent notes, though an evaluation can be covered when "
        "therapy is not needed (cov-112). Code list: the treatment codes.",
        (
            ("L34428-cov-013", "potential for improvement from the services"),
            (
                "L34428-cov-112",
                "Initial evaluations or re-evaluations may be determined "
                "reasonable and necessary even when the evaluation determines that skilled "
                "rehabilitation is not required",
            ),
        ),
        new_applies=("97110", "97140", "97530"),
    ),
    Entry(
        "B34",
        "POL-SURG-003.c1",
        "TYPE",
        "c1 is the LCD's ablation limitation (cov-022), so it belongs on the ablation codes. "
        "That leaves stab phlebectomy (37765) with no requirement, so a new c4 holds the LCD's "
        "section A indications, which cov-017 also applies to ablation and cov-028 to same-day "
        "phlebectomy. c4 is a new criterion: approve it separately.",
        (
            ("L34209-cov-022", "ERFA and laser ablation are covered only for"),
            ("L34209-cov-008", "A 3-month trial of conservative therapy"),
            ("L34209-cov-017", "In addition to the above (see A)"),
            (
                "L34209-cov-028",
                "stab phlebectomy of the same vein performed on the same day as "
                "endovenous radiofrequency or laser ablation may be covered if the criteria for "
                "reasonable and necessary as described in this LCD are met.",
            ),
        ),
        new_applies=("36475", "36478"),
        new_criteria=(
            {
                "criterion_id": "POL-SURG-003.c4",
                "type": "requirement",
                "applies_to": "every code of the policy",
                "text": (
                    "Treatment of varicose veins, including stab phlebectomy, is covered when a "
                    "3-month trial of conservative therapy, such as exercise, periodic leg "
                    "elevation, weight loss, compression or avoiding long immobility, has failed, "
                    "and the patient is symptomatic with one or more of: pain or burning in the "
                    "leg severe enough to impair mobility; recurrent superficial phlebitis; a "
                    "non-healing skin ulcer; bleeding from a varicosity; stasis dermatitis; or "
                    "refractory dependent edema."
                ),
                "source": "LCD L34209 v43 cov-007 to cov-015, cov-017, cov-028.",
            },
        ),
    ),
    Entry(
        "B37",
        "POL-WOUND-001.c1",
        "TYPE",
        "A debridement requirement shown on the compression code (29581) gives NOT_DOCUMENTED "
        "(PEND) on a compression line with silent notes. Code list: the debridement codes; c2 "
        "and c4 still apply to 29581.",
        (
            (
                "L38902-cov-031",
                "Active wound care procedures involve selective and non-selective "
                "debridement techniques and are performed to remove devitalized tissue",
            ),
        ),
        new_applies=("11042", "97597"),
    ),
)


def source_text(label: str, lcds: Mapping[str, ps.Lcd]) -> str:
    """The word-for-word text of an LCD block ("L34005-cov-009") or a manual section ("§290.F")."""
    if label.startswith("§"):
        return bpm_sections()[label.removeprefix("§")][0]
    lcd_id, tag, index = label.split("-")
    field_name = {"cov": ps.COVERAGE_FIELD, "doc": ps.ASSOCIATED_FIELD}[tag]
    return ps.blocks(field_name, lcds[lcd_id].fields.get(field_name, ""))[int(index)].text


def check(entries: Sequence[Entry], criteria: Mapping[str, V2Criterion]) -> list[str]:
    problems = []
    lcds = ps.load_lcds({q[0].split("-")[0] for e in entries for q in e.quotes if q[0][0] == "L"})
    rows = [e.row for e in entries]
    if len(set(rows)) != len(rows):
        problems.append("a row is triaged twice")
    for e in entries:
        if e.category not in CATEGORIES:
            problems.append(f"{e.row}: unknown category {e.category}")
        if e.criterion not in criteria:
            problems.append(f"{e.row}: {e.criterion} is not a v2 criterion")
        changes = (e.new_text, e.new_applies, e.new_source, e.new_criteria)
        if e.action == "fix" and not any(changes):
            problems.append(f"{e.row}: a fix needs a new text, code list or source")
        if e.action == "keep" and any(changes):
            problems.append(f"{e.row}: {e.category} proposes no change")
        if not e.quotes:
            problems.append(f"{e.row}: no excerpt words")
        for label, words in e.quotes:
            if words not in source_text(label, lcds):
                problems.append(f"{e.row}: {label} does not contain {words!r}")
    return problems


def render(entries: Sequence[Entry], criteria: Mapping[str, V2Criterion]) -> str:
    counts = Counter(e.category for e in entries)
    out = [
        "# Policies v2 review sheet: author triage of the pass 2 rows",
        "",
        TRIAGE_NOTE,
        "",
        "The 22 rows: the 17 that pass 1 flagged, plus the 5 random MATCHES rows (A2, A6, A10, "
        "A11, A24). Categories: "
        + ", ".join(f"{c} {counts[c]}" for c in CATEGORIES if counts[c])
        + ". Proposed fixes change draft text of new v2 criteria in place (no v2 data uses them "
        "yet) or only the code list of kept criteria (their ID and text stay); one new criterion "
        "(SURG-003.c4) needs its own approval. Every excerpt below is checked word for word "
        "against data/raw by scripts/verify/policies_v2_triage.py.",
        "",
        "| Row | Criterion | Category | Action | Reason |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {e.row} | {e.criterion} | {e.category} | {e.action} | {e.reason} |" for e in entries
    ]
    out += ["", "## Drafts and excerpts", ""]
    for e in entries:
        c = criteria[e.criterion]
        out += [
            f"### {e.row}. {e.criterion}: {e.category}, {e.action}",
            "",
            f"- Reason: {e.reason}",
        ]
        if e.new_text:
            out += [f"- Old text: {c.text}", f"- **New text:** {e.new_text}"]
        if e.new_applies:
            out += [
                f"- Old Applies to: {', '.join(c.applies_to) or 'every code of the policy'}",
                f"- **New Applies to:** {', '.join(e.new_applies)} (text and ID unchanged)",
            ]
        if e.new_source:
            out += [f"- Old source line: {c.source}", f"- **New source line:** {e.new_source}"]
        for new in e.new_criteria:
            out += [
                f"- **New criterion {new['criterion_id']}** ({new['type']}; applies to "
                f"{new['applies_to']}): {new['text']}",
                f"  Source line: {new['source']}",
            ]
        out += ["- Excerpt words (word for word):"]
        out += [f'  - **{label}**: "{words}"' for label, words in e.quotes]
        out.append("")
    return "\n".join(out) + "\n"


def record_in_sheet(text: str) -> str:
    """The sheet with TRIAGE_NOTE under the pass 1 provenance line (once)."""
    if TRIAGE_NOTE in text:
        return text
    lines = text.splitlines()
    at = lines.index("## Verdicts")
    end = next(i for i in range(at + 1, len(lines)) if lines[i].startswith("Pass 1 ("))
    lines[end + 1 : end + 1] = ["", TRIAGE_NOTE]
    return "\n".join(lines) + "\n"


# The reviewer's pass 2 decisions on TRIAGE (2026-10-09): row -> (decision, condition, final
# text replacing the draft when the approval carries a condition).
A17_TEXT = (
    "Injections given to treat non-specific low back pain, axial spine pain, complex regional "
    "pain syndrome, widespread diffuse pain, pain from neuropathy of other causes, or "
    "cervicogenic headaches are not covered."
)
PASS2: dict[str, tuple[str, str, str | None]] = {
    **{
        row: ("approve", "", None)
        for row in (
            "A1",
            "A3",
            "A15",
            "A19",
            "A20",
            "A22",
            "A24",
            "A26",
            "A27",
            "A30",
            "B4",
            "B18",
            "B29",
            "B34",
            "B37",
        )
    },  # fmt: skip
    "A17": (
        "approve with a condition",
        "remove the gloss but keep the LCD's 'to treat' wording, so the exclusion is about what "
        "the injection treats; a patient with radicular pain who also has axial pain is not "
        "excluded",
        A17_TEXT,
    ),
    **{row: ("keep", "", None) for row in ("A2", "A6", "A10", "A11", "B17", "B27")},
}
VERDICT_WORD = {  # (part, triage category) -> the sheet's verdict word for pass 2
    ("A", "ADDED"): "NOT IN SOURCE",
    ("A", "LIMITING CHANGE"): "DIFFERENT MEANING",
    ("A", "MISSING LIMIT"): "DIFFERENT MEANING",
    ("A", "MISSING EXAMPLE"): "MATCHES",
    ("A", "REWORDING"): "MATCHES",
    ("A", "OK"): "MATCHES",
    ("B", "TYPE"): "DISAGREE",
    ("B", "REWORDING"): "AGREE",
    ("B", "OK"): "AGREE",
}


def pass2_cells(entry: Entry) -> tuple[str, str]:
    decision, condition, _ = PASS2[entry.row]
    verdict = VERDICT_WORD[(entry.row[0], entry.category)]
    if decision == "keep":
        said = "kept"
    elif condition:
        said = f"fix approved with a condition: {condition}"
    else:
        said = "fix approved (old and new text in P2_policies_v2_triage.md)"
    if entry.new_criteria:
        said += "; adds " + ", ".join(n["criterion_id"] for n in entry.new_criteria)
    return verdict, f"{entry.category}; {said}. {PASS2_BY[0].upper()}{PASS2_BY[1:]}."


def record_pass2(text: str, entries: Sequence[Entry]) -> tuple[str, list[str]]:
    """The sheet with the pass 2 cells of the triaged rows filled (only empty ones, or the same
    content again), and PASS2_NOTE under the triage note."""
    problems = []
    lines = text.splitlines()
    start = lines.index("## Verdicts")
    by_row = {e.row: e for e in entries}
    for i in range(start, len(lines)):
        match = re.match(r"^\| ([AB][0-9]+) \| (POL-[^|]+?) \|", lines[i])
        if not match or match.group(1) not in by_row:
            continue
        entry = by_row[match.group(1)]
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if cells[1] != entry.criterion:
            problems.append(
                f"{entry.row}: the sheet names {cells[1]}, the triage {entry.criterion}"
            )
            continue
        verdict, notes = pass2_cells(entry)
        if (cells[4] or cells[5]) and (cells[4], cells[5]) != (verdict, notes):
            problems.append(f"{entry.row}: the sheet already holds a different pass 2 decision")
            continue
        lines[i] = f"| {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {verdict} | {notes} |"
    if PASS2_NOTE not in lines:
        at = lines.index(TRIAGE_NOTE)
        lines[at + 1 : at + 1] = ["", PASS2_NOTE]
    return "\n".join(lines) + "\n", problems


def criterion_block(c: V2Criterion) -> list[str]:
    out = [f"## {c.criterion_id}", c.text, "", f"Type: {c.type}"]
    if c.applies_to:
        out.append(f"Applies to: {', '.join(c.applies_to)}")
    if c.group:
        out.append(f"Group: {c.group}")
    return [*out, f"Source: {c.source}"]


def fixed(entry: Entry, current: V2Criterion) -> V2Criterion:
    final = PASS2[entry.row][2] or entry.new_text
    return V2Criterion(
        current.criterion_id,
        current.number,
        final or current.text,
        current.type,
        entry.new_applies if entry.new_applies is not None else current.applies_to,
        current.group,
        entry.new_source or current.source,
    )


def apply_fixes(entries: Sequence[Entry]) -> dict[str, str]:
    """File name -> new text of every v2 policy file an approved fix changes. A changed criterion's
    section is rebuilt in place; an added criterion goes at the end of its file."""
    approved = [e for e in entries if e.action == "fix" and PASS2[e.row][0] != "keep"]
    out: dict[str, str] = {}
    for policy in read_v2():
        changes = {
            e.criterion: e
            for e in approved
            if e.criterion.startswith(policy.meta["policy_id"] + ".")
        }
        if not changes:
            continue
        path = V2_DIR / policy.name
        text = path.read_text(encoding="utf-8")
        front, body = text[: text.index("\n## ")], text[text.index("\n## ") + 1 :]
        sections = re.split(r"(?m)^(?=## POL-)", body)
        rebuilt = []
        appended = []
        for section in (s for s in sections if s.strip()):
            cid = section.split("\n", 1)[0].removeprefix("## ").strip()
            current = next(c for c in policy.criteria if c.criterion_id == cid)
            new = fixed(changes[cid], current) if cid in changes else current
            rebuilt.append("\n".join(criterion_block(new)))
            for added in changes[cid].new_criteria if cid in changes else ():
                appended.append(
                    "\n".join(
                        criterion_block(
                            V2Criterion(
                                added["criterion_id"],
                                int(added["criterion_id"].rsplit(".c", 1)[1]),
                                added["text"],
                                added["type"],
                                (),
                                "",
                                added["source"],
                            )
                        )
                    )
                )
        out[policy.name] = front + "\n" + "\n\n".join(rebuilt + appended) + "\n"
    return out


def append_rows(sheet: str, entries: Sequence[Entry]) -> tuple[str, list[str]]:
    """The sheet with each criterion a fix adds appended as a new Part A row (after the reviewed
    rows, so their numbers stay) and in the Part A verdict table, with a note under Part A."""
    added = [
        n["criterion_id"] for e in entries if PASS2[e.row][0] != "keep" for n in e.new_criteria
    ]
    lines = sheet.splitlines()
    numbers = [int(m.group(1)) for line in lines if (m := re.match(r"^### A([0-9]+)\. ", line))]
    on_sheet = {m.group(1) for line in lines if (m := re.match(r"^### A[0-9]+\. (POL-\S+)", line))}
    todo = [cid for cid in added if cid not in on_sheet]
    if not todo:
        return sheet, []
    v1 = read_v1()
    policies = read_v2()
    _, rows = check_sources(policies, v1, lcds_cited(policies), "")
    by_id = {r.criterion.criterion_id: r for r in rows}
    blocks: list[str] = []
    table: list[str] = []
    for n, cid in enumerate(todo, start=max(numbers) + 1):
        blocks += row_block(n, by_id[cid], v1)
        table.append(f"| A{n} | {cid} |  |  |  |  |")
    part_b = lines.index(next(line for line in lines if line.startswith("## Part B:")))
    note = (
        f"Rows added after pass 1 ({', '.join(todo)}): from approved pass 2 fixes; not yet "
        "reviewed."
    )
    lines[part_b:part_b] = [note, "", *blocks]
    at = lines.index(next(line for line in lines if line.startswith("### Part A (")))
    end = next(i for i in range(at + 3, len(lines)) if not lines[i].startswith("|"))
    lines[end:end] = table
    return "\n".join(lines) + "\n", []


def decide() -> None:
    missing = sorted({e.row for e in TRIAGE} - set(PASS2))
    if missing:
        raise SystemExit(f"no pass 2 decision for {missing}")
    sheet, problems = record_pass2(SHEET.read_text(encoding="utf-8"), TRIAGE)
    files = apply_fixes(TRIAGE)
    for name, text in files.items():
        (V2_DIR / name).write_text(text, encoding="utf-8")  # rows below read the new files
    sheet, more = append_rows(sheet, TRIAGE)
    problems += more
    hits = {n: k for n, k in ama_hits({SHEET.name: sheet, **files}).items() if k}
    if hits:
        problems.append(f"AMA CPT descriptor text found: {hits}")
    if problems:
        raise SystemExit(
            "stopped (policy files may be written; check git diff):\n  " + "\n  ".join(problems)
        )
    SHEET.write_text(sheet, encoding="utf-8")
    print(
        f"pass 2 recorded for {len(PASS2)} rows; fixes applied to {len(files)} policy files "
        f"({', '.join(sorted(files))})"
    )


def write() -> None:
    criteria = {c.criterion_id: c for p in read_v2() for c in p.criteria}
    applied = [e.row for e in TRIAGE if e.new_text and criteria[e.criterion].text == e.new_text]
    if applied:
        raise SystemExit(f"fixes already applied ({applied}); the triage file is the record")
    problems = check(TRIAGE, criteria)
    written = render(TRIAGE, criteria)
    sheet = record_in_sheet(SHEET.read_text(encoding="utf-8"))
    hits = {n: k for n, k in ama_hits({OUT.name: written, SHEET.name: sheet}).items() if k}
    if hits:
        problems.append(f"AMA CPT descriptor text found: {hits}")
    if problems:
        raise SystemExit("not written:\n  " + "\n  ".join(problems))
    OUT.write_text(written, encoding="utf-8")
    SHEET.write_text(sheet, encoding="utf-8")
    fixes = sum(e.action == "fix" for e in TRIAGE)
    print(
        f"{len(TRIAGE)} rows triaged: {fixes} fixes, {len(TRIAGE) - fixes} keep; wrote {OUT.name}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("write", "decide"))
    {"write": write, "decide": decide}[parser.parse_args().step]()


if __name__ == "__main__":
    main()
