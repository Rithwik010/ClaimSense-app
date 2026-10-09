"""Policies v2, checkpoint 1: check the v2 coverage policies against v1 and their sources, and
write the review sheet. Report and sheet only: the loader reads the v2 files from checkpoint 2.

Checked for every file in data/curated/coverage_policies/v2/:

- format: the v1 front matter keys with their v1 values (sources may only be added), plus
  `policy_set: v2` and `replaces` (retired v1 ID -> its new IDs); per criterion one text, one
  `Type:` line (requirement, exclusion or conditional), at most one `Applies to:` line (codes of
  the policy) and one `Group:` line (indication), and one `Source:` line;
- IDs (a changed meaning gets a new ID): a criterion that keeps its v1 ID keeps its v1 text byte
  for byte; a new criterion is numbered above the policy's highest v1 number, so no number is ever
  reused; every retired v1 ID is listed under `replaces`, whose values are new IDs;
- groups: an indication group holds 2 or more conditional criteria (alternatives);
- indication groups: every covered indication the sources give for the codes of each
  indication-group policy is listed (INDICATIONS) with the criterion that holds it, or why it is
  left out; the LCD indication lists are covered block by block;
- the sources of every new criterion (needs data/raw): each cited LCD block, by its V1b ID
  (L<lcd>-cov-NNN in the coverage field, -doc-NNN in Associated Information; ranges allowed;
  headings and background blocks included), exists in the cited LCD version, which must be the
  version in data/raw; each cited section of the Medicare Benefit Policy Manual chapter 15 exists;
  each cited decision is in DECISIONS.md; every excerpt appears word for word in its source text;
  numbers, durations and thresholds of the criterion that no excerpt contains are flagged for the
  reviewer (the V1b heuristic, qualifiers ignored);
- no AMA CPT descriptor text of our codes in the policy files or the sheet.

The excerpts on the sheet are copied from data/raw by this script, never typed.

    uv run python -m scripts.verify.policies_v2_sources check      # the checks, report only
    uv run python -m scripts.verify.policies_v2_sources selftest   # planted cases
    uv run python -m scripts.verify.policies_v2_sources sheet      # the checks, then the sheet
"""

import argparse
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.db.curated import CRITERION_HEADING, load_curated, parse_policy
from scripts.verify import policy_sources as ps

ROOT = Path(__file__).resolve().parents[2]
V1_DIR = ROOT / "data" / "curated" / "coverage_policies"
V2_DIR = V1_DIR / "v2"
BPM_PDF = ROOT / "data" / "raw" / "cms-manual" / "bp102c15" / "bp102c15.pdf"
BPM_NAME = "Medicare Benefit Policy Manual Ch. 15"
DECISIONS_MD = ROOT / "DECISIONS.md"
SHEET = ROOT / "data" / "verification" / "reviews" / "P2_policies_v2_sheet.md"

TYPES = ("requirement", "exclusion", "conditional")
GROUPS = ("indication",)
KEPT_KEYS = (
    "policy_id",
    "title",
    "procedure_codes",
    "plan_ids",
    "effective_date",
    "billing_article",
    "split",
)
FIELD = re.compile(r"^(Type|Applies to|Group|Source):\s*(.*?)\s*$")
REF_LCD = re.compile(r"^LCD (L[0-9]+) v([0-9]+) (.+)$")
BLOCK_ID = re.compile(r"^(cov|doc)-([0-9]{3})(?: to (cov|doc)-([0-9]{3}))?$")
REF_BPM = re.compile(rf"^{re.escape(BPM_NAME)} (.+)$")
SECTION_ID = re.compile(r"^§(290(?:\.[A-G](?:\.[0-9])?)?)$")
REF_DECISION = re.compile(r"^decision (D-[A-Z0-9]+-[0-9]+)$")
TAG_FIELD = {"cov": ps.COVERAGE_FIELD, "doc": ps.ASSOCIATED_FIELD}
FIELD_NAME = {ps.COVERAGE_FIELD: "coverage field", ps.ASSOCIATED_FIELD: "Associated Information"}

# Why each new criterion differs from v1 (decision, what changed), for the reviewer.
NOTES: dict[str, tuple[str, str]] = {
    "POL-CAR-001.c4": (
        "D-V2-1",
        "Replaces the first sentence of v1 c1; re-sourced to L37379's covered-indication list "
        "(its section headings A to Q).",
    ),
    "POL-CAR-001.c5": (
        "D-V2-1",
        "The second sentence of v1 c1, same words; split out because a criterion has one type.",
    ),
    "POL-CAR-002.c4": (
        "D-V2-1, D-V2-2 CAR-002.F1, Q2",
        "v1 c1 and c2 merged and limited to recording up to 48 hours (the LCD's one list, '1 or "
        "more of the following'); the ejection fraction condition stays with 48-hour recording; "
        "adds cov-017 (other acute and subacute forms of ischemic heart disease), which v1 left "
        "out.",
    ),
    "POL-CAR-002.c5": (
        "D-V2-1",
        "Split from v1 c3: recording or event monitoring for more than 48 hours up to 15 days.",
    ),
    "POL-CAR-002.c6": (
        "D-V2-1, D-V2-2 CAR-002.F1",
        "Split from v1 c3: 30-day monitoring, with the LCD's own list; heart attack survivors "
        "without the ejection fraction condition. cov-020's 'no other EKG monitoring codes' is "
        "enforced by the NCCI edits (R11), not by a criterion.",
    ),
    "POL-DX-001.c4": (
        "D-V2-1, Q6",
        "v1 c2 without the accreditation requirement, with the home-testing conditions of "
        "cov-109 and cov-110 spelled out. Typed exclusion, so silent notes give NOT_APPLICABLE. "
        "The other home-testing conditions (cov-107 and cov-108) are c5.",
    ),
    "POL-DX-001.c5": (
        "D-POL-4 (checkpoint 1 review)",
        "New: the home-testing conditions of cov-107 and cov-108. A requirement on the home-test "
        "code: the code list carries the condition, as for CAR-002 c4 to c6.",
    ),
    "POL-DX-002.c4": (
        "D-RULE-6, Q9",
        "New. Applies when a nerve conduction study is done without needle EMG; then needs "
        "documented carpal tunnel syndrome with a high pre-test probability (notes showing "
        "another cause: NOT_MET; silent notes: NOT_DOCUMENTED).",
    ),
    "POL-DX-003.c4": (
        "D-V2-2 DX-003.F1",
        "v1 c1 with foods removed from intradermal testing (the LCD lists foods for prick tests "
        "only).",
    ),
    "POL-DX-003.c5": ("D-V2-2 DX-003.F1", "New exclusion: intradermal testing for food allergy."),
    "POL-FOOT-001.c4": (
        "Q4 (new finding)",
        "New: manual section 290.C.3 (systemic conditions), with 290.D's list and its asterisk "
        "rule, 290.F's class findings, and 290.G's 'the mere statement of a diagnosis ... does "
        "not of itself indicate the severity'.",
    ),
    "POL-FOOT-001.c5": ("Q4 (new finding)", "New: manual section 290.C.4 (mycotic nails)."),
    "POL-FOOT-001.c6": (
        "D-V2-1, Q4",
        "Replaces v1 c3: cites manual section 290.B.2 (now in data/raw) and says 'except in the "
        "situations this policy covers', since c4 and c5 add exceptions.",
    ),
    "POL-PAIN-001.c6": (
        "D-ESI-2",
        "v1 c2 plus: the baseline score is a numeric score or a named scale.",
    ),
    "POL-PAIN-001.c7": (
        "D-ESI-7",
        "v1 c4 plus: a code that includes imaging guidance counts as evidence of guidance, and "
        "contrast use (or the documented allergy or pregnancy) must be in the notes; caudal "
        "injections added to the one-level limit (cov-017). The level limits are also enforced "
        "by R18.",
    ),
    "POL-PAIN-001.c8": (
        "D-ESI-2, V1a open item",
        "v1 c5 plus the repeat after a poor first response (after 14 days, with a different "
        "approach, level or medication, the reason documented).",
    ),
    "POL-PAIN-001.c9": ("D-ESI-4, Q5", "New exclusion with every condition cov-029 lists."),
    "POL-PAIN-002.c5": (
        "D-V2-1",
        "v1 c4 plus the LCD's documented-exception clause; shown on the diagnostic injection "
        "codes only.",
    ),
    "POL-REHAB-001.c4": (
        "D-V2-2 REHAB-001.F1",
        "v1 c2, shown on treatment codes only: an evaluation needs no plan of care.",
    ),
    "POL-REHAB-001.c5": (
        "D-V2-2 REHAB-001.F2",
        "New: physician or NPP care and plan certification, treatment codes only.",
    ),
    "POL-SURG-002.c4": (
        "D-V2-2 SURG-002.F1",
        "v1 c1 plus the covered indications it missed (cov-014, cov-022, cov-024 to cov-026, "
        "cov-032, cov-033, doc-001). The LCD's therapeutic indications are c7.",
    ),
    "POL-SURG-002.c5": (
        "D-V2-1",
        "v1 c2 plus the large sessile adenoma definition (more than 2 cm) and the rectosigmoid "
        "exclusion; no intervals (D-RULE-1).",
    ),
    "POL-SURG-002.c6": (
        "D-V2-2 SURG-002.F3",
        "New exclusion: the LCD limitations that R15 cannot catch, including cov-044 (bright "
        "red bleeding with an anorectal source; checkpoint 1 review). Left out: cov-040 (R15 "
        "denies it: billing article A56456 covers none of its diagnosis codes).",
    ),
    "POL-SURG-002.c7": (
        "D-POL-4 (checkpoint 1 review)",
        "New: the LCD's therapeutic indications (cov-027 to cov-031, cov-034), in the indication "
        "group, on the biopsy and polyp-removal codes, so those lines are not pended for want of "
        "an indication.",
    ),
    "POL-SURG-001.c4": (
        "D-POL-4 (checkpoint 1 review)",
        "New: L33558 cov-008, a covered indication no v1 criterion held (found while listing the "
        "indication group's sources). A separate criterion, so c3 keeps its ID.",
    ),
    "POL-SURG-004.c5": (
        "D-V2-2 SURG-004.F1, Q3",
        "v1 c1 plus the reconstructive conditions: the LCD's group 2 (cov-030 to cov-041) and "
        "group 3 (blepharospasm, cov-042 and cov-043). The V1b finding cited only cov-030 and "
        "cov-038.",
    ),
    "POL-SURG-004.c6": (
        "D-V2-2 SURG-004.F1",
        "v1 c2 limited to the four group 1 conditions; the reconstructive conditions are exempt "
        "(cov-016).",
    ),
    "POL-SURG-004.c7": (
        "D-V2-2 SURG-004.F1",
        "v1 c3 limited to the four group 1 conditions; the reconstructive conditions are exempt "
        "(cov-016).",
    ),
    "POL-SURG-004.c8": (
        "D-V2-2 SURG-004.F1, Q3",
        "v1 c4 limited to the four group 1 conditions; sourced to the LCD's cosmetic definitions "
        "(background blocks cov-001, cov-004 and cov-006) and cov-016.",
    ),
    "POL-WOUND-001.c4": (
        "D-V2-2 WOUND-001.F3",
        "v1 c3's frequency sentence plus the firm rule only: no continued care without "
        "improvement, and a revised plan when healing is not documented after 30 days. v1's "
        "'frequent repeated debridement requires a documented reassessment' is replaced by the "
        "30-day revision. Left out: the expectations in cov-112, cov-113 and cov-117.",
    ),
}
# The situation in which each conditional criterion applies (D-ESI-6), for the reviewer.
CONDITIONS: dict[str, str] = {
    "POL-CAR-001.c2": "the study repeats one done within the past year",
    "POL-DX-001.c3": "a repeat facility study",
    "POL-DX-002.c4": "a nerve conduction study with no needle EMG on the claim",
    "POL-FOOT-001.c1": "nerve damage in the feet without blood-vessel impairment",
    "POL-FOOT-001.c2": "the patient takes blood thinners",
    "POL-FOOT-001.c4": "a systemic condition",
    "POL-FOOT-001.c5": "mycotic toenails without a systemic condition",
    "POL-IMG-001.c2": "headache or dizziness",
    "POL-IMG-002.c3": "plantar fasciitis",
    "POL-IMG-002.c4": "both limbs are scanned",
    "POL-PAIN-001.c8": "a repeat injection",
    "POL-SURG-001.c1": "a cataract causing impaired vision",
    "POL-SURG-001.c3": "another eye disease, retinal surgery or a difference between the eyes",
    "POL-SURG-001.c4": "another procedure or treatment likely to speed up the cataract",
    "POL-SURG-002.c3": "screening of a high-risk patient",
    "POL-SURG-002.c4": "symptoms or findings to investigate",
    "POL-SURG-002.c5": "surveillance",
    "POL-SURG-002.c7": "treatment during the colonoscopy",
    "POL-SURG-004.c6": "dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis",
    "POL-SURG-004.c7": "dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis",
    "POL-WOUND-001.c4": "continuing or repeated wound care",
}

# Every covered indication the sources give for the codes of each indication-group policy, and
# the criterion that holds it, or why it is left out (checkpoint 1 review, point 4). LCD blocks
# by V1b ID; manual sections as "§290.X.n".
NOT_OUR_CODES = "not an indication for the nail codes 11720 and 11721 (Q4); "
INDICATIONS: dict[str, list[tuple[str, str, str]]] = {
    "POL-FOOT-001": [
        ("L33941-cov-002", "POL-FOOT-001.c1", ""),
        ("L33941-cov-003", "POL-FOOT-001.c2", ""),
        ("§290.A", "", NOT_OUR_CODES + "treatment of subluxation, billed with other codes"),
        (
            "§290.C.1",
            "",
            NOT_OUR_CODES + "routine care done as a necessary and integral part of another "
            "covered service, such as ulcer, wound or infection treatment, goes with that service",
        ),
        ("§290.C.2", "", NOT_OUR_CODES + "treatment of warts, billed with other codes"),
        ("§290.C.3", "POL-FOOT-001.c4", ""),
        ("§290.C.4", "POL-FOOT-001.c5", ""),
        ("§290.D", "POL-FOOT-001.c4", "the systemic conditions and the asterisk rule"),
        ("§290.E", "", NOT_OUR_CODES + "supportive devices and therapeutic shoes"),
        ("§290.F", "POL-FOOT-001.c4", "the class findings that show the severity"),
        (
            "§290.G",
            "POL-FOOT-001.c4",
            "the sentence that a diagnosis alone does not show the severity; its items 1 and 2 "
            "are payment rules for other services (a covered procedure, initial diagnostic "
            "services)",
        ),
    ],
    "POL-SURG-001": [
        ("L33558-cov-004", "POL-SURG-001.c1", ""),
        ("L33558-cov-005", "POL-SURG-001.c3", ""),
        ("L33558-cov-006", "POL-SURG-001.c3", ""),
        ("L33558-cov-007", "POL-SURG-001.c3", ""),
        ("L33558-cov-008", "POL-SURG-001.c4", ""),
        ("L33558-cov-009", "POL-SURG-001.c3", ""),
    ],
    "POL-SURG-002": [
        *[(f"L34005-cov-{n:03d}", "POL-SURG-002.c4", "") for n in (7, 9, 10, 11, 12, 14)],
        ("L34005-cov-013", "POL-SURG-002.c5", ""),
        ("L34005-cov-015", "POL-SURG-002.c5", ""),
        ("L34005-cov-016", "POL-SURG-002.c3", ""),
        ("L34005-cov-017", "POL-SURG-002.c5", ""),
        ("L34005-cov-018", "POL-SURG-002.c3", "the LCD repeats cov-016"),
        *[(f"L34005-cov-{n:03d}", "POL-SURG-002.c5", "") for n in (19, 20, 21)],
        *[(f"L34005-cov-{n:03d}", "POL-SURG-002.c4", "") for n in (22, 23, 24, 25, 26)],
        *[(f"L34005-cov-{n:03d}", "POL-SURG-002.c7", "") for n in (27, 28, 29, 30, 31)],
        *[(f"L34005-cov-{n:03d}", "POL-SURG-002.c4", "") for n in (32, 33)],
        ("L34005-cov-034", "POL-SURG-002.c7", ""),
        ("L34005-doc-001", "POL-SURG-002.c4", ""),
    ],
}
# The LCD indication lists that INDICATIONS must cover block by block: (LCD, tag, first, last).
INDICATION_RANGES = {
    "POL-SURG-001": ("L33558", "cov", 4, 9),
    "POL-SURG-002": ("L34005", "cov", 7, 34),
}


# --- parsing ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class V2Criterion:
    criterion_id: str
    number: int
    text: str
    type: str
    applies_to: tuple[str, ...]
    group: str
    source: str


@dataclass(frozen=True)
class V2Policy:
    name: str
    meta: Mapping[str, Any]
    criteria: tuple[V2Criterion, ...]
    problems: tuple[str, ...]  # format problems


def parse_v2(name: str, text: str) -> V2Policy:
    """A v2 policy file: YAML front matter, then `## <criterion id>` sections holding the text and
    the Type, Applies to, Group and Source lines."""
    if not text.startswith("---\n") or text.find("\n---\n", 4) < 0:
        return V2Policy(name, {}, (), ("no front matter between --- lines",))
    end = text.find("\n---\n", 4)
    meta = yaml.safe_load(text[4:end]) or {}
    parts = CRITERION_HEADING.split(text[end + 5 :])
    problems = ["text before the first criterion"] if parts[0].strip() else []
    criteria = []
    for criterion_id, section in zip(parts[1::2], parts[2::2], strict=True):
        fields: dict[str, list[str]] = {}
        lines = []
        for line in (raw.strip() for raw in section.splitlines()):
            match = FIELD.match(line)
            if match:
                fields.setdefault(match.group(1), []).append(match.group(2))
            elif line:
                lines.append(line)
        for key in ("Type", "Source"):
            count = len(fields.get(key, []))
            if count != 1:
                problems.append(f"{criterion_id}: needs exactly one {key} line, found {count}")
        for key in ("Applies to", "Group"):
            if len(fields.get(key, [])) > 1:
                problems.append(f"{criterion_id}: more than one {key} line")
        if not lines:
            problems.append(f"{criterion_id}: no text")
        applies = (fields.get("Applies to") or [""])[0]
        criteria.append(
            V2Criterion(
                criterion_id,
                int(criterion_id.rsplit(".c", 1)[1]),
                " ".join(lines),  # joined as the v1 loader joins them
                (fields.get("Type") or [""])[0],
                tuple(code.strip() for code in applies.split(",") if code.strip()),
                (fields.get("Group") or [""])[0],
                (fields.get("Source") or [""])[0],
            )
        )
    return V2Policy(name, meta, tuple(criteria), tuple(problems))


def read_v1() -> dict[str, tuple[dict[str, str], dict[str, Any]]]:
    """policy ID -> (criterion ID -> v1 text, v1 front matter), from the v1 files."""
    out = {}
    for path in sorted(V1_DIR.glob("POL-*.md")):
        text = path.read_text(encoding="utf-8")
        policy = parse_policy(text)
        meta = yaml.safe_load(text.split("---", 2)[1])
        out[policy.policy_id] = ({c.criterion_id: c.text for c in policy.criteria}, meta)
    return out


def read_v2() -> list[V2Policy]:
    return [
        parse_v2(path.name, path.read_text(encoding="utf-8"))
        for path in sorted(V2_DIR.glob("POL-*.md"))
    ]


# --- IDs, types, groups -----------------------------------------------------------------------


def number_of(criterion_id: str) -> int:
    return int(criterion_id.rsplit(".c", 1)[1])


def id_problems(v1: Mapping[str, str], policy: V2Policy) -> list[str]:
    """`v1`: criterion ID -> text, for this policy's v1 file."""
    out = []
    numbers = [c.number for c in policy.criteria]
    if numbers != sorted(set(numbers)):
        out.append("criterion IDs must be unique and ascending")
    v1_max = max((number_of(i) for i in v1), default=0)
    owner = f"{policy.meta.get('policy_id')}.c"
    new = set()
    for c in policy.criteria:
        if not c.criterion_id.startswith(owner):
            out.append(f"{c.criterion_id} belongs to another policy")
        elif c.criterion_id in v1:
            if c.text != v1[c.criterion_id]:
                out.append(
                    f"{c.criterion_id} keeps its v1 ID but its text changed: a changed meaning "
                    "needs a new ID"
                )
        elif c.number <= v1_max:
            out.append(f"{c.criterion_id} is new but not numbered above c{v1_max}")
        else:
            new.add(c.criterion_id)
    replaces = policy.meta.get("replaces")
    if not isinstance(replaces, dict):
        return [*out, "replaces must be a mapping (use {} when nothing is retired)"]
    retired = set(v1) - {c.criterion_id for c in policy.criteria}
    for old, targets in replaces.items():
        if old not in retired:
            out.append(f"replaces {old}: not a retired v1 criterion of this policy")
        if not isinstance(targets, list) or not targets:
            out.append(f"replaces {old}: needs a list of new IDs")
            continue
        out += [f"replaces {old}: {t} is not a new criterion" for t in targets if t not in new]
    unlisted = sorted(retired - set(replaces))
    out += [f"{old} is retired but not listed under replaces" for old in unlisted]
    return out


def field_problems(policy: V2Policy, v1_meta: Mapping[str, Any]) -> list[str]:
    out = []
    meta = policy.meta
    for key in KEPT_KEYS:
        if str(meta.get(key)) != str(v1_meta.get(key)):
            out.append(f"front matter {key} differs from v1")
    sources = meta.get("sources") or []
    if not set(v1_meta.get("sources") or []) <= set(sources):
        out.append("front matter sources must keep the v1 sources")
    if meta.get("policy_set") != "v2":
        out.append("front matter policy_set must be v2")
    codes = {str(code) for code in meta.get("procedure_codes") or []}
    groups: dict[str, int] = {}
    for c in policy.criteria:
        if c.type not in TYPES:
            out.append(
                f"{c.criterion_id}: type {c.type!r} is not requirement, exclusion or conditional"
            )
        out += [
            f"{c.criterion_id}: applies to {code}, which the policy does not cover"
            for code in c.applies_to
            if code not in codes
        ]
        if c.group:
            if c.group not in GROUPS:
                out.append(f"{c.criterion_id}: unknown group {c.group!r}")
            elif c.type != "conditional":
                out.append(
                    f"{c.criterion_id}: an indication-group criterion must be conditional, "
                    f"not {c.type}"
                )
            groups[c.group] = groups.get(c.group, 0) + 1
    out += [
        f"group {g} has {n} criterion; a group needs 2 or more alternatives"
        for g, n in groups.items()
        if n < 2
    ]
    return out


# --- sources ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ref:
    kind: str  # lcd | bpm | decision
    lcd_id: str = ""
    version: str = ""
    blocks: tuple[tuple[str, int], ...] = ()  # (cov | doc, block index)
    sections: tuple[str, ...] = ()  # "290.C.4"
    decision: str = ""


def parse_refs(source: str) -> tuple[list[Ref], list[str]]:
    """A new criterion's Source line: references separated by "; " -- `LCD L<id> v<n> <blocks>`
    (blocks `cov-NNN` or `doc-NNN`, comma separated, `cov-005 to cov-018` for a range),
    `Medicare Benefit Policy Manual Ch. 15 §290.X.n` (comma separated), `decision D-XXX-n`."""
    refs: list[Ref] = []
    problems: list[str] = []
    for part in (p.strip() for p in source.strip().rstrip(".").split(";")):
        lcd, bpm, decision = REF_LCD.match(part), REF_BPM.match(part), REF_DECISION.match(part)
        if lcd:
            blocks: list[tuple[str, int]] = []
            for token in lcd.group(3).split(", "):
                b = BLOCK_ID.match(token)
                if not b:
                    problems.append(f"cannot read block {token!r} in {part!r}")
                    continue
                tag, start = b.group(1), int(b.group(2))
                if b.group(3) is None:
                    blocks.append((tag, start))
                elif b.group(3) != tag or int(b.group(4)) < start:
                    problems.append(f"range {token!r} must run upwards within one field")
                else:
                    blocks += [(tag, i) for i in range(start, int(b.group(4)) + 1)]
            refs.append(Ref("lcd", lcd.group(1), lcd.group(2), tuple(blocks)))
        elif bpm:
            sections = [SECTION_ID.match(token) for token in bpm.group(1).split(", ")]
            if not all(sections):
                problems.append(f"cannot read manual sections in {part!r}")
                continue
            refs.append(Ref("bpm", sections=tuple(s.group(1) for s in sections if s)))
        elif decision:
            refs.append(Ref("decision", decision=decision.group(1)))
        else:
            problems.append(f"cannot read source {part!r}")
    return refs, problems


def _bare(value: str) -> str:
    """ "at least 4 week" -> "4 week": the number and unit of a V1b value."""
    return " ".join(value.split()[-2:])


def missing_values(criterion: str, excerpts: Sequence[str]) -> list[str]:
    """Numbers, durations and thresholds of the criterion (V1b's `values`) whose number and unit
    appear in no excerpt; qualifiers are left to the reviewer."""
    found = {_bare(v) for e in excerpts for v in ps.values(e)}
    return sorted(v for v in ps.values(criterion) if _bare(v) not in found)


@dataclass(frozen=True)
class Excerpt:
    label: str  # "L34636-cov-019", "Manual Ch. 15 §290.C.4"
    where: str  # "item", "heading", "background block" (LCD) or "pages 261-262" (manual)
    section: str
    text: str


@lru_cache
def bpm_sections() -> dict[str, tuple[str, tuple[int, ...]]]:
    """Section 290 of the chapter and its lettered and (in B and C) numbered subsections:
    "290.C.4" -> (text, pages). Lines are joined with single spaces."""
    import pymupdf

    with pymupdf.open(BPM_PDF) as doc:
        lines = [
            (n + 1, line) for n, page in enumerate(doc) for line in page.get_text().splitlines()
        ]
    starts = [i for i, (_, line) in enumerate(lines) if line.strip() == "290 - Foot Care"]
    start = starts[-1]  # the first one is in the table of contents
    end = next(i for i in range(start, len(lines)) if lines[i][1].startswith("300 - Diabetes"))
    current = ["290"]
    collected: dict[str, list[tuple[int, str]]] = {"290": []}
    for page, line in lines[start + 1 : end]:
        letter = re.match(r"^([A-G])\.\s{2,}\S", line)
        number = re.match(r"^([1-9])\.\s{2,}\S", line)
        if letter:
            current = ["290", f"290.{letter.group(1)}"]
        elif number and len(current) > 1 and current[1][-1] in "BC":
            current = current[:2] + [f"{current[1]}.{number.group(1)}"]
        for key in current:
            collected.setdefault(key, []).append((page, line))
    return {
        key: (re.sub(r"\s+", " ", " ".join(line for _, line in rows)).strip(), _pages(rows))
        for key, rows in collected.items()
    }


def _pages(rows: Sequence[tuple[int, str]]) -> tuple[int, ...]:
    return tuple(sorted({page for page, line in rows if line.strip()}))


def bpm_text() -> str:
    """The whole of section 290 as the excerpts are taken from it."""
    return bpm_sections()["290"][0]


def resolve(
    ref: Ref, lcds: Mapping[str, ps.Lcd], decisions: str
) -> tuple[list[Excerpt], list[str]]:
    """The excerpts a reference cites, and its problems."""
    if ref.kind == "decision":
        found = f"{ref.decision}:" in decisions or f"{ref.decision} " in decisions
        return [], [] if found else [f"decision {ref.decision} is not in DECISIONS.md"]
    if ref.kind == "bpm":
        sections = bpm_sections()
        out, problems = [], []
        for key in ref.sections:
            if key not in sections:
                problems.append(f"manual section §{key} not found")
                continue
            text, pages = sections[key]
            if text not in bpm_text():
                problems.append(f"manual section §{key} is not word for word in the chapter")
            where = f"page {pages[0]}" if len(pages) == 1 else f"pages {pages[0]}-{pages[-1]}"
            out.append(Excerpt(f"Manual Ch. 15 §{key}", where, "", text))
        return out, problems
    lcd = lcds.get(ref.lcd_id)
    if lcd is None:
        return [], [f"LCD {ref.lcd_id} is not in data/raw"]
    problems = []
    if ref.version != lcd.version:
        problems.append(f"cites {ref.lcd_id} v{ref.version}; data/raw holds v{lcd.version}")
    out = []
    for tag, index in ref.blocks:
        field = TAG_FIELD[tag]
        blocks = ps.blocks(field, lcd.fields.get(field, ""))
        label = f"{ref.lcd_id}-{tag}-{index:03d}"
        if index >= len(blocks):
            problems.append(f"{label} does not exist")
            continue
        block = blocks[index]
        if block.text not in lcd.text(field):
            problems.append(f"{label} is not word for word in the LCD text")
        kind = "heading" if block.heading else "background block" if block.background else "item"
        out.append(Excerpt(label, kind, block.section, block.text))
    return out, problems


# --- the whole check --------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    policy: V2Policy
    criterion: V2Criterion
    replaced: tuple[str, ...]  # the v1 IDs it replaces
    excerpts: tuple[Excerpt, ...]
    flagged: tuple[str, ...]  # numbers not in the excerpts
    problems: tuple[str, ...]


def check(
    policies: Sequence[V2Policy],
    v1: Mapping[str, tuple[dict[str, str], dict[str, Any]]],
    lcds: Mapping[str, ps.Lcd] | None = None,
    decisions: str | None = None,
) -> tuple[list[str], list[Row]]:
    """(problems of the files, one row per new criterion). Sources are resolved only when `lcds`
    is given (needs data/raw)."""
    problems: list[str] = []
    rows: list[Row] = []
    for policy in policies:
        pid = str(policy.meta.get("policy_id", policy.name))
        texts, meta = v1.get(pid, ({}, {}))
        if not texts:
            problems.append(f"{policy.name}: no v1 policy {pid}")
        problems += [f"{policy.name}: {p}" for p in policy.problems]
        problems += [f"{policy.name}: {p}" for p in id_problems(texts, policy)]
        problems += [f"{policy.name}: {p}" for p in field_problems(policy, meta)]
        replaced_by: dict[str, list[str]] = {}
        for old, targets in (policy.meta.get("replaces") or {}).items():
            for target in targets or []:
                replaced_by.setdefault(target, []).append(old)
        for c in policy.criteria:
            if c.criterion_id in texts:
                continue
            refs, row_problems = parse_refs(c.source)
            if not any(r.kind in ("lcd", "bpm") for r in refs):
                row_problems.append("a new criterion must cite LCD blocks or manual sections")
            excerpts: list[Excerpt] = []
            if lcds is not None:
                for ref in refs:
                    found, ref_problems = resolve(ref, lcds, decisions or "")
                    excerpts += found
                    row_problems += ref_problems
            flagged = missing_values(c.text, [e.text for e in excerpts]) if excerpts else []
            rows.append(
                Row(
                    policy,
                    c,
                    tuple(replaced_by.get(c.criterion_id, [])),
                    tuple(excerpts),
                    tuple(flagged),
                    tuple(row_problems),
                )
            )
            problems += [f"{c.criterion_id}: {p}" for p in row_problems]
    return problems, rows


@dataclass(frozen=True)
class Indication:
    excerpt: Excerpt
    held_by: str  # criterion ID, or "" when left out
    note: str


def indications(
    policies: Sequence[V2Policy],
    lcds: Mapping[str, ps.Lcd],
    table: Mapping[str, Sequence[tuple[str, str, str]]] = INDICATIONS,
) -> tuple[list[str], dict[str, list[Indication]]]:
    """(problems, policy -> its listed indications) for INDICATIONS: each listed source exists;
    a holding criterion is in the policy's indication group and, when new, cites the source; a
    left-out source has a reason; every indication-group criterion holds something; the LCD
    indication lists of INDICATION_RANGES are listed block by block."""
    problems: list[str] = []
    out: dict[str, list[Indication]] = {}
    by_id = {p.meta["policy_id"]: p for p in policies}
    for pid, entries in table.items():
        criteria = {c.criterion_id: c for c in by_id[pid].criteria}
        group = {i for i, c in criteria.items() if c.group == "indication"}
        listed = []
        for source, held_by, note in entries:
            if source.startswith("§"):
                ref = Ref("bpm", sections=(source.removeprefix("§"),))
            else:
                lcd_id, tag, index = source.split("-")
                version = lcds[lcd_id].version if lcd_id in lcds else ""
                ref = Ref("lcd", lcd_id, version, ((tag, int(index)),))
            excerpts, ref_problems = resolve(ref, lcds, "")
            problems += [f"{pid} indications: {p}" for p in ref_problems]
            if not excerpts:
                continue
            listed.append(Indication(excerpts[0], held_by, note))
            if not held_by:
                if not note:
                    problems.append(f"{pid} indications: {source} is left out without a reason")
                continue
            if held_by not in group:
                problems.append(f"{pid} indications: {held_by} is not in the indication group")
                continue
            refs = parse_refs(criteria[held_by].source)[0]
            cited = any(
                (r.kind == "bpm" and source.removeprefix("§") in r.sections)
                or (
                    r.kind == "lcd"
                    and source.startswith(r.lcd_id)
                    and (source.split("-")[1], int(source.split("-")[2])) in r.blocks
                )
                for r in refs
            )
            if refs and not cited:
                problems.append(f"{pid} indications: {held_by} does not cite {source}")
        holders = {i.held_by for i in listed}
        problems += [
            f"{pid} indications: {c} holds no listed indication" for c in sorted(group - holders)
        ]
        if pid in INDICATION_RANGES:
            lcd_id, tag, first, last = INDICATION_RANGES[pid]
            blocks = ps.blocks(TAG_FIELD[tag], lcds[lcd_id].fields.get(TAG_FIELD[tag], ""))
            named = {source for source, _, _ in entries}
            problems += [
                f"{pid} indications: {lcd_id}-{tag}-{b.index:03d} is not listed"
                for b in blocks[first : last + 1]
                if not b.heading and f"{lcd_id}-{tag}-{b.index:03d}" not in named
            ]
        out[pid] = listed
    return problems, out


def lcds_cited(policies: Sequence[V2Policy]) -> dict[str, ps.Lcd]:
    ids = {
        ref.lcd_id
        for policy in policies
        for c in policy.criteria
        for ref in parse_refs(c.source)[0]
        if ref.kind == "lcd"
    }
    ids |= {
        source.split("-")[0]
        for entries in INDICATIONS.values()
        for source, _, _ in entries
        if not source.startswith("§")
    }
    return ps.load_lcds(ids)


def ama_hits(texts: Mapping[str, str]) -> dict[str, int]:
    descriptors = ps.cpt_descriptors(set(load_curated().scope))
    return {name: ps.redact(text, descriptors)[1] for name, text in texts.items()}


# --- self-test --------------------------------------------------------------------------------


def selftest() -> list[tuple[str, bool]]:
    """Planted cases on copies of real v2 files: each must give the expected result."""
    v1 = read_v1()
    decisions = DECISIONS_MD.read_text(encoding="utf-8")
    car = (V2_DIR / "POL-CAR-002.md").read_text(encoding="utf-8")
    foot = (V2_DIR / "POL-FOOT-001.md").read_text(encoding="utf-8")
    lcds = ps.load_lcds({"L34636", "L33941"})

    def problems(name: str, text: str) -> list[str]:
        return check([parse_v2(name, text)], v1, lcds, decisions)[0]

    def has(found: Sequence[str], fragment: str) -> bool:
        return any(fragment in p for p in found)

    clean, rows = check([parse_v2("POL-CAR-002.md", car)], v1, lcds, decisions)
    c5_source = "Source: LCD L34636 v38 cov-004, cov-019."
    c6_source = "cov-001, cov-004, cov-020 to cov-032."
    c5_foot = "Type: conditional\nGroup: indication\nSource: " + BPM_NAME + " §290.C.4"
    longer = check(
        [parse_v2("POL-CAR-002.md", car.replace("up to 15 days", "up to 21 days"))],
        v1,
        lcds,
        decisions,
    )[1]
    c4_blocks = [e.label for e in rows[0].excerpts if e.label.startswith("L34636-cov-")]
    section = bpm_sections()["290.C.4"]
    policies = read_v2()
    all_lcds = lcds_cited(policies)
    surg = INDICATIONS["POL-SURG-002"]
    dropped = {"POL-SURG-002": [e for e in surg if e[0] != "L34005-cov-028"]}
    moved = {
        "POL-SURG-002": [
            (src, "POL-SURG-002.c7" if src == "L34005-cov-007" else held, note)
            for src, held, note in surg
        ]
    }
    return [
        (
            "an LCD indication left off a group's list is a problem",
            has(indications(policies, all_lcds, dropped)[0], "L34005-cov-028 is not listed"),
        ),
        (
            "a holding criterion that does not cite the indication is a problem",
            has(
                indications(policies, all_lcds, moved)[0],
                "POL-SURG-002.c7 does not cite L34005-cov-007",
            ),
        ),
        ("the real CAR-002 file has no problems", not clean),
        ("cov-004 plus the range cov-005 to cov-018 gives 15 blocks", len(c4_blocks) == 15),
        (
            "a block that does not exist is a problem",
            has(problems("POL-CAR-002.md", car.replace("cov-019.", "cov-999.")), "does not exist"),
        ),
        (
            "an LCD version other than data/raw's is a problem",
            has(
                problems("POL-CAR-002.md", car.replace(c5_source, c5_source.replace("v38", "v37"))),
                "data/raw holds v38",
            ),
        ),
        ("a number that no excerpt contains is flagged", "at most 21 day" in longer[1].flagged),
        (
            "a kept ID whose text changed is a problem",
            has(
                problems("POL-FOOT-001.md", foot.replace("on blood thinners", "on any thinner")),
                "keeps its v1 ID but its text changed",
            ),
        ),
        (
            "a reused v1 number is a problem",
            has(
                problems("POL-CAR-002.md", car.replace("POL-CAR-002.c6", "POL-CAR-002.c3")),
                "POL-CAR-002.c3 keeps its v1 ID but its text changed",
            ),
        ),
        (
            "a code the policy does not cover is a problem",
            has(
                problems("POL-CAR-002.md", car.replace("Applies to: 93268", "Applies to: 93270")),
                "which the policy does not cover",
            ),
        ),
        (
            "an indication-group member that is not conditional is a problem",
            has(
                problems(
                    "POL-FOOT-001.md",
                    foot.replace(c5_foot, c5_foot.replace("conditional", "requirement")),
                ),
                "must be conditional",
            ),
        ),
        (
            "a manual section is found with its page (290.C.4, page 261)",
            section[1] == (261,) and "Mycotic Nails" in section[0],
        ),
        (
            "a manual section that does not exist is a problem",
            has(problems("POL-FOOT-001.md", foot.replace("§290.C.4;", "§290.C.9;")), "not found"),
        ),
        (
            "a decision that is not in DECISIONS.md is a problem",
            has(
                problems(
                    "POL-CAR-002.md",
                    car.replace(c6_source, c6_source.rstrip(".") + "; decision D-NONE-9."),
                ),
                "D-NONE-9",
            ),
        ),
        (
            "a new criterion that cites prose instead of blocks is a problem",
            has(
                problems(
                    "POL-CAR-002.md",
                    car.replace(c5_source, "Source: LCD L34636 v38, Medical necessity."),
                ),
                "cannot read source",
            ),
        ),
    ]


# --- the review sheet -------------------------------------------------------------------------

VERDICT_HEADER = (
    "| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | "
    "Pass 2 notes |"
)
VERDICTS_A = "MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE"
VERDICTS_B = "AGREE, DISAGREE or UNSURE"
VERDICTS_C = "COMPLETE, GAPS or UNSURE"
MINUTES_C = 4
MINUTES_A = 3
MINUTES_B = 0.5


def _quote(text: str) -> str:
    return text.replace("|", "\\|")


def _excerpt_line(e: Excerpt) -> str:
    where = e.where
    if e.where in ("item", "background block"):
        where += f"; under: {e.section or 'the top of the field'}"
    return f"**{e.label}** ({where})"


def _escaped(text: str) -> str:
    return text.replace("*", chr(92) + "*")


def sheet(
    rows: Sequence[Row],
    policies: Sequence[V2Policy],
    v1: Mapping[str, Any],
    groups: Mapping[str, Sequence[Indication]],
) -> str:
    curated = load_curated()
    kept = [
        (p, c) for p in policies for c in p.criteria if c.criterion_id in v1[p.meta["policy_id"]][0]
    ]
    retired = sum(len(texts) for texts, _ in v1.values()) - len(kept)
    flagged = [r for r in rows if r.flagged]
    out = [
        "# Policies v2: source review sheet (checkpoint 1)",
        "",
        "Two passes: pass 1 in a separate Claude chat (paste the whole sheet and ask for the three "
        "verdict tables at the end, filled); pass 2 by the reviewer, for every row whose pass 1 "
        "verdict is not MATCHES, AGREE or COMPLETE, plus 5 random MATCHES rows.",
        "",
        "- **Who wrote what.** The v2 texts, the choice of excerpts, the types, the code lists and "
        "the notes were written by the same model (Claude, in the repository session); the two "
        "passes are the check.",
        "- **Excerpts are copied word for word from data/raw by "
        "`scripts/verify/policies_v2_sources.py`, never typed.** LCD text: the CMS Medicare "
        "Coverage Database download (data/raw/mcd/2026-09-21/current_lcd.zip, lcd.csv, latest "
        "version of each LCD), with tags removed, entities decoded and whitespace collapsed, as "
        "in V1b. Block IDs are the V1b IDs: L<LCD>-cov-NNN is block NNN of the LCD's coverage "
        "field, L<LCD>-doc-NNN of its Associated Information field; headings and background "
        "blocks are marked. Manual text: Medicare Benefit Policy Manual, chapter 15, Rev. 13889 "
        "(data/raw/cms-manual/bp102c15/bp102c15.pdf), line breaks joined.",
        "- **No AMA CPT text.** Codes are shown with the team's plain-language descriptions "
        "(data/curated/procedure_descriptions.csv), not CPT descriptors; the sheet was checked "
        "against the CPT descriptor texts of our codes before writing (0 found).",
        "- In the excerpts, a backslash before `*` is Markdown escaping, not source text. 'under:' "
        "names the headings above an LCD block, as the V1b parser reads them.",
        "- **Decisions** cited as `decision D-...` are team decisions recorded in DECISIONS.md, "
        "not sources: do not mark a row NOT IN SOURCE for what such a decision adds.",
        f"- Part A: {len(rows)} new criteria (each replaces a v1 criterion or is new); Part B: "
        f"{len(kept)} criteria kept from v1 with their v1 ID and text; v1 criteria retired: "
        f"{retired}. v2 total: {len(rows) + len(kept)}. Part C: {len(groups)} indication "
        "groups, each with every covered indication its sources give.",
        f"- Automatic checks: every cited block and section found, every excerpt word for word in "
        f"its source; rows with a number, duration or threshold that no excerpt contains: "
        f"{len(flagged)} ({', '.join(r.criterion.criterion_id for r in flagged) or 'none'}).",
        f"- Estimated time: Part A about {MINUTES_A} minutes a row ({len(rows) * MINUTES_A} "
        f"minutes), Part B about {round(len(kept) * MINUTES_B)} minutes, Part C about "
        f"{MINUTES_C * len(groups)} minutes.",
        "",
        "## How to judge",
        "",
        f"**Part A** ({VERDICTS_A}): does the v2 text say what its excerpts say, no more and no "
        "less, for its type and codes? A plain-language paraphrase is fine.",
        "",
        "- MATCHES: the same meaning.",
        "- DIFFERENT MEANING: the text adds, drops or changes a condition, number, list item or "
        "scope. Say which in the notes.",
        "- NOT IN SOURCE: something in the text has no support in the excerpts (apart from cited "
        "decisions).",
        "- UNSURE: say why.",
        "",
        f"**Part B** ({VERDICTS_B}): is the type right for the text, and the code list and group?",
        "",
        f"**Part C** ({VERDICTS_C}): for each indication group, is every covered indication its "
        "sources give for the policy's codes held by the criterion named, and is each reason to "
        "leave one out right?",
        "",
        "**Types** (decisions D-ESI-6 and D-GEN-3) fix what the notes' silence means:",
        "",
        "- requirement: must be satisfied; silent notes give NOT_DOCUMENTED.",
        "- exclusion: describes a situation that is not covered; present gives NOT_MET, absent or "
        "silent gives NOT_APPLICABLE; never MET.",
        "- conditional: applies only in the situation named with it; otherwise NOT_APPLICABLE; "
        "when it applies, it works as a requirement.",
        "- Group: indication: alternative indications of one policy, which count only as a "
        "group (D-POL-3). Counting only the criteria that apply to the line's code, the group is "
        "satisfied when any member is MET; a member's NOT_MET or NOT_DOCUMENTED never decides the "
        "line on its own. Any NOT_MET outside the group gives DENY; otherwise an unsatisfied group "
        "gives PEND with 'no covered indication documented'; otherwise any NOT_DOCUMENTED outside "
        "the group gives PEND; otherwise APPROVE. Explicit non-coverage is in exclusion criteria, "
        "outside the group.",
        "- Applies to: the criterion is shown only on lines billing these codes; without it, on "
        "every code of the policy.",
        "",
        "## Codes of the policies",
        "",
        "| Policy | Code | Plain-language description (team's, not the CPT descriptor) |",
        "|---|---|---|",
    ]
    for p in policies:
        for code in p.meta["procedure_codes"]:
            out.append(
                f"| {p.meta['policy_id']} | {code} | {curated.descriptions.get(str(code), '-')} |"
            )
    out += ["", f"## Part A: new criteria ({len(rows)} rows)", ""]
    for n, r in enumerate(rows, start=1):
        c = r.criterion
        decision, note = NOTES.get(c.criterion_id, ("-", "-"))
        replaced = f"replaces {', '.join(r.replaced)}" if r.replaced else "new, no v1 predecessor"
        out += [
            f"### A{n}. {c.criterion_id} ({replaced})",
            "",
            f"- Decision: {decision}",
            f"- What changed: {note}",
        ]
        texts = v1[r.policy.meta["policy_id"]][0]
        out += [f"- v1 text ({old}): {texts[old]}" for old in r.replaced]
        out += [
            f"- **v2 text:** {c.text}",
            f"- Type: {c.type}"
            + (
                f" (applies when: {CONDITIONS[c.criterion_id]})"
                if c.criterion_id in CONDITIONS
                else ""
            )
            + f". Applies to: {', '.join(c.applies_to) or 'every code of the policy'}. "
            f"Group: {c.group or '-'}.",
            f"- Source line: {c.source}",
            "- Automatic check, numbers in the v2 text that no excerpt contains: "
            + (", ".join(r.flagged) if r.flagged else "none"),
            "",
            "Excerpts, word for word:",
            "",
        ]
        for e in r.excerpts:
            out += [f"> {_excerpt_line(e)}: {_escaped(e.text)}", ""]
    out += [
        f"## Part B: kept criteria ({len(kept)} rows)",
        "",
        "Text and ID unchanged from v1 (checked byte for byte); only the type, code list and group "
        "are new.",
        "",
        "| Row | Criterion | Text | Type | Applies to | Group |",
        "|---|---|---|---|---|---|",
    ]
    for n, (_, c) in enumerate(kept, start=1):
        kind = c.type + (
            f" (applies when: {CONDITIONS[c.criterion_id]})" if c.criterion_id in CONDITIONS else ""
        )
        out.append(
            f"| B{n} | {c.criterion_id} | {_quote(c.text)} | {kind} | "
            f"{', '.join(c.applies_to) or 'all'} | {c.group or '-'} |"
        )
    by_id = {p.meta["policy_id"]: p for p in policies}
    out += [
        "",
        f"## Part C: indication groups ({len(groups)} rows)",
        "",
        "Every covered indication the sources give for the policy's codes, word for word, and the "
        "criterion that holds it, or why it is left out. Checked automatically: every listed "
        "source exists; a new criterion that holds one cites it; every group criterion holds at "
        "least one; the LCD indication lists (SURG-001: L33558 cov-004 to cov-009; SURG-002: "
        "L34005 cov-007 to cov-034, plus doc-001) are listed block by block.",
        "",
    ]
    for n, (pid, listed) in enumerate(groups.items(), start=1):
        policy = by_id[pid]
        members = [
            f"{c.criterion_id.rsplit('.', 1)[1]}"
            + (f" ({', '.join(c.applies_to)})" if c.applies_to else "")
            for c in policy.criteria
            if c.group == "indication"
        ]
        out += [
            f"### C{n}. {pid} (group: {', '.join(members)}; codes "
            f"{', '.join(str(c) for c in policy.meta['procedure_codes'])})",
            "",
        ]
        for i in listed:
            if i.held_by:
                target = f"**{i.held_by}**" + (f" ({i.note})" if i.note else "")
            else:
                target = f"left out: {i.note}"
            out += [
                f"- {_excerpt_line(i.excerpt)} -> {target}.",
                "",
                f"  > {_escaped(i.excerpt.text)}",
                "",
            ]
    out += [
        "## Verdicts",
        "",
        f"### Part A ({VERDICTS_A})",
        "",
        VERDICT_HEADER,
        "|---|---|---|---|---|---|",
    ]
    out += [
        f"| A{n} | {r.criterion.criterion_id} |  |  |  |  |" for n, r in enumerate(rows, start=1)
    ]
    out += [
        "",
        f"### Part B ({VERDICTS_B})",
        "",
        VERDICT_HEADER,
        "|---|---|---|---|---|---|",
    ]
    out += [f"| B{n} | {c.criterion_id} |  |  |  |  |" for n, (_, c) in enumerate(kept, start=1)]
    out += ["", f"### Part C ({VERDICTS_C})", "", VERDICT_HEADER, "|---|---|---|---|---|---|"]
    out += [f"| C{n} | {pid} |  |  |  |  |" for n, pid in enumerate(groups, start=1)]
    return "\n".join(out) + "\n"


def has_verdicts(text: str) -> bool:
    """True when any verdict row of the sheet has a filled pass 1 or pass 2 cell (verdict rows
    are the rows under "## Verdicts"; Part B's own table above uses the same row IDs)."""
    lines = text.splitlines()
    for line in lines[lines.index("## Verdicts") if "## Verdicts" in lines else len(lines) :]:
        if re.match(r"^\| [ABC][0-9]+ \| POL-", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if any(cells[2:]):
                return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("check", "selftest", "sheet"))
    step = parser.parse_args().step
    if step == "selftest":
        cases = selftest()
        for name, ok in cases:
            print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        passed = sum(ok for _, ok in cases)
        print(f"{passed}/{len(cases)} planted cases behaved as expected")
        if passed != len(cases):
            raise SystemExit(1)
        return
    v1 = read_v1()
    policies = read_v2()
    lcds = lcds_cited(policies)
    problems, rows = check(policies, v1, lcds, DECISIONS_MD.read_text(encoding="utf-8"))
    group_problems, groups = indications(policies, lcds)
    problems += group_problems
    texts = {p.name: (V2_DIR / p.name).read_text(encoding="utf-8") for p in policies}
    if step == "sheet":
        texts[SHEET.name] = sheet(rows, policies, v1, groups)
    hits = {name: n for name, n in ama_hits(texts).items() if n}
    if hits:
        problems.append(f"AMA CPT descriptor text found: {hits}")
    print(f"v2 policies: {len(policies)}; new criteria: {len(rows)}; problems: {len(problems)}")
    for p in problems:
        print(f"  {p}")
    for r in rows:
        if r.flagged:
            print(f"  flagged {r.criterion.criterion_id}: {', '.join(r.flagged)}")
    if problems:
        raise SystemExit(1)
    if step == "sheet":
        if SHEET.exists() and has_verdicts(SHEET.read_text(encoding="utf-8")):
            raise SystemExit(
                f"{SHEET.name} holds review verdicts; not overwritten (move them first)"
            )
        SHEET.write_text(texts[SHEET.name], encoding="utf-8")
        print(f"wrote {SHEET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
